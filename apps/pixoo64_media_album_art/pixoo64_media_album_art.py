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
        url: "192.168.86.21"                       # Pixoo device URL
        full_control: True                         # Control display on/off with play/pause
        contrast: True                             # Apply 50% contrast filter
        clock: True                                # Show clock top corner
        clock_align: Right                         # Clock align - Left or Right
        tv_icon: True                              # Shows TV icon when playing sound from TV
        lyrics: False                              # Show track lyrics. In this mode the show_text and clock feture will disable.
        spotify_slide: False                       # Force album art slide (needs spotify_cliend_id & spotify_client_secret). Clock/Title disabed in this mode.
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
import base64
import os
import re
import json
import time
import zlib
import random
import traceback
from datetime import datetime, timezone
from collections import OrderedDict, Counter
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import math


# Third-party library imports
import aiohttp
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageChops
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

# Home Assistant plugins
from appdaemon.plugins.hass import hassapi as hass

# Constants
AI_ENGINE = "https://pollinations.ai/p"
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
        super().__init__(*args, **kwargs)
        self.image_lock = asyncio.Lock()
        self.pending_task = None
        self.clear_timer_task = None
        self.image_cache = OrderedDict()
        self.cache_size = 25 #Number of images in cache

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
        pixoo_url = self.args.get('pixoo', {}).get("url", "192.168.86.21")
        pixoo_url = f"http://{pixoo_url}" if not pixoo_url.startswith('http') else pixoo_url
        pixoo_url = f"{pixoo_url}:80/post" if not pixoo_url.endswith(':80/post') else pixoo_url
        self.url = pixoo_url

        # Display settings
        self.full_control = self.args.get('pixoo', {}).get("full_control", True)
        self.contrast = self.args.get('pixoo', {}).get("contrast", False)
        self.show_clock = self.args.get('pixoo', {}).get("clock", True)
        self.clock_align = self.args.get('pixoo', {}).get("clock_align", "Left")
        self.tv_icon_pic = self.args.get('pixoo', {}).get("tv_icon", True)
        self.spotify_slide = self.args.get('pixoo', {}).get("spotify_slide", False)

        # Text display settings
        self.show_lyrics = self.args.get('pixoo', {}).get("lyrics", False)
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
        self.fallback = False
        self.fail_txt = False
        self.playing_radio = False
        self.radio_logo = False
        self.spotify_slide_pass = False
        self.media_position = 0
        self.media_duration = 0
        self.media_position_updated_at = None
        self.spotify_data = None

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
        self.listen_state(self.safe_state_change_callback, self.media_player, attribute='state')
        if self.show_lyrics:
            self.run_every(self.calculate_position, datetime.now(), 1)  # Run every second
        
        #self.run_daily(self.clear_cache, "04:00:00")
        self.output_folder = "/homeassistant/www/"  # Folder to save GIF
        
        # Update headers
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Connection": "keep-alive",
            "User-Agent": "PixooClient/1.0"
        }

        # Test connection
        self.is_processing = False
        self.lyrics = []
        self.lyrics_font_color = "#FF00AA"
        self.callback_timeout = 20  # Increase the callback timeout limit
        self.select_index = await self.get_current_channel_index()

    async def safe_state_change_callback(self, entity, attribute, old, new, kwargs, timeout=aiohttp.ClientTimeout(total=20)):
        """Wrapper for state change callback with timeout protection"""
        if self.is_processing:
            self.log(f"Ignoring new callback {new} - {old}", level="WARNING")
            return  # Ignore if already processing

        try:
            # Create a task with timeout
            async with asyncio.timeout(self.callback_timeout):
                await self.state_change_callback(entity, attribute, old, new, kwargs)
        except asyncio.TimeoutError:
            self.log("Callback timed out - cancelling operation", level="WARNING")
            # Optionally reset any state or cleanup here
        except Exception as e:
            self.log(f"Error in callback: {str(e)}", level="ERROR")

    async def state_change_callback(self, entity, attribute, old, new, kwargs):
        """Main callback with early exit conditions"""
        try:
            # Quick checks for early exit
            if new == old or (await self.get_state(self.toggle)) != "on":
                return
            
            media_state = await self.get_state(self.media_player)
            if media_state in ["off", "idle", "pause", "paused"]:
                await self.set_state(self.pixoo_sensor, state="off")

                if self.full_control:
                    await asyncio.sleep(10)  # Delay to not turn off during track changes
                    if await self.get_state(self.media_player) not in ["playing", "on"]:
                        await self.send_pixoo({
                            "Command": "Draw/CommandList",
                            "CommandList": [
                                {"Command": "Draw/ClearHttpText"},
                                {"Command": "Draw/ResetHttpGifId"},
                                {"Command": "Channel/OnOffScreen", "OnOff": 0}
                            ]
                        })
                        await self.set_state(self.pixoo_sensor, state="off")
                        if self.light:
                            await self.control_light('off')
                return

            # If we get here, proceed with the main logic
            await self.update_attributes(entity, attribute, old, new, kwargs)

        except Exception as e:
            self.log(f"Error in state change callback: {str(e)}")

    async def update_attributes(self, entity, attribute, old, new, kwargs):
        """Modified to be more efficient"""
        try:
            # Quick validation of media state
            if (media_state := await self.get_state(self.media_player)) not in ["playing", "on"]:
                if self.light:
                    await self.control_light('off')
                return

            # Get current title and check if we need to update
            if not (title := await self.get_state(self.media_player, attribute="media_title")):
                return

            title = self.clean_title(title) if self.clean_title_enabled else title

            if self.show_lyrics:
                artist = await self.get_state(self.media_player, attribute="media_artist")
                await self.get_lyrics(artist, title)  # Fetch lyrics here
            else:
                self.lyrics = []
            
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
                    self.media_position = await self.get_state(self.media_player, attribute="media_position", default=0)
                    self.media_position_updated_at = await self.get_state(self.media_player, attribute="media_position_updated_at", default=None)
                    self.media_duration = await self.get_state(self.media_player, attribute="media_duration", default=0)
                    original_title = title
                    title = self.clean_title(title) if self.clean_title_enabled else title
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
                        self.ai_title = normalized_title
                        self.ai_artist = normalized_artist
                        
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

                        if not self.is_processing:
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
                            color_font_rgb = tuple(min(255, c + brightness_factor) for c in background_color_rgb)
                            color_font = '#%02x%02x%02x' % color_font_rgb
                        except Exception as e:
                            self.log(f"Error calculating color_font: {e}")
                            color_font = '#ffffff'

                        color_font = color_font if self.font_c else recommended_font_color
                                                
                        await self.send_pixoo(payload)
                        
                        if self.light:
                            await self.control_light('on',background_color_rgb)

                        if self.spotify_slide and not self.radio_logo:
                            self.spotify_data = await self.get_spotify_json(artist, title)
                            if self.spotify_data:
                                await self.spotify_albums_slide()
                                if self.spotify_slide_pass:
                                    return
                                else:
                                    await self.send_pixoo(payload)

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

                        if (self.show_clock and self.fallback == False):
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

                        if (self.show_text or self.show_clock) and not (self.fallback or self.show_lyrics or self.spotify_slide):
                            await self.send_pixoo(moreinfo)

                        if self.fail_txt and self.fallback:
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

        except Exception as e:
            self.log(f"Error in pixoo_run: {str(e)}\n{traceback.format_exc()}")
        
        finally:
            await asyncio.sleep(0.10)
        

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

        async with self.image_lock:
            self.pending_task = picture

        # Check cache; if found, return directly.  No decompression needed here.
        if picture in self.image_cache:
            self.log("Image found in cache")
            cached_item = self.image_cache.pop(picture)
            self.image_cache[picture] = cached_item  # Re-add to maintain LRU order
            return cached_item['img']

        try:
            async with aiohttp.ClientSession() as session:
                url = picture if picture.startswith('http') else f"{self.ha_url}{picture}"
                async with session.get(url) as response:
                    if response.status != 200:
                        #self.fail_txt = True
                        self.fallback = True
                        return None

                    image_data = await response.read()
                    img = await self.process_image_data(image_data) # Process image *before* caching

                    async with self.image_lock:
                        if self.pending_task != picture:
                            return None

                    if img:
                        if len(self.image_cache) >= self.cache_size:
                            self.image_cache.popitem(last=False)
                        self.image_cache[picture] = {'img': img}  #Only store the processed image
            return img

        except Exception as e:
            self.log(f"Error in get_image: {str(e)}\n{traceback.format_exc()}", level="ERROR")
            self.fail_txt = True
            self.fallback = True
            return None

    async def process_image_data(self, image_data):
        self.is_processing = True
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            img = await loop.run_in_executor(
                executor,
                self._process_image,
                image_data
            )
        self.is_processing = False
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
            service_data.update({'rgb_color': background_color_rgb, 'transition': 1, })
        try:
            await self.call_service(f'light/turn_{action}', **service_data)
        except Exception as e:
            self.log(f"Light Error: {self.light} - {e}\n{traceback.format_exc()}")

    def reset_img_values(self):
        font_color_rgb = (255, 255, 255)  # White
        recommended_font_color_rgb = (0, 0, 0) # Black
        background_color_rgb = (0, 0, 0)  # Black
        most_common_color_alternative_rgb = (0, 0, 0) #Black
        brightness = brightness_lower_part = 0
        return font_color_rgb, recommended_font_color_rgb, recommended_font_color_rgb, brightness, brightness_lower_part, background_color_rgb, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb

    def img_values(self, img):
        font_color, recommended_font_color, recommended_font_color_rgb, background_color, most_common_color_alternative_rgb, most_common_color_alternative, background_color_rgb, brightness, brightness_lower_part = self.reset_img_values()
        full_img = img

        # Lower Part
        lower_part = img.crop((3, 48, 61, 61))
        lower_part = self.ensure_rgb(lower_part)
        most_common_color = self.most_vibrant_color(lower_part)
        opposite_color = tuple(255 - i for i in most_common_color)
        opposite_color_brightness = int(sum(opposite_color)/3)
        brightness_lower_part = round(1 - opposite_color_brightness / 255, 2) if 0 <= opposite_color_brightness <= 255 else 0

        # Full Image
        most_common_color_alternative_rgb = self.most_vibrant_color(full_img)
        most_common_color_alternative = '#%02x%02x%02x' % most_common_color_alternative_rgb
        brightness = int(sum(most_common_color_alternative_rgb) / 3)
        opposite_color_full = tuple(255 - i for i in most_common_color_alternative_rgb)
        opposite_color_brightness_full = int(sum(opposite_color_full)/3)
        self.brightness_full = round(1 - opposite_color_brightness_full / 255, 2) if 0 <= opposite_color_brightness_full <= 255 else 0

        font_color =  self.get_optimal_font_color(lower_part)
        self.lyrics_font_color = self.get_optimal_font_color(img)

        enhancer = ImageEnhance.Contrast(full_img)
        full_img = enhancer.enhance(2.0)
        background_color_rgb = self.most_vibrant_color(full_img)
        background_color = '#%02x%02x%02x' % most_common_color_alternative_rgb
        recommended_font_color_rgb = opposite_color
        
        return (font_color, recommended_font_color, brightness, brightness_lower_part, background_color, 
                background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative)

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
        if self.spotify_token_cache['token'] and time.time() < self.spotify_token_cache['expires']:
            return self.spotify_token_cache['token']

        url = "https://accounts.spotify.com/api/token"
        spotify_headers = {
            "Authorization": "Basic " + base64.b64encode(f"{self.spotify_client_id}:{self.spotify_client_secret}".encode()).decode(),
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {"grant_type": "client_credentials"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=spotify_headers, data=payload) as response:
                    response_json = await response.json()
                    access_token = response_json["access_token"]
                    self.spotify_token_cache = {
                        'token': access_token,
                        'expires': time.time() + 3500
                    }
                    return access_token
        except Exception as e:
            self.log(f"Error getting Spotify access token: {e}")
            return False

    async def get_spotify_json(self, artist, title):
        token = await self.get_spotify_access_token()
        if not token:
            return None

        url = "https://api.spotify.com/v1/search"
        spotify_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "q": f"track: {title} artist: {artist}",
            "type": "track",
            "limit": 20
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=spotify_headers, params=payload) as response:
                    response_json = await response.json()
                    tracks = response_json.get('tracks', {}).get('items', [])
                    if tracks:
                        return response_json
                    else:
                        self.log("No tracks found on Spotify.")
                        return None

        except (IndexError, KeyError) as e:
            self.log(f"Error parsing Spotify track info: {e}")
            return None
        except Exception as e:
            self.log(f"Error getting Spotify album ID: {e}")
            return None
        finally:
            await asyncio.sleep(0.5)


    async def spotify_best_album(self, tracks, artist):
        best_album = None
        earliest_year = float('inf')
        preferred_types = ["single", "ep", "album"]

        for track in tracks:
            album = track.get('album')
            album_type = album.get('album_type')
            release_date = album.get('release_date')
            year = int(release_date[:4]) if release_date else float('inf')
            artists = album.get('artists', [])
            album_artist = artists[0]['name'] if artists else ""

            if artist.lower() == album_artist.lower():
                #Corrected Prioritization:
                if album_type in preferred_types:
                    if year < earliest_year:  #Only choose the album if its year is earlier.
                        earliest_year = year
                        best_album = album
                elif year < earliest_year: #If not preferred type, choose based on year alone.
                    earliest_year = year
                    best_album = album

        if best_album:
            return best_album['id']
        else:
            if tracks:
                self.spotify_defualt_album = tracks[0]['album']['id']
                self.log("Most likey album art from Spotify is wrong. Trying next method.")
                #return self.spotify_defualt_album
                return None
            else:
                self.log("No suitable album found on Spotify.")
                return None

    async def get_spotify_album_id(self, artist, title):
        token = await self.get_spotify_access_token()
        if not token:
            return None

        self.spotify_defualt_album = None
        try:
            self.spotify_data = []
            response_json = await self.get_spotify_json(artist, title)
            self.spotify_data = response_json
            tracks = response_json.get('tracks', {}).get('items', [])
            if tracks:
                best_album = await self.spotify_best_album(tracks, artist)
                return best_album
            else:
                self.log("No tracks found on Spotify.")
                return None

        except (IndexError, KeyError) as e:
            self.log(f"Error parsing Spotify track info: {e}")
            return None
        except Exception as e:
            self.log(f"Error getting Spotify album ID: {e}")
            return None
        finally:
            await asyncio.sleep(0.5)


    async def get_spotify_album_image_url(self, album_id):
        token = await self.get_spotify_access_token()
        if not token or not album_id:
            return None
        url = f"https://api.spotify.com/v1/albums/{album_id}"
        spotify_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=spotify_headers) as response:
                    response_json = await response.json()
                    return response_json['images'][0]['url']
        except (IndexError, KeyError):
            self.log("Album image not found on Spotify.")
            return None
        except Exception as e:
            self.log(f"Error getting Spotify album image URL: {e}")
            return None
        finally:
            await asyncio.sleep(0.5)


    async def search_discogs_album_art(self):
        base_url = "https://api.discogs.com/database/search"
        headers = {
            "User-Agent": "AlbumArtSearchApp/1.0",
            "Authorization": f"Discogs token={self.discogs}"
        }
        params = {
            "artist": self.ai_artist,
            "track": self.ai_title,
            "type": "release",
            "format": "album",
            "per_page": 100 #Increased to get more results.
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("results", [])
                    if results:
                        best_release = None
                        earliest_year = float('inf')

                        for release in results:
                            year = int(release.get("year", earliest_year)) # Default to inf if no year
                            master_id = release.get("master_id")
                            # Prioritize releases with master_id
                            master_priority = 0 if master_id else 1
                            if year < earliest_year or (year == earliest_year and master_priority < 1):
                                earliest_year = year
                                best_release = release

                        if best_release:
                            album_art_url = best_release.get("cover_image")
                            if album_art_url:
                                return album_art_url
                            else:
                                self.log("Album art URL not found in best Discogs result.")
                                return None
                        else:
                            self.log("No suitable album found on Discogs.")
                            return None
                    else:
                        self.log("No results found for the specified artist and track @ Discogs.")
                        return None
                else:
                    self.log(f"Discogs API request failed: {response.status} - {response.reason}")
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
        self.fail_txt = False
        self.fallback = False

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
            self.log(f"looking for {self.ai_artist} {self.ai_title}")

            """ Fallback begins """
            # Try Spotify
            if self.spotify_client_id and self.spotify_client_secret:
                self.log("Trying to find album art @ Spotify")
                try:
                    album_id = await self.get_spotify_album_id(self.ai_artist, self.ai_title)
                    if album_id:
                        image_url = await self.get_spotify_album_image_url(album_id)
                        if image_url:
                            result = await self.process_picture(image_url)
                            if result:
                                self.log("Successfully processed the Album Art @ Spotify")
                                return result
                        else:
                            self.log("Failed to process Spotify image")
                except Exception as e:
                    self.log(f"Spotify fallback failed with error: {str(e)}")

            # Try Discogs:
            if self.discogs:
                self.log("Trying to find album art @ Discogs")
                try:
                    album_art = await self.search_discogs_album_art()
                    if album_art:
                        result = await self.process_picture(album_art)
                        if result:
                            self.log("Successfully processed the Album Art @ Discogs")
                            return result
                        else:
                            self.log("Failed to process Discogs image")
                except Exception as e:
                    self.log(f"Discogs fallback failed with error: {str(e)}")

            # Try Last.fm:
            if self.lastfm:
                self.log("Trying to find album art @ Last.fm")
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

            # Try Defult Spotify Album
            if self.spotify_defualt_album:
                try:
                    image_url = await self.get_spotify_album_image_url(self.spotify_defualt_album)
                    result = await self.process_picture(image_url)
                    if result:
                        self.log("Sending Spotify defualt image")
                        return result
                except Exception as e:
                    self.log("Faild to load Spotify defualt image")

            # Try MusicBrainz
            if self.musicbrainz:
                self.log("Trying to find album art @ MusicBrainz")
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
                self.log("Trying to Generate AI album art")
                ai_url = self.format_ai_image_prompt(self.ai_artist, self.ai_title)
                self.fail_txt = False
                self.fallback = False
                result = await self.process_picture(ai_url)
                if result:
                    self.log("Successfully Generated AI Image")
                    return result
            except Exception as e:
                self.log(f"AI generation failed: {e}")


        # Ultimate fallback
        default_values = self.reset_img_values()
        self.fail_txt = True
        self.fallback = True
        gif_base64 = self.gbase64(self.create_black_screen())
        self.log("Ultimate fallback")
        return gif_base64, *default_values


    def ensure_rgb(self, img):
        try:
            if img and img.mode != "RGB":
                img = img.convert("RGB")
            return img
        except Exception as e:
            self.log(f"Error converting image to RGB: {e}", level="ERROR")
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
        temp_img = img
        
        if self.crop_extra:
            img = img.filter(ImageFilter.BoxBlur(5))
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.95)

        try:
            width, height = img.size

            # More robust border detection (less sensitive to noise)
            border_color = self.get_dominant_border_color(img)

            # Create a mask to identify the non-border region
            mask = Image.new("L", img.size, 0)
            for x in range(width):
                for y in range(height):
                    if img.getpixel((x, y)) != border_color:
                        mask.putpixel((x, y), 255)

            bbox = mask.getbbox()
            if bbox:
                # Calculate center
                center_x = (bbox[0] + bbox[2]) // 2
                center_y = (bbox[1] + bbox[3]) // 2

                # Crop size (at least 64x64)
                crop_size = min(bbox[2] - bbox[0], bbox[3] - bbox[1])
                crop_size = max(crop_size, 64)  # Ensure minimum size
                half_crop_size = crop_size // 2

                # Correctly calculate crop boundaries
                left = max(0, center_x - half_crop_size)
                top = max(0, center_y - half_crop_size)
                right = min(width, center_x + half_crop_size)
                bottom = min(height, center_y + half_crop_size)

                # Adjust the crop to ensure no borders
                if left < 0:
                    right -= left
                    left = 0
                if right > width:
                    left -= (right - width)
                    right = width
                if top < 0:
                    bottom -= top
                    top = 0
                if bottom > height:
                    top -= (bottom - height)
                    bottom = height

                img = temp_img.crop((left, top, right, bottom))
            else:
                # Handle cases where no non-border pixels are found
                img = temp_img.crop((0, 0, 64, 64))  # Crop to a default square

        except Exception as e:
            self.log(f"Failed to crop image: {e}", level="ERROR")
            img = temp_img

        return img


    def get_dominant_border_color(self, img):
        width, height = img.size
        top_row = img.crop((0,0,width,1))
        bottom_row = img.crop((0, height-1, width,height))
        left_col = img.crop((0,0,1,height))
        right_col = img.crop((width-1, 0,width, height))

        all_border_pixels = []
        all_border_pixels.extend(top_row.getdata())
        all_border_pixels.extend(bottom_row.getdata())
        all_border_pixels.extend(left_col.getdata())
        all_border_pixels.extend(right_col.getdata())

        return max(set(all_border_pixels), key=all_border_pixels.count) if all_border_pixels else (0,0,0)


    def text_clock_img(self, img, brightness_lower_part):
        if self.spotify_slide:
            return img
        
        # Check if there are no lyrics before proceeding
        if self.show_lyrics and self.lyrics != [] and self.media_position_updated_at != None and self.text_bg:
            enhancer_lp = ImageEnhance.Brightness(img)
            img = enhancer_lp.enhance(0.55) #self.brightness_full) 
            return img

        if self.text_bg and self.show_text and not self.show_lyrics:
            lpc = (0,48,64,64)
            lower_part_img = img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(brightness_lower_part)
            img.paste(lower_part_img, lpc)

        if self.show_clock and not self.show_lyrics:
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
            self.fallback = False
            self.fail_text = False
            return gif_base64
            

        except Exception as e:
            self.fail_txt = True
            self.fallback = True
            return None

    def create_black_screen(self):
        """Creates a zlib-compressed black screen image."""
        img = Image.new("RGB", (64, 64), (0, 0, 0))  # Create a black image
        buffer = BytesIO()
        img.save(buffer, format="PNG")  # Save as PNG (or another suitable format)
        #compressed_data = zlib.compress(buffer.getvalue())
        return img


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

    async def calculate_position(self, kwargs):
        media_state = await self.get_state(self.media_player)  # Get the current state of the media player
        if media_state not in ["playing", "on"]:  # Check if the media player is playing
            return  # Exit the function if not playing

        self.media_position = await self.get_state(self.media_player, attribute="media_position", default=0)
        self.media_position_updated_at = await self.get_state(self.media_player, attribute="media_position_updated_at", default=None)
        self.media_duration = await self.get_state(self.media_player, attribute="media_duration", default=0)
        if self.media_position_updated_at:
            media_position_updated_at = datetime.fromisoformat(self.media_position_updated_at.replace('Z', '+00:00'))
            current_time = datetime.now(timezone.utc)
            time_diff = (current_time - media_position_updated_at).total_seconds()
            current_position = self.media_position + time_diff
            current_position = min(current_position, self.media_duration)
            self.track_position = int(current_position)
            current_position = self.track_position
            if current_position is not None and self.lyrics and self.show_lyrics:
                for i, lyric in enumerate(self.lyrics):
                    lyric_time = lyric['seconds']
                    
                    if int(current_position) == lyric_time - 1:
                        await self.create_lyrics_payloads(lyric['lyrics'], 10)
                        next_lyric_time = self.lyrics[i + 1]['seconds'] if i + 1 < len(self.lyrics) else None
                        lyrics_diplay = (next_lyric_time - lyric_time) if next_lyric_time else lyric_time + 10
                        if lyrics_diplay > 9:
                            await asyncio.sleep(8)
                            await self.send_pixoo({"Command": "Draw/ClearHttpText"})
                        break


    async def get_lyrics(self, artist, title):
        """Fetch lyrics for the given artist and title."""
        # Use HTTP instead of HTTPS
        lyrics_url = f"http://api.textyl.co/api/lyrics?q={artist} - {title}"
        try:
            # Create a session with SSL verification disabled
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(lyrics_url) as response:
                    if response.status == 200:
                        lyrics_data = await response.json()
                        # Store the lyrics and seconds in a list of dictionaries
                        self.lyrics = [{'seconds': line['seconds'], 'lyrics': line['lyrics']} for line in lyrics_data]
                        self.log(f"Retrieved lyrics for {artist} - {title}")
                    else:
                        self.log(f"Failed to fetch lyrics: {response.status}")
                        self.lyrics = []  # Reset lyrics if fetching fails
        except Exception as e:
            self.log(f"Error fetching lyrics: {str(e)}")
            self.lyrics = []  # Reset lyrics on error

    async def create_lyrics_payloads(self, lyrics, x):
        # Split the lyrics into lines based on the max character limit
        
        all_lines = self.split_string(self.get_display(lyrics) if lyrics and self.has_bidi(lyrics) else lyrics, x)
        if len(all_lines) > 4:
            all_lines[4] += ' ' + ' '.join(all_lines[5:])
            all_lines = all_lines[:5]
        
        start_y = (64 - len(all_lines) * 11) // 2
        payloads = [
            {
                "Command": "Draw/SendHttpText",
                "TextId": i + 1,  # Unique TextId for each line
                "x": 0,
                "y": start_y + (i * 11),  # Adjust y position for each line
                "dir": 0,
                "font": self.font,
                "TextWidth": 64,
                "speed": 80,
                "TextString": line,
                "color": self.lyrics_font_color,
                "align": 2
            }
            for i, line in enumerate(all_lines)
        ]
        # Clear text command 
        clear_text_command = {"Command": "Draw/ClearHttpText"}
        full_command_list = [clear_text_command] + payloads
        payload = {"Command": "Draw/CommandList", "CommandList": full_command_list}
        await self.send_pixoo(payload)


    def get_optimal_font_color(self, img):
        """Determine a colorful, readable font color that avoids all colors in the image palette and maximizes distinctiveness."""

        # Resize for faster processing
        small_img = img.resize((16, 16), Image.Resampling.LANCZOS)

        # Get all unique colors in the image (palette)
        image_palette = set(small_img.getdata())

        # Calculate luminance to analyze image brightness
        def luminance(color):
            r, g, b = color
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        # Calculate average brightness of the image palette
        avg_brightness = sum(luminance(color) for color in image_palette) / len(image_palette)

        # Define the contrast ratio calculation
        def contrast_ratio(color1, color2):
            L1 = luminance(color1) + 0.05
            L2 = luminance(color2) + 0.05
            return max(L1, L2) / min(L1, L2)

        # Check if the color is sufficiently distinct from all colors in the image
        def is_distinct_color(color, threshold=50):
            return all(math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color, img_color))) > threshold for img_color in image_palette)

        # Define a set of colorful candidate colors
        candidate_colors = [
            (255, 99, 71), (218, 112, 214), (72, 61, 139), (255, 165, 0), (50, 205, 50),
            (30, 144, 255), (255, 140, 0), (173, 255, 47), (106, 90, 205), (255, 69, 0),
            (123, 104, 238), (210, 105, 30), (0, 255, 255), (255, 105, 180), (0, 191, 255),
            (138, 43, 226), (255, 20, 147), (127, 255, 0), (255, 215, 0), (70, 130, 180),
            (189, 183, 107), (176, 196, 222), (219, 112, 147), (100, 149, 237), (144, 238, 144),
            (173, 216, 230), (250, 128, 114), (46, 139, 87), (147, 112, 219), (233, 150, 122),
            (139, 69, 19), (240, 128, 128), (245, 222, 179), (0, 128, 128), (255, 99, 71),
            (255, 160, 122), (255, 228, 181), (0, 250, 154), (153, 50, 204), (107, 142, 35),
            (222, 184, 135), (233, 150, 122), (255, 182, 193), (127, 255, 212), (255, 218, 185),
            (32, 178, 170), (238, 130, 238), (0, 255, 127), (245, 245, 220), (95, 158, 160),
            (173, 255, 47), (176, 224, 230), (199, 21, 133), (255, 127, 80), (186, 85, 211),
            (238, 232, 170), (250, 250, 210), (255, 222, 173), (255, 239, 213), (245, 255, 250),
            (0, 206, 209), (175, 238, 238), (255, 228, 225), (238, 221, 130), (255, 228, 196),
            (144, 238, 144), (210, 180, 140), (176, 196, 222), (240, 248, 255), (135, 206, 235),
            (255, 69, 0), (127, 255, 0), (255, 140, 0), (255, 105, 180), (100, 149, 237),
            (139, 0, 139), (255, 20, 147), (255, 99, 71), (218, 112, 214), (123, 104, 238),
            (34, 139, 34), (255, 215, 0), (32, 178, 170), (152, 251, 152), (0, 0, 255),
            (255, 69, 0), (0, 128, 0), (173, 255, 47), (139, 69, 19), (0, 191, 255),
            (240, 230, 140), (176, 224, 230), (245, 245, 220), (32, 178, 170), (255, 0, 255),
            (255, 140, 0), (199, 21, 133), (250, 128, 114), (0, 250, 154), (123, 104, 238),
            (255, 228, 196), (255, 182, 193), (250, 250, 210), (255, 218, 185), (255, 222, 173)
        ]

        random.shuffle(candidate_colors)
        best_color = None
        max_saturation = -1  # Initialize to a negative value

        # Check each candidate color against the image palette
        for font_color in candidate_colors:
            if is_distinct_color(font_color, threshold=100):
                # Calculate the saturation of the candidate color
                r, g, b = font_color
                max_val = max(r, g, b)
                min_val = min(r, g, b)
                saturation = (max_val - min_val) / max_val if max_val != 0 else 0

                # Ensure contrast with image brightness
                contrast_with_white = contrast_ratio(font_color, (255, 255, 255))
                contrast_with_black = contrast_ratio(font_color, (0, 0, 0))
                if (avg_brightness < 127 and contrast_with_white >= 3) or (avg_brightness >= 127 and contrast_with_black >= 3):
                    # Update best color if this candidate has a higher saturation
                    if saturation > max_saturation:
                        max_saturation = saturation
                        best_color = font_color

        # If a best color was found, return it
        if best_color:
            return '#%02x%02x%02x' % best_color

        # Fallback if no suitable color is found
        return '#000000' if avg_brightness > 127 else '#ffffff'

    def clear_cache(self, kwargs):
        self.image_cache.clear()
        self.log("Image cache cleared.")



    """ Spotify Album Art Slide """
    async def get_album_list(self):
        """Retrieves album art URLs, filtering and prioritizing albums."""
        if not self.spotify_data:
            return []

        try:
            if not isinstance(self.spotify_data, dict):
                self.log("Unexpected Spotify data format.  Expected a dictionary.")
                return []

            tracks = self.spotify_data.get('tracks', {}).get('items', [])
            albums = {}  # Use a dictionary to store albums for easier filtering and sorting
            for track in tracks:
                album = track.get('album', {})
                album_id = album.get('id')
                artists = album.get('artists', [])
                
                #Check for 'Various Artists' and skip
                if any(artist.get('name', '').lower() == 'various artists' for artist in artists):
                    continue
                
                #Check if artist name matches
                if self.ai_artist.lower() not in [artist.get('name', '').lower() for artist in artists]:
                    continue
                
                if album_id not in albums:
                    albums[album_id] = album

            #Prioritize singles, EPs, Albums, Live Albums, Compilations
            sorted_albums = sorted(albums.values(), key=lambda x: (
                x.get("album_type") == "single",  #Singles first
                x.get("album_type") == "ep",    #EPs second
                x.get("album_type") == "album",  #Albums third
                x.get("album_type") == "livealbum", #Live albums fourth (If supported)
                x.get("album_type") == "compilation" #Compilations last
            ))


            album_urls = []
            album_base64 = []
            for album in sorted_albums:
                images = album.get("images", [])
                if images:
                    #album_urls.append(images[0]["url"])
                    base64_data = await self.get_slide_img(images[0]["url"])
                    album_base64.append(base64_data)
            return album_base64


        except (KeyError, IndexError, TypeError, AttributeError) as e:
            self.log(f"Error processing Spotify data: {e}")
            return []



    async def get_slide_img(self, picture):
        """Fetches, processes, and returns base64-encoded image data."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(picture) as response:
                    if response.status != 200:
                        self.log(f"Error fetching image {picture}: {response.status}")
                        return None

                    image_data = await response.read()

        except Exception as e:
            self.log(f"Error processing image {picture}: {e}")
            return None
        
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
                    
                if self.contrast:
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(1.5)
                    
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
                return self.gbase64(img)
        except Exception as e:
                return None

    async def send_pixoo_animation_frame(self, command, pic_num, pic_width, pic_offset, pic_id, pic_speed, pic_data):
        """Sends a single frame of an animation to the Pixoo device."""
        payload = {
        "Command": command,
        "PicNum": pic_num,
        "PicWidth": pic_width,
        "PicOffset": pic_offset,
        "PicID": pic_id,
        "PicSpeed": pic_speed,
        "PicData": pic_data
        }
        # Send the payload to the Pixoo device (assuming you have a send_payload method)
        response = await self.send_payload(payload)
        return response

    async def spotify_albums_slide(self):
        """Fetches and processes images, printing base64 data."""
        self.spotify_slide_pass = True
        album_urls = await self.get_album_list()
        if not album_urls:
            self.log("No albums found for slide")
            
            self.spotify_slide_pass = False
            #await self.send_payload({"Command":"Draw/ResetHttpGifId"})
            await self.send_payload({"Command": "Channel/SetIndex", "SelectIndex": 4})
            return

        frames = len(album_urls)
        if frames < 2:
            self.spotify_slide_pass = False
            #await self.send_payload({"Command":"Draw/ResetHttpGifId"})
            await self.send_payload({"Command": "Channel/SetIndex", "SelectIndex": 4})
            return

        self.log(f"Creating album slide from spotify with {frames} frames for {self.ai_artist}")
        pic_offset = 0
        await self.send_payload({"Command":"Draw/ResetHttpGifId"})
        for album_url in album_urls:
            try:
                if album_url:
                    pic_speed = 5000  # Example speed, adjust as needed
                    await self.send_pixoo_animation_frame(
                    command="Draw/SendHttpGif",
                    pic_num=frames,
                    pic_width=64,
                    pic_offset=pic_offset,
                    pic_id=1,
                    pic_speed=pic_speed,
                    pic_data=album_url
                    )

                # Increment pic_id for the next animation frame
                    pic_offset += 1
                else:
                    print(f"Failed to process image: {album_url}")
                    break

            except Exception as e:
                print(f"Error processing image {album_url}: {e}")
                break

    async def send_payload(self, payload_command):
        """Send command to Pixoo device"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, headers=self.headers, json=payload_command, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        self.log(f"Failed to send REST: {response.status}")
                    else:
                        pass
        except Exception as e:
            self.log(f"Error sending command to Pixoo: {str(e)}\n{traceback.format_exc()}")


