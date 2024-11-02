"""
Divoom Pixoo64 Album Art Display
--------------------------------
This functionality automatically showcases the album cover art of the currently playing track on your Divoom Pixoo64 screen.
In addition to this, it extracts useful information like the artist's name and the predominant color from the album art. This extracted data can be leveraged for additional automation within your Home Assistant setup.
This script also supports AI image creation It's designed to show alternative AI-generated album cover art when no album art exists, or when using music services (like SoundCloud) where the script can't fetch the image.

APPDAEMON CONFIGURATION
python_packages:
  - requests
  - unidecode
  - pillow
  - numpy==1.26.4
  - python-bidi

# appdaemon/apps/apps.yaml
-----
pixoo64_media_album_art:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    home_assistant:
        ha_url: "http://homeassistant.local:8123"  # Home Assistant URL
        media_player: "media_player.era300"        # Media player entity ID
        toggle: "input_boolean.pixoo64_album_art"  # Boolean sensor to control script execution (Optional)
        pixoo_sensor: "sensor.pixoo64_media_data"  # Sensor to store media data (Optional)
        light: "light.strip_stone"                 # RGB light entity ID (if any) (Optional)
        ai_fallback: turbo                         # Create alternative AI image when fallback - use model 'flex' or 'turbo'
    pixoo:
        url: "http://192.168.86.21:80/post"        # Pixoo device URL
        full_control: True                         # Control display on/off with play/pause
        contrast: True                             # Apply 50% contrast filter
        clock: True                                # Show clock top corner
        clock_align: Right                         # Clock align - Left or Right
        tv_icon: True                              # Shows TV icon when playing sound from TV
        show_text:
            enabled: False                         # Show media artist and title 
            clean_title: True                      # Remove "Remaster" labels, track number and file extentions from the title if any
            text_background: True                  # Change background color or better text display with image
            font: 2                                # Pixoo internal font type (0-7) for fallback text when there is no image
            color: False                           # Use alternative font color
        crop_borders:
            enabled: True                          # Crop image borders if present
            extra: True                            # Apply enhanced border crop
"""
import re
import os
import base64
import json
import time
import zlib
import random
import traceback
from io import BytesIO
from collections import Counter
from appdaemon.plugins.hass import hassapi as hass

try:
    from PIL import Image, UnidentifiedImageError, ImageEnhance, ImageFilter
except ImportError:
    print("the 'pillow' module is not installed or not available. No image support")
try:
    import requests
except ImportError:
    print("The 'request' module is not installed or not available. It's mandatory!")
try:
    import numpy as np
except ImportError:
    print("The 'numpy' module is not installed or not available. Crop feaure won't work")
try:
    from unidecode import unidecode
    undicode_m = True
except ImportError:
    print("The 'unidecoed' module is not installed or not available. Special chars might not display")
    undicode_m = False
try:
    from bidi import get_display
except ImportError:
    print("The 'bidi.algorithm' module is not installed or not available. RTL texts will display reverce")

AI_ENGINE = "https://pollinations.ai/p"
BLK_SCR = b'x\x9c\xed\xc11\x01\x00\x00\x00\xc2\xa0l\xeb_\xca\x18>@\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00o\x03\xda:@\xf1'
TV_ICON_PATH = "/local/pixoo64/tv-icon-1.png"
local_directory = "/homeassistant/www/pixoo64/"
files = { "tv-icon-1.png": "https://raw.githubusercontent.com/idodov/pixoo64-media-album-art/refs/heads/main/apps/pixoo64_media_album_art/tv-icon-1.png"}
hebrew = r"\u0590-\u05FF"
arabic = r"\u0600-\u06FF|\u0750-\u077F|\u08A0-\u08FF|\uFB50-\uFDFF|\uFE70-\uFEFF|\u0621-\u06FF"
syriac = r"\u0700-\u074F"
thaana = r"\u0780-\u07BF"
nkoo = r"\u07C0-\u07FF"
rumi = r"\U00010E60-\U00010E7F"
arabic_math = r"\U0001EE00-\U0001EEFF"
symbols = r"\U0001F110-\U0001F5FF"
old_persian_phaistos = r"\U00010F00-\U00010FFF"
samaritan = r"\u0800-\u08FF"
bidi_marks = r"\u200E|\u200F"
HEADERS = {"Content-Type": "application/json; charset=utf-8"}

class Pixoo64_Media_Album_Art(hass.Hass):
    def initialize(self):
        self.media_player = self.args.get('home_assistant', {}).get("media_player", "media_player.era300")
        self.toggle = self.args.get('home_assistant', {}).get("toggle", "input_boolean.pixoo64_album_art")
        self.ha_url = self.args.get('home_assistant', {}).get("ha_url", "http://homeassistant.local:8123")
        self.pixoo_sensor = self.args.get('home_assistant', {}).get("pixoo_sensor", "sensor.pixoo64_media_data")
        self.light = self.args.get('home_assistant', {}).get("light", None)
        self.ai_fallback = self.args.get('home_assistant', {}).get("ai_fallback", 'flux')

        self.url = self.args.get('pixoo', {}).get("url", "192.168.86.21:80/post")
        self.full_control = self.args.get('pixoo', {}).get("full_control", True)
        self.contrast = self.args.get('pixoo', {}).get("contrast", False)
        self.show_clock = self.args.get('pixoo', {}).get("clock", True)
        self.clock_align = self.args.get('pixoo', {}).get("clock_align", "Left")
        self.tv_icon_pic = self.args.get('pixoo', {}).get("tv_icon", True)

        self.show_text = self.args.get('pixoo', {}).get('show_text', {}).get("enabled", False)
        self.clean_title_enabled = self.args.get('pixoo', {}).get('show_text', {}).get("clean_title", True) 
        self.font = self.args.get('pixoo', {}).get('show_text', {}).get("font", 2)
        self.font_c = self.args.get('pixoo', {}).get('show_text', {}).get("color", True)
        self.text_bg = self.args.get('pixoo', {}).get('show_text', {}).get("text_background", True)

        self.crop_borders = self.args.get('pixoo', {}).get('crop_borders', {}).get("enabled", True)
        self.crop_extra = self.args.get('pixoo', {}).get('crop_borders', {}).get("extra", True)

        self.fallback = self.fail_txt = self.playing_radio = self.radio_logo = False
        self.album_name = self.get_state(self.media_player, attribute="media_album_name")
        self.listen_state(self.update_attributes, self.media_player, attribute='media_title')
        self.listen_state(self.update_attributes, self.media_player)

        if self.ai_fallback not in ["flux", "turbo"]:
            self.ai_fallback = "turbo"

        if not os.path.exists(local_directory):
            os.makedirs(local_directory)

        # Check if files exist locally, if not download them
        for file_name, url in files.items():
            local_file_path = os.path.join(local_directory, file_name)
    
            if not os.path.exists(local_file_path):
                response = requests.get(url)
                if response.status_code == 200:
                    with open(local_file_path, 'wb') as file:
                        file.write(response.content)

    def update_attributes(self, entity, attribute, old, new, kwargs):
        try:
            input_boolean = self.get_state(self.toggle)
        
        except Exception as e:
            self.log(f"Error getting state for {self.toggle}: {e}. Please create it in HA configuration.yaml")
            self.set_state(self.toggle, state="on", attributes={"friendly_name": "Pixoo64 Album Art"})
            input_boolean = "on"
        
        media_state = self.get_state(self.media_player)
        if media_state in ["off", "idle", "pause"]:
            self.set_state(self.pixoo_sensor, state="off")
            self.album_name = "media player is not playing - removing the album name"
        
        if input_boolean == "on":
            self.pixoo_run(media_state)

    def clean_title(self, title):
        cleaned_title = re.sub(r"\.(mp3|wav|flac|ogg|aac|m4a)$", "", title, flags=re.IGNORECASE)
        cleaned_title = re.sub(r"\((?:.*?Remaster(?:ed)?|.*?Version).*?\)|\[(?:.*?Remaster(?:ed)?|.*?Version).*?\]", "", cleaned_title).strip()
        cleaned_title = re.sub(r"\((?:.*?Mix(?:ed)?).*?\)|\[(?:.*?Remix(?:ed)?).*?\]", "", cleaned_title).strip()
        cleaned_title = re.sub(r"-(?:.*?Remaster(?:ed)?).*?$", "", cleaned_title).strip()
        cleaned_title = re.sub(r"-(?:.*?Radio Edit(?:ed)?).*?$", "", cleaned_title).strip()
        cleaned_title = re.sub(r"^\d+\s*-\s*", "", cleaned_title).strip()
        return cleaned_title

    def pixoo_run(self, media_state):
        payload = '{ "Command" : "Channel/GetIndex" }'
        response = requests.request("POST", self.url, headers=HEADERS, data=payload)
        response_data = json.loads(response.text)
        select_index = response_data.get('SelectIndex', None)

        if media_state in ["playing", "on"]:  # Check for playing state
            title = self.get_state(self.media_player, attribute="media_title")
            original_title = title
            # Use the corrected variable name:
            title = self.clean_title(title) if self.clean_title_enabled else title

            album_name_check = self.get_state(self.media_player, attribute="media_album_name") or title
            self.send_pic = album_name_check != self.album_name

            if title != "TV" and title is not None:
                artist = self.get_state(self.media_player, attribute="media_artist")
                original_artist = artist
                artist = artist if artist else ""
                if undicode_m:
                    normalized_title = unidecode(title)
                    normalized_artist = unidecode(artist) if artist else ""
                else:
                    normalized_title = title
                    normalized_artist = artist if artist else ""
                self.ai_title = normalized_title
                self.ai_artist = normalized_artist
                picture = self.get_state(self.media_player, attribute="entity_picture")
                original_picture = picture
                media_content_id = self.get_state(self.media_player, attribute="media_content_id")
                queue_position = self.get_state(self.media_player, attribute="queue_position")
                media_channel = self.get_state(self.media_player, attribute="media_channel")

                # Check if lisening to radio station
                if media_channel and (media_content_id.startswith("x-rincon") or media_content_id.startswith("aac://http") or media_content_id.startswith("rtsp://")):
                    self.playing_radio = True
                    self.radio_logo = False
                    if artist:
                        picture = self.format_ai_image_prompt(artist, title)
                    # Show radio station logo if Tunein jingel is playing
                    if ('https://tunein' in media_content_id or 
                            queue_position == 1 or 
                            original_title == media_channel or 
                            original_title == original_artist or 
                            original_artist == media_channel or 
                            original_artist == 'Live'):
                        picture = original_picture
                        self.radio_logo = True
                else:
                    self.playing_radio = self.radio_logo = False
                    picture = original_picture
                gif_base64, font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative = self.process_picture(picture)
                new_attributes = {"artist": artist,"normalized_artist": normalized_artist, "media_title": title,"normalized_title": normalized_title, "font_color": font_color, "font_color_alternative": recommended_font_color, "background_color_brightness": brightness, "background_color": background_color, "color_alternative_rgb": most_common_color_alternative, "background_color_rgb": background_color_rgb, "recommended_font_color_rgb": recommended_font_color_rgb, "color_alternative": most_common_color_alternative_rgb,}
                self.set_state(self.pixoo_sensor, state="on", attributes=new_attributes)
                payload = {"Command":"Draw/CommandList", "CommandList":[{"Command":"Channel/OnOffScreen", "OnOff":1},{"Command": "Draw/ResetHttpGifId"},{"Command": "Draw/SendHttpGif", "PicNum": 1, "PicWidth": 64, "PicOffset": 0, "PicID": 0, "PicSpeed": 1000, "PicData": gif_base64 }]}
                moreinfo = {"Command": "Draw/SendHttpItemList", "ItemList": []}
                textid = 0
                text_track = (artist + " - " + title) 
                if len(text_track) > 14:
                    text_track = text_track + "       "
                text_string = self.convert_text(text_track) if artist else self.convert_text(title)
                dir = 1 if self.has_bidi(text_string) else 0
                brightness_factor = 50  
                color_font = tuple(min(255, c + brightness_factor) for c in background_color_rgb)
                color_font = '#%02x%02x%02x' % color_font
                color_font = color_font if self.font_c else recommended_font_color
                if self.send_pic:
                    self.album_name = album_name_check # Will not try to upload a new pic while listening to the same album
                    self.send_pixoo(payload)
                    if self.light:
                        self.control_light('on',background_color_rgb)
                
                if self.show_text and not self.fallback and not self.radio_logo:
                    textid +=1
                    text_temp = { "TextId":textid, "type":22, "x":0, "y":48, "dir":dir, "font":2, "TextWidth":64, "Textheight":16, "speed":100, "align":2, "TextString": text_string, "color":color_font }
                    moreinfo["ItemList"].append(text_temp)

                if self.show_clock and not self.fallback:
                    textid +=1
                    x = 44 if self.clock_align == "Right" else 3
                    clock_item =  { "TextId":textid, "type":5, "x":x, "y":3, "dir":0, "font":18, "TextWidth":32, "Textheight":16, "speed":100, "align":1, "color":color_font }
                    moreinfo["ItemList"].append(clock_item)

                if (self.show_text or self.show_clock) and not self.fallback:
                    self.send_pixoo(moreinfo)

                if self.fallback and self.fail_txt:
                    payloads = self.create_payloads(normalized_artist, normalized_title, 13)
                    payload = {"Command":"Draw/CommandList", "CommandList": payloads}
                    self.send_pixoo(payload)
            else:
                if self.tv_icon_pic:
                    picture = TV_ICON_PATH
                    img = self.get_image(picture)
                    img = self.ensure_rgb(img)
                    gif_base64 = self.gbase64(img)
                    payload = {"Command":"Draw/CommandList", "CommandList":[{"Command":"Channel/OnOffScreen", "OnOff":1},{"Command": "Draw/ResetHttpGifId"},{"Command": "Draw/SendHttpGif","PicNum": 1,"PicWidth": 64, "PicOffset": 0, "PicID": 0, "PicSpeed": 1000, "PicData": gif_base64 }]}
                else:
                    payload = {"Command":"Draw/CommandList", "CommandList":[{"Command":"Draw/ClearHttpText"},{"Command": "Draw/ResetHttpGifId"},{"Command":"Channel/SetIndex", "SelectIndex": 4 },{"Command":"Channel/SetIndex", "SelectIndex": select_index }]}

                self.send_pixoo(payload)
                if self.light:
                    self.control_light('off')
        else:
            self.album_name = "no music is playing and no album name"
                
            if self.full_control:
                payload = {"Command":"Draw/CommandList", "CommandList":[{"Command":"Draw/ClearHttpText"},{"Command": "Draw/ResetHttpGifId"},{"Command":"Channel/OnOffScreen", "OnOff":0} ]}
                time.sleep(5) # Delay to not turn off the screen when changing music tracks while playing a track
            else:
                payload = {"Command":"Draw/CommandList", "CommandList":[{"Command":"Draw/ClearHttpText"},{"Command": "Draw/ResetHttpGifId"},{"Command":"Channel/SetIndex", "SelectIndex": 4 },{"Command":"Channel/SetIndex", "SelectIndex": select_index }]}
                
            media_state = self.get_state(self.media_player)
            if not media_state in ["playing", "on"]:
                self.send_pixoo(payload)
                self.set_state(self.pixoo_sensor, state="off")
                if self.light:
                    self.control_light('off')

    def reset_img_values(self):
        font_color = recommended_font_color = recommended_font_color_rgb = "#FFFFFF"
        background_color  = most_common_color_alternative_rgb = most_common_color_alternative = "#0000FF"
        background_color_rgb = tuple(random.randint(10, 200) for _ in range(3))
        brightness = brightness_lower_part = 0
        return font_color, recommended_font_color, recommended_font_color_rgb, background_color, most_common_color_alternative_rgb, most_common_color_alternative, background_color_rgb, brightness, brightness_lower_part

    def img_values(self, img):
        font_color, recommended_font_color, recommended_font_color_rgb, background_color, most_common_color_alternative_rgb, most_common_color_alternative, background_color_rgb, brightness, brightness_lower_part = self.reset_img_values()
        full_img = img
        lower_part = img.crop((3, 48, 61, 61))
        lower_part = self.ensure_rgb(lower_part)
        most_common_color = self.most_vibrant_color(lower_part)
        most_common_color_alternative_rgb = self.most_vibrant_color(full_img)
        most_common_color_alternative = '#%02x%02x%02x' % most_common_color_alternative_rgb
        brightness = int(sum(most_common_color_alternative_rgb) / 3)
        brightness_lower_part = int(sum(most_common_color)/ 3)
        most_common_colors = [item[0] for item in Counter(lower_part.getdata()).most_common(10)]
        candidate_colors = [(0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 255, 255), (255, 0, 255)]
            
        for color in candidate_colors:
            if color not in most_common_colors:
                font_color = '#%02x%02x%02x' % color
                break
            
        opposite_color = tuple(255 - i for i in most_common_color)
        opposite_color_brightness = int(sum(opposite_color)/3)
        brightness_lower_part = round(1 - opposite_color_brightness / 255, 2) if 0 <= opposite_color_brightness <= 255 else 0
        recommended_font_color = '#%02x%02x%02x' % opposite_color
        enhancer = ImageEnhance.Contrast(full_img)
        full_img = enhancer.enhance(2.0)
        background_color_rgb = self.most_vibrant_color(full_img)
        background_color = '#%02x%02x%02x' % most_common_color_alternative_rgb
        recommended_font_color_rgb = opposite_color
        return font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative

    def process_picture(self, picture, timeout=30):
        font_color, recommended_font_color, recommended_font_color_rgb, background_color, most_common_color_alternative_rgb, most_common_color_alternative, background_color_rgb, brightness, brightness_lower_part = self.reset_img_values()
        try:
            img = self.get_image(picture)
            img = self.ensure_rgb(img)
            font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative = self.img_values(img)
            img = self.text_clock_img(img, brightness_lower_part)
            gif_base64 = self.gbase64(img)
            self.fallback = self.fail_text = False

        except Exception as e:
            self.log(f"Error processing image: {e}.\n Will try to create AI Image")
            self.fallback = True
            self.fail_txt = False
            try:
                gif_base64, font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative = self.get_ai_image()
            except Exception as e:
                self.log(f"Failed to create AI image: {e}")  
                gif_base64 = zlib.decompress(BLK_SCR).decode()
                self.fail_txt = self.fallback = True
        return gif_base64, font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative

    def get_image(self, picture):
        try:
            if picture.startswith('http'):
                # If it starts with 'http', use the picture URL as is
                response = requests.get(picture)
                response.raise_for_status()
            else:
                # Otherwise, prepend ha_url
                response = requests.get(f"{self.ha_url}{picture}")
                response.raise_for_status()
            
            if response.status_code != 200:
                self.fail_txt = self.fallback = True
                return None
            
            img = Image.open(BytesIO(response.content))
            img = img.convert("RGB")
            
            # Check if the image is grayscale
            grayscale = np.array(img)
            if np.all(grayscale[:, :, 0] == grayscale[:, :, 1]) and np.all(grayscale[:, :, 1] == grayscale[:, :, 2]):
                # Apply 90% contrast if the image is grayscale
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.9)  # 90% contrast
            
            if self.crop_borders and not self.fallback and not self.playing_radio:
                img = self.crop_img(img)
                
            if self.contrast and not grayscale.all():
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)  # 50% contrast for non-grayscale images
            
            img.thumbnail((64, 64), Image.Resampling.LANCZOS)
            return img
        
        except (UnidentifiedImageError, requests.RequestException) as e:
            self.log(f"Failed to get image: {str(e)}")
            self.fail_txt = self.fallback = True
            return None

        except Exception as e:
            self.log(f"Unexpected error in get_image: {str(e)}")
            self.fail_txt = self.fallback = True
            return None

    def crop_img(self, img):
        temp_img = img
        if self.crop_extra:
            img = img.filter(ImageFilter.BoxBlur(5))
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.95)
        
        try:
            np_image = np.array(img)
            edge_pixels = np.concatenate([np_image[0, :], np_image[-1, :], np_image[:, 0], np_image[:, -1]])
            colors, counts = np.unique(edge_pixels, axis=0, return_counts=True)
            border_color = colors[counts.argmax()]
            dists = np.linalg.norm(np_image - border_color, axis=2)
            mask = dists < 100  # TOLERANCE
            coords = np.argwhere(mask == False)

            if coords.size == 0:
                raise ValueError("No non-border pixels found")
            
            x_min, y_min = coords.min(axis=0)
            x_max, y_max = coords.max(axis=0) + 1

            # Exclude top areas with text by removing rows near the top that are too small
            rows_with_few_pixels = np.sum(mask[:x_min], axis=1) > 0.98 * mask.shape[1]
            if np.any(rows_with_few_pixels):
                first_valid_row = np.argmax(~rows_with_few_pixels)
                x_min = max(x_min, first_valid_row)

            width, height = x_max - x_min, y_max - y_min
            max_size = max(width, height)
            x_center, y_center = (x_min + x_max) // 2, (y_min + y_max) // 2

            # Ensure the final crop size is at least 64x64
            if max_size < 64:
                max_size = 64

            x_min = max(0, x_center - max_size // 2)
            y_min = max(0, y_center - max_size // 2)
            x_max = min(np_image.shape[0], x_min + max_size)
            y_max = min(np_image.shape[1], y_min + max_size)

            # Adjust if the crop dimensions don't match the expected max_size
            if x_max - x_min < max_size:
                x_min = max(0, x_max - max_size)
            if y_max - y_min < max_size:
                y_min = max(0, y_max - max_size)

            img = temp_img
            img = img.crop((y_min, x_min, y_max, x_max))
                
        except Exception as e:
            self.log(f"Failed to crop: {e}")  
            enhancer = ImageEnhance.Contrast(temp_img)
            temp_img = enhancer.enhance(2.0)
            img = temp_img
        return img

    def send_pixoo(self, payload_command):
        response = requests.post(self.url, headers=HEADERS, data=json.dumps(payload_command))
        if response.status_code != 200:
            self.log(f"Failed to send REST: {response.content}")
        else:
            time.sleep(0.25)
    
    def ensure_rgb(self, img):
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img

    def split_string(self, text, length):
        words = text.split(' ')
        lines = []
        current_line = ''
        
        for word in words:
            if len(current_line) + len(word) > length: 
                lines.append(current_line)
                current_line = word
            else:
                current_line += ' ' + word if current_line else word  
        
        lines.append(current_line)
        return lines

    def create_payloads(self, normalized_artist, normalized_title, x):
        artist_lines = self.split_string(normalized_artist, x)
        title_lines = self.split_string(normalized_title, x)
        all_lines = artist_lines + title_lines
        
        if len(all_lines) > 4:
            all_lines[3] += ' ' + ' '.join(all_lines[4:])
            all_lines = all_lines[:4]
        
        start_y = (64 - len(all_lines) * 15) // 2
        payloads = [{"Command":"Draw/ClearHttpText"}] 
        
        for i, line in enumerate(all_lines):
            payload = {"Command":"Draw/SendHttpText", "TextId": i+1, "x": 0, "y": start_y + i*15, "dir": 0, "font": self.font, "TextWidth": 64,"speed": 80, "TextString": line, "color": "#a0e5ff" if i < len(artist_lines) else "#f9ffa0", "align": 2}
            payloads.append(payload)
        return payloads
    
    def control_light(self, action, background_color_rgb=None):
        service_data = {'entity_id': self.light}
        if action == 'on':
            service_data.update({'rgb_color': background_color_rgb, 'transition': 2 })
        try:
            self.call_service(f'light/turn_{action}', **service_data)
        except Exception as e:
            self.log(f"Light Error: {self.light} - {e}\n{traceback.format_exc()}")
            
    def most_vibrant_color(self, full_img):
        full_img.thumbnail((64, 64), Image.Resampling.LANCZOS)
        color_counts = Counter(full_img.getdata())
        most_common_colors = color_counts.most_common()
        
        for color, count in most_common_colors:
            r, g, b = color
            max_color = max(r, g, b)
            min_color = min(r, g, b)
            if max_color + min_color > 400 or max_color - min_color < 50:  
                continue
            if max_color - min_color < 100:  
                continue
            return color
        return tuple(random.randint(100, 200) for _ in range(3))

    def convert_text(self, text):
        try:
            return get_display(text) if text and self.has_bidi(text) else text
        except Exception as e:
            self.log(f"To display RTL text you need to add bidi-algorithm packadge: {e}.")
            return text

    def has_bidi(self, text):
        # covering Arabic, Hebrew and other RTL ranges
        bidi_regex = f"[{hebrew}|{arabic}|{syriac}|{thaana}|{nkoo}|{rumi}|{arabic_math}|{symbols}|{old_persian_phaistos}|{samaritan}]"
        return bool(re.search(bidi_regex, text))

    def get_ai_image(self, timeout=30):
        artist = self.clean_title(self.ai_artist).replace("&", "and").replace("?", "").replace('"', '')
        title = self.clean_title(self.ai_title).replace("&", "and").replace("?", "").replace('"', '')
        font_color, recommended_font_color, recommended_font_color_rgb, background_color, most_common_color_alternative_rgb, most_common_color_alternative, background_color_rgb, brightness, brightness_lower_part = self.reset_img_values()
        picture = self.format_ai_image_prompt(artist, title)
        try:
            img = self.get_image(picture)
            img = self.ensure_rgb(img)
            font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative = self.img_values(img)
            img = self.text_clock_img(img, brightness_lower_part)
            gif_base64 = self.gbase64(img)
            return gif_base64, font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative

        except Exception as e:
            self.log(f"Failed to create AI image for {artist} - {title}: {e}")  
            gif_base64 = zlib.decompress(BLK_SCR).decode()
            self.fail_txt = self.fallback = True
            return gif_base64, font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative

    def text_clock_img(self, img, brightness_lower_part):
        if self.text_bg and self.show_text and not self.radio_logo:
            lpc = (0,48,64,64)
            lower_part_img = img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(brightness_lower_part)
            img.paste(lower_part_img, lpc)

        if self.show_clock:
            lpc = (43, 2, 62, 9) if self.clock_align == "Right" else (2, 2, 21, 9)
            lower_part_img = img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(0.2)
            img.paste(lower_part_img, lpc)
        return img

    def gbase64(self, img):
        try:
            if img.mode == "RGB":
                pixels = [item for p in list(img.getdata()) for item in p]
            else:
                pixels = list(img.getdata())
            b64 = base64.b64encode(bytearray(pixels))
            gif_base64 = b64.decode("utf-8")
            self.fallback = self.fail_text = False
            return gif_base64

        except Exception as e:
            gif_base64 = zlib.decompress(BLK_SCR).decode()
            self.fail_txt = self.fallback = True
            return gif_base64

    def format_ai_image_prompt(self, artist, title):
        # Format the AI image prompt with the given artist and title
        if artist:
            prompt = f"Create a photorealistic image inspired by {artist}'s, titled: '{title}'. The artwork should feature an accurate likeness of the artist and creatively interpret the title into a pop art visual imagery in 80's video game style."
        else:
            prompt = f"Create a photorealistic image inspired by: '{title}'. Incorporate bold colors and pop art visual imagery in 80's video game style."
        prompt = f"{AI_ENGINE}/{prompt}?model={self.ai_fallback}"
        return prompt
        
