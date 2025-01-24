"""
Divoom Pixoo64 Album Art Display
--------------------------------
This script automatically displays the album art of the currently playing track on your Divoom Pixoo64 screen.
Additionally, this script supports AI-based image creation. It is designed to generate and display alternative album cover art when the original art is unavailable or when using music services (like SoundCloud) from which the script cannot retrieve album art.

APPDAEMON CONFIGURATION
# Required python packages (pillow is mandatory while python-bidi is opotinal and used to display RTL texts like Arabic or Hebrew exc,):
python_packages:
    - pillow
    - python-bidi

# appdaemon/apps/apps.yaml
-----
# Basic Configuration
# -------------------
pixoo64_media_album_art:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    home_assistant:
        ha_url: "http://homeassistant.local:8123"   # Your Home Assistant URL.
        media_player: "media_player.living_room"    # The entity ID of your media player.
    pixoo:
        url: "192.168.86.21"                        # The IP address of your Pixoo64 device.


# Full Configuration
# ------------------
pixoo64_media_album_art:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    home_assistant:
        ha_url: "http://homeassistant.local:8123"   # Your Home Assistant URL.
        media_player: "media_player.era300"         # The entity ID of your media player.
        toggle: "input_boolean.pixoo64_album_art"   # An input boolean to enable or disable the script's execution.
        pixoo_sensor: "sensor.pixoo64_media_data"   # A sensor to store extracted media data.
        temperature_sensor: "sensor.temperature"    # HomeAssistant Temperature sensor name instead of the Divoom weather.
        light: "light.living_room"                  # The entity ID of an RGB light to synchronize with the album art colors.
        ai_fallback: "turbo"                        # The AI model to use for generating alternative album art when needed (supports 'flux' or 'turbo').
        force_ai: False                             # If True, only AI-generated images will be displayed all the time.
        musicbrainz: True                           # If True, attempts to find a fallback image on MusicBrainz if other sources fail.
        spotify_client_id: False                    # Your Spotify API client ID (needed for Spotify features). Obtain from https://developers.spotify.com.
        spotify_client_secret: False                # Your Spotify API client secret (needed for Spotify features).
        tidal_client_id: False                      # Your TIDAL API client ID. Obrain from https://developer.tidal.com/dashboard.
        tidal_client_secret: False                  # Your TIDAL client secret.
        last.fm: False                              # Your Last.fm API key. Obtain from https://www.last.fm/api/account/create.
        discogs: False                              # Your Discogs API key. Obtain from https://www.discogs.com/settings/developers.
    pixoo:
        url: "192.168.86.21"                        # The IP address of your Pixoo64 device.
        full_control: True                          # If True, the script will control the Pixoo64's on/off state in sync with the media player's play/pause.
        contrast: True                              # If True, applies a 50% contrast filter to the images displayed on the Pixoo.
        sharpness: False                            # If True, add sharpness effect.
        colors: False                               # If True, enhanced colors.
        kernel: False                               # If True, add embos/edge effect.
        special_mode: False                         # Show day, time and temperature above in upper bar.
        info: False                                 # Show information while fallback.
        clock: True                                 # If True, a clock is displayed in the top corner of the screen.
        clock_align: "Right"                        # Clock alignment: "Left" or "Right".
        tv_icon: True                               # If True, displays a TV icon when audio is playing from a TV source.
        lyrics: False                               # If True, attempts to display lyrics on the Pixoo64 (show_text and clock will be disabled).
        lyrics_font: 2                              # Recommend values: 2, 4, 32, 52, 58, 62, 48, 80, 158, 186, 190, 590. More values can be found at https://app.divoom-gz.com/Device/GetTimeDialFontList (you need ID value)
        limit_colors: False                         # Reduces the number of colors in the picture from 4 to 256, or set it to False for original colors.
        spotify_slide: False                        # If True, forces an album art slide (requires a Spotify client ID and secret). Note: clock and title will be disabled in this mode.
        images_cache: 25                            # The number of processed images to keep in the memory cache. Use wisely to avoid memory issues (each image is approximately 17KB).
        show_text:
            enabled: False                          # If True, displays the artist and title of the current track.
            clean_title: True                       # If True, removes "Remastered," track numbers, and file extensions from the title.
            text_background: True                   # If True, adjusts the background color behind the text for improved visibility.
            special_mode_spotify_slider: False      # Create animation album art slider
        crop_borders:
            enabled: True                           # If True, attempts to crop any borders from the album art.
            extra: True                             # If True, applies an enhanced border cropping algorithm.
    wled:
        wled_ip: "192.168.86.55"                    # Your WLED IP Adress
        brightness: 255                             # 0 to 255
        effect: 38                                  # 0 to 186 (Effect ID - https://kno.wled.ge/features/effects/)
        effect_speed: 50                            # 0 to 255
        effect_intensity: 128                       # 0 to 255
        pallete: 0                                  # 0 to 70 (Pallete ID - https://kno.wled.ge/features/palettes/)
        sound_effect: 0                             # Setting of the sound simulation type for audio enhanced effects (0: 'BeatSin', 1: 'WeWillRockYou', 2: '10_3', 3: '14_3')
        only_at_night: False                        # Runs only at night hours
"""
import aiohttp
import asyncio
import base64
import json
import logging
import math
import os
import random
import re
import sys
import time
import traceback
from appdaemon.plugins.hass import hassapi as hass
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time as dt_time, timezone
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

# Third-party library imports
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw

try:
    from bidi import get_display
    bidi_support = True
except ImportError:
    bidi_support = False
    print("The 'bidi.algorithm' module is not installed or not available. RTL texts will display reverce")

# Configure the logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
_LOGGER = logging.getLogger(__name__)

# Constants
AI_ENGINE = "https://pollinations.ai/p"
LOCAL_DIRECTORY = "/homeassistant/www/pixoo64/"


# Regex patterns for RTL text detection
HEBREW = r"\u0590-\u05FF"
ARABIC = r"\u0600-\u06FF|\u0750-\u077F|\u08A0-\u08FF|\uFB50-\uFDFF|\uFE70-\uFEFF|\u0621-\u06FF"
SYRIAC = r"\u0700-\u074F"
THAANA = r"\u0780-\u07BF"
NKOO = r"\u07C0-\u07FF"
RUMI = r"\U00010E60-\U00010E7F"
ARABIC_MATH = r"\U0001EE00-\U0001EEFF"
SYMBOLS = r"\U0001F110-\U0001F5FF"
OLD_PERSIAN_PHAISTOS = r"\U00010F00-\U00010FFF"
SAMARITAN = r"\u0800-\u08FF"
BIDI_MARKS = r"\u200E|\u200F"

# Helpers
def split_string(text, length):
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

def img_adptive(img, x):
    colors = x
    colors = False if colors > 256 else colors
    colors = 4 if colors < 5 else colors
    if colors:
        try:
            img = img.convert('P', palette=Image.ADAPTIVE, colors=colors).convert('RGB')
        except:
            pass
    return img

def format_memory_size(size_in_bytes):
    """Formats memory size in bytes to KB or MB as appropriate."""
    if size_in_bytes < 1024 * 1024:  # Less than 1 MB
        return f"{size_in_bytes / 1024:.2f} KB"
    else:
        return f"{size_in_bytes / (1024 * 1024):.2f} MB"

def get_bidi(text):
    """Convert text for display, handling RTL languages"""
    if not bidi_support:
        _LOGGER.error(f"To display RTL text you need to add bidi-algorithm package: {e}.")
        return text
    else:
        return get_display(text)

def has_bidi(text):
    """Check if text contains bidirectional characters"""
    bidi_regex = f"[{HEBREW}|{ARABIC}|{SYRIAC}|{THAANA}|{NKOO}|{RUMI}|{ARABIC_MATH}|{SYMBOLS}|{OLD_PERSIAN_PHAISTOS}|{SAMARITAN}]"
    return bool(re.search(bidi_regex, text))

def ensure_rgb(img):
    try:
        if img and img.mode != "RGB":
            img = img.convert("RGB")
        return img
    except Exception as e:
        _LOGGER.error(f"Error converting image to RGB: {e}")
        return None


class Config:
    def __init__(self, app_args):
        ha_config = app_args.get('home_assistant', {})
        wled_light = app_args.get('wled', {})
        pixoo_config = app_args.get('pixoo', {})
        show_text_config = pixoo_config.get('show_text', {})
        crop_borders_config = pixoo_config.get('crop_borders', {})
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Connection": "keep-alive",
            "User-Agent": "PixooClient/1.0"
        }

        # Home Assistant settings
        self.media_player: str = ha_config.get("media_player", "media_player.living_room")
        self.toggle: str = ha_config.get("toggle", "input_boolean.pixoo64_album_art")
        self.ha_url: str = ha_config.get("ha_url", "http://homeassistant.local:8123")
        self.pixoo_sensor: str = ha_config.get("pixoo_sensor", "sensor.pixoo64_media_data")
        self.ha_temperature: str = ha_config.get("temperature_sensor", None)
        self.light: str = ha_config.get("light", None)
        self.force_ai: bool = ha_config.get("force_ai", False)

        # AI and Fallback services settings
        self.ai_fallback: str = ha_config.get("ai_fallback", 'flux')
        self.musicbrainz: bool = ha_config.get("musicbrainz", True)
        self.spotify_client_id: str = ha_config.get("spotify_client_id", False)
        self.spotify_client_secret: str = ha_config.get("spotify_client_secret", False)
        self.tidal_client_id: str = ha_config.get("tidal_client_id", False)
        self.tidal_client_secret: str = ha_config.get("tidal_client_secret", False)
        self.discogs: str = ha_config.get("discogs", False)
        self.lastfm: str = ha_config.get("last.fm", False)

        # Pixoo device settings
        pixoo_url: str = pixoo_config.get("url", "192.168.86.21")
        self.full_control: bool = pixoo_config.get("full_control", True)
        self.contrast: bool = pixoo_config.get("contrast", False)
        self.sharpness: bool = pixoo_config.get("sharpness", False)
        self.colors: bool = pixoo_config.get("colors", False)
        self.kernel: bool = pixoo_config.get("kernel", False)

        self.special_mode: bool = pixoo_config.get("special_mode", False)
        self.info: bool = pixoo_config.get("info", False)
        self.show_clock: bool = pixoo_config.get("clock", False)
        self.clock_align: str = pixoo_config.get("clock_align", "Left")
        self.temperature: bool = pixoo_config.get("temperature", False)
        self.tv_icon_pic: bool = pixoo_config.get("tv_icon", True)
        self.spotify_slide: bool = pixoo_config.get("spotify_slide", False)
        self.images_cache: int = max(1, min(int(pixoo_config.get("images_cache", 10)), 100))

        # Text display settings
        self.limit_color: bool = pixoo_config.get("limit_colors", False)
        self.show_lyrics: bool = pixoo_config.get("lyrics", False)
        self.lyrics_font: int = pixoo_config.get("lyrics_font", 190)
        self.show_text: bool = show_text_config.get("enabled", False)
        self.clean_title_enabled: bool = show_text_config.get("clean_title", True)
        self.text_bg: bool = show_text_config.get("text_background", True)
        self.special_mode_spotify_slider: bool = show_text_config.get("special_mode_spotify_slider", False)

        # Image processing settings
        self.crop_borders: bool = crop_borders_config.get("enabled", True)
        self.crop_extra: bool = crop_borders_config.get("extra", True)

        # WLED Settings
        self.wled: str = wled_light.get("wled_ip", None)
        self.wled_brightness: int = wled_light.get("brightness", 255)
        self.wled_effect: int = wled_light.get("effect", 38)
        self.wled_effect_speed:  int = wled_light.get("effect_speed", 60)
        self.wled_effect_intensity: int = wled_light.get("effect_intensity", 128)
        self.wled_only_at_night: bool = wled_light.get("only_at_night", False)
        self.wled_pallete: int = wled_light.get("pallete", 0)
        self.wled_sound_effect: int = max(0, min(int(wled_light.get("sound_effect", 0)), 3))

        # Fixing args if needed
        pixoo_url = f"http://{pixoo_url}" if not pixoo_url.startswith('http') else pixoo_url
        self.pixoo_url: str = f"{pixoo_url}:80/post" if not pixoo_url.endswith(':80/post') else pixoo_url

        if self.ai_fallback not in ["flux", "turbo"]:
            self.ai_fallback = "turbo"


class PixooDevice:
    def __init__(self, config):
        self.config = config
        self.select_index = None
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Connection": "keep-alive",
            "User-Agent": "PixooClient/1.0"
        }


    async def send_command(self, payload_command):
        """Send command to Pixoo device"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.config.pixoo_url, headers=self.headers, json=payload_command, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Failed to send REST: {response.status}")
                    else:
                        await asyncio.sleep(0.20)
        except Exception as e:
            _LOGGER.error(f"Error sending command to Pixoo: {str(e)}") #\n{traceback.format_exc()}")

    async def get_current_channel_index(self):
        channel_command = {
            "Command": "Channel/GetIndex"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.pixoo_url,
                    headers=self.headers,
                    json=channel_command,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    response_text = await response.text()
                    response_data = json.loads(response_text)
                    return response_data.get('SelectIndex', 1)
        except Exception as e:
            _LOGGER.error(f"Failed to get channel index from Pixoo: {str(e)}")
            return 1  # Default fallback value


class ImageProcessor:
    def __init__(self, config):
        self.config = config
        self.image_cache = OrderedDict()
        self.cache_size = config.images_cache # Number of images in cache
        self.lyrics_font_color = "#FF00AA"

    @property
    def _cache_size(self):
        """Helper property to get current cache size"""
        return len(self.image_cache)
    
    def _calculate_item_size(self, item):
        """Calculates the approximate memory size of a single cache item."""
        size = 0

        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, str):
                    size += sys.getsizeof(value)
                elif isinstance(value, (int, float, bool)):
                    size += sys.getsizeof(value)
                elif isinstance(value, tuple):
                    size += sys.getsizeof(value)  # Account for tuples
                elif isinstance(value, list):
                    for list_item in value:
                        size += sys.getsizeof(list_item) # Account for lists
        return size

    def _calculate_cache_memory_size(self):
        """Calculates the total approximate memory size of the cache in bytes."""
        total_size = 0
        for item in self.image_cache.values():
            total_size += self._calculate_item_size(item)
        return total_size


    async def get_image(self, picture, media_data, spotify_slide=False):
        if not picture:
            return None
        
        cache_key = media_data.album
        if not cache_key: #If the album name is None, do not use the cache.
            try:
                async with aiohttp.ClientSession() as session:
                    url = picture if picture.startswith('http') else f"{self.config.ha_url}{picture}"
                    async with session.get(url) as response:
                        if response.status != 200:
                            return None

                        image_data = await response.read()
                        processed_data = await self.process_image_data(image_data, media_data)  # Process image *before* caching
                        return processed_data
            except Exception as e:
                _LOGGER.error(f"Error in get_image: {str(e)}\n{traceback.format_exc()}")
                return None

        # Check cache; if found, return directly with all data.
        if cache_key in self.image_cache and not spotify_slide and not media_data.playing_tv:
            _LOGGER.info("Image found in cache")
            cached_item = self.image_cache.pop(cache_key)
            self.image_cache[cache_key] = cached_item  # Re-add to maintain LRU order
            return cached_item
        
        try:
            async with aiohttp.ClientSession() as session:
                url = picture if picture.startswith('http') else f"{self.config.ha_url}{picture}"
                async with session.get(url) as response:
                    if response.status != 200:
                        return None

                    image_data = await response.read()
                    processed_data = await self.process_image_data(image_data, media_data)  # Process image *before* caching
                    if processed_data and not spotify_slide:
                        if len(self.image_cache) >= self.cache_size:
                            self.image_cache.popitem(last=False)
                        self.image_cache[cache_key] = processed_data  # Store all processed data in cache
                        memory_size = self._calculate_cache_memory_size()
                        media_data.image_cache_memory = format_memory_size(memory_size)
                        media_data.image_cache_count = self._cache_size
                    return processed_data
        except Exception as e:
            _LOGGER.error(f"Error in get_image: {str(e)}\n{traceback.format_exc()}")
            return None


    async def process_image_data(self, image_data, media_data):
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor,
                self._process_image,
                image_data,
                media_data
            )
        return result

    def _process_image(self, image_data, media_data):
        try:
            with Image.open(BytesIO(image_data)) as img:
                img = ensure_rgb(img)
                img = self.fixed_size(img)

                if (self.config.crop_borders or self.config.special_mode) and not media_data.radio_logo:
                    img = self.crop_image_borders(img, media_data.radio_logo)

                if self.config.contrast or self.config.sharpness or self.config.colors or self.config.kernel or self.config.limit_color:
                    img = self.filter_image(img)

                img = self.special_mode(img) if self.config.special_mode else img.resize((64, 64), Image.Resampling.LANCZOS)
                font_color, brightness, brightness_lower_part, background_color, background_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative, color1, color2, color3 = self.img_values(img)
                
                media_data.lyrics_font_color = self.get_optimal_font_color(img) if self.config.show_lyrics or self.config.info else "#FFA000"
                media_data.color1 = color1
                media_data.color2 = color2
                media_data.color3 = color3
                img = self.text_clock_img(img, brightness_lower_part, media_data) if not self.config.special_mode else img 
                base64_image = self.gbase64(img)

                if self.config.info:
                    lpc = (0, 10, 64, 30)
                    lower_part_img = img.crop(lpc)
                    enhancer_lp = ImageEnhance.Brightness(lower_part_img)
                    lower_part_img = enhancer_lp.enhance(0.4)
                    img.paste(lower_part_img, lpc)
                    media_data.info_img = self.gbase64(img)

                return {
                    'base64_image': base64_image,
                    'font_color': font_color,
                    'brightness': brightness,
                    'brightness_lower_part': brightness_lower_part,
                    'background_color': background_color,
                    'background_color_rgb': background_color_rgb,
                    'most_common_color_alternative_rgb': most_common_color_alternative_rgb,
                    'most_common_color_alternative': most_common_color_alternative,
                    'color1': color1,
                    'color2': color2,
                    'color3': color3
                }

        except Exception as e:
            _LOGGER.error(f"Error processing image: {str(e)}")
            return None

    def fixed_size(self, img):
        # Ensure the image is square
        width, height = img.size
        if width == height:
            return img
        elif height < width:  # Check if height is less than width
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
        return img 

    def filter_image(self, img):
        img = img.resize((64, 64), Image.Resampling.LANCZOS)
        if self.config.limit_color:
            colors = int(self.config.limit_color)
            img = img_adptive(img, colors)

        if self.config.sharpness:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(4.0)

        if self.config.contrast:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)

        if self.config.colors:
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(1.5)

        if self.config.kernel:
            kernel_5x5 = [-2,  0, -1,  0,  0,
                        0, -2, -1,  0,  0,
                        -1, -1,  1,  1,  1,
                        0,  0,  1,  2,  0,
                        0,  0,  1,  0,  2]

            img = img.filter(ImageFilter.Kernel((5, 5), kernel_5x5, 1, 0))
        
        return img

    def special_mode(self, img):
        if img is None:
            _LOGGER.error("Error: Provided image is None.")
            return None
        
        output_size = (64, 64)
        album_size = (34, 34) if self.config.show_text else (56, 56)
        album_art = img.resize(album_size, Image.Resampling.LANCZOS)

        # Get the colors for the gradient
        left_color = album_art.getpixel((0, album_size[1] // 2))
        right_color = album_art.getpixel((album_size[0] - 1, album_size[1] // 2))
                    
        # Select a darker color for the background
        dark_background_color = (
        min(left_color[0], right_color[0]) // 2,
        min(left_color[1], right_color[1]) // 2,
        min(left_color[2], right_color[2]) // 2
        )
        if album_size == (34, 34):
            dark_background_color = (0, 0, 0)
        background = Image.new('RGB', output_size, dark_background_color)

        x = (output_size[0] - album_size[0]) // 2
        y = 8  # Top padding

        if album_size == (34, 34):
            # Create the gradient on the left side, within 32 pixels height
            for i in range(x):
                gradient_color = (
                    int(left_color[0] * (x - i) / x),
                    int(left_color[1] * (x - i) / x),
                    int(left_color[2] * (x - i) / x)
                )
                for j in range(y, y + album_size[1]):
                    background.putpixel((i, j), gradient_color)

            # Create the gradient on the right side, within 32 pixels height
            for i in range(x + album_size[0], output_size[0]):
                gradient_color = (
                    int(right_color[0] * (i - (x + album_size[0])) / (output_size[0] - (x + album_size[0]))),
                    int(right_color[1] * (i - (x + album_size[0])) / (output_size[0] - (x + album_size[0]))),
                    int(right_color[2] * (i - (x + album_size[0])) / (output_size[0] - (x + album_size[0])))
                )
                for j in range(y, y + album_size[1]):
                    background.putpixel((i, j), gradient_color)

        # Paste the album art on the background
        background.paste(album_art, (x, y))

        return background


    def crop_image_borders(self, img, radio_logo):
        if radio_logo:
            return img

        temp_img = img

        if self.config.crop_extra or (self.config.special_mode): # Force extra crop if special_mode is true
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
            _LOGGER.error(f"Failed to crop image: {e}")
            img = temp_img

        return img

    def get_dominant_border_color(self, img):
        width, height = img.size
        top_row = img.crop((0, 0, width, 1))
        bottom_row = img.crop((0, height - 1, width, height))
        left_col = img.crop((0, 0, 1, height))
        right_col = img.crop((width - 1, 0, width, height))

        all_border_pixels = []
        all_border_pixels.extend(top_row.getdata())
        all_border_pixels.extend(bottom_row.getdata())
        all_border_pixels.extend(left_col.getdata())
        all_border_pixels.extend(right_col.getdata())

        return max(set(all_border_pixels), key=all_border_pixels.count) if all_border_pixels else (0, 0, 0)


    def gbase64(self, img):
        try:
            pixels = [item for p in list(img.getdata()) for item in p]
            b64 = base64.b64encode(bytearray(pixels))
            gif_base64 = b64.decode("utf-8")
            return gif_base64
        except Exception as e:
            _LOGGER.error(f"Error converting image to base64: {e}")
            return None

    def text_clock_img(self, img, brightness_lower_part, media_data):
        if media_data.playing_tv or self.config.special_mode or self.config.spotify_slide:
            return img

        # Check if there are no lyrics before proceeding
        if media_data.lyrics and self.config.show_lyrics and self.config.text_bg and brightness_lower_part != None and not media_data.playing_radio:
            enhancer_lp = ImageEnhance.Brightness(img)
            img = enhancer_lp.enhance(0.55)  # self.brightness_full)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(0.5)
            return img

        if self.config.show_clock and not self.config.show_lyrics:
            lpc = (43, 2, 62, 9) if self.config.clock_align == "Right" else (2, 2, 21, 9)
            lower_part_img = img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(0.3)
            img.paste(lower_part_img, lpc)


        if (self.config.temperature or media_data.temperature) and not self.config.show_lyrics:
            lpc = (2, 2, 18, 9) if self.config.clock_align == "Right" else (47, 2, 63, 9)
            lower_part_img = img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(0.3)
            img.paste(lower_part_img, lpc)


        if self.config.text_bg and self.config.show_text and not self.config.show_lyrics and not media_data.playing_tv:
            lpc = (0, 48, 64, 64)
            lower_part_img = img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(brightness_lower_part)
            img.paste(lower_part_img, lpc)
        return img

    def img_values(self, img):
        full_img = img
        font_color = '#ff00ff'
        brightness = 0.67
        brightness_lower_part = '#ffff00'
        background_color = (255, 255, 0)
        background_color_rgb = (0, 0, 255)
        recommended_font_color_rgb = (255, 255, 0)
        most_common_color_alternative_rgb = (0,0,0) # Give default to avoid errors
        most_common_color_alternative = '#000000' # Give default to avoid errors

        # Lower Part
        lower_part = img.crop((3, 48, 61, 61))
        color_counts_lower_part = Counter(lower_part.getdata())
        most_common_colors_lower_part = color_counts_lower_part.most_common()
        most_common_color = self.most_vibrant_color(most_common_colors_lower_part)
        opposite_color = tuple(255 - i for i in most_common_color)
        opposite_color_brightness = int(sum(opposite_color) / 3)
        brightness_lower_part = round(1 - opposite_color_brightness / 255, 2) if 0 <= opposite_color_brightness <= 255 else 0
        font_color = self.get_optimal_font_color(lower_part)

        # Full Image
        small_temp_img = full_img.resize((16, 16), Image.Resampling.LANCZOS)
        color_counts = Counter(small_temp_img.getdata())
        most_common_colors = color_counts.most_common()
        most_common_color_alternative_rgb = self.most_vibrant_color(most_common_colors)
        most_common_color_alternative = '#%02x%02x%02x' % most_common_color_alternative_rgb
        background_color_rgb = self.most_vibrant_color(most_common_colors)
        background_color = '#%02x%02x%02x' % background_color_rgb
        recommended_font_color_rgb = opposite_color
        brightness = int(sum(most_common_color_alternative_rgb) / 3)
        opposite_color_full = tuple(255 - i for i in most_common_color_alternative_rgb)
        opposite_color_brightness_full = int(sum(opposite_color_full) / 3)
        self.brightness_full = round(1 - opposite_color_brightness_full / 255, 2) if 0 <= opposite_color_brightness_full <= 255 else 0
        
        if self.config.wled:
            color1, color2, color3 = self.most_vibrant_colors_wled(small_temp_img)
        else:
            color1 = color2 = color3 = '%02x%02x%02x' % most_common_color_alternative_rgb
        
        return_values = (
            font_color,
            brightness,
            brightness_lower_part,
            background_color,
            background_color_rgb,
            recommended_font_color_rgb,
            most_common_color_alternative,
            color1, color2, color3
            )

        return return_values


    def most_vibrant_color(self, most_common_colors):
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

    def rgb_to_hex(self, rgb):
        return '{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])

    def is_strong_color(self, color):
        """Check if at least one RGB component is greater than 220."""
        return any(c > 220 for c in color)

    def color_distance(self, color1, color2):
        """Calculate the Euclidean distance between two colors."""
        return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color1, color2)))
        
    def is_vibrant_color(self, r, g, b):
        """Simplified vibrancy check, looking for a significant difference between components."""
        return (max(r, g, b) - min(r, g, b) > 50)

    def generate_close_but_different_color(self, existing_colors):
        """Generates a color close to the existing colors but distinct."""
        if not existing_colors:
            return (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))

        # Calculate the average color of existing colors
        avg_r = sum(c[0] for c, _ in existing_colors) // len(existing_colors)
        avg_g = sum(c[1] for c, _ in existing_colors) // len(existing_colors)
        avg_b = sum(c[2] for c, _ in existing_colors) // len(existing_colors)
        
        while True:
            # Generate color based on the average.
            new_color = (
                max(0, min(255, avg_r + random.randint(-40, 40))),
                max(0, min(255, avg_g + random.randint(-40, 40))),
                max(0, min(255, avg_b + random.randint(-40, 40)))
            )
            # Check if the new color is distinct from existing colors.
            is_distinct = True
            for existing_color, _ in existing_colors:
                if self.color_distance(new_color, existing_color) < 50:
                    is_distinct = False
                    break
            if is_distinct:
                return new_color
        
    def color_score(self, color_count):
        """Calculate a score for a color based on frequency and saturation."""
        color, count = color_count
        max_val = max(color)
        min_val = min(color)
        saturation = (max_val - min_val) / max_val if max_val > 0 else 0
        return count * saturation

    def most_vibrant_colors_wled(self, full_img):
        """Extract the three most dominant vibrant colors from an image, ensuring diverse hues and strong colors."""
        # Adaptive Color Enhancement
        enhancer = ImageEnhance.Contrast(full_img)
        full_img = enhancer.enhance(2.0)
        enhancer = ImageEnhance.Color(full_img)
        full_img = enhancer.enhance(3.0) # reduced enhancement

        color_counts = Counter(full_img.getdata())
        most_common_colors = color_counts.most_common(50)  # Get more colors
    
        # Filter only vibrant colors
        vibrant_colors = [(color, count) for color, count in most_common_colors if self.is_vibrant_color(*color)]
        
        # Sort by frequency and saturation
        vibrant_colors.sort(key=self.color_score, reverse=True)
    
        # Select top 3 unique colors by checking for distance between them and if at least one value > 220
        selected_colors = []
        
        for color, _ in vibrant_colors:
            if self.is_strong_color(color):
                is_similar = False
                for selected_color, _ in selected_colors:
                    if self.color_distance(color, selected_color) < 50: # Threshold for color distance
                        is_similar = True
                        break
                if not is_similar:
                    selected_colors.append((color, _))
                    if len(selected_colors) == 3:
                        break
        
        if len(selected_colors) < 3: # Less then 3 - check the other colors by the same rule.
                for color, _ in vibrant_colors:
                    is_similar = False
                    if not self.is_strong_color(color):
                        for selected_color, _ in selected_colors:
                            if self.color_distance(color, selected_color) < 50: # Threshold for color distance
                                is_similar = True
                                break
                        if not is_similar:
                            selected_colors.append((color, _))
                            if len(selected_colors) == 3:
                                break
        # Ensure we have 3 colors
        while len(selected_colors) < 3:
            new_color = self.generate_close_but_different_color(selected_colors)
            selected_colors.append((new_color, 1))

        return self.rgb_to_hex(selected_colors[0][0]), self.rgb_to_hex(selected_colors[1][0]), self.rgb_to_hex(selected_colors[2][0])

        
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
        def is_distinct_color(color, threshold=110):
            return all(math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color, img_color))) > threshold for img_color in image_palette)

        # Define a set of colorful candidate colors (modified for brightness)
        candidate_colors = [
                (30, 144, 255),  # Dodger Blue
                (0, 0, 255),     # Blue
                (0, 255, 255),   # Cyan
                (0, 191, 255),   # Deep Sky Blue
                (50, 205, 50),   # Lime Green
                (0, 255, 127),   # Spring Green
                (127, 255, 0),   # Chartreuse
                (255, 215, 0),   # Gold
                (255, 165, 0),   # Orange
                (173, 255, 47),  # Green Yellow
                (255, 140, 0),   # Dark Orange
                (255, 69, 0),    # Red Orange
                (255, 99, 71),   # Tomato
                (0, 255, 0),     # Green
                (255, 0, 255),   # Magenta
                (138, 43, 226),  # Blue Violet
                (238, 130, 238)  # Violet
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
                if (avg_brightness < 127 and contrast_with_white >= 2.5) or (avg_brightness >= 127 and contrast_with_black >= 2.5): # Lowering the contrast req.
                    # Update best color if this candidate has a higher saturation
                    if saturation > max_saturation:
                        max_saturation = saturation
                        best_color = font_color

        # If a best color was found, return it
        if best_color:
            return '#%02x%02x%02x' % best_color

        # Fallback if no suitable color is found
        return '#000000' if avg_brightness > 127 else '#ffffff'

class MediaData:
    def __init__(self, config, image_processor):
        self.config = config
        self.image_processor = image_processor 
        self.fallback = False
        self.fail_txt = False
        self.playing_radio = False
        self.radio_logo = False
        self.spotify_slide_pass = False
        self.playing_tv = False
        self.image_cache_count = 0
        self.image_cache_memory = 0
        self.media_position = 0
        self.media_duration = 0
        self.process_duration = 0
        self.spotify_frames = 0
        self.media_position_updated_at = None
        self.spotify_data = None
        self.artist = ""
        self.title = ""
        self.album = None
        self.lyrics = []
        self.picture = None
        self.select_index_original = 0
        self.lyrics_font_color = "#FFA000"
        self.color1 = "00FFAA"
        self.color2 = "AA00FF"
        self.color3 = "FFAA00"
        self.temperature = None
        self.info_img = None
        self.is_night = False
    
    async def update(self, hass):
        self.select_index_original = await hass.get_state(self.config.pixoo_sensor, attribute="pixoo_channel")
        try:
            sun = await hass.get_state("sun.sun")
            self.is_night = True if sun == "below_horizon" else False
            media_state = await hass.get_state(self.config.media_player)
            if media_state not in ["playing", "on"]:
                return None

            if not (title := await hass.get_state(self.config.media_player, attribute="media_title")):
                return None

            title = self.clean_title(title) if self.config.clean_title_enabled else title

            if self.config.show_lyrics and not self.config.special_mode:
                artist = await hass.get_state(self.config.media_player, attribute="media_artist")
                self.lyrics = await LyricsProvider(self.config, self.image_processor).get_lyrics(artist, title) 
            else:
                self.lyrics = []

            self.media_position = await hass.get_state(self.config.media_player, attribute="media_position", default=0)
            self.media_position_updated_at = await hass.get_state(self.config.media_player, attribute="media_position_updated_at", default=None)
            self.media_duration = await hass.get_state(self.config.media_player, attribute="media_duration", default=0)
            original_title = title
            title = self.clean_title(title) if self.config.clean_title_enabled else title
            if title != "TV" and title is not None:
                self.playing_tv = False
                artist = await hass.get_state(self.config.media_player, attribute="media_artist")
                original_artist = artist
                artist = artist if artist else ""
                self.title = title
                self.artist = artist
                self.picture = await hass.get_state(self.config.media_player, attribute="entity_picture")
                original_picture = self.picture
                media_content_id = await hass.get_state(self.config.media_player, attribute="media_content_id")
                queue_position = await hass.get_state(self.config.media_player, attribute="queue_position")
                media_channel = await hass.get_state(self.config.media_player, attribute="media_channel")
                album = await hass.get_state(self.config.media_player, attribute="media_album_name")
                self.album = album

                if media_channel and (media_content_id.startswith("x-rincon") or media_content_id.startswith("aac://http") or media_content_id.startswith("rtsp://")):
                    self.playing_radio = True
                    self.radio_logo = False
                    self.picture = original_picture

                    if ('https://tunein' in media_content_id or
                        # queue_position == 1 or
                        original_title == media_channel or
                        original_title == original_artist or
                        original_artist == media_channel or
                        original_artist == 'Live' or
                        original_artist == None):
                        self.picture = original_picture
                        self.radio_logo = True
                        self.album = media_channel

                else:
                    self.playing_radio = self.radio_logo = False
                    self.picture = original_picture
            else:
                self.artist = self.title = "TV"
                self.playing_tv = True

                if self.config.tv_icon_pic:
                    self.picture = "TV_IS_ON_ICON"
                else:
                    self.picture = "TV_IS_ON"

            if self.config.ha_temperature:
                temperature = await hass.get_state(self.config.ha_temperature)
                temperature_format = await hass.get_state(self.config.ha_temperature, attribute="unit_of_measurement")
                try:
                    self.temperature = (f"{int(float(temperature))}{temperature_format.lower()}")
                except:
                    self.temperature = None
                    
            return self

        except Exception as e:
            _LOGGER.error(f"Error updating Media Data: {str(e)}\n{traceback.format_exc()}")
            return None
        
    def format_ai_image_prompt(self, artist, title):
        # List of prompt templates
        if not artist:
            artist = 'Pixoo64'
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
        prompt = f"{AI_ENGINE}/{prompt}?model={self.config.ai_fallback}"
        return prompt
    
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


class FallbackService:
    def __init__(self, config, image_processor):
        self.config = config
        self.image_processor = image_processor
        self.tv_icon = self.image_processor.gbase64(self.create_tv_icon_image()) if self.config.tv_icon_pic else None
        
        # Tidal Token
        self.tidal_token_cache = {
            'token': None,
            'expires': 0
        }
        self.tidal_client_token = None # Used for client_id and secret.

    async def get_final_url(self, picture, media_data):
        self.fail_txt = False
        self.fallback = False

        if self.config.force_ai and not media_data.radio_logo and not media_data.playing_tv:
            try:
                _LOGGER.info("Trying to Generate AI album art. It may take few seconds")
                if self.config.info:
                    await self.send_info(media_data.artist, "FORCE   AI", media_data.lyrics_font_color)
                ai_url = media_data.format_ai_image_prompt(media_data.artist, media_data.title)
                self.fail_txt = False
                self.fallback = False
                try:
                    result = await asyncio.wait_for(
                    self.image_processor.get_image(ai_url, media_data, media_data.spotify_slide_pass),
                    timeout=25
                )
                    if result:
                        _LOGGER.info("Successfully Generated AI Image")
                        return result
                except asyncio.TimeoutError:
                    _LOGGER.warning("AI image generation timed out after 25 seconds")
            except Exception as e:
                _LOGGER.error(f"AI generation failed: {e}")

        else:
            if picture == "TV_IS_ON_ICON":
                _LOGGER.info("Sending TV icon image")

                return {
                    'base64_image': self.tv_icon, 
                    'font_color': '#ff00ff', 
                    'brightness': 0.67, 
                    'brightness_lower_part': '#ffff00', 
                    'background_color': (255, 255, 0), 
                    'background_color_rgb': (0, 0, 255), 
                    'most_common_color_alternative_rgb': (0,0,0), 
                    'most_common_color_alternative': '#ffff00'}

            # Process original picture
            try:
                if not media_data.playing_radio or media_data.radio_logo:
                    result = await self.image_processor.get_image(picture, media_data, media_data.spotify_slide_pass)
                    if result:
                        return result
            except Exception as e:
                _LOGGER.error(f"Original picture processing failed: {e}")

            """ Fallback begins """
            _LOGGER.info(f"Looking for {media_data.artist} - {media_data.title}")
            self.spotify_first_album = None
            self.spotify_artist_pic = None

            if self.config.info and media_data.info_img:
                await self.send_info_img(media_data.info_img)

            # Try Spotify
            if self.config.spotify_client_id and self.config.spotify_client_secret:
                if self.config.info:
                    await self.send_info(media_data.artist, "SPOTIFY", media_data.lyrics_font_color)
                try:
                    spotify_service = SpotifyService(self.config)
                    album_id, first_album = await spotify_service.get_spotify_album_id(media_data.artist, media_data.title)
                    if first_album:
                        self.spotify_first_album = await spotify_service.get_spotify_album_image_url(first_album)
                        
                    if album_id:
                        image_url = await spotify_service.get_spotify_album_image_url(album_id)
                        if image_url:
                            result = await self.image_processor.get_image(image_url, media_data, media_data.spotify_slide_pass)
                            if result:
                                _LOGGER.info("Successfully processed the Album Art @ Spotify")
                                return result
                        else:
                            _LOGGER.error("Failed to process Spotify image")
                    
                    # Get Artist Picture If Album Art Was Not Found
                    self.spotify_artist_pic = await spotify_service.get_spotify_artist_image_url_by_name(media_data.artist)

                except Exception as e:
                    _LOGGER.error(f"Spotify fallback failed with error: {str(e)}")

            # Try Discogs:
            if self.config.discogs:
                if self.config.info:
                    await self.send_info(media_data.artist, "DISCOGS", media_data.lyrics_font_color)
                try:
                    discogs_art = await self.search_discogs_album_art(media_data.artist, media_data.title)
                    if discogs_art:
                        result = await self.image_processor.get_image(discogs_art, media_data, media_data.spotify_slide_pass)
                        if result:
                            _LOGGER.info("Successfully processed the Album Art @ Discogs")
                            return result
                        else:
                            _LOGGER.error("Failed to process Discogs image")
                except Exception as e:
                    _LOGGER.error(f"Discogs fallback failed with error: {str(e)}")

            # Try Last.fm:
            if self.config.lastfm:
                if self.config.info:
                    await self.send_info(media_data.artist, "LAST.FM", media_data.lyrics_font_color)
                try:
                    lastfm_art = await self.search_lastfm_album_art(media_data.artist, media_data.title)
                    if lastfm_art:
                        result = await self.image_processor.get_image(lastfm_art, media_data, media_data.spotify_slide_pass)
                        if result:
                            _LOGGER.info("Successfully found and processed the Album Art @ Last.fm")
                            return result
                        else:
                            _LOGGER.error("Failed to process Last.fm image")
                except Exception as e:
                    _LOGGER.error(f"Last.fm fallback failed with error: {str(e)}")
            
            # Try TIDAL
            if self.config.tidal_client_id and self.config.tidal_client_secret:
                if self.config.info:
                    await self.send_info(media_data.artist, "TIDAL", media_data.lyrics_font_color)
                try:
                    tidal_art = await self.get_tidal_album_art_url(media_data.artist, media_data.title)
                    if tidal_art:
                        result = await self.image_processor.get_image(tidal_art, media_data, media_data.spotify_slide_pass)
                        if result:
                            _LOGGER.info("Successfully found and processed the Album Art @ TIDAL")
                            return result
                        else:
                            _LOGGER.error("Failed to process TIDAL image")
                except Exception as e:
                    _LOGGER.error(f"TIDAL fallback failed with error: {str(e)}")

            # Show Artist Picture if all API keys method fail
            if self.spotify_artist_pic:
                result = await self.image_processor.get_image(self.spotify_artist_pic, media_data, media_data.spotify_slide_pass)
                if result:
                    _LOGGER.info("Successfully processed the Artist picture @ Spotify")
                    return result

            # Try MusicBrainz
            if self.config.musicbrainz:
                if self.config.info:
                    await self.send_info(media_data.artist, "MUSICBRAINZ", media_data.lyrics_font_color)
                try:
                    mb_url = await self.get_musicbrainz_album_art_url(media_data.artist, media_data.title)
                    if mb_url:
                        try:
                            result = await asyncio.wait_for(
                            self.image_processor.get_image(mb_url, media_data, media_data.spotify_slide_pass),
                            timeout=10
                            )
                            if result:
                                _LOGGER.info("Successfully found and processed the Album Art @ MusicBrainz")
                                return result
                            else:
                                _LOGGER.error("Failed to process MusicBrainz image")
                        except asyncio.TimeoutError:
                            _LOGGER.warning("MusicBrainz timed out after 10 seconds")
                
                except Exception as e:
                    _LOGGER.error(f"MusicBrainz fallback failed with error: {str(e)}")


            # Fallback to AI generation
            try:
                _LOGGER.info("Trying to Generate AI album art. Will quit if fail after 20 seconds")
                ai_url = media_data.format_ai_image_prompt(media_data.artist, media_data.title)
                self.fail_txt = False
                self.fallback = False
                if self.config.info:
                    await self.send_info(media_data.artist, "AI   IMAGE", media_data.lyrics_font_color)

                try:
                    result = await asyncio.wait_for(
                    self.image_processor.get_image(ai_url, media_data, media_data.spotify_slide_pass),
                    timeout=20
                )
                    if result:
                        _LOGGER.info("Successfully Generated AI Image")
                        return result
                except asyncio.TimeoutError:
                    _LOGGER.warning("AI image generation timed out after 20 seconds")
            except Exception as e:
                _LOGGER.error(f"AI generation failed: {e}")

            # Last try on spotify:
            if self.spotify_first_album:
                if self.config.info:
                    await self.send_info(media_data.artist, "SPOTIFY", media_data.lyrics_font_color)
                try:
                    result = await self.image_processor.get_image(self.spotify_first_album, media_data, media_data.spotify_slide_pass)
                    if result:
                        _LOGGER.info("Successfully processed the defualt Album Art @ Spotify")
                        return result

                except Exception as e:
                    _LOGGER.error(f"Spotify fallback failed with error: {str(e)}")

        # Ultimate fallback
        self.fail_txt = True
        self.fallback = True
        black_screen = self.image_processor.gbase64(self.create_black_screen())
        _LOGGER.info("Ultimate fallback")
        return {
            'base64_image': black_screen, 
            'font_color': '#ff00ff', 
            'brightness': 0.67, 
            'brightness_lower_part': '#ffff00', 
            'background_color': (255, 255, 0), 
            'background_color_rgb': (0, 0, 255), 
            'most_common_color_alternative_rgb': (0,0,0), 
            'most_common_color_alternative': '#ffff00'}

    async def send_info_img(self, base64_image):
        payload = {
            "Command": "Draw/CommandList",
            "CommandList": [
                {"Command": "Draw/ResetHttpGifId"},
                {"Command": "Draw/SendHttpGif",
                    "PicNum": 1, "PicWidth": 64, "PicOffset": 0,
                    "PicID": 0, "PicSpeed": 10000, "PicData": base64_image }]}
        await PixooDevice(self.config).send_command(payload)

    async def send_info(self, artist, text, lyrics_font_color):
        payload = {"Command":"Draw/SendHttpItemList",
            "ItemList":[{ "TextId":10,
            "type":22, "x":0, "y":12,
            "dir":0, "font":114,
            "TextString": text.upper(),
            "TextWidth":64, "Textheight":16,
            "speed":100, "align":2, "color": lyrics_font_color },
        {   "TextId":11,
            "type":22, "x":0, "y":22,
            "dir":0, "font":114,
            "TextString": artist.upper(),
            "TextWidth":64, "Textheight":16,
            "speed":100, "align":2, "color": lyrics_font_color }]}
        await PixooDevice(self.config).send_command(payload)

    async def get_musicbrainz_album_art_url(self, ai_artist, ai_title) -> str:
        """Get album art URL from MusicBrainz asynchronously"""
        search_url = "https://musicbrainz.org/ws/2/release/"
        headers = {
            "Accept": "application/json",
            "User-Agent": "PixooClient/1.0"
        }
        params = {
            "query": f'artist:"{ai_artist}" AND recording:"{ai_title}"',
            "fmt": "json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Get the release ID
                async with session.get(search_url, params=params, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        _LOGGER.error(f"MusicBrainz API error: {response.status}")
                        return None

                    data = await response.json()
                    if not data.get("releases"):
                        _LOGGER.info("No releases found in MusicBrainz")
                        return None

                    release_id = data["releases"][0]["id"]
                    
                    # Get the cover art
                    cover_art_url = f"https://coverartarchive.org/release/{release_id}"
                    async with session.get(cover_art_url, headers=headers, timeout=20) as art_response:
                        if art_response.status != 200:
                            _LOGGER.error(f"MusicBrainz - Cover art archive error: {art_response.status}\n{cover_art_url}")
                            return None

                        art_data = await art_response.json()
                        # Look for front cover and get 250px thumbnail
                        for image in art_data.get("images", []):
                            if image.get("front", False):
                                return image.get("thumbnails", {}).get("250")

                        _LOGGER.info("MusicBrainz - No front cover found in cover art archive")
                        return None

        except asyncio.TimeoutError:
            _LOGGER.error("MusicBrainz request timed out")
    
    async def search_discogs_album_art(self, ai_artist, ai_title):
        base_url = "https://api.discogs.com/database/search"
        headers = {
            "User-Agent": "AlbumArtSearchApp/1.0",
            "Authorization": f"Discogs token={self.config.discogs}"
        }
        params = {
            "artist": ai_artist,
            "track": ai_title,
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
                                _LOGGER.info("Album art URL not found in best Discogs result.")
                                return None
                        else:
                            _LOGGER.info("No suitable album found on Discogs.")
                            return None
                    else:
                        _LOGGER.info("No results found for the specified artist and track @ Discogs.")
                        return None
                else:
                    _LOGGER.error(f"Discogs API request failed: {response.status} - {response.reason}")
                    return None


    async def search_lastfm_album_art(self, ai_artist, ai_title):
        base_url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "track.getInfo",
            "api_key": self.config.lastfm,
            "artist": ai_artist,
            "track": ai_title,
            "format": "json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    album_art_url = data.get("track", {}).get("album", {}).get("image", [])
                    if album_art_url:
                        return album_art_url[-1]["#text"]
                    else:
                        _LOGGER.info("No suitable album found on Last.FM.")
                return None


    async def get_tidal_album_art_url(self, artist, title):
        """
        Retrieves the album art URL from TIDAL API using artist and track title.
        """
        base_url = "https://openapi.tidal.com/v2/"
        access_token = await self.get_tidal_access_token()
        if not access_token:
            return None

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        search_params = {
            "countryCode": "US",  # Example country code
            "include": ["artists", "albums", "tracks"],
        }
        try:
            async with aiohttp.ClientSession() as session:
                # 1. Search for tracks using the title and artist
                search_url = f"{base_url}searchresults/{artist} - {title}"
                async with session.get(search_url, headers=headers, params=search_params) as response:
                    response.raise_for_status()
                    search_data = await response.json()
                    # Directly search for albums in the "included" array
                    albums = [item for item in search_data.get("included", []) if item.get("type") == "albums"]
                    if not albums:
                        _LOGGER.info("No albums found on TIDAL")
                        return None
                    
                best_album = albums[0]

                if best_album:
                        # Extract and return image URLs from albums object
                        image_links = best_album.get("attributes", {}).get("imageLinks", [])
                        return image_links[3].get("href")

                else:
                    _LOGGER.info(f"TIDAL - No album found that matches '{artist} - {title}'")
                    return None

        except aiohttp.ClientError as e:
            _LOGGER.error(f"TIDAL API Request failed with error: {e}")
            return None
        except json.JSONDecodeError as e:
            _LOGGER.error(f"TIDAL Json parsing error: {e}")
            return None


    async def get_tidal_access_token(self):
        if self.tidal_token_cache['token'] and time.time() < self.tidal_token_cache['expires']:
            return self.tidal_token_cache['token']

        url = "https://auth.tidal.com/v1/oauth2/token"  # Real TIDAL auth endpoint
        tidal_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.config.tidal_client_id,
            "client_secret": self.config.tidal_client_secret,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=tidal_headers, data=payload) as response:
                    response.raise_for_status()
                    response_json = await response.json()
                    access_token = response_json["access_token"]
                    self.tidal_token_cache = {
                        'token': access_token,
                        'expires': time.time() + 3500
                    }
                    return access_token

        except aiohttp.ClientError as e:
            _LOGGER.error(f"TIDAL - Error getting access token: {e}")
            return None
        except json.JSONDecodeError as e:
            _LOGGER.error(f"TIDAL - Error during json parsing: {e}")
            return None


    def create_black_screen(self):
        img = Image.new("RGB", (64, 64), (0, 0, 0))  # Create a black image
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return img

    def create_tv_icon_image(self):
        size = 64
        image = Image.new("RGB", (size, size), "black")
        draw = ImageDraw.Draw(image)

        # Define colors
        screen_color = (50, 50, 50)  # Dark Grey for Screen
        body_color = (150, 150, 150)  # Light Grey for Body
        stand_color = (100, 100, 100)  # Medium Grey for Stand

        # Calculate some dimensions for the icon (scaled by the size)
        margin = int(size * 0.2)  # margin from the edges
        screen_width = int(size * 0.6) + 1 # Width of the TV screen
        screen_height = int(size * 0.4) # Height of the TV screen
        screen_x = margin
        screen_y = margin

        body_width = screen_width + 2 * int(size * 0.05)  # Width of the body
        body_height = screen_height + int(size * 0.1)  # Height of the body
        body_x = screen_x - int(size * 0.05)
        body_y = screen_y - int(size * 0.05)

        stand_width = int(size * 0.2)
        stand_height = int(size * 0.1)
        stand_x = (size - stand_width) // 2
        stand_y = screen_y + screen_height
        y_offset = 3

        # Draw the TV body
        draw.rectangle((body_x, body_y + y_offset, body_x + body_width, body_y + body_height + y_offset), fill=body_color)

        # Draw the TV screen
        draw.rectangle((screen_x, screen_y + y_offset, screen_x + screen_width, screen_y + screen_height + y_offset), fill=screen_color)

        # Draw the stand
        draw.rectangle((stand_x, stand_y + y_offset, stand_x + stand_width, stand_y + stand_height + y_offset), fill=stand_color)

        return image


class LyricsProvider:
    def __init__(self, config, image_processor):
        self.config = config
        self.lyrics = []
        self.track_position = 0
        self.image_processor = image_processor

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
                        _LOGGER.info(f"Retrieved lyrics for {artist} - {title}")
                        return self.lyrics
                    else:
                        _LOGGER.error(f"Failed to fetch lyrics: {response.status}")
                        self.lyrics = []
                        return []  # Reset lyrics if fetching fails
        except Exception as e:
            _LOGGER.error(f"Error fetching lyrics: {str(e)}")
            return [] # Reset lyrics on error
    
    async def calculate_position(self, media_data, hass):
        if not media_data.lyrics:
            return

        if media_data.media_position_updated_at:
            media_position_updated_at = datetime.fromisoformat(media_data.media_position_updated_at.replace('Z', '+00:00'))
            current_time = datetime.now(timezone.utc)
            time_diff = (current_time - media_position_updated_at).total_seconds()
            current_position = media_data.media_position + time_diff
            current_position = min(current_position, media_data.media_duration)
            self.track_position = int(current_position)
            current_position = self.track_position
            if current_position is not None and media_data.lyrics and self.config.show_lyrics:
                for i, lyric in enumerate(media_data.lyrics):
                    lyric_time = lyric['seconds']
                    
                    if int(current_position) == lyric_time - 1:
                        #await self.create_lyrics_payloads(lyric['lyrics'], 10, hass, media_data.lyrics_font_color)
                        await self.create_lyrics_payloads(lyric['lyrics'], 10, media_data.lyrics_font_color)

                        next_lyric_time = media_data.lyrics[i + 1]['seconds'] if i + 1 < len(media_data.lyrics) else None
                        lyrics_diplay = (next_lyric_time - lyric_time) if next_lyric_time else lyric_time + 10
                        if lyrics_diplay > 9:
                            await asyncio.sleep(8)
                            await PixooDevice(self.config, hass.headers).send_command({"Command": "Draw/ClearHttpText"})
                            
                        break

    async def create_lyrics_payloads(self, lyrics, x, lyrics_font_color):

        if not lyrics:
            return
        
        all_lines = split_string(get_bidi(lyrics) if lyrics and has_bidi(lyrics) else lyrics, x)

        if len(all_lines) > 4:
            all_lines[4] += ' ' + ' '.join(all_lines[5:])
            all_lines = all_lines[:5]
        screen_width = 64 
        screen_height = 64
        font_height = 12
        item_list = []
        start_y = (screen_height - len(all_lines) * font_height) // 2

        for i, line in enumerate(all_lines):
            y = start_y + (i * font_height)
            dir = 1 if has_bidi(line) else 0
            item_list.append({
                "TextId": i + 1, "type": 22,
                "x": 0, "y": y,
                "dir": dir, "font": self.config.lyrics_font,
                "TextWidth": 64, "Textheight": 16,
                "speed": 100, "align": 2,
                "TextString": line,
                "color": lyrics_font_color,
            })

        payload = {
            "Command": "Draw/SendHttpItemList",
            "ItemList": item_list
        }
        clear_text_command = {"Command": "Draw/ClearHttpText"}
        await PixooDevice(self.config).send_command(clear_text_command)
        await PixooDevice(self.config).send_command(payload)

class SpotifyService:
    def __init__(self, config):
        self.config = config
        self.spotify_token_cache = {
            'token': None,
            'expires': 0
        }
        self.spotify_data = None

    async def get_spotify_access_token(self):
        if self.spotify_token_cache['token'] and time.time() < self.spotify_token_cache['expires']:
            return self.spotify_token_cache['token']

        url = "https://accounts.spotify.com/api/token"
        spotify_headers = {
            "Authorization": "Basic " + base64.b64encode(f"{self.config.spotify_client_id}:{self.config.spotify_client_secret}".encode()).decode(),
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
            _LOGGER.error(f"Error getting Spotify access token: {e}")
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
            "limit": 50
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=spotify_headers, params=payload) as response:
                    response_json = await response.json()
                    tracks = response_json.get('tracks', {}).get('items', [])
                    if tracks:
                        return response_json
                    else:
                        _LOGGER.info("No tracks found on Spotify.")
                        return None

        except (IndexError, KeyError) as e:
            _LOGGER.error(f"Error parsing Spotify track info: {e}")
            return None
        except Exception as e:
            _LOGGER.error(f"Error getting Spotify album ID: {e}")
            return None
        finally:
            await asyncio.sleep(0.5)


    async def spotify_best_album(self, tracks, artist):
        best_album = None
        earliest_year = float('inf')
        preferred_types = ["single", "album", "compilation"]
        first_album = tracks[0]['album']['id']
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
            return best_album['id'], first_album
        else:
            if tracks:
                _LOGGER.info("Most likey album art from Spotify is wrong.")
                #return  tracks[0]['album']['id']
                return None, first_album
            else:
                _LOGGER.info("No suitable album found on Spotify.")
                return None, first_album


    async def get_spotify_album_id(self, artist, title):
        token = await self.get_spotify_access_token()
        if not token:
            return None
        try:
            self.spotify_data = []
            response_json = await self.get_spotify_json(artist, title)
            self.spotify_data = response_json
            tracks = response_json.get('tracks', {}).get('items', [])
            if tracks:
                best_album, first_album = await self.spotify_best_album(tracks, artist)
                return best_album, first_album
            else:
                _LOGGER.info("No tracks found on Spotify.")
                return None

        except (IndexError, KeyError) as e:
            _LOGGER.error(f"Error parsing Spotify track info: {e}")
            return None
        except Exception as e:
            _LOGGER.error(f"Error getting Spotify album ID: {e}")
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
            _LOGGER.info("Album image not found on Spotify.")
            return None
        except Exception as e:
            _LOGGER.error(f"Error getting Spotify album image URL: {e}")
            return None
        finally:
            await asyncio.sleep(0.5)
    

    async def get_spotify_artist_image_url_by_name(self, artist_name):
        """
        Retrieves the URL of the first image of a Spotify artist given their name.
        """
        token = await self.get_spotify_access_token()
        if not token or not artist_name:
            return None

        search_url = "https://api.spotify.com/v1/search"
        spotify_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        search_payload = {
            "q": f"artist:{artist_name}",
            "type": "artist",
            "limit": 1
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=spotify_headers, params=search_payload) as response:
                    response_json = await response.json()
                    if response.status != 200:
                        _LOGGER.error(f"Failed to search artist on Spotify: {response.status} - {response_json}")
                        return None
                    
                    artists = response_json.get('artists', {}).get('items', [])
                    if not artists:
                        _LOGGER.info(f"No artist found on Spotify with the name: {artist_name}")
                        return None

                    artist_id = artists[0]['id']
                    return await self.get_spotify_artist_image_url(artist_id)

        except (IndexError, KeyError) as e:
            _LOGGER.info(f"Error parsing Spotify artist search data: {e}")
            return None
        except Exception as e:
            _LOGGER.error(f"Error getting Spotify artist image URL by name: {e}")
            return None
        finally:
            await asyncio.sleep(0.5)

    async def get_spotify_artist_image_url(self, artist_id):
        """
        Retrieves the URL of the first image of a Spotify artist given their ID.
        """
        token = await self.get_spotify_access_token()
        if not token or not artist_id:
            return None
        url = f"https://api.spotify.com/v1/artists/{artist_id}"
        spotify_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=spotify_headers) as response:
                    response_json = await response.json()
                    if response.status != 200:
                        _LOGGER.error(f"Failed to get artist data from Spotify: {response.status} - {response_json}")
                        return None
                    
                    images = response_json.get('images', [])
                    if images:
                        return images[0]['url']
                    else:
                        _LOGGER.info("Artist image not found on Spotify.")
                        return None

        except (IndexError, KeyError) as e:
            _LOGGER.info(f"Error parsing Spotify artist data: {e}")
            return None
        except Exception as e:
            _LOGGER.error(f"Error getting Spotify artist image URL: {e}")
            return None
        finally:
            await asyncio.sleep(0.5)


    """ Spotify Album Art Slide """
    async def get_album_list(self, media_data, returntype):
        """Retrieves album art URLs, filtering and prioritizing albums."""
        if not self.spotify_data or media_data.playing_tv:
            return []

        try:
            if not isinstance(self.spotify_data, dict):
                _LOGGER.error("Unexpected Spotify data format.  Expected a dictionary.")
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
                if media_data.artist.lower() not in [artist.get('name', '').lower() for artist in artists]:
                    continue
                
                if album_id not in albums:
                    albums[album_id] = album

            sorted_albums = sorted(albums.values(), key=lambda x: (
                x.get("album_type") == "single",  #Singles first
                x.get("album_type") == "album",  #Albums Second
                x.get("album_type") == "compilation" #Compilations last
            ))

            album_urls = []
            album_base64 = []
            show_lyrics_is_on = True if media_data.lyrics else False
            playing_radio_is_on = True if media_data.playing_radio else False

            for album in sorted_albums:
                images = album.get("images", [])
                if images:
                    album_urls.append(images[0]["url"])
                    base64_data = await self.get_slide_img(images[0]["url"], show_lyrics_is_on, playing_radio_is_on)
                    album_base64.append(base64_data)

            if returntype == "b64":
                return album_base64 
            else:
                return album_urls

        except (KeyError, IndexError, TypeError, AttributeError) as e:
            _LOGGER.error(f"Error processing Spotify data: {e}")
            return []


    async def get_slide_img(self, picture, show_lyrics_is_on, playing_radio_is_on):
        """Fetches, processes, and returns base64-encoded image data."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(picture) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Error fetching image {picture}: {response.status}")
                        return None

                    image_raw_data = await response.read()

        except Exception as e:
            _LOGGER.error(f"Error processing image {picture}: {e}")
            return None
        
        try:
            with Image.open(BytesIO(image_raw_data)) as img:
                img = ensure_rgb(img)
                img = ImageProcessor(self.config).fixed_size(img)

                img = img.resize((64, 64), Image.Resampling.LANCZOS)
                
                if self.config.limit_color or self.config.contrast or self.config.sharpness or self.config.colors or self.config.kernel:
                    img = ImageProcessor(self.config).filter_image(img)

                if self.config.special_mode:
                    img = ImageProcessor(self.config).special_mode(img)

                if show_lyrics_is_on and not playing_radio_is_on and not self.config.special_mode:
                    enhancer_lp = ImageEnhance.Brightness(img)
                    img = enhancer_lp.enhance(0.55)
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(0.5)
                
                return ImageProcessor(self.config).gbase64(img)

        except Exception as e:
            _LOGGER.error(f"Error processing image {picture}: {e}")
            return None

    async def send_pixoo_animation_frame(self, pixoo_device, command, pic_num, pic_width, pic_offset, pic_id, pic_speed, pic_data):
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
        # Use the pixoo_device object directly
        response = await pixoo_device.send_command(payload)
        return response


    async def spotify_albums_slide(self, pixoo_device, media_data):
        """Fetches and processes images, printing base64 data."""
        media_data.spotify_slide_pass = True
        album_urls = await self.get_album_list(media_data, returntype="b64")
        if not album_urls:
            _LOGGER.info("No albums found for slide")
            media_data.spotify_frames = 0
            media_data.spotify_slide_pass = False
            return

        frames = len(album_urls)
        media_data.spotify_frames = frames
        if frames < 2:
            media_data.spotify_slide_pass = False
            media_data.spotify_frames = 0
            return

        _LOGGER.info(f"Creating album slide from spotify with {frames} frames for {media_data.artist}")
        pic_offset = 0
        await pixoo_device.send_command({"Command": "Draw/CommandList", "CommandList": 
            [ {"Command": "Channel/OnOffScreen", "OnOff": 1}, {"Command": "Draw/ResetHttpGifId"} ]})

        for album_url in album_urls:
            try:
                if album_url:
                    pic_speed = 5000  # 5 seconds
                    await self.send_pixoo_animation_frame(
                    pixoo_device=pixoo_device,
                    command="Draw/SendHttpGif",
                    pic_num=frames,
                    pic_width=64,
                    pic_offset=pic_offset,
                    pic_id=0,
                    pic_speed=pic_speed,
                    pic_data=album_url
                    )

                # Increment pic_id for the next animation frame
                    pic_offset += 1
                else:
                    _LOGGER.error(f"Failed to process image: {album_url}")
                    break

            except Exception as e:
                _LOGGER.error(f"Error processing image {album_url}: {e}")
                break
    
    async def spotify_album_art_animation(self, pixoo_device, media_data, start_time=None):
        """Creates and sends a static slide show with 3 albums to the Pixoo device."""
        if media_data.playing_tv:
            return
        
        try:
            album_urls = await self.get_album_list(media_data, returntype="url")
            if not album_urls:
                _LOGGER.info("spotify_album_art_animation - No albums found for slide.")
                media_data.spotify_frames = 0
                return

            num_albums = len(album_urls)
            if num_albums < 3:
                _LOGGER.info("spotify_album_art_animation - Not enough albums to create animation.")
                media_data.spotify_frames = 0
                media_data.spotify_slide_pass = False
                return

            images = []
            for album_url in album_urls:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(album_url) as response:
                            if response.status != 200:
                                _LOGGER.error(f"Error fetching image {album_url}: {response.status}")
                                return
                            image_data = await response.read()
                            img = Image.open(BytesIO(image_data))
                            img = img.resize((34, 34), Image.Resampling.LANCZOS)
                            images.append(img)
                except Exception as e:
                    _LOGGER.error(f"spotify_album_art_animation - Error decoding or processing image in animation: {e}")
                    return
            
            total_frames = min(num_albums, 60)
            media_data.spotify_frames = total_frames

            await pixoo_device.send_command({"Command": "Draw/CommandList", "CommandList": 
                [ {"Command": "Channel/OnOffScreen", "OnOff": 1}, {"Command": "Draw/ResetHttpGifId"} ]})

            pixoo_frames = []

            for index in range(total_frames):
                try:
                    canvas = Image.new("RGB", (64, 64), (0, 0, 0))
                    
                    left_index = (index - 1) % num_albums
                    center_index = index % num_albums
                    right_index = (index + 1) % num_albums

                    x_positions = [1, 16, 51] # Corrected x positions
                    
                    for album_index, x in zip([left_index, center_index, right_index], x_positions):
                        try:
                            album_img = images[album_index]
                            if album_index != center_index:
                                album_img = album_img.filter(ImageFilter.GaussianBlur(2))
                                enhancer = ImageEnhance.Brightness(album_img)
                                album_img = enhancer.enhance(0.5)
                            else:
                                draw = ImageDraw.Draw(album_img)
                                draw.rectangle([0, 0, album_img.width, album_img.height], outline="black", width=1)
                            canvas.paste(album_img, (x, 8))
                        except Exception as e:
                            _LOGGER.error(f"spotify_album_art_animation - Error pasting image in animation {e}")
                            return

                    base64_image = ImageProcessor(self.config).gbase64(canvas)
                    pixoo_frames.append(base64_image)

                except Exception as e:
                    _LOGGER.error(f"spotify_album_art_animation - Error creating frame: {e}")
                    return

            pic_offset = 0
            pic_speed = 5000
            _LOGGER.info(f"spotify_album_art_animation - sending {total_frames} frames")
            for i, frame in enumerate(pixoo_frames):
                await self.send_pixoo_animation_frame(
                    pixoo_device=pixoo_device,
                    command="Draw/SendHttpGif",
                    pic_num=total_frames,
                    pic_width=64,
                    pic_offset=pic_offset,
                    pic_id=1,
                    pic_speed=pic_speed,
                    pic_data=frame
                )
                
                pic_offset += 1
            media_data.spotify_slide_pass = True
        except Exception as e:
            _LOGGER.error(f"spotify_album_art_animation - Error in spotify_album_art_animation: {e}")
            media_data.spotify_frames = 0
            return


    async def create_album_slider(self, media_data):
        album_urls = await self.get_album_list(media_data, returntype="url")
        if not album_urls or len(album_urls) < 3:
            _LOGGER.info("Not enough albums to create slider.")
            return None

        album_urls = album_urls[:10]  # Limit to 10 albums
        canvas_width = 34 * (len(album_urls))
        canvas = Image.new("RGB", (canvas_width, 64), (0, 0, 0))

        for i, album_url in enumerate(album_urls):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(album_url) as response:
                        if response.status != 200:
                            _LOGGER.error(f"Error fetching image {album_url}: {response.status}")
                            return None
                        image_data = await response.read()
                        img = Image.open(BytesIO(image_data))
                        img = img.resize((34, 34), Image.Resampling.LANCZOS)
                        canvas.paste(img, (34 * i, 8))
            except Exception as e:
                _LOGGER.error(f"Error processing image {album_url}: {e}")
                return None

        return canvas

    async def create_slider_animation(self, media_data):
        canvas = await self.create_album_slider(media_data)
        if not canvas:
            return None

        frames = []
        total_frames = (canvas.width) // 3  # Move 3 pixels per frame
        for i in range(total_frames):
            frame = canvas.crop((i * 3, 0, i * 3 + 64, 64))
            frame = frame.resize((64, 64), Image.Resampling.LANCZOS)
            base64_image = ImageProcessor(self.config).gbase64(frame)
            frames.append(base64_image)

        return frames

    async def send_slider_animation(self, pixoo_device, media_data):
        media_data.spotify_slide_pass = False
        frames = await self.create_slider_animation(media_data)
        if not frames:
            return

        await pixoo_device.send_command({"Command": "Draw/CommandList", "CommandList": 
            [ {"Command": "Channel/OnOffScreen", "OnOff": 1}, {"Command": "Draw/ResetHttpGifId"} ]})

        pic_offset = 0
        for i, frame in enumerate(frames):
            await self.send_pixoo_animation_frame(
                pixoo_device=pixoo_device,
                command="Draw/SendHttpGif",
                pic_num=len(frames),
                pic_width=64,
                pic_offset=pic_offset,
                pic_id=0,
                pic_speed=750,
                pic_data=frame
            )
            pic_offset += 1
        media_data.spotify_slide_pass = True


class Pixoo64_Media_Album_Art(hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clear_timer_task = None
        self.callback_timeout = 20  # Increase the callback timeout limit
        self.current_image_task = None  # Track the current image processing task
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Connection": "keep-alive",
            "User-Agent": "PixooClient/1.0"
        }

    async def initialize(self):
        """Initialize the app and set up state listeners."""
        self.config = Config(self.args)
        self.pixoo_device = PixooDevice(self.config) #, self.headers) # Pass config and headers
        self.image_processor = ImageProcessor(self.config)
        self.media_data = MediaData(self.config, self.image_processor)
        self.fallback_service = FallbackService(self.config, self.image_processor)

        # Load configuration
        self.config = Config(self.args)
        self.pixoo_device = PixooDevice(self.config) #, self.headers)
        self.image_processor = ImageProcessor(self.config)
        self.media_data = MediaData(self.config, self.image_processor)
        self.fallback_service = FallbackService(self.config, self.image_processor)

        # Set up state listeners
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute='media_title')
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute='state')
        if self.config.show_lyrics:
            self.run_every(self.calculate_position, datetime.now(), 1)  # Run every second

        self.select_index = await self.pixoo_device.get_current_channel_index()
        self.media_data_sensor = self.config.pixoo_sensor # State sensor

    async def safe_state_change_callback(self, entity, attribute, old, new, kwargs, timeout=aiohttp.ClientTimeout(total=20)):
        """Wrapper for state change callback with timeout protection"""
        try:
            # Create a task with timeout
            async with asyncio.timeout(self.callback_timeout):
                await self.state_change_callback(entity, attribute, old, new, kwargs)
        except asyncio.TimeoutError:
            _LOGGER.warning("Callback timed out - cancelling operation")
            # Optionally reset any state or cleanup here
        except Exception as e:
            _LOGGER.error(f"Error in callback: {str(e)}")

    async def state_change_callback(self, entity, attribute, old, new, kwargs):
        """Main callback with early exit conditions"""
        try:
            # Quick checks for early exit
            if new == old or (await self.get_state(self.config.toggle)) != "on":
                return
            
            media_state = await self.get_state(self.config.media_player)
            if media_state in ["off", "idle", "pause", "paused"]:
                await asyncio.sleep(6)  # Delay to not turn off during track changes
                # Quick validation of media state
                if (media_state := await self.get_state(self.config.media_player)) not in ["playing", "on"]:
                    pass
                else:
                    return
                if self.config.full_control:
                    await self.pixoo_device.send_command({
                            "Command": "Draw/CommandList",
                            "CommandList": [
                                {"Command": "Channel/SetIndex", "SelectIndex": self.select_index},
                                {"Command": "Channel/OnOffScreen", "OnOff": 0}
                            ]
                        })
                else:
                    await self.pixoo_device.send_command({
                        "Command": "Draw/CommandList",
                        "CommandList": [
                            {"Command": "Draw/ClearHttpText"},
                            {"Command": "Draw/ResetHttpGifId"},
                            {"Command": "Channel/SetIndex", "SelectIndex": self.select_index}
                            ]
                        })
                await self.set_state(self.media_data_sensor, state="off")
                if self.config.light:
                    await self.control_light('off')
                if self.config.wled:
                    await self.control_wled_light('off')
                return

            # If we get here, proceed with the main logic
            await self.update_attributes(entity, attribute, old, new, kwargs)

        except Exception as e:
            _LOGGER.error(f"Error in state change callback: {str(e)}")

    async def update_attributes(self, entity, attribute, old, new, kwargs):
        """Modified to be more efficient"""
        try:
            # Quick validation of media state
            if (media_state := await self.get_state(self.config.media_player)) not in ["playing", "on"]:
                if self.config.light:
                    await self.control_light('off')
                if self.config.wled:
                    await self.control_wled_light('off')
                return

            # Get current title and check if we need to update
            media_data = await self.media_data.update(self)
            if not media_data:
                return
            
            # Proceed with the main logic
            await self.pixoo_run(media_state, media_data)
            

        except Exception as e:
            _LOGGER.error(f"Error in update_attributes: {str(e)}\n{traceback.format_exc()}")

    async def pixoo_run(self, media_state, media_data):
        """Add timeout protection to pixoo_run"""
        try:
            async with asyncio.timeout(self.callback_timeout):
                # Get current channel index
                self.select_index = await self.pixoo_device.get_current_channel_index()
                self.select_index = media_data.select_index_original if self.select_index == 4 else self.select_index
                
                if media_state in ["playing", "on"]:
                    
                    # Cancel any ongoing image processing task
                    if self.current_image_task:
                        self.current_image_task.cancel()
                        self.current_image_task = None

                    # Create a new task for image processing
                    self.current_image_task = asyncio.create_task(self._process_and_display_image(media_data))

        except Exception as e:
            _LOGGER.error(f"Error in pixoo_run: {str(e)}\n{traceback.format_exc()}")
        
        finally:
            await asyncio.sleep(0.10)

    async def _process_and_display_image(self, media_data):
        """Processes and displays the image, with cancellation support."""
        if media_data.picture == "TV_IS_ON":
            payload = ({
                        "Command": "Draw/CommandList",
                        "CommandList": [
                            {"Command": "Channel/OnOffScreen", "OnOff": 1},
                            {"Command": "Draw/ClearHttpText"},
                            {"Command": "Draw/ResetHttpGifId"},
                            {"Command": "Channel/SetIndex", "SelectIndex": self.select_index} ]
                        })
            await self.pixoo_device.send_command(payload)
            if self.config.light:
                await self.control_light('off')
            if self.config.wled:
                await self.control_wled_light('off')

            return

        try:
            start_time = time.perf_counter()
            processed_data = await self.fallback_service.get_final_url(media_data.picture, media_data)
            
            if not processed_data:
                return
            media_data.spotify_frames = 0
            base64_image = processed_data.get('base64_image')
            font_color = processed_data.get('font_color')
            brightness = processed_data.get('brightness')
            brightness_lower_part = processed_data.get('brightness_lower_part')
            background_color = processed_data.get('background_color')
            background_color_rgb = processed_data.get('background_color_rgb')
            most_common_color_alternative_rgb = processed_data.get('most_common_color_alternative_rgb')
            most_common_color_alternative = processed_data.get('most_common_color_alternative')

            if self.config.light and not media_data.playing_tv:
                await self.control_light('on',background_color_rgb, media_data.is_night)
            
            if self.config.wled and not media_data.playing_tv:
                # Retrieve cached color values if available
                color1 = processed_data.get('color1')
                color2 = processed_data.get('color2')
                color3 = processed_data.get('color3')
                await self.control_wled_light('on', color1, color2, color3, media_data.is_night)
            if media_data.playing_tv:
                if self.config.light:
                    await self.control_light('off')
                if self.config.wled:
                    await self.control_wled_light('off')
                
            new_attributes = {
                "artist": media_data.artist,
                "media_title": media_data.title,
                "font_color": font_color, 
                "background_color_brightness": brightness,  
                "background_color": background_color, 
                "color_alternative_rgb": most_common_color_alternative, 
                "background_color_rgb": background_color_rgb, 
                "color_alternative": most_common_color_alternative_rgb,
                "images_in_cache": media_data.image_cache_count,
                "image_memory_cache": media_data.image_cache_memory,
                "process_duration": media_data.process_duration,
                "spotify_frames": media_data.spotify_frames,
                "pixoo_channel": self.select_index
                }
                
            payload = {
                "Command": "Draw/CommandList",
                "CommandList": [
                    {"Command": "Channel/OnOffScreen", "OnOff": 1},
                    {"Command": "Draw/ClearHttpText"},
                    {"Command": "Draw/ResetHttpGifId"},
                    {"Command": "Draw/SendHttpGif",
                        "PicNum": 1, "PicWidth": 64, "PicOffset": 0,
                        "PicID": 0, "PicSpeed": 10000, "PicData": base64_image }]}

            if self.config.spotify_slide and not media_data.radio_logo and not media_data.playing_tv:
                spotify_service = SpotifyService(self.config)
                spotify_service.spotify_data = await spotify_service.get_spotify_json(media_data.artist, media_data.title)
                if spotify_service.spotify_data:
                    start_time = time.perf_counter()
                    media_data.spotify_frames = 0

                    if self.config.special_mode: # and self.config.show_text:
                        if self.config.special_mode_spotify_slider:
                            await spotify_service.send_slider_animation(self.pixoo_device, media_data)
                        else:
                            await spotify_service.spotify_album_art_animation(self.pixoo_device, media_data)
                    else:
                        await spotify_service.spotify_albums_slide(self.pixoo_device, media_data)

                    if media_data.spotify_slide_pass:
                        new_attributes["process_duration"] = media_data.process_duration
                        new_attributes["spotify_frames"] = media_data.spotify_frames
                    else:
                        await self.pixoo_device.send_command({"Command": "Channel/SetIndex", "SelectIndex": 4}) # Avoid Animation Glitch
                        
            if not media_data.spotify_slide_pass:
                await self.pixoo_device.send_command(payload) 

            end_time = time.perf_counter()
            duration = end_time - start_time
            media_data.process_duration = f"{duration:.2f} seconds"
            new_attributes["process_duration"] = media_data.process_duration
            await self.set_state(self.media_data_sensor, state="on", attributes=new_attributes)

            if self.fallback_service.fail_txt and self.fallback_service.fallback:
                black_img = self.fallback_service.create_black_screen()
                black_pic = self.image_processor.gbase64(black_img)
                payload = {
                    "Command": "Draw/CommandList",
                    "CommandList": [
                        {"Command": "Channel/OnOffScreen", "OnOff": 1},
                        {"Command": "Draw/ResetHttpGifId"},
                    ]
                }
                await self.pixoo_device.send_command(payload)
                await self.pixoo_device.send_command({
                            "Command": "Draw/SendHttpGif",
                            "PicNum": 1, "PicWidth": 64,
                            "PicOffset": 0, "PicID": 0,
                            "PicSpeed": 1000, "PicData": black_pic
                        })
                payloads = self.create_payloads(media_data.artist, media_data.title, 11)
                await self.pixoo_device.send_command(payloads)
                return

            textid = 0
            text_string = None
            text_track = (media_data.artist + " - " + media_data.title) 

            if len(text_track) > 14:
                text_track = text_track + "       "
            text_string = get_bidi(text_track) if media_data.artist else get_bidi(media_data.title)
            dir = 1 if has_bidi(text_string) else 0
            brightness_factor = 50
            try:
                color_font_rgb = tuple(min(255, c + brightness_factor) for c in background_color_rgb)
                color_font = '#%02x%02x%02x' % color_font_rgb
            except Exception as e:
                _LOGGER.error(f"Error calculating color_font: {e}")
                color_font = '#ffff00'
            
            moreinfo = {
                "Command": "Draw/SendHttpItemList",
                "ItemList": []
            }

            if text_string and self.config.show_text and not media_data.radio_logo and not media_data.playing_tv and not self.config.special_mode:
                textid +=1
                text_temp = { 
                    "TextId":textid, "type":22, "x":0, "y":48, 
                    "dir":dir, "font":2, "TextWidth":64, "Textheight":16, 
                    "speed":100, "align":2, "TextString": text_string, "color":color_font 
                }
                moreinfo["ItemList"].append(text_temp)

            if (self.config.show_clock and not self.config.special_mode):
                textid +=1
                x = 44 if self.config.clock_align == "Right" else 3
                clock_item =  { 
                    "TextId":textid, "type":5, "x":x, "y":3, 
                    "dir":0, "font":18, "TextWidth":32, "Textheight":16, 
                    "speed":100, "align":1, "color":color_font 
                }
                moreinfo["ItemList"].append(clock_item)
                
            if (self.config.temperature or self.config.temperature_ha) and not self.config.special_mode:
                textid +=1
                x = 3 if self.config.clock_align == "Right" else 48
                if self.config.temperature and not media_data.temperature:
                    temperature = { "TextId": textid, "type":17, "x":x, "y":3,
                        "dir":0, "font":18, "TextWidth":20, "Textheight":6,
                        "speed":100, "align":1, "color": color_font }
                    moreinfo["ItemList"].append(temperature)
                elif media_data.temperature:
                    temperature = { "TextId": textid, "type":22, "x":x, "y":3,
                        "dir":0, "font":18, "TextWidth":20, "Textheight":6,
                        "speed":100, "align":1, "color": color_font, "TextString": media_data.temperature }
                    moreinfo["ItemList"].append(temperature)

            if (self.config.show_text or self.config.show_clock or self.config.temperature) and not (self.config.show_lyrics or self.config.spotify_slide or self.config.special_mode):
                await self.pixoo_device.send_command(moreinfo)
                return

            if self.config.special_mode:
                day = {
                    "TextId":1, "type":14, "x":4, "y":1,
                    "dir":0, "font":18, "TextWidth":33,
                    "Textheight":6, "speed":100, "align":1,
                    "color": color_font }
                
                clock = { "TextId":2, "type":5, "x":0, "y":1,
                    "dir":0, "font":18, "TextWidth":64,
                    "Textheight":6, "speed":100, "align":2,
                    "color": background_color }

                if media_data.temperature:
                    temperature = { "TextId": 3, "type":22, "x":46, "y":1,
                        "dir":0, "font":18, "TextWidth":20, "Textheight":6,
                        "speed":100, "align":1, "color": color_font, "TextString": media_data.temperature }
                else:
                    temperature = { "TextId":4, "type":17, "x":46, "y":1,
                    "dir":0, "font":18, "TextWidth":20, "Textheight":6,
                    "speed":100, "align":3, "color": color_font }
                
                dir = 1 if has_bidi(media_data.artist) else 0
                text = get_bidi(media_data.artist) if dir == 1 else media_data.artist
                artist = {
                    "TextId":4, "type":22, "x":0, "y":42,
                    "dir": dir, "font":190, "TextWidth":64,
                    "Textheight":16, "speed":100, "align":2,
                    "TextString": text, "color": color_font }
                
                dir = 1 if has_bidi(media_data.title) else 0
                text = get_bidi(media_data.title) if dir == 1 else media_data.title
                title = {
                    "TextId":5, "type":22, "x":0, "y":52, "dir": dir,
                    "font": 190, #2, 4, 32, 52, 58, 62, 158, 186, 190, 590
                    "TextWidth":64, "Textheight":16, "speed":100, "align":2,
                    "TextString": text, "color": background_color }

                moreinfo["ItemList"].append(day)
                moreinfo["ItemList"].append(clock)
                moreinfo["ItemList"].append(temperature)
                if (self.config.show_text and not media_data.playing_tv) or (media_data.spotify_slide_pass and self.config.spotify_slide):
                    moreinfo["ItemList"].append(artist)
                    moreinfo["ItemList"].append(title)
                await self.pixoo_device.send_command(moreinfo)

        except asyncio.CancelledError:
            _LOGGER.info("Image processing task cancelled.")
        except Exception as e:
            _LOGGER.error(f"Error in _process_and_display_image: {str(e)}\n{traceback.format_exc()}")
        finally:
            self.current_image_task = None # Reset the task variable

    async def control_light(self, action, background_color_rgb=None, is_night=True):
        if not is_night and self.config.wled_only_at_night:
            return
        service_data = {'entity_id': self.config.light}
        if action == 'on':
            service_data.update({'rgb_color': background_color_rgb, 'transition': 1, })
        try:
            await self.call_service(f'light/turn_{action}', **service_data)
        except Exception as e:
            _LOGGER.error(f"Light Error: {self.config.light} - {e}\n{traceback.format_exc()}")

    async def control_wled_light(self, action, color1=False, color2=False, color3=False, is_night=True):
        # Ensure we control the light only if time conditions and settings allow
        if not is_night and self.config.wled_only_at_night:
            return

        ip_address = self.config.wled

        if not ip_address:
            _LOGGER.warning(f"IP address provided for WLED light control is invalid: {ip_address}")
            return
        
        effect_id = self.config.wled_effect
        # Validate the effect ID
        if not (0 <= effect_id <= 117):  # Ensure the effect ID is within the valid range
            _LOGGER.error(f"Invalid effect ID: {effect_id}. Must be between 0 and 117.")
            return

        # Prepare the segment dictionary based on effect requirements
        segment = {"fx": effect_id} 

        # Add colors based on effect requirements
        #if effect_id in { 0, 1, 2, 3, 6, 7, 38, 54, 87, 92, 105, 56, 55, 39, 9, 26, 86, 8, 42, 17, 79, 50}:
        if effect_id:
            if effect_id == 0:  # Solid effect uses only one color
                segment["col"] = [color1]
            else:
                segment["col"] = [color1, color2, color3]

        # Add speed if the effect supports it
        #if effect_id in {2, 3, 6, 7, 8, 38, 9, 42, 105, 56, 55, 86, 92, 50, 79, 17, 26, 87}:
        if self.config.wled_effect_speed:
            segment["sx"] = self.config.wled_effect_speed

        # Add intensity if the effect supports it
        #if effect_id in {2, 7, 38, 42, 105, 56, 55, 79, 17, 86}:
        if self.config.wled_effect_intensity:
            segment["ix"] = self.config.wled_effect_intensity

        #if effect_id in { 8, 38, 42, 67, 87, 54, 55, 56}:
        if self.config.wled_pallete:
            segment["pal"] = self.config.wled_pallete

        if self.config.wled_sound_effect:
            segment["si"] = self.config.wled_sound_effect

        # Prepare the JSON payload
        payload = {"on": True, "bri": self.config.wled_brightness, "seg": [segment]}

        if action == "off":
            payload = {"on": False}  # Off action simply turns off the light
        url = f"http://{ip_address}/json/state"
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            try:
                async with session.post(url, json=payload) as response:
                    response.raise_for_status()  # Raise an error for bad status codes
                    #_LOGGER.info(f"WLED control command sent successfully to {ip_address}")
            except aiohttp.ClientError as e:
                _LOGGER.error(f"Error sending WLED control command: {e}")


    def create_payloads(self, artist, title, x):
        artist_lines = split_string(artist, x)
        title_lines = split_string(title, x)
        all_lines = artist_lines + title_lines
        moreinfo = {
                "Command": "Draw/SendHttpItemList",
                "ItemList": []
            }
        if len(all_lines) > 5:
            all_lines[4] += ' ' + ' '.join(all_lines[5:])
            all_lines = all_lines[:5]
        
        start_y = (64 - len(all_lines) * 12) // 2
        item_list = []
        for i, line in enumerate(all_lines):
            text_string = line if not has_bidi(line) else get_bidi(line)
            y = start_y + (i * 12)
            dir = 1 if has_bidi(line) else 0
            item_list.append({
                "TextId": i + 1, "type": 22,
                "x": 0, "y": y,
                "dir": dir, "font": 190,
                "TextWidth": 64, "Textheight": 16,
                "speed": 100, "align": 2,
                "TextString": text_string,
                "color": "#a0e5ff" if i < len(artist_lines) else "#f9ffa0",
            })

        payloads = {
            "Command": "Draw/SendHttpItemList",
            "ItemList": item_list
        }
        return payloads

    async def calculate_position(self, kwargs):
        await LyricsProvider(self.config, self.image_processor).calculate_position(self.media_data, self)
