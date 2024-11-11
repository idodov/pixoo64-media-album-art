"""
Divoom Pixoo64 Album Art Display
--------------------------------
This functionality automatically showcases the album cover art of the currently playing track on your Divoom Pixoo64 screen.
In addition to this, it extracts useful information like the artist's name and the predominant color from the album art. This extracted data can be leveraged for additional automation within your Home Assistant setup.
This script also supports AI image creation It's designed to show alternative AI-generated album cover art when no album art exists, or when using music services (like SoundCloud) where the script can't fetch the image.

APPDAEMON CONFIGURATION
python_packages:
  - pillow
  - unidecode
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
        force_ai: False                            # Show only AI Images
        musicbrainz: True                          # Get fallback image from MusicBrainz 
        spotify_client_id: False                   # client_id key API KEY from https://developers.spotify.com
        spotify_client_secret: False               # client_id_secret API KEY
        last.fm: False                             # Last.fm API KEY from https://www.last.fm/api/account/create
        discogs: False                             # Discogs API KEY from https://www.discogs.com/settings/developers
    pixoo:
        url: "http://192.168.86.21/post"        # Pixoo device URL
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
import asyncio
import aiohttp
import re
import os
import base64
import json
import time
import zlib
import random
import traceback
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from appdaemon.plugins.hass import hassapi as hass

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

# Constants
AI_ENGINE = "https://pollinations.ai/p"
BLK_SCR = b'x\x9c\xed\xc11\x01\x00\x00\x00\xc2\xa0l\xeb_\xca\x18>@\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00o\x03\xda:@\xf1'
TV_ICON_PATH = "/local/pixoo64/tv-icon-1.png"
local_directory = "/homeassistant/www/pixoo64/"

files = {
    "tv-icon-1.png": "https://raw.githubusercontent.com/idodov/pixoo64-media-album-art/refs/heads/main/apps/pixoo64_media_album_art/tv-icon-1.png"
}

# Regex patterns for RTL text detection
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

class Pixoo64_Media_Album_Art(hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # Call the parent class's __init__ method
        self.image_lock = asyncio.Lock()  # Initialize a lock for image processing
        self.pending_task = None  # To keep track of the last task

    async def initialize(self):
        """Initialize the app and set up state listeners."""
        # Home Assistant settings
        self.media_player = self.args.get('home_assistant', {}).get("media_player", "media_player.era300")
        self.toggle = self.args.get('home_assistant', {}).get("toggle", "input_boolean.pixoo64_album_art")
        self.ha_url = self.args.get('home_assistant', {}).get("ha_url", "http://homeassistant.local:8123")
        self.pixoo_sensor = self.args.get('home_assistant', {}).get("pixoo_sensor", "sensor.pixoo64_media_data")
        self.light = self.args.get('home_assistant', {}).get("light", None)
        self.force_ai = self.args.get('home_assistant', {}).get("force_ai", False)

        # AI and Fallback services settings
        self.ai_fallback = self.args.get('home_assistant', {}).get("ai_fallback", 'flux')
        self.musicbrainz = self.args.get('home_assistant', {}).get("musicbrainz", True)
        self.spotify_client_id = self.args.get('home_assistant', {}).get("spotify_client_id", False)
        self.spotify_client_secret = self.args.get('home_assistant', {}).get("spotify_client_secret", False)
        self.discogs = self.args.get('home_assistant', {}).get("discogs", False)
        self.lastfm = self.args.get('home_assistant', {}).get("last.fm", False)

        # Pixoo device settings
        pixoo_url = self.args.get('pixoo', {}).get("url", "http://192.168.86.21:80/post")
        self.url = self.validate_pixoo_url(pixoo_url)

        # Display settings
        self.full_control = self.args.get('pixoo', {}).get("full_control", True)
        self.contrast = self.args.get('pixoo', {}).get("contrast", False)
        self.show_clock = self.args.get('pixoo', {}).get("clock", True)
        self.clock_align = self.args.get('pixoo', {}).get("clock_align", "Left")
        self.tv_icon_pic = self.args.get('pixoo', {}).get("tv_icon", True)

        # Text display settings
        self.show_text = self.args.get('pixoo', {}).get('show_text', {}).get("enabled", False)
        self.clean_title_enabled = self.args.get('pixoo', {}).get('show_text', {}).get("clean_title", True) 
        self.font = self.args.get('pixoo', {}).get('show_text', {}).get("font", 2)
        self.font_c = self.args.get('pixoo', {}).get('show_text', {}).get("color", True)
        self.text_bg = self.args.get('pixoo', {}).get('show_text', {}).get("text_background", True)
        self.ai_artist = self.ai_title = None

        # Image processing settings
        self.crop_borders = self.args.get('pixoo', {}).get('crop_borders', {}).get("enabled", True)
        self.crop_extra = self.args.get('pixoo', {}).get('crop_borders', {}).get("extra", True)

        # State variables
        self.fallback = self.fail_txt = self.playing_radio = self.radio_logo = False
        self.album_name = self.get_state(self.media_player, attribute="media_album_name")

        # Validate AI model
        if self.ai_fallback not in ["flux", "turbo"]:
            self.ai_fallback = "turbo"

        # Initialize local directory
        if not os.path.exists(local_directory):
            os.makedirs(local_directory)

        # Download required files asynchronously
        async def download_file(file_name, url):
            local_file_path = os.path.join(local_directory, file_name)
            if not os.path.exists(local_file_path):
                self.log(f"Downloading {file_name} from {url}...")  # Log the download action
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            with open(local_file_path, 'wb') as file:
                                file.write(await response.read())
                        else:
                            self.log(f"Failed to download {file_name}: {response.status}")  # Log failure

        # Create a list of download tasks
        download_tasks = [download_file(file_name, url) for file_name, url in files.items()]
        await asyncio.gather(*download_tasks)
        
        # Spotify token cache
        self.spotify_token_cache = {
            'token': None,
            'expires': 0
        }

        # Set up state listeners
        self.listen_state(self.safe_state_change_callback, self.media_player, attribute='media_title')
        self.listen_state(self.safe_state_change_callback, self.media_player)
        
        # Update headers
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Connection": "keep-alive",
            "User-Agent": "PixooClient/1.0"
        }

        # Test connection
        self.is_processing = False
        self.callback_timeout = 30  # Increase the callback timeout limit
        self.select_index = await self.get_current_channel_index()

    async def safe_state_change_callback(self, entity, attribute, old, new, kwargs):
        """Wrapper for state change callback with timeout protection"""
        if hasattr(self, 'is_processing') and self.is_processing:
            self.log(f"Ignoring new callback {self.ai_artist} - {self.ai_title}", level="WARNING")
            return  # Ignore if already processing

        self.is_processing = True  # Set the flag to indicate processing has started
        try:
            # Create a task with timeout
            async with asyncio.timeout(self.callback_timeout):
                await self.state_change_callback(entity, attribute, old, new, kwargs)
        except asyncio.TimeoutError:
            self.log("Callback timed out - cancelling operation", level="WARNING")
            # Optionally reset any state or cleanup here
        except Exception as e:
            self.log(f"Error in callback: {str(e)}", level="ERROR")
        finally:
            self.is_processing = False  # Reset the flag when processing is done

    async def state_change_callback(self, entity, attribute, old, new, kwargs):
        """Main callback with early exit conditions"""
        try:
            # Quick checks for early exit
            if new == old:
                return
            
            # Get the state of the input boolean
            input_boolean = await self.get_state(self.toggle)
            if input_boolean != "on":
                return
            
            media_state = await self.get_state(self.media_player)
            if media_state in ["off", "idle", "pause", "paused"]:
                await self.set_state(self.pixoo_sensor, state="off")
                self.album_name = "media player is not playing - removing the album name"

                if self.full_control:
                    # Check state again after delay to ensure music is still stopped
                    await asyncio.sleep(2)  # Delay to not turn off during track changes
                    current_state = await self.get_state(self.media_player)
                    
                    if current_state not in ["playing", "on"]:
                        payload = {
                            "Command": "Draw/CommandList",
                            "CommandList": [
                                {"Command": "Draw/ClearHttpText"},
                                {"Command": "Draw/ResetHttpGifId"},
                                {"Command": "Channel/OnOffScreen", "OnOff": 0}
                            ]
                        }
                        await self.send_pixoo(payload)
                        await self.set_state(self.pixoo_sensor, state="off")
                        if self.light:
                            await self.control_light('off')
                else:
                    # If not in full control, just update the display
                    current_state = await self.get_state(self.media_player)
                    if current_state not in ["playing", "on"]:
                        payload = {
                            "Command": "Draw/CommandList",
                            "CommandList": [
                                {"Command": "Draw/ClearHttpText"},
                                {"Command": "Draw/ResetHttpGifId"},
                                {"Command": "Channel/SetIndex", "SelectIndex": 4},
                                {"Command": "Channel/SetIndex", "SelectIndex": self.select_index}
                            ]
                        }
                        await self.send_pixoo(payload)
                        await self.set_state(self.pixoo_sensor, state="off")
                        if self.light:
                            await self.control_light('off')
                return

            # If we get here, proceed with the main logic
            await self.update_attributes(entity, attribute, old, new, kwargs)

        except Exception as e:
            self.log(f"Error in state change callback: {str(e)}", level="ERROR")

    async def update_attributes(self, entity, attribute, old, new, kwargs):
        """Modified to be more efficient"""
        try:
            # Quick validation of media state
            media_state = await self.get_state(self.media_player)
            if media_state not in ["playing", "on"]:
                if self.light:
                    await self.control_light('off')
                return

            # Get current title and check if we need to update
            title = await self.get_state(self.media_player, attribute="media_title")
            if not title:
                return

            title = self.clean_title(title) if self.clean_title_enabled else title

            # Check if we need to update the album art
            album_name_check = await self.get_state(self.media_player, attribute="media_album_name") or title
            if album_name_check == self.album_name:
                return  # No need to update if it's the same album

            # Proceed with the main logic
            await self.pixoo_run(media_state)

        except Exception as e:
            self.log(f"Error in update_attributes: {str(e)}\n{traceback.format_exc()}")

    async def pixoo_run(self, media_state):
        """Add timeout protection to pixoo_run"""
        try:
            async with asyncio.timeout(self.callback_timeout):
                # Get current channel index
                self.select_index = await self.get_current_channel_index()
                if media_state in ["playing", "on"]:
                    title = await self.get_state(self.media_player, attribute="media_title")
                    original_title = title
                    title = self.clean_title(title) if self.clean_title_enabled else title

                    album_name_check = await self.get_state(self.media_player, attribute="media_album_name") or title
                    self.send_pic = album_name_check != self.album_name

                    if title != "TV" and title is not None:
                        artist = await self.get_state(self.media_player, attribute="media_artist")
                        original_artist = artist
                        artist = artist if artist else ""
                        if undicode_m:
                            normalized_title = unidecode(title)
                            normalized_artist = unidecode(artist) if artist else ""
                        else:
                            normalized_title = title
                            normalized_artist = artist if artist else ""
                        self.ai_title = original_title #normalized_title
                        self.ai_artist = original_artist #normalized_artist
                        
                        picture = await self.get_state(self.media_player, attribute="entity_picture")
                        original_picture = picture
                        media_content_id = await self.get_state(self.media_player, attribute="media_content_id")
                        queue_position = await self.get_state(self.media_player, attribute="queue_position")
                        media_channel = await self.get_state(self.media_player, attribute="media_channel")

                        if media_channel and (media_content_id.startswith("x-rincon") or media_content_id.startswith("aac://http") or media_content_id.startswith("rtsp://")):
                            self.playing_radio = True
                            self.radio_logo = False
                            if artist:
                                picture = self.format_ai_image_prompt(artist, title)
                            if ('https://tunein' in media_content_id or
                                    queue_position == 1 or 
                                    original_title == media_channel or 
                                    original_title == original_artist or 
                                    original_artist == media_channel or 
                                    original_artist == 'Live' or 
                                    original_artist == None):
                                picture = original_picture
                                self.radio_logo = True
                        else:
                            self.playing_radio = self.radio_logo = False
                            picture = original_picture
                        gif_base64, font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative = await self.get_final_url(picture)

                        new_attributes = {"artist": artist,"normalized_artist": normalized_artist, "media_title": title,"normalized_title": normalized_title, "font_color": font_color, "font_color_alternative": recommended_font_color, "background_color_brightness": brightness, "background_color": background_color, "color_alternative_rgb": most_common_color_alternative, "background_color_rgb": background_color_rgb, "recommended_font_color_rgb": recommended_font_color_rgb, "color_alternative": most_common_color_alternative_rgb,}
                        await self.set_state(self.pixoo_sensor, state="on", attributes=new_attributes)
                        payload = {
                            "Command": "Draw/CommandList",
                            "CommandList": [
                                {"Command": "Channel/OnOffScreen", "OnOff": 1},
                                {"Command": "Draw/ResetHttpGifId"},
                                {
                                    "Command": "Draw/SendHttpGif",
                                    "PicNum": 1,
                                    "PicWidth": 64,
                                    "PicOffset": 0,
                                    "PicID": 0,
                                    "PicSpeed": 1000,
                                    "PicData": gif_base64
                                }
                            ]
                        }
                        moreinfo = {
                            "Command": "Draw/SendHttpItemList",
                            "ItemList": []
                        }
                        textid = 0
                        text_track = (artist + " - " + title) 
                        if len(text_track) > 14:
                            text_track = text_track + "       "
                        text_string = self.convert_text(text_track) if artist else self.convert_text(title)
                        dir = 1 if self.has_bidi(text_string) else 0
                        brightness_factor = 50  
                        try:
                            color_font = tuple(min(255, c + brightness_factor) for c in background_color_rgb)
                        except Exception as e:
                            background_color_rgb = (200,200,200)
                            color_font = (255,255,255)
                        #color_font = tuple(min(255, int(c) + brightness_factor) for c in background_color_rgb)

                        color_font = '#%02x%02x%02x' % color_font
                        color_font = color_font if self.font_c else recommended_font_color
                        if self.send_pic:
                            self.album_name = album_name_check # Will not try to upload a new pic while listening to the same album
                            await self.send_pixoo(payload)
                            if self.light:
                                await self.control_light('on',background_color_rgb)
                        
                        if self.show_text and not self.fallback and not self.radio_logo:
                            textid +=1
                            text_temp = { 
                                "TextId":textid, 
                                "type":22, 
                                "x":0, 
                                "y":48, 
                                "dir":dir, 
                                "font":2, 
                                "TextWidth":64, 
                                "Textheight":16, 
                                "speed":100, 
                                "align":2, 
                                "TextString": text_string, 
                                "color":color_font 
                            }
                            moreinfo["ItemList"].append(text_temp)

                        if self.show_clock and not self.fallback:
                            textid +=1
                            x = 44 if self.clock_align == "Right" else 3
                            clock_item =  { 
                                "TextId":textid, 
                                "type":5, 
                                "x":x, 
                                "y":3, 
                                "dir":0, 
                                "font":18, 
                                "TextWidth":32, 
                                "Textheight":16, 
                                "speed":100, 
                                "align":1, 
                                "color":color_font 
                                }
                            moreinfo["ItemList"].append(clock_item)

                        if (self.show_text or self.show_clock) and not self.fallback:
                            await self.send_pixoo(moreinfo)

                        if self.fallback and self.fail_txt:
                            payloads = self.create_payloads(normalized_artist, normalized_title, 13)
                            payload = {"Command":"Draw/CommandList", "CommandList": payloads}
                            await self.send_pixoo(payload)
                    else:
                        if self.tv_icon_pic:
                            picture = TV_ICON_PATH
                            img = await self.get_image(picture)
                            img = self.ensure_rgb(img)
                            gif_base64 = self.gbase64(img)
                            payload = {
                                "Command": "Draw/CommandList",
                                "CommandList": [
                                    {"Command": "Channel/OnOffScreen", "OnOff": 1},
                                    {"Command": "Draw/ResetHttpGifId"},
                                    {
                                        "Command": "Draw/SendHttpGif",
                                        "PicNum": 1,
                                        "PicWidth": 64,
                                        "PicOffset": 0,
                                        "PicID": 0,
                                        "PicSpeed": 1000,
                                        "PicData": gif_base64
                                    }
                                ]
                            }
                        else:
                            payload = {
                                "Command": "Draw/CommandList",
                                "CommandList": [
                                    {"Command": "Draw/ClearHttpText"},
                                    {"Command": "Draw/ResetHttpGifId"},
                                    {"Command": "Channel/SetIndex", "SelectIndex": 4},
                                    {"Command": "Channel/SetIndex", "SelectIndex": self.select_index}
                                ]
                            }

                        await self.send_pixoo(payload)
                        if self.light:
                            await self.control_light('off')
                else:
                    self.album_name = "no music is playing and no album name"
                    
        except Exception as e:
            self.log(f"Error in pixoo_run: {str(e)}\n{traceback.format_exc()}")

    async def send_pixoo(self, payload_command):
        """Send command to Pixoo device"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, headers=self.headers, json=payload_command, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        self.log(f"Failed to send REST: {response.status}")
                    else:
                        await asyncio.sleep(0.25)
        except Exception as e:
            self.log(f"Error sending command to Pixoo: {str(e)}\n{traceback.format_exc()}")

    async def get_image(self, picture):
        if not picture:
            return None
        
        async with self.image_lock:  # Acquire the lock before processing
            self.pending_task = picture  # Set the current task as pending

        try:
            async with aiohttp.ClientSession() as session:
                url = picture if picture.startswith('http') else f"{self.ha_url}{picture}"
                async with session.get(url) as response:
                    if response.status != 200:
                        self.fail_txt = self.fallback = True
                        return None
                    
                    image_data = await response.read()
                    result = await self.process_image_data(image_data)

                    # Check if a new task was set while processing
                    async with self.image_lock:
                        if self.pending_task != picture:  # If a new task is pending
                            return None  # Ignore the result of this task

                    return result

        except Exception as e:
            self.log(f"Unexpected error in get_image: {str(e)}\n{traceback.format_exc()}")
            self.fail_txt = self.fallback = True
            return None

    async def process_image_data(self, image_data):
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            img = await loop.run_in_executor(
                executor,
                self._process_image,
                image_data
            )
        return img

    def _process_image(self, image_data):
        try:
            with Image.open(BytesIO(image_data)) as img:
                img = self.ensure_rgb(img)
                
                # Ensure the image is square
                width, height = img.size
                if height < width:  # Check if height is less than width
                    # Calculate the border size
                    border_size = (width - height) // 2
                    background_color = img.getpixel((1, 1))
                    
                    new_img = Image.new("RGB", (width, width), background_color)  # Create a square image
                    new_img.paste(img, (0, border_size))  # Paste the original image onto the new image
                    img = new_img  # Update img to the new image
                elif width != height:
                    new_size = min(width, height)
                    left = (width - new_size) // 2
                    top = (height - new_size) // 2
                    img = img.crop((left, top, left + new_size, top + new_size))
                

                if self.crop_borders and not self.radio_logo:
                    img = self.crop_image_borders(img)
                    
                if self.contrast:
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(1.5)
                    
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
                return img

        except Exception as e:
            self.log(f"Error processing image: {str(e)}")
            return None

    async def control_light(self, action, background_color_rgb=None):
        service_data = {'entity_id': self.light}
        if action == 'on':
            service_data.update({'rgb_color': background_color_rgb, 'transition': 2})
        try:
            await self.call_service(f'light/turn_{action}', **service_data)
        except Exception as e:
            self.log(f"Light Error: {self.light} - {e}\n{traceback.format_exc()}")

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

    async def process_picture(self, picture):
        try:
            img = await self.get_image(picture)
            if not img:
                return None

            # Create a new event loop for the executor
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    self._process_picture_sync,
                    img
                )
            return result

        except Exception as e:
            self.log(f"Failed to process picture: {e}")
            return None

    def _process_picture_sync(self, img):
        """Synchronous image processing helper function"""
        font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative = self.img_values(img)
        img = self.text_clock_img(img, brightness_lower_part)
        gif_base64 = self.gbase64(img)
        return (gif_base64, font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative)

    async def get_musicbrainz_album_art_url(self) -> str:
        """Get album art URL from MusicBrainz asynchronously"""
        search_url = "https://musicbrainz.org/ws/2/release/"
        headers = {
            "Accept": "application/json",
            "User-Agent": "PixooClient/1.0"
        }
        params = {
            "query": f'artist:"{self.ai_artist}" AND recording:"{self.ai_title}"',
            "fmt": "json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Get the release ID
                async with session.get(search_url, params=params, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        self.log(f"MusicBrainz API error: {response.status}")
                        return None

                    data = await response.json()
                    if not data.get("releases"):
                        self.log("No releases found in MusicBrainz")
                        return None

                    release_id = data["releases"][0]["id"]
                    
                    # Get the cover art
                    cover_art_url = f"https://coverartarchive.org/release/{release_id}"
                    async with session.get(cover_art_url, headers=headers, timeout=20) as art_response:
                        if art_response.status != 200:
                            self.log(f"Cover art archive error: {art_response.status}\n{cover_art_url}")
                            return None

                        art_data = await art_response.json()
                        # Look for front cover and get 250px thumbnail
                        for image in art_data.get("images", []):
                            if image.get("front", False):
                                return image.get("thumbnails", {}).get("250")

                        self.log("No front cover found in cover art archive")
                        return None

        except asyncio.TimeoutError:
            self.log("MusicBrainz request timed out")

    async def get_spotify_access_token(self):
        try:
            # Check if cached token is still valid
            if (self.spotify_token_cache['token'] and 
                time.time() < self.spotify_token_cache['expires']):
                return self.spotify_token_cache['token']

            url = "https://accounts.spotify.com/api/token"
            spotify_headers = {
                "Authorization": "Basic " + base64.b64encode(f"{self.spotify_client_id}:{self.spotify_client_secret}".encode()).decode(),
                "Content-Type": "application/x-www-form-urlencoded"
            }
            payload = {
                "grant_type": "client_credentials"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=spotify_headers, data=payload) as response:
                    response_json = await response.json()
                    access_token = response_json["access_token"]
            
            # Cache the new token
            self.spotify_token_cache = {
                'token': access_token,
                'expires': time.time() + 3500  # Cache for slightly less than 1 hour
            }
            
            self.log("Got new Spotify access token")
            return access_token
            
        except Exception as e:
            self.log(f"Error getting Spotify access token: {str(e)}\nCheck client_id and client_secret at https://developer.spotify.com/dashboard")
            self.spotify_client_id = False
            return False

    # Function to get album ID by artist and track
    async def get_spotify_album_id(self):
        try:
            token = await self.get_spotify_access_token()
            if not token:
                return None
                
            url = "https://api.spotify.com/v1/search"
            spotify_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            payload = {
                "q": f"track: {self.ai_title} artist: {self.ai_artist}",
                "type": "track",
                "limit": 1
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=spotify_headers, params=payload) as response:
                    response_json = await response.json()
                    track_info = response_json['tracks']['items'][0]
                    album_id = track_info['album']['id']
                    return album_id
        except Exception:
            self.log(f"Error getting spotify album id")
            return None

    # Function to get album image URL
    async def get_spotify_album_image_url(self, album_id):
        try:
            token = await self.get_spotify_access_token()
            if not token or not album_id:
                return None
                
            url = f"https://api.spotify.com/v1/albums/{album_id}"
            spotify_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=spotify_headers) as response:
                    response_json = await response.json()
                    image_url = response_json['images'][0]['url']
                    if image_url:
                        return image_url
        except Exception:
            self.log(f"Error getting spotify album url")
            return None
    # Function to get album image URL from Discogs

    async def search_discogs_album_art(self):
        # Define the base URL and headers for Discogs API
        base_url = "https://api.discogs.com/database/search"
        headers = {
            "User-Agent": "AlbumArtSearchApp/1.0",
            "Authorization": f"Discogs token={self.discogs}"
        }

        # Set up the search parameters
        params = {
            "artist": self.ai_artist,
            "track": self.ai_title,
            "type": "release",
            "format": "album"
        }

        # Perform an asynchronous HTTP request
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, headers=headers, params=params) as response:
                # Check if the request was successful
                if response.status == 200:
                    data = await response.json()
                    # Check if there are results
                    if data["results"]:
                        # Get the album art URL from the first result
                        album_art_url = data["results"][0].get("cover_image")
                        if album_art_url:
                            return album_art_url
                        else:
                            print("Album art not found @ Discogs.")
                            return None
                    else:
                        self.log("No results found for the specified artist and track @ Discogs.")
                        return None
                else:
                    print(f"Error: {response.status} - {response.reason}")
                    return None

    async def search_lastfm_album_art(self):
        base_url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "track.getInfo",
            "api_key": self.lastfm,
            "artist": self.ai_artist,
            "track": self.ai_title,
            "format": "json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    album_art_url = data.get("track", {}).get("album", {}).get("image", [])
                    if album_art_url:
                        return album_art_url[-1]["#text"]
                return None

    async def get_final_url(self, picture, timeout=30):
        self.fail_txt = self.fallback = False

        if self.force_ai and not self.radio_logo:
            try:
                ai_url = self.format_ai_image_prompt(self.ai_artist, self.ai_title)
                result = await self.process_picture(ai_url)
                if result:
                    self.log("Force Generated AI Image")
                    return result
            except Exception as e:
                self.log(f"AI generation failed: {e}")
        else:
        # Process original picture
            try:
                if not self.playing_radio or self.radio_logo:
                    result = await self.process_picture(picture)
                    if result:
                        return result
            except Exception as e:
                self.log(f"Original picture processing failed: {e}")

            """ Fallback begins """
            # Try Discogs:
            if self.discogs:
                try:
                    album_art = await self.search_discogs_album_art()
                    if album_art:
                        result = await self.process_picture(album_art)
                        if result:
                            self.log("Successfully found and processed the Album Art @ Discogs")
                            return result
                        else:
                            self.log("Failed to process Discogs image")
                except Exception as e:
                    self.log(f"Discogs fallback failed with error: {str(e)}")

            # Try Spotify
            if self.spotify_client_id and self.spotify_client_secret:
                try:
                    album_id = await self.get_spotify_album_id()
                    if album_id:
                        image_url = await self.get_spotify_album_image_url(album_id)
                        if image_url:
                            result = await self.process_picture(image_url)
                            if result:
                                self.log("Successfully found and processed the Album Art @ Spotify")
                                return result
                        else:
                            self.log("Failed to process Spotify image")
                except Exception as e:
                    self.log(f"Spotify fallback failed with error: {str(e)}")
        
            #Try Last.fm:
            if self.lastfm:
                try:
                    album_art = await self.search_lastfm_album_art()
                    if album_art:
                        result = await self.process_picture(album_art)
                        if result:
                            self.log("Successfully found and processed the Album Art @ Last.fm")
                            return result
                        else:
                            self.log("Failed to process Last.fm image")
                except Exception as e:
                    self.log(f"Last.fm fallback failed with error: {str(e)}")

            # Try MusicBrainz
            if self.musicbrainz:
                try:
                    mb_url = await self.get_musicbrainz_album_art_url()
                    if mb_url:
                        result = await self.process_picture(mb_url)
                        if result:
                            self.log("Successfully found and processed the Album Art @ MusicBrainz")
                            return result
                        else:
                            self.log("Failed to process MusicBrainz image")
                except Exception as e:
                    self.log(f"MusicBrainz fallback failed with error: {str(e)}")

            # Fallback to AI generation
            try:
                ai_url = self.format_ai_image_prompt(self.ai_artist, self.ai_title)
                result = await self.process_picture(ai_url)
                if result:
                    self.log("Successfully Generated AI Image")
                    return result
            except Exception as e:
                self.log(f"AI generation failed: {e}")

        # Ultimate fallback
        default_values = self.reset_img_values()
        self.fail_txt = self.fallback = True
        return (zlib.decompress(BLK_SCR).decode(), *default_values)

    def ensure_rgb(self, img):
        try:
            if img.mode != "RGB":
                img = img.convert("RGB")
            return img
        except Exception:
            return None

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
        payloads = [
            {
                "Command": "Draw/SendHttpText",
                "TextId": i + 1,
                "x": 0,
                "y": start_y + i * 15,
                "dir": 0,
                "font": self.font,
                "TextWidth": 64,
                "speed": 80,
                "TextString": line,
                "color": "#a0e5ff" if i < len(artist_lines) else "#f9ffa0",
                "align": 2
            }
            for i, line in enumerate(all_lines)
        ]
        return payloads
    
    def most_vibrant_color(self, full_img):
        """Extract the most vibrant color from an image"""
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
        """Convert text for display, handling RTL languages"""
        try:
            return get_display(text) if text and self.has_bidi(text) else text
        except Exception as e:
            self.log(f"To display RTL text you need to add bidi-algorithm package: {e}.")
            return text

    def has_bidi(self, text):
        """Check if text contains bidirectional characters"""
        bidi_regex = f"[{hebrew}|{arabic}|{syriac}|{thaana}|{nkoo}|{rumi}|{arabic_math}|{symbols}|{old_persian_phaistos}|{samaritan}]"
        return bool(re.search(bidi_regex, text))

    def validate_pixoo_url(self, url):
        # Ensure the URL starts with 'http'
        if not url.startswith('http'):
            url = f"http://{url}"

        # Ensure the URL ends with ':80/post'
        if not url.endswith(':80/post'):
            url = f"{url}:80/post"

        return url

    def clean_title(self, title):
        """Clean up the title by removing common patterns"""
        if not title:
            return title

        # Patterns to remove
        patterns = [
            r'\([^)]*remaster[^)]*\)',  # Remove remaster information
            r'\([^)]*remix[^)]*\)',     # Remove remix information
            r'\([^)]*version[^)]*\)',   # Remove version information
            r'\([^)]*edit[^)]*\)',      # Remove edit information
            r'\([^)]*live[^)]*\)',      # Remove live information
            r'\([^)]*bonus[^)]*\)',     # Remove bonus track information
            r'\([^)]*deluxe[^)]*\)',    # Remove deluxe information
            r'\([^)]*\d{4}\)',          # Remove years in parentheses
            r'^\d+\s*[\.-]\s*',         # Remove track numbers at start
            r'\.mp3$', r'\.m4a$', r'\.wav$', r'\.flac$'  # Remove file extensions
        ]

        # Apply each pattern
        cleaned_title = title
        for pattern in patterns:
            cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.IGNORECASE)

        # Remove extra whitespace
        cleaned_title = ' '.join(cleaned_title.split())
        return cleaned_title


    def crop_image_borders(self, img):
        """Crop image to make it square and then crop borders based on the most common border color."""
        temp_img = img

        if self.crop_extra:
            img = img.filter(ImageFilter.BoxBlur(5))
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.95)

        try:
            border_pixels = []
            width, height = img.size
            
            border_pixels.extend([img.getpixel((x, 0)) for x in range(width)])  # Top border
            border_pixels.extend([img.getpixel((x, height - 1)) for x in range(width)])  # Bottom border
            border_pixels.extend([img.getpixel((0, y)) for y in range(height)])  # Left border
            border_pixels.extend([img.getpixel((width - 1, y)) for y in range(height)])  # Right border

            border_color = max(set(border_pixels), key=border_pixels.count)

            mask = Image.new("L", img.size, 0)  # Create a mask with the same size as the image
            for x in range(width):
                for y in range(height):
                    if img.getpixel((x, y)) != border_color:
                        mask.putpixel((x, y), 255)

            bbox = mask.getbbox() 
            if bbox:
                center_x = (bbox[0] + bbox[2]) // 2
                center_y = (bbox[1] + bbox[3]) // 2
                size = min(bbox[2] - bbox[0], bbox[3] - bbox[1])
                
                half_size = max(size // 2, 32)
                img = temp_img.crop((center_x - half_size, center_y - half_size, center_x + half_size, center_y + half_size))  # Crop the image to the bounding box
            else:
                img = temp_img  

        except Exception as e:
            self.log(f"Failed to crop: {e}")  
            img = temp_img
            
        return img

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
        # List of prompt templates
        if not artist:
            artist = 'Pixoo64 (a real 64x64 led screen)'
        prompts = [
            f"Create an image inspired by the music artist {artist}, titled: '{title}'. The artwork should feature an accurate likeness of the artist and creatively interpret the title into a visual imagery.",
            f"Design a vibrant album cover for '{title}' by {artist}, incorporating elements that reflect the mood and theme of the music.",
            f"Imagine a surreal landscape that represents the essence of '{title}' by {artist}. Use bold colors and abstract shapes.",
            f"Create a retro-style album cover for '{title}' by {artist}, featuring pixel art and nostalgic elements from the 80s.",
            f"Illustrate a dreamlike scene inspired by '{title}' by {artist}, blending fantasy and reality in a captivating way.",
            f"Generate a minimalist design for '{title}' by {artist}, focusing on simplicity and elegance in the artwork.",
            f"Craft a dynamic and energetic cover for '{title}' by {artist}, using motion and vibrant colors to convey excitement.",
            f"Produce a whimsical and playful illustration for '{title}' by {artist}, incorporating fun characters and imaginative elements.",
            f"Create a dark and moody artwork for '{title}' by {artist}, using shadows and deep colors to evoke emotion.",
            f"Design a futuristic album cover for '{title}' by {artist}, featuring sci-fi elements and innovative designs."
        ]

        # Randomly select a prompt
        prompt = random.choice(prompts)
        prompt = f"{AI_ENGINE}/{prompt}?model={self.ai_fallback}"
        return prompt

    async def get_current_channel_index(self):
        channel_command = {
            "Command": "Channel/GetIndex"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.url,
                    headers=self.headers,
                    json=channel_command,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    response_text = await response.text()
                    response_data = json.loads(response_text)
                    return response_data.get('SelectIndex', 1)
        except Exception as e:
            self.log(f"Failed to get channel index from Pixoo: {str(e)}")
            return 1  # Default fallback value
