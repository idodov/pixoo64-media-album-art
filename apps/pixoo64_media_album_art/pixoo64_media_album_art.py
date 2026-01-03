"""
Divoom Pixoo64 Album Art Display
--------------------------------
This script automatically displays the album art of the currently playing track on your Divoom Pixoo64 screen.
Additionally, this script supports AI-based image creation. It is designed to generate and display alternative album cover art when the original art is unavailable or when using music services (like SoundCloud) from which the script cannot retrieve album art.

APPDAEMON CONFIGURATION
# Required python packages (pillow is mandatory while unidecode and python-bidi are opotinal. unidecode design to support special characters in burned mode. Python-bidi used to display RTL texts like Arabic or Hebrew exc,):
python_packages:
    - pillow
    - unidecode
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
        lyrics_sync_entity: "input_number.pixoo64_album_art_lyrics_sync"    # Lyics sync
        mode_select: "input_select.pixoo64_album_art_display_mode"          # A sensor to store display modes
        crop_select: "input_select.pixoo64_album_art_crop_mode"             # A sensor to store the crop display modes
        temperature_sensor: "sensor.temperature"    # HomeAssistant Temperature sensor name instead of the Divoom weather.
        light: "light.living_room"                  # The entity ID of an RGB light to synchronize with the album art colors.
        ai_fallback: "turbo"                        # The AI model to use for generating alternative album art when needed (supports 'flux' or 'turbo').
        force_ai: False                             # If True, only AI-generated images will be displayed all the time.
        musicbrainz: True                           # If True, attempts to find a fallback image on MusicBrainz if other sources fail.
        spotify_client_id: False                    # Your Spotify API client ID (needed for Spotify features). Obtain from https://developers.spotify.com
        spotify_client_secret: False                # Your Spotify API client secret (needed for Spotify features).
        tidal_client_id: False                      # Your TIDAL API client ID. Obrain from https://developer.tidal.com/dashboard
        tidal_client_secret: False                  # Your TIDAL client secret.
        last.fm: False                              # Your Last.fm API key. Obtain from https://www.last.fm/api/account/create
        discogs: False                              # Your Discogs API key. Obtain from https://www.discogs.com/settings/developers
        pollinations: False                         # Your pollinations API key. Obtain from https://pollinations.ai/
    pixoo:
        url: "192.168.86.21"                        # The IP address of your Pixoo64 device.
        full_control: True                          # If True, the script will control the Pixoo64's on/off state in sync with the media player's play/pause.
        contrast: True                              # If True, applies a 50% contrast filter to the images displayed on the Pixoo.
        sharpness: False                            # If True, add sharpness effect.
        colors: False                               # If True, enhanced colors.
        kernel: False                               # If True, add embos/edge effect.
        special_mode: False                         # Show day, time and temperature above in upper bar.
        info: False                                 # Show information while fallback.
        temperature: True                           # Show temeprature
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
            force_font_color: False                 # Or HEX value, example: "#000000" for black or "#FFFFFF" for white.
            top_text: True                          # If True, show text (Artist/Title) at the top bar
        crop_borders:
            enabled: True                           # If True, attempts to crop any borders from the album art.
            extra: True                             # If True, applies an enhanced border cropping algorithm.
    wled:
        wled_ip: "192.168.86.55"                    # Your WLED IP Adress
        brightness: 255                             # 0 to 255
        effect: 38                                  # 0 to 186 (Effect ID - https://kno.wled.ge/features/effects/)
        effect_speed: 50                            # 0 to 255
        effect_intensity: 128                       # 0 to 255
        palette: 0                                  # 0 to 70 (palette ID - https://kno.wled.ge/features/palettes/)
        sound_effect: 0                             # Setting of the sound simulation type for audio enhanced effects (0: 'BeatSin', 1: 'WeWillRockYou', 2: '10_3', 3: '14_3')
        only_at_night: False                        # Runs only at night hours
"""

import aiohttp
import asyncio
import base64
import json
import logging
import math
import random
import re
import sys
import time
import textwrap 
import urllib.parse
from appdaemon.plugins.hass import hassapi as hass
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

# Third-party library imports
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont, UnidentifiedImageError

try:
    from unidecode import unidecode
    unidecode_support = True
except ImportError:
    unidecode_support = False

try:
    from bidi import get_display
    bidi_support = True
except ImportError:
    bidi_support = False

_LOGGER = logging.getLogger(__name__)

# --- CONSTANTS & REGEX ---

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

BIDI_REGEX_PATTERN = f"[{HEBREW}|{ARABIC}|{SYRIAC}|{THAANA}|{NKOO}|{RUMI}|{ARABIC_MATH}|{SYMBOLS}|{OLD_PERSIAN_PHAISTOS}|{SAMARITAN}]"
BIDI_REGEX = re.compile(BIDI_REGEX_PATTERN)

# High-visibility colors
COLOR_PALETTE = [
    (255, 51, 51), (255, 99, 71), (255, 140, 0),    # Bright Reds/Oranges
    (255, 215, 0), (255, 255, 0),                   # Golds/Yellows
    (173, 255, 47), (127, 255, 0), (50, 205, 50),   # Bright Greens
    (0, 255, 255), (0, 191, 255), (30, 144, 255),   # Cyans/Light Blues
    (238, 130, 238), (255, 0, 255), (255, 20, 147), # Magentas/Pinks
    (255, 255, 255)                                 # White
]

# --- HELPERS ---
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
        except Image.Error:
            pass
    return img

def format_memory_size(size_in_bytes):
    if size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.2f} KB"
    return f"{size_in_bytes / (1024 * 1024):.2f} MB"

def get_bidi(text):
    if not bidi_support:
        return text
    return get_display(text)

def has_bidi(text):
    if not text: return False
    return bool(BIDI_REGEX.search(text))

def ensure_rgb(img):
    try:
        if img and img.mode != "RGB":
            img = img.convert("RGB")
        return img
    except (UnidentifiedImageError, OSError):
        return None

class Config:
    SENSOR_NAME = 'pixoo64_album_art'
    SECTION_DEFAULTS: Dict[str, Dict[str, Any]] = {
        'home_assistant': {
            'media_player': 'media_player.living_room',
            'toggle': 'input_boolean.' + SENSOR_NAME,
            'ha_url': 'http://homeassistant.local:8123',
            'pixoo_sensor': 'sensor.pixoo64_media_data',
            'mode_entity': ('mode_select', 'input_select.' + SENSOR_NAME + '_display_mode'),
            'crop_entity': ('crop_select', 'input_select.' + SENSOR_NAME + '_crop_mode'),
            'lyrics_sync_entity': ('input_number.' + SENSOR_NAME + '_lyrics_sync'),
            'temperature_sensor': None,
            'light': None,
            'force_ai': False,
            'ai_fallback': 'turbo',
            'musicbrainz': True,
            'spotify_client_id': None,
            'spotify_client_secret': None,
            'tidal_client_id': None,
            'tidal_client_secret': None,
            'discogs': None,
            'lastfm': ('last.fm', None),
            'pollinations': None,
        },
        'pixoo': {
            'url': None,
            'full_control': True,
            'contrast': False,
            'sharpness': False,
            'colors': False,
            'kernel': False,
            'special_mode': False,
            'info': False,
            'show_clock': ('clock', False),
            'clock_align': 'Right',
            'temperature': False,
            'tv_icon_pic': ('tv_icon', True),
            'spotify_slide': False,
            'images_cache': 25,
            'limit_color': ('limit_colors', None),
            'show_lyrics': ('lyrics', False),
            'lyrics_font': 190,
            'lyrics_sync': -1 
        },
        'show_text': { 
            'show_text': ('enabled', False),
            'clean_title': ('clean_title', True),
            'text_bg': ('text_background', True),
            'special_mode_spotify_slider': False,
            'force_font_color': None, 
            'burned': False,
            'top_text': False,
        },
        'crop_borders': { 
            'crop_borders': ('enabled', False),
            'crop_extra': ('extra', False),
        },
        'wled': {
            'wled': ('wled_ip', None),
            'brightness': 255,
            'effect': 38,
            'effect_speed': 60,
            'effect_intensity': 128,
            'only_at_night': False,
            'palette': 0,
            'sound_effect': 0,
        },
    }

    NESTED_YAML_STRUCTURE_MAP: Dict[str, str] = {
        'show_text': 'pixoo',
        'crop_borders': 'pixoo',
    }

    def __init__(self, app_args: Dict[str, Any]):
        for section_key_in_defaults, defaults_for_section in self.SECTION_DEFAULTS.items():
            user_data_for_this_section = {}
            parent_yaml_key = self.NESTED_YAML_STRUCTURE_MAP.get(section_key_in_defaults)

            if parent_yaml_key:
                parent_config_from_yaml = app_args.get(parent_yaml_key, {})
                user_data_for_this_section = parent_config_from_yaml.get(section_key_in_defaults, {})
            else:
                user_data_for_this_section = app_args.get(section_key_in_defaults, {})

            for attr_name_in_class, default_spec in defaults_for_section.items():
                if isinstance(default_spec, tuple):
                    yaml_key_in_user_data, default_value = default_spec
                else:
                    yaml_key_in_user_data, default_value = attr_name_in_class, default_spec
                
                setattr(self, attr_name_in_class, user_data_for_this_section.get(yaml_key_in_user_data, default_value))

        self.images_cache = max(1, min(int(self.images_cache) if self.images_cache is not None else 1, 300))
        self.sound_effect = max(0, min(int(self.sound_effect) if self.sound_effect is not None else 0, 3))

        self._fix_config_args(getattr(self, 'url', None))
        self._validate_config()

        self.original_crop_borders = self.crop_borders
        self.original_crop_extra = self.crop_extra
        self.original_show_lyrics = self.show_lyrics
        self.original_spotify_slide = self.spotify_slide
        self.original_special_mode = self.special_mode
        self.original_special_mode_spotify_slider = self.special_mode_spotify_slider
        self.original_show_clock = self.show_clock
        self.original_temperature = self.temperature
        self.original_show_text = self.show_text
        self.original_text_bg = self.text_bg
        self.original_force_ai = self.force_ai
        self.original_full_control = self.full_control
        self.original_ai_fallback = self.ai_fallback
        self.original_burned = self.burned
        self.original_top = self.top_text

    def _fix_config_args(self, pixoo_url_raw: Optional[str]):
        if pixoo_url_raw:
            pixoo_url = f"http://{pixoo_url_raw}" if not pixoo_url_raw.startswith('http') else pixoo_url_raw
            self.pixoo_url: str = f"{pixoo_url}:80/post" if not pixoo_url.endswith(':80/post') else pixoo_url
        else:
            self.pixoo_url = None

        if self.ai_fallback not in ["flux", "turbo"]:
            self.ai_fallback = "turbo"

    def _validate_config(self):
        if not self.pixoo_url:
            _LOGGER.error("Pixoo IP address is MISSING.")
            return

        if hasattr(self, 'force_font_color'):
            current_color_val = self.force_font_color
            if current_color_val is False:
                self.force_font_color = None
            elif isinstance(current_color_val, str):
                if len(current_color_val) == 6:
                    self.force_font_color = "#" + current_color_val
                elif not current_color_val.startswith('#'):
                    self.force_font_color = None

class PixooDevice:
    """Handles communication with the Divoom Pixoo device.""" 

    def __init__(self, config: "Config", session: aiohttp.ClientSession): 
        self.config = config
        self.session = session
        self.select_index: Optional[int] = None 
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Connection": "keep-alive",
            "User-Agent": "PixooClient/1.0"
        }

    async def send_command(self, payload_command: dict) -> None: 
        try:
            async with self.session.post(
                self.config.pixoo_url,
                headers=self.headers,
                json=payload_command,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    response_text = await response.text() 
                    _LOGGER.error(f"Failed to send command to Pixoo. Status: {response.status}, Response: {response_text}") 
                else:
                    await asyncio.sleep(0.15) 
        except aiohttp.ClientError as e: 
            _LOGGER.error(f"Error sending command to Pixoo: {e}") 
        except asyncio.TimeoutError: 
            _LOGGER.error(f"Timeout sending command to Pixoo after 10 seconds.") 
        except Exception as e: 
            _LOGGER.exception(f"Unexpected error sending command to Pixoo: {e}") 

    async def get_current_channel_index(self) -> int: 
        channel_command = {
            "Command": "Channel/GetIndex"
        }
        try:
            async with self.session.post(
                self.config.pixoo_url,
                headers=self.headers,
                json=channel_command,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                response.raise_for_status() 
                response_text = await response.text()
                response_data = json.loads(response_text)
                return response_data.get('SelectIndex', 0)
        except aiohttp.ClientError as e: 
            _LOGGER.error(f"Failed to get channel index from Pixoo: {e}") 
        except json.JSONDecodeError as e: 
            _LOGGER.error(f"Failed to decode JSON response when getting channel index: {e}") 
        except asyncio.TimeoutError: 
            _LOGGER.error(f"Timeout getting channel index from Pixoo after 5 seconds.") 
        except Exception as e: 
            _LOGGER.exception(f"Unexpected error getting channel index from Pixoo: {e}") 
        return 1  # Default fallback value

class ImageProcessor:
    """Processes images for display on the Pixoo64 device, including caching and filtering.""" 
    def __init__(self, config: "Config", session: aiohttp.ClientSession): 
        self.config = config
        self.session = session
        self.image_cache: OrderedDict[str, dict] = OrderedDict() 
        self.cache_size: int = config.images_cache 
        
    @property
    def _cache_size(self) -> int: 
        return len(self.image_cache)

    def _calculate_item_size(self, item: dict) -> int: 
        size = 0
        if isinstance(item, dict):
            for key, value in item.items():
                if key == 'pil_image': 
                    size += 64 * 64 * 3 
                elif isinstance(value, str):
                    size += len(value)
                elif isinstance(value, (int, float, bool)):
                    size += 8
        return size

    def _calculate_cache_memory_size(self) -> float:
        total_size = 0
        for item in self.image_cache.values():
            total_size += self._calculate_item_size(item)
        return total_size

    async def get_image(self, picture: Optional[str], media_data: "MediaData", spotify_slide: bool = False) -> Optional[dict]: 
        if not picture:
            return None

        if media_data.album and media_data.album not in ["None", "", None]:
            cache_key = f"{media_data.artist} - {media_data.album}"
        else:
            cache_key = picture

        use_cache = not spotify_slide and not media_data.playing_tv and not self.config.burned
        cached_data = None

        if use_cache and cache_key in self.image_cache:
            cached_data = self.image_cache.pop(cache_key)
            self.image_cache[cache_key] = cached_data
        else:
            try:
                url = picture if picture.startswith('http') else f"{self.config.ha_url}{picture}"
                async with self.session.get(url, timeout=30) as response: 
                    response.raise_for_status() 
                    image_data = await response.read()
                    
                    cached_data = await self.process_image_data(image_data, media_data)
                    
                    if cached_data and not spotify_slide:
                        if len(self.image_cache) >= self.cache_size:
                            self.image_cache.popitem(last=False)
                        self.image_cache[cache_key] = cached_data
                        
                        memory_size = self._calculate_cache_memory_size()
                        media_data.image_cache_memory = format_memory_size(memory_size)
                        media_data.image_cache_count = self._cache_size
            except Exception as e: 
                _LOGGER.error(f"Error fetching/processing image: {e}") 
                return None

        if not cached_data:
            return None

        final_img = cached_data['pil_image'].copy()
        final_img = self.text_clock_img(final_img, cached_data['brightness_lower_part'], media_data)
        
        if self.config.info:
            lpc = (0, 10, 64, 30)
            lower_part_img = final_img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(0.4)
            final_img.paste(lower_part_img, lpc)
            media_data.info_img = self.gbase64(final_img)

        base64_result = self.gbase64(final_img)

        return {
            'base64_image': base64_result,
            **cached_data 
        }

    async def process_image_data(self, image_data: bytes, media_data: "MediaData") -> Optional[dict]: 
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            try: 
                result = await loop.run_in_executor(executor, self._process_image, image_data, media_data)
                return result
            except Exception as e: 
                _LOGGER.exception(f"Error during thread pool image processing: {e}") 
                return None

    def _process_image(self, image_data: bytes, media_data: "MediaData") -> Optional[dict]: 
        try:
            with Image.open(BytesIO(image_data)) as img:
                img = ensure_rgb(img)
                img = self.fixed_size(img)

                if (self.config.crop_borders or self.config.special_mode) and not media_data.radio_logo:
                    img = self.crop_image_borders(img, media_data.radio_logo)

                if self.config.contrast or self.config.sharpness or self.config.colors or self.config.kernel or self.config.limit_color:
                    img = self.filter_image(img)

                if self.config.burned and not media_data.radio_logo:
                    img = self._draw_burned_text(img, media_data.artist, media_data.title_clean)

                img = self.special_mode(img) if self.config.special_mode else img.resize((64, 64), Image.Resampling.BILINEAR)
                
                vals = self.img_values(img)
                font_color = vals['font_color']
                brightness = vals['brightness']
                brightness_lower_part = vals['brightness_lower_part']
                background_color = vals['background_color']
                background_color_rgb = vals['background_color_rgb']
                most_common_color_alternative_rgb = vals['most_common_color_alternative_rgb']
                most_common_color_alternative = vals['most_common_color_alternative']
                color1 = vals['color1']
                color2 = vals['color2']
                color3 = vals['color3']

                media_data.lyrics_font_color = self.get_optimal_font_color(img) if self.config.show_lyrics or self.config.info else "#FFA000"
                media_data.color1 = color1
                media_data.color2 = color2
                media_data.color3 = color3

                return {
                    'pil_image': img, 
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
            _LOGGER.error(f"Error processing image: {e}") 
            return None

    def fixed_size(self, img: Image.Image) -> Image.Image: 
        width, height = img.size
        if width == height:
            return img
        elif height < width:
            border_size = (width - height) // 2
            try:
                background_color = img.getpixel((0, 0)) 
            except Exception: 
                background_color = (0, 0, 0)
            new_img = Image.new("RGB", (width, width), background_color)
            new_img.paste(img, (0, border_size))
            img = new_img
        elif width != height:
            new_size = min(width, height)
            left = (width - new_size) // 2
            top = (height - new_size) // 2
            img = img.crop((left, top, left + new_size, top + new_size))
        return img

    def filter_image(self, img: Image.Image) -> Image.Image: 
        img = img.resize((64, 64), Image.Resampling.BILINEAR)

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

    def special_mode(self, img: Image.Image) -> Image.Image: 
        if img is None: return None

        output_size = (64, 64)
        album_size = (34, 34) if self.config.show_text else (56, 56)
        
        album_art = img.resize(album_size, Image.Resampling.BILINEAR)

        try: 
            left_color = album_art.getpixel((0, album_size[1] // 2))
            right_color = album_art.getpixel((album_size[0] - 1, album_size[1] // 2))
        except Exception: 
            left_color = (100, 100, 100) 
            right_color = (150, 150, 150) 

        dark_background_color = (
            min(left_color[0], right_color[0]) // 2,
            min(left_color[1], right_color[1]) // 2,
            min(left_color[2], right_color[2]) // 2
        )
        if album_size == (34, 34):
            dark_background_color = (0, 0, 0)
        background = Image.new('RGB', output_size, dark_background_color)

        x = (output_size[0] - album_size[0]) // 2
        y = 8 

        if album_size == (34, 34):
            for i in range(x):
                gradient_color = (
                    int(left_color[0] * (x - i) / x),
                    int(left_color[1] * (x - i) / x),
                    int(left_color[2] * (x - i) / x)
                )
                for j in range(y, y + album_size[1]):
                    background.putpixel((i, j), gradient_color)

            for i in range(x + album_size[0], output_size[0]):
                gradient_color = (
                    int(right_color[0] * (i - (x + album_size[0])) / (output_size[0] - (x + album_size[0]))),
                    int(right_color[1] * (i - (x + album_size[0])) / (output_size[0] - (x + album_size[0]))),
                    int(right_color[2] * (i - (x + album_size[0])) / (output_size[0] - (x + album_size[0])))
                )
                for j in range(y, y + album_size[1]):
                    background.putpixel((i, j), gradient_color)

        background.paste(album_art, (x, y))
        return background

    def gbase64(self, img: Image.Image) -> Optional[str]: 
        try:
            raw_data = img.tobytes()
            b64 = base64.b64encode(raw_data)
            return b64.decode("utf-8")
        except Exception as e: 
            _LOGGER.error(f"Error converting image to base64: {e}") 
            return None

    def text_clock_img(self, img: Image.Image, brightness_lower_part: float, media_data: "MediaData") -> Image.Image: 
        if media_data.playing_tv or self.config.special_mode or self.config.spotify_slide:
            return img

        if media_data.lyrics and self.config.show_lyrics and self.config.text_bg and brightness_lower_part != None and not media_data.playing_radio:
            enhancer_lp = ImageEnhance.Brightness(img)
            img = enhancer_lp.enhance(0.55)  
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(0.5)
            return img

        # 1. Clock Background
        if bool(self.config.show_clock and self.config.text_bg) and not self.config.show_lyrics:
            if self.config.top_text:
                # Text is Top, so Clock is Bottom (y=55 to y=62)
                lpc = (43, 55, 62, 62) if self.config.clock_align == "Right" else (2, 55, 21, 62)
            else:
                # Default: Clock is Top (y=2 to y=9)
                lpc = (43, 2, 62, 9) if self.config.clock_align == "Right" else (2, 2, 21, 9)
            
            lower_part_img = img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(0.3)
            img.paste(lower_part_img, lpc)

        # 2. Temperature Background
        if bool(self.config.temperature and self.config.text_bg) and not self.config.show_lyrics:
            if self.config.top_text:
                # Text is Top, so Temp is Bottom (y=55 to y=62)
                lpc = (2, 55, 18, 62) if self.config.clock_align == "Right" else (47, 55, 63, 62)
            else:
                # Default: Temp is Top (y=2 to y=9)
                lpc = (2, 2, 18, 9) if self.config.clock_align == "Right" else (47, 2, 63, 9)
                
            lower_part_img = img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(0.3)
            img.paste(lower_part_img, lpc)

        # 3. Text (Artist/Title) Background
        if self.config.text_bg and self.config.show_text and not self.config.show_lyrics and not media_data.playing_tv:
            if self.config.top_text:
                # Text is Top (y=0 to y=16)
                lpc = (0, 0, 64, 16)
            else:
                # Default: Text is Bottom (y=48 to y=64)
                lpc = (0, 48, 64, 64)
                
            lower_part_img = img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(brightness_lower_part)
            img.paste(lower_part_img, lpc)
            
        return img

    def img_values(self, img: Image.Image) -> dict: 
        full_img = img
        font_color = '#ff00ff'
        brightness = 0.67
        brightness_lower_part = 0.0
        background_color = (255, 255, 0)
        background_color_rgb = (0, 0, 255)
        most_common_color_alternative_rgb = (0,0,0)
        most_common_color_alternative = '#000000'

        lower_part = img.crop((3, 48, 61, 61))
        
        most_common_colors_lower_part_raw = lower_part.getcolors(maxcolors=4096)
        if most_common_colors_lower_part_raw:
            most_common_colors_lower_part = [(c[1], c[0]) for c in most_common_colors_lower_part_raw]
            most_common_colors_lower_part.sort(key=lambda x: x[1], reverse=True)
        else:
            most_common_colors_lower_part = []

        most_common_color = self.most_vibrant_color(most_common_colors_lower_part)
        opposite_color = tuple(255 - i for i in most_common_color)
        opposite_color_brightness = int(sum(opposite_color) / 3)
        brightness_lower_part = round(1 - opposite_color_brightness / 255, 2) if 0 <= opposite_color_brightness <= 255 else 0
        font_color = self.get_optimal_font_color(lower_part)

        small_temp_img = full_img.resize((16, 16), Image.Resampling.BILINEAR)
        
        most_common_colors_raw = small_temp_img.getcolors(maxcolors=256)
        if most_common_colors_raw:
            most_common_colors = [(c[1], c[0]) for c in most_common_colors_raw]
            most_common_colors.sort(key=lambda x: x[1], reverse=True)
        else:
            most_common_colors = []

        most_common_color_alternative_rgb = self.most_vibrant_color(most_common_colors)
        most_common_color_alternative = f'#{most_common_color_alternative_rgb[0]:02x}{most_common_color_alternative_rgb[1]:02x}{most_common_color_alternative_rgb[2]:02x}'
        background_color_rgb = self.most_vibrant_color(most_common_colors)
        background_color = f'#{background_color_rgb[0]:02x}{background_color_rgb[1]:02x}{background_color_rgb[2]:02x}'
        brightness = int(sum(most_common_color_alternative_rgb) / 3)

        if self.config.wled:
            color1_hex, color2_hex, color3_hex = self.most_vibrant_colors_wled(small_temp_img)
        else:
            color1_hex, color2_hex, color3_hex = ('#000000', '#000000', '#000000')

        return {
            'font_color': font_color,
            'brightness': brightness,
            'brightness_lower_part': brightness_lower_part,
            'background_color': background_color,
            'background_color_rgb': background_color_rgb,
            'most_common_color_alternative_rgb': most_common_color_alternative_rgb,
            'most_common_color_alternative': most_common_color_alternative,
            'color1': color1_hex, 
            'color2': color2_hex, 
            'color3': color3_hex
        }

    def most_vibrant_color(self, most_common_colors: list[tuple[tuple[int, int, int], int]]) -> tuple[int, int, int]: 
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

    def rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'

    def is_strong_color(self, color: tuple[int, int, int]) -> bool: 
        return any(c > 220 for c in color)

    def color_distance(self, color1: tuple[int, int, int], color2: tuple[int, int, int]) -> float: 
        return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color1, color2)))

    def is_vibrant_color(self, r: int, g: int, b: int) -> bool: 
        return (max(r, g, b) - min(r, g, b) > 50)

    def generate_close_but_different_color(self, existing_colors: list[tuple[tuple[int, int, int], int]]) -> tuple[int, int, int]: 
        if not existing_colors:
            return (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
        avg_r = sum(c[0] for c, _ in existing_colors) // len(existing_colors)
        avg_g = sum(c[1] for c, _ in existing_colors) // len(existing_colors)
        avg_b = sum(c[2] for c, _ in existing_colors) // len(existing_colors)
        while True:
            new_color = (
                max(0, min(255, avg_r + random.randint(-40, 40))),
                max(0, min(255, avg_g + random.randint(-40, 40))),
                max(0, min(255, avg_b + random.randint(-40, 40)))
            )
            is_distinct = True
            for existing_color, _ in existing_colors:
                if self.color_distance(new_color, existing_color) < 50:
                    is_distinct = False
                    break
            if is_distinct:
                return new_color

    def color_score(self, color_count: tuple[tuple[int, int, int], int]) -> float: 
        color, count = color_count
        max_val = max(color)
        min_val = min(color)
        saturation = (max_val - min_val) / max_val if max_val > 0 else 0
        return count * saturation

    def most_vibrant_colors_wled(self, full_img: Image.Image) -> tuple[str, str, str]: 
        enhancer = ImageEnhance.Contrast(full_img)
        full_img = enhancer.enhance(2.0)
        enhancer = ImageEnhance.Color(full_img)
        full_img = enhancer.enhance(3.0) 
        
        color_counts_raw = full_img.getcolors(maxcolors=1024)
        if not color_counts_raw:
            return "#000000", "#000000", "#000000"

        most_common_colors = [(c[1], c[0]) for c in color_counts_raw]
        most_common_colors.sort(key=lambda x: x[1], reverse=True)
        most_common_colors = most_common_colors[:50]

        vibrant_colors = [(color, count) for color, count in most_common_colors if self.is_vibrant_color(*color)]
        vibrant_colors.sort(key=self.color_score, reverse=True)
        selected_colors = []
        for color, _ in vibrant_colors:
            if self.is_strong_color(color):
                is_similar = False
                for selected_color, _ in selected_colors:
                    if self.color_distance(color, selected_color) < 50: 
                        is_similar = True
                        break
                if not is_similar:
                    selected_colors.append((color, _))
                    if len(selected_colors) == 3:
                        break
        if len(selected_colors) < 3: 
                for color, _ in vibrant_colors:
                    is_similar = False
                    if not self.is_strong_color(color):
                        for selected_color, _ in selected_colors:
                            if self.color_distance(color, selected_color) < 50: 
                                is_similar = True
                                break
                        if not is_similar:
                            selected_colors.append((color, _))
                            if len(selected_colors) == 3:
                                break
        while len(selected_colors) < 3:
            new_color = self.generate_close_but_different_color(selected_colors)
            selected_colors.append((new_color, 1))
        return self.rgb_to_hex(selected_colors[0][0]), self.rgb_to_hex(selected_colors[1][0]), self.rgb_to_hex(selected_colors[2][0])

    def get_optimal_font_color(self, img: Image.Image) -> str: 
        if self.config.force_font_color:
            return self.config.force_font_color
        
        small_img = img.resize((16, 16), Image.Resampling.BILINEAR)
        image_palette = set(small_img.getdata())
        
        # Helper to calculate brightness
        def get_brightness(c):
            return (c[0] * 299 + c[1] * 587 + c[2] * 114) / 1000

        def is_distinct_color(color: tuple[int, int, int], threshold: int = 110) -> bool: 
            return all(self.color_distance(color, img_color) > threshold for img_color in image_palette) 
        
        candidate_colors = list(COLOR_PALETTE)
        random.shuffle(candidate_colors)
        
        best_color = None
        max_saturation = -1 
        
        for font_color in candidate_colors:
            text_brightness = get_brightness(font_color)

            if text_brightness < 150:
                continue

            if is_distinct_color(font_color, threshold=80): # Lowered threshold slightly to allow more matches
                r, g, b = font_color
                max_val = max(r, g, b)
                min_val = min(r, g, b)
                saturation = (max_val - min_val) / max_val if max_val != 0 else 0
                
                if saturation > max_saturation:
                    max_saturation = saturation
                    best_color = font_color

        if best_color:
            return f'#{best_color[0]:02x}{best_color[1]:02x}{best_color[2]:02x}'
        
        return '#ffffff'

    def get_dominant_border_color(self, img: Image.Image) -> tuple[int, int, int]:
        width, height = img.size
        if width == 0 or height == 0:
            return (0, 0, 0)
        img_rgb = img if img.mode == "RGB" else img.convert("RGB")
        all_border_pixels = []
        if height > 0 and width > 0:
            top_row_img = img_rgb.crop((0, 0, width, 1))
            all_border_pixels.extend(list(top_row_img.getdata()))
        if height > 1 and width > 0:
            bottom_row_img = img_rgb.crop((0, height - 1, width, height))
            all_border_pixels.extend(list(bottom_row_img.getdata()))
        start_y_for_cols = 1 if height > 1 else 0
        end_y_for_cols = height - 1 if height > 1 else height
        if width > 0 and end_y_for_cols > start_y_for_cols : 
            left_col_img = img_rgb.crop((0, start_y_for_cols, 1, end_y_for_cols))
            all_border_pixels.extend(list(left_col_img.getdata()))
        if width > 1 and end_y_for_cols > start_y_for_cols:
            right_col_img = img_rgb.crop((width - 1, start_y_for_cols, width, end_y_for_cols))
            all_border_pixels.extend(list(right_col_img.getdata()))
        if not all_border_pixels:
            if width > 0 and height > 0:
                try:
                    return img_rgb.getpixel((0, 0)) 
                except IndexError: 
                    return (0, 0, 0)
            return (0, 0, 0)
        counts = Counter(all_border_pixels)
        return counts.most_common(1)[0][0]

    def _find_content_bounding_box(self, image_to_scan: Image.Image, border_color_to_detect: tuple[int, int, int], threshold: float) -> Optional[Tuple[int, int, int, int]]:
        width, height = image_to_scan.size
        if width == 0 or height == 0:
            return None
        try:
            pix = image_to_scan.load()
        except Exception:
            return None
        min_x, min_y = width, height
        max_x, max_y = -1, -1
        content_found = False
        for y_coord in range(height):
            for x_coord in range(width):
                try:
                    pixel_data = pix[x_coord, y_coord]
                    r, g, b = pixel_data[0], pixel_data[1], pixel_data[2]
                except (IndexError, TypeError): 
                    continue
                if math.hypot(r - border_color_to_detect[0], g - border_color_to_detect[1], b - border_color_to_detect[2]) > threshold:
                    min_x = min(min_x, x_coord)
                    max_x = max(max_x, x_coord)
                    min_y = min(min_y, y_coord)
                    max_y = max(max_y, y_coord)
                    content_found = True
        if not content_found:
            return None
        return min_x, min_y, max_x, max_y

    def _balance_border(self, detect: Image.Image, orig: Image.Image, left: int, top: int, size: int, border_color: tuple, thresh: float) -> Image.Image:
        orig_width, orig_height = orig.size
        detect_width, detect_height = detect.size 
        eff_detect_left = max(0, left)
        eff_detect_top = max(0, top)
        eff_detect_right = min(left + size, detect_width)
        eff_detect_bottom = min(top + size, detect_height)
        if eff_detect_right <= eff_detect_left or eff_detect_bottom <= eff_detect_top:
            final_left_orig = max(0, min(left, orig_width - size))
            final_top_orig = max(0, min(top, orig_height - size))
            actual_crop_dim_orig = min(size, orig_width - final_left_orig, orig_height - final_top_orig)
            if actual_crop_dim_orig < 1: return orig 
            return orig.crop((final_left_orig, final_top_orig, final_left_orig + actual_crop_dim_orig, final_top_orig + actual_crop_dim_orig))
        cropped_detect_window = detect.crop((eff_detect_left, eff_detect_top, eff_detect_right, eff_detect_bottom))
        local_size_w = cropped_detect_window.width
        local_size_h = cropped_detect_window.height
        if local_size_w == 0 or local_size_h == 0:
            final_left_orig = max(0, min(left, orig_width - size))
            final_top_orig = max(0, min(top, orig_height - size))
            actual_crop_dim_orig = min(size, orig_width - final_left_orig, orig_height - final_top_orig)
            if actual_crop_dim_orig < 1: return orig
            return orig.crop((final_left_orig, final_top_orig, final_left_orig + actual_crop_dim_orig, final_top_orig + actual_crop_dim_orig))
        try:
            pix_detect = cropped_detect_window.load()
        except Exception:
            final_left_orig = max(0, min(left, orig_width - size))
            final_top_orig = max(0, min(top, orig_height - size))
            actual_crop_dim_orig = min(size, orig_width - final_left_orig, orig_height - final_top_orig)
            if actual_crop_dim_orig < 1: return orig
            return orig.crop((final_left_orig, final_top_orig, final_left_orig + actual_crop_dim_orig, final_top_orig + actual_crop_dim_orig))
        top_border_rows = 0
        for y in range(local_size_h):
            is_border_row = True
            for x in range(local_size_w):
                r, g, b = pix_detect[x,y][:3] 
                if math.hypot(r - border_color[0], g - border_color[1], b - border_color[2]) > thresh:
                    is_border_row = False
                    break
            if is_border_row:
                top_border_rows += 1
            else:
                break
        bottom_border_rows = 0
        for y in range(local_size_h - 1, -1, -1):
            is_border_row = True
            for x in range(local_size_w):
                r, g, b = pix_detect[x,y][:3]
                if math.hypot(r - border_color[0], g - border_color[1], b - border_color[2]) > thresh:
                    is_border_row = False
                    break
            if is_border_row:
                bottom_border_rows += 1
            else:
                break
        target_crop_dim = size 
        new_top_orig = top 
        if top_border_rows > 0 and bottom_border_rows == 0:
            shift = top_border_rows // 2
            new_top_orig = top + shift 
        elif bottom_border_rows > 0 and top_border_rows == 0:
            shift = bottom_border_rows // 2
            new_top_orig = top - shift 
        final_left = max(0, min(left, orig_width - target_crop_dim))
        final_top = max(0, min(new_top_orig, orig_height - target_crop_dim)) 
        actual_final_w = min(target_crop_dim, orig_width - final_left)
        actual_final_h = min(target_crop_dim, orig_height - final_top)
        actual_final_dim = min(actual_final_w, actual_final_h) 
        if actual_final_dim < 1:
            return orig
        return orig.crop((final_left, final_top, final_left + actual_final_dim, final_top + actual_final_dim))

    def _perform_border_crop(self, img_to_crop: Image.Image) -> Optional[Image.Image]:
        detect_img = img_to_crop.convert("RGB") if img_to_crop.mode != "RGB" else img_to_crop.copy()
        border_color = self.get_dominant_border_color(detect_img) 
        threshold = 20
        bbox = self._find_content_bounding_box(detect_img, border_color, threshold) 
        if bbox is None:
            return None 
        min_x, min_y, max_x, max_y = bbox
        content_w = max_x - min_x + 1
        content_h = max_y - min_y + 1
        crop_dim = max(64, max(content_w, content_h))
        center_x = min_x + content_w // 2
        center_y = min_y + content_h // 2
        half_crop_dim = crop_dim // 2
        left = max(0, center_x - half_crop_dim)
        top = max(0, center_y - half_crop_dim)
        img_width, img_height = detect_img.size
        if left + crop_dim > img_width:
            left = img_width - crop_dim
        if top + crop_dim > img_height:
            top = img_height - crop_dim
        left = max(0, left) 
        top = max(0, top)
        actual_crop_size = min(crop_dim, img_width - left, img_height - top)
        if actual_crop_size < 1:
            return img_to_crop 
        return self._balance_border(detect_img, img_to_crop, left, top, actual_crop_size, border_color, threshold)

    def _perform_object_focus_crop(self, img_to_crop: Image.Image) -> Optional[Image.Image]:
        base_for_detect = img_to_crop.convert("RGB") if img_to_crop.mode != "RGB" else img_to_crop.copy()
        detect_img_processed = base_for_detect.filter(ImageFilter.BoxBlur(5))
        detect_img_processed = ImageEnhance.Brightness(detect_img_processed).enhance(1.95)
        threshold_find_bbox_obj = 50
        border_color_for_detect = self.get_dominant_border_color(detect_img_processed) 
        bbox = self._find_content_bounding_box(detect_img_processed, border_color_for_detect, threshold_find_bbox_obj) 
        if bbox is None:
            return None 
        min_x_orig_bbox, min_y_orig_bbox, max_x_orig_bbox, max_y_orig_bbox = bbox
        expansion_pixels = -10 
        min_x = max(0, min_x_orig_bbox - expansion_pixels)
        min_y = max(0, min_y_orig_bbox - expansion_pixels)
        max_x = min(detect_img_processed.width - 1, max_x_orig_bbox + expansion_pixels)
        max_y = min(detect_img_processed.height - 1, max_y_orig_bbox + expansion_pixels)
        content_w = max_x - min_x + 1
        content_h = max_y - min_y + 1
        if content_w <= 0 or content_h <= 0:
            return img_to_crop 
        crop_dim = max(64, max(content_w, content_h))
        center_x = min_x + content_w // 2
        center_y = min_y + content_h // 2
        half_crop_dim = crop_dim // 2
        left = max(0, center_x - half_crop_dim)
        top = max(0, center_y - half_crop_dim)
        img_width, img_height = base_for_detect.size 
        if left + crop_dim > img_width: left = img_width - crop_dim
        if top + crop_dim > img_height: top = img_height - crop_dim
        left = max(0, left)
        top = max(0, top)
        actual_crop_size = min(crop_dim, img_width - left, img_height - top)
        if actual_crop_size < 1:
            return img_to_crop
        threshold_balance_obj = 60
        return self._balance_border(detect_img_processed, img_to_crop, left, top, actual_crop_size, border_color_for_detect, threshold_balance_obj)

    def crop_image_borders(self, img: Image.Image, radio_logo: bool) -> Image.Image:
        if radio_logo or not self.config.crop_borders:
            return img
        cropped_image: Optional[Image.Image] = None
        if self.config.crop_extra or self.config.special_mode: 
            cropped_image = self._perform_object_focus_crop(img)
            if cropped_image is None: 
                cropped_image = self._perform_border_crop(img)
        else:
            cropped_image = self._perform_border_crop(img)
        if cropped_image is None: 
            return img
        return cropped_image

    def _draw_text_with_outline(self, draw: ImageDraw.ImageDraw, xy: tuple, text: str, font: ImageFont.FreeTypeFont, text_color: tuple, outline_color: tuple, outline_width: int = 1):
        x, y = xy
        for i in range(-outline_width, outline_width + 1):
            for j in range(-outline_width, outline_width + 1):
                if i == 0 and j == 0:
                    continue  
                draw.text((x + i, y + j), text, font=font, fill=outline_color)
        draw.text((x, y), text, font=font, fill=text_color)

    def _draw_text_with_shadow(self, draw: ImageDraw.ImageDraw, xy: tuple, text: str, font: ImageFont.FreeTypeFont, text_color: tuple, shadow_color: tuple):
        x, y = xy
        draw.text((x + 1, y + 1), text, font=font, fill=shadow_color)
        draw.text((x, y + 1), text, font=font, fill=shadow_color)
        if shadow_color == (255, 255, 255, 128):
            draw.text((x + 1, y - 1), text, font=font, fill=shadow_color)
            draw.text((x - 1, y), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=text_color)

    def _get_text_dimensions(self, text: str, font: ImageFont.FreeTypeFont, draw: Optional[ImageDraw.ImageDraw] = None) -> tuple[int, int]:
        try:
            if draw: 
                bbox = draw.textbbox((0, 0), text, font=font)
                return bbox[2] - bbox[0], bbox[3] - bbox[1]
            else: 
                bbox = font.getbbox(text)
                return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError: 
            if draw:
                try:
                    return draw.textsize(text, font=font)
                except AttributeError: 
                    return len(text) * (font.size // 2 if hasattr(font, 'size') else 5), (font.size if hasattr(font, 'size') else 10)
            else: 
                return len(text) * (font.size // 2 if hasattr(font, 'size') else 5), (font.size if hasattr(font, 'size') else 10)
        except Exception:
            return 0,0

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
        if not text:
            return []
        avg_char_width_fallback = 5
        avg_char_width = avg_char_width_fallback
        try:
            char_width_sample, _ = self._get_text_dimensions("x", font, draw)
            if char_width_sample > 0:
                avg_char_width = char_width_sample
        except Exception:
            pass
        
        wrap_width_chars = max(1, max_width // avg_char_width if avg_char_width > 0 else 10)
        raw_lines = text.splitlines()
        processed_lines = []
        for raw_line_idx, raw_line in enumerate(raw_lines):
            if not raw_line.strip():
                continue
            current_line_width_px, _ = self._get_text_dimensions(raw_line, font, draw)
            if current_line_width_px <= max_width:
                processed_lines.append(raw_line)
                continue
            
            attempt_textwrap = True 
            if attempt_textwrap and max_width > avg_char_width * 3: 
                try:
                    wrapped_sub_lines = textwrap.wrap(raw_line, width=wrap_width_chars, break_long_words=True, replace_whitespace=False, drop_whitespace=False)
                    temp_textwrap_lines = []
                    textwrap_failed_to_fit = False
                    for sub_line in wrapped_sub_lines:
                        if not sub_line.strip(): continue
                        sub_line_pixel_width, _ = self._get_text_dimensions(sub_line, font, draw)
                        if sub_line_pixel_width <= max_width:
                            temp_textwrap_lines.append(sub_line)
                        else:
                            textwrap_failed_to_fit = True
                            break 
                    
                    if not textwrap_failed_to_fit:
                        processed_lines.extend(temp_textwrap_lines)
                        continue 
                except Exception:
                    pass
            
            words = raw_line.split(' ')
            current_manual_line = ""
            for word_idx, word in enumerate(words):
                if not word: continue
                word_pixel_width, _ = self._get_text_dimensions(word, font, draw)
                if word_pixel_width > max_width:
                    if current_manual_line:
                        processed_lines.append(current_manual_line.strip())
                        current_manual_line = ""
                    processed_lines.extend(self._char_wrap_long_word(word, font, max_width, draw))
                else:
                    test_line = f"{current_manual_line} {word}".strip() if current_manual_line else word
                    test_line_pixel_width, _ = self._get_text_dimensions(test_line, font, draw)
                    if test_line_pixel_width <= max_width:
                        current_manual_line = test_line
                    else:
                        if current_manual_line:
                            processed_lines.append(current_manual_line.strip())
                        current_manual_line = word
            
            if current_manual_line:
                processed_lines.append(current_manual_line.strip())
        
        final_cleaned_lines = [line for line in processed_lines if line.strip()]
        return final_cleaned_lines

    def _char_wrap_long_word(self, word: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
        lines = []
        if not word: return lines
        current_char_line = ""
        for char_idx, char in enumerate(word):
            test_char_line = current_char_line + char
            char_line_w, _ = self._get_text_dimensions(test_char_line, font, draw)
            if char_line_w <= max_width:
                current_char_line = test_char_line
            else:
                if current_char_line: 
                    lines.append(current_char_line)
                current_char_line = char
                single_char_w, _ = self._get_text_dimensions(char, font, draw)
                if single_char_w > max_width:
                    lines.append(char)
                    current_char_line = "" 
        if current_char_line: 
            lines.append(current_char_line)
        return lines

    def _contrast_ratio(self, c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
        def _luminance(c: tuple[int, int, int]) -> float:
            r, g, b = [v / 255 for v in c]
            r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
            g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
            b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
            return 0.2126 * r + 0.7152 * g + 0.0722 * b
        l1, l2 = _luminance(c1) + 0.05, _luminance(c2) + 0.05
        return max(l1, l2) / min(l1, l2)

    def _pick_two_contrasting_colors(self, img: Image.Image, min_ratio: float = 4.5) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        thumb = img.resize((16, 16), Image.Resampling.BICUBIC)
        pixels = list(thumb.getdata())
        bg = tuple(sum(ch) // len(pixels) for ch in zip(*pixels))  
        palette = COLOR_PALETTE
        random.shuffle(palette)
        first = second = None
        for cand in palette:
            if self._contrast_ratio(cand, bg) < min_ratio:
                continue
            if first is None:
                first = cand
                continue
            if self.color_distance(cand, first) > 80:
                second = cand
                break
        if first is None:                       
            first = (255, 255, 255) if self._contrast_ratio((255, 255, 255), bg) >= self._contrast_ratio((0, 0, 0), bg) else (0, 0, 0)
        if second is None:
            alt = (0, 0, 0) if first == (255, 255, 255) else (255, 255, 255)
            second = alt if self._contrast_ratio(alt, bg) >= min_ratio else first
        return first, second

    def _draw_burned_text(self, img: Image.Image, artist: str, title: str) -> Image.Image:
        if not (artist or title):
            return img
        artist_rgb_text, title_rgb_text = self._pick_two_contrasting_colors(img, 4.5)
        artist_fill  = (*artist_rgb_text, 255)
        title_fill   = (*title_rgb_text, 255)
        def _calculate_perceptual_luminance(rgb_color: tuple[int, int, int]) -> float:
            r, g, b = rgb_color
            return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        thumb_for_bg_analysis = img.resize((8, 8), Image.Resampling.BICUBIC).convert("RGB")
        pixels_for_bg_analysis = list(thumb_for_bg_analysis.getdata())
        avg_img_rgb: tuple[int, int, int]
        if not pixels_for_bg_analysis:
            avg_img_rgb = (128, 128, 128)
        else:
            r_sum = sum(p[0] for p in pixels_for_bg_analysis)
            g_sum = sum(p[1] for p in pixels_for_bg_analysis)
            b_sum = sum(p[2] for p in pixels_for_bg_analysis)
            num_pixels = len(pixels_for_bg_analysis)
            avg_img_rgb = (r_sum // num_pixels, g_sum // num_pixels, b_sum // num_pixels)
        avg_img_luminance = _calculate_perceptual_luminance(avg_img_rgb)
        shadow_base_rgb_for_bg: tuple[int, int, int]
        if avg_img_luminance > 0.5:  
            shadow_base_rgb_for_bg = (0, 0, 0)      
        else:  
            shadow_base_rgb_for_bg = (255, 255, 255)  
        SHADOW_TEXT_MIN_CONTRAST_RATIO = 4.5
        final_shadow_base_rgb = shadow_base_rgb_for_bg
        cr_artist_shadow = self._contrast_ratio(final_shadow_base_rgb, artist_rgb_text)
        cr_title_shadow  = self._contrast_ratio(final_shadow_base_rgb, title_rgb_text)
        if cr_artist_shadow < SHADOW_TEXT_MIN_CONTRAST_RATIO or cr_title_shadow < SHADOW_TEXT_MIN_CONTRAST_RATIO:
            flipped_shadow_base_rgb = (0,0,0) if final_shadow_base_rgb == (255,255,255) else (255,255,255)
            final_shadow_base_rgb = flipped_shadow_base_rgb
        shadow_alpha = 128  
        dynamic_shadow_color = (*final_shadow_base_rgb, shadow_alpha) 
        pad = 2
        max_h = img.height - 2 * pad
        max_w = img.width  - 2 * pad
        spacer_px, inter_px = 4, 2
        img_copy = img.copy().convert("RGBA") 
        layer = ImageDraw.Draw(img_copy)
        base_font = ImageFont.load_default()
        if unidecode_support:
            artist_b = unidecode(artist) if artist else ""
            title_b = unidecode(title) if title else ""
        else:
            artist_b = get_bidi(artist) if artist and has_bidi(artist) else (artist or "")
            title_b  = get_bidi(title)  if title  and has_bidi(title)  else (title or "")
        prelim_artist_lines = self._wrap_text(artist_b, base_font, max_w, layer) if artist_b else []
        prelim_title_lines  = self._wrap_text(title_b,  base_font, max_w, layer) if title_b  else []
        prelim = prelim_artist_lines + prelim_title_lines
        if not prelim: return img.convert("RGB")
        eff_h = max_h - (spacer_px if prelim_artist_lines and prelim_title_lines else 0)
        font = ImageFont.load_default()
        art_lines = self._wrap_text(artist_b, font, max_w, layer) if artist_b else []
        tit_lines = self._wrap_text(title_b,  font, max_w, layer) if title_b  else []
        all_render_lines = art_lines + tit_lines
        heights = [self._get_text_dimensions(t, font, layer)[1] for t in all_render_lines]
        num_inter_line_spaces = len(all_render_lines) - 1 if len(all_render_lines) > 0 else 0
        total_h = sum(heights) + (inter_px * num_inter_line_spaces)
        if art_lines and tit_lines: total_h += spacer_px
        y = pad + max(0, (max_h - total_h) // 2)
        def _blit_text_line_with_shadow(text_line_content, main_text_color_fill, y_current_pos):
            w, h = self._get_text_dimensions(text_line_content, font, layer)
            x_current_pos = pad + max(0, (max_w - w) // 2)
            self._draw_text_with_shadow(draw=layer, xy=(x_current_pos, y_current_pos), text=text_line_content, font=font, text_color=main_text_color_fill, shadow_color=dynamic_shadow_color)
            return h
        for i, line_content in enumerate(art_lines):
            line_height = _blit_text_line_with_shadow(line_content, artist_fill, y)
            y += line_height + (inter_px if i < len(art_lines) - 1 else 0)
        if art_lines and tit_lines: y += spacer_px
        for i, line_content in enumerate(tit_lines):
            line_height = _blit_text_line_with_shadow(line_content, title_fill, y)
            y += line_height + (inter_px if i < len(tit_lines) - 1 else 0)
        return img_copy.convert("RGB")

class LyricsProvider:
    """Provides lyrics with 6-Line Limit, Filler Removal, and Stateless Seek Handling."""

    def __init__(self, config: "Config", session: aiohttp.ClientSession):
        self.config = config
        self.session = session 
        
        # --- CACHE ---
        self.lyrics_cache: OrderedDict[str, list] = OrderedDict()
        self.cache_limit: int = 100 

        # --- PLAYBACK STATE ---
        self.visual_timeline: list[dict] = [] 
        self.current_song_key: Optional[str] = None
        
        # --- TRACKING STATE ---
        self.current_frame_index: int = -1  
        self.last_sent_hash: int = 0        
        self.is_in_gap_state: bool = True
        self.update_lock = asyncio.Lock()

        self.filler_regex = re.compile(r"(?:[\s\W]+(?:oh+|ooh+|yeah|yea|woah|la+|na+)+[\W]*)+$", re.IGNORECASE)

    async def get_lyrics(self, artist: Optional[str], title: str, album: Optional[str] = None, duration: int = 0) -> list[dict]:
        if not artist or not title:
            self._reset_state()
            return []

        new_key = f"{artist}|{title}".lower()

        if new_key == self.current_song_key:
            return self.lyrics_cache.get(new_key, [])

        self._reset_state()
        self.current_song_key = new_key
        
        if new_key in self.lyrics_cache:
            self.lyrics_cache.move_to_end(new_key)
            raw_lyrics = self.lyrics_cache[new_key]
            self._build_visual_timeline(raw_lyrics) 
            return raw_lyrics

        fetched_lyrics = []
        base_url_get = "https://lrclib.net/api/get"
        params = { 'artist_name': artist, 'track_name': title }
        if album: params['album_name'] = album
        if duration: params['duration'] = str(int(duration))

        try:
            async with self.session.get(base_url_get, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('syncedLyrics'):
                        fetched_lyrics = self._parse_lrc(data['syncedLyrics'])
        except Exception:
            pass

        if not fetched_lyrics:
            try:
                base_url_search = "https://lrclib.net/api/search"
                search_params = {'q': f"{artist} {title}"}
                async with self.session.get(base_url_search, params=search_params, timeout=10) as response:
                    if response.status == 200:
                        results = await response.json()
                        if results and isinstance(results, list):
                            target_dur = float(duration) if duration else 0
                            for item in results:
                                if not item.get('syncedLyrics'): continue
                                if abs(item.get('duration', 0) - target_dur) < 15:
                                    fetched_lyrics = self._parse_lrc(item['syncedLyrics'])
                                    break
            except Exception:
                pass

        if len(self.lyrics_cache) >= self.cache_limit:
            self.lyrics_cache.popitem(last=False)
        
        self.lyrics_cache[new_key] = fetched_lyrics
        self._build_visual_timeline(fetched_lyrics)
        
        return fetched_lyrics

    def _reset_state(self):
        self.visual_timeline = []
        self.current_song_key = None
        self.current_frame_index = -1
        self.last_sent_hash = 0
        self.is_in_gap_state = True

    def _parse_lrc(self, lrc_text: str) -> list[dict]:
        if not lrc_text: return []
        parsed = []
        pattern = re.compile(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)')
        
        for line in lrc_text.split('\n'):
            match = pattern.match(line)
            if match:
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                text = match.group(3).strip()
                if not text: continue
                raw_total = minutes * 60 + seconds
                total_seconds = int(raw_total + 0.5)
                parsed.append({'seconds': total_seconds, 'lyrics': text})
        
        parsed.sort(key=lambda x: x['seconds'])
        return parsed

    def _deduplicate_timestamps(self, lyrics: list[dict]) -> list[dict]:
        if not lyrics: return []
        cleaned = []
        current_block = lyrics[0].copy()
        for i in range(1, len(lyrics)):
            item = lyrics[i]
            if item['seconds'] == current_block['seconds']:
                current_block['lyrics'] += "\n" + item['lyrics']
            else:
                cleaned.append(current_block)
                current_block = item.copy()
        cleaned.append(current_block)
        return cleaned

    def _basic_wrap(self, text: str, width: int) -> list[str]:
        words = text.split(' ')
        lines = []
        current_line = []
        current_len = 0

        for word in words:
            word_len = len(word)
            space = 1 if current_line else 0
            if current_len + word_len + space <= width:
                current_line.append(word)
                current_len += word_len + space
            else:
                lines.append(current_line)
                current_line = [word]
                current_len = word_len
        if current_line: lines.append(current_line)
        return [" ".join(l) for l in lines]

    def _smart_wrap(self, text: str, width: int) -> list[str]:
        lines = self._basic_wrap(text, width)
        if len(lines) <= 6:
            return lines

        cleaned_text = self.filler_regex.sub("", text).strip()
        if len(cleaned_text) < len(text):
            lines = self._basic_wrap(cleaned_text, width)
            if len(lines) <= 6:
                return lines

        lines = self._basic_wrap(text, width + 2)
        if len(lines) <= 6:
            return lines

        if len(cleaned_text) < len(text):
            lines = self._basic_wrap(cleaned_text, width + 2)
            if len(lines) <= 6:
                return lines

        return lines[:6]

    def _build_visual_timeline(self, raw_lyrics: list[dict]):
        self.visual_timeline = []
        self.current_frame_index = -1
        self.is_in_gap_state = True
        self.last_sent_hash = 0
        
        if not raw_lyrics: return
        
        processed_lyrics = self._deduplicate_timestamps(raw_lyrics)
        n = len(processed_lyrics)
        
        for i in range(n):
            current = processed_lyrics[i]
            text = current['lyrics']
            start_time = current['seconds']
            
            if i + 1 < n:
                next_start = processed_lyrics[i+1]['seconds']
            else:
                next_start = start_time + 60.0 

            word_count = len(text.split())
            reading_duration = 2.0 + (word_count * 0.4)
            reading_duration = max(3.0, min(reading_duration, 8.0))
            
            calculated_end_time = start_time + reading_duration

            gap_to_next = next_start - calculated_end_time
            if 0 < gap_to_next < 2.5:
                end_time = next_start
            else:
                end_time = min(calculated_end_time, next_start)
            
            if end_time <= start_time:
                end_time = start_time + 1.0

            final_width = 10 if has_bidi(text) else 11
            layout_items = self._calculate_layout_items(text, final_width)

            self.visual_timeline.append({
                'start': start_time,
                'end': end_time,
                'layout': layout_items
            })

    def _calculate_layout_items(self, text: str, line_length: int) -> list[dict]:
        is_bidi_text = has_bidi(text)
        raw_blocks = text.split('\n')
        final_render_lines = []

        for block_idx, block in enumerate(raw_blocks):
            if len(final_render_lines) >= 6:
                break

            wrapped = self._smart_wrap(block, line_length)
            slots_remaining = 6 - len(final_render_lines)

            if len(wrapped) > slots_remaining:
                if slots_remaining == 1:
                    wrapped = [" ".join(wrapped)]
                else:
                    safe_part = wrapped[:slots_remaining - 1]
                    overflow_part = " ".join(wrapped[slots_remaining - 1:])
                    wrapped = safe_part + [overflow_part]

            if is_bidi_text:
                wrapped = [get_bidi(line) for line in wrapped]

            for line_idx, line in enumerate(wrapped):
                is_new_block = (line_idx == 0 and block_idx > 0)
                final_render_lines.append((line, is_new_block))

        if len(final_render_lines) >= 6:
            font_height = 10
            block_gap = 0
            current_y = 1 # Start at the very top (Y=1) to ensure Line 6 fits
        else:
            font_height = 12
            block_gap = 2
            num_gaps = sum(1 for _, is_new in final_render_lines if is_new)
            total_h = (len(final_render_lines) * font_height) + (num_gaps * block_gap)
            current_y = (64 - total_h) // 2
        
        items = []
        for i, (line_text, is_new_block) in enumerate(final_render_lines):
            if is_bidi_text:
                line_text = line_text.replace("(", "###TEMP###").replace(")", "(").replace("###TEMP###", ")")
            
            if is_new_block: current_y += block_gap
            
            items.append({
                "y": current_y,
                "dir": 1 if has_bidi(line_text) else 0,
                "text": line_text,
            })
            current_y += font_height
            
        return items

    async def calculate_position(self, media_data: "MediaData", hass_app: "hass.Hass") -> None:
        if not media_data.lyrics or not self.visual_timeline or not self.config.show_lyrics:
            return

        if self.update_lock.locked():
            return

        async with self.update_lock:
            try:
                offset = float(self.config.lyrics_sync)
            except:
                offset = 0.0

            if not media_data.media_position_updated_at:
                return

            now = datetime.now(timezone.utc)
            elapsed = (now - media_data.media_position_updated_at).total_seconds()
            current_pos = media_data.media_position + elapsed - offset
            found_index = -1
            
            if self.current_frame_index != -1 and self.current_frame_index < len(self.visual_timeline):
                frame = self.visual_timeline[self.current_frame_index]
                if frame['start'] <= current_pos < frame['end']:
                    found_index = self.current_frame_index
            
            if found_index == -1:
                for i, frame in enumerate(self.visual_timeline):
                    if frame['start'] <= current_pos < frame['end']:
                        found_index = i
                        break

                    if frame['start'] > current_pos:
                        break

            if found_index != -1:
                self.is_in_gap_state = False
                
                new_hash = hash((found_index, media_data.lyrics_font_color))
                
                if found_index != self.current_frame_index or self.last_sent_hash != new_hash:
                    self.current_frame_index = found_index
                    frame = self.visual_timeline[found_index]
                    await self._send_payload(frame['layout'], media_data.lyrics_font_color, hass_app, found_index)
                    self.last_sent_hash = new_hash
            else:
                if not self.is_in_gap_state:
                    await self._send_payload([], media_data.lyrics_font_color, hass_app, -999)
                    self.is_in_gap_state = True
                    self.current_frame_index = -1
                    self.last_sent_hash = 0

    async def _send_payload(self, layout_items: list, color: str, hass_app, target_index: int):
        if target_index != -999 and target_index != self.current_frame_index:
             return

        pixoo_items = []
        for i in range(6):
            if i < len(layout_items):
                item = layout_items[i]
                text_string = item['text']
                y_pos = item['y']
                direction = item['dir']
            else:
                text_string = ""
                y_pos = 0
                direction = 0

            pixoo_items.append({
                "TextId": i + 1,
                "type": 22,
                "x": 0,
                "y": y_pos,
                "dir": direction,
                "font": self.config.lyrics_font, 
                "TextWidth": 64,
                "Textheight": 16,
                "speed": 100,
                "align": 2,
                "TextString": text_string,
                "color": color
            })

        payload = {
            "Command": "Draw/SendHttpItemList", 
            "ItemList": pixoo_items
        }
        try:
            await hass_app.pixoo_device.send_command(payload)
        except Exception:
            pass

class MediaData:
    """Data class to hold and update media information.""" 

    def __init__(self, config: "Config", image_processor: "ImageProcessor", session: aiohttp.ClientSession): 
        self.config = config
        self.image_processor = image_processor
        self.session = session
        
        self.lyrics_provider = LyricsProvider(self.config, self.session)
        self.last_group_start_index: int = -1
        self.last_group_end_index: int = -1
        self.last_lyrics_len: int = 0
        self.reset_state()

    def reset_state(self):
        self.fallback = False
        self.fail_txt = False
        self.playing_radio = False
        self.radio_logo = False
        self.spotify_slide_pass = False
        self.playing_tv = False
        self.image_cache_count = 0
        self.image_cache_memory = "0 KB" 
        self.media_position = 0
        self.media_duration = 0
        self.process_duration = "0 seconds" 
        self.spotify_frames = 0
        self.media_position_updated_at = None 
        self.spotify_data = None 
        self.artist = ""
        self.title = ""
        self.title_original = ""
        self.album = None 
        self.lyrics = [] 
        self.picture = None 
        self.select_index_original = None 
        self.lyrics_font_color = "#FFA000"
        self.color1 = "00FFAA"
        self.color2 = "AA00FF"
        self.color3 = "FFAA00"
        self.temperature = None 
        self.info_img = None 
        self.is_night = False
        self.pic_source = None
        self.pic_url = None

    async def update(self, hass: "hass.Hass") -> Optional["MediaData"]:
        try:
            media_player = self.config.media_player
            media_state_obj = await hass.get_state(media_player, attribute="all")
            
            if not media_state_obj:
                return None
                
            state = media_state_obj.get('state')
            if state not in ["playing", "on"]:
                return None

            attributes = media_state_obj.get('attributes', {})
            raw_title = attributes.get('media_title')
            raw_artist = attributes.get('media_artist')
            app_name = attributes.get('app_name')

            if raw_title is None or str(raw_title).strip() == "":
                if app_name and str(app_name).strip() != "":
                    raw_title = app_name
                else:
                    return None

            # 3. Fallback for Artist
            if (raw_artist is None or str(raw_artist).strip() == "") and app_name:
                raw_artist = app_name

            # 4. ANTI-SPOOFING CHECKS
            t_check = str(raw_title).strip().lower()
            a_check = str(app_name).strip().lower() if app_name else ""
            art_check = str(raw_artist).strip().lower() if raw_artist else ""

            if a_check and t_check == a_check:
                _LOGGER.debug(f"Ignoring spoofed media (Title == App): {raw_title}")
                return None

            if art_check and t_check == art_check:
                _LOGGER.debug(f"Ignoring spoofed media (Title == Artist): {raw_title}")
                return None

            # --- END VALIDATION ---

            self.title_original = raw_title
            self.artist = raw_artist if raw_artist else ""

            self.media_position = attributes.get('media_position', 0)
            self.media_duration = attributes.get('media_duration', 0)
            
            # --- IMAGE PATH FIX ---
            original_picture = attributes.get('entity_picture')
            
            # Detect local Windows paths (e.g. C:\Users...) or file:// URIs that AppDaemon cannot access
            # This prevents URL errors and forces the script to use Online Fallback immediately.
            if original_picture:
                # Check for Windows Drive letters (e.g. C:\) or file:// protocol
                if re.match(r'^[a-zA-Z]:\\', original_picture) or original_picture.startswith("file://"):
                    _LOGGER.info(f"Local image path detected ({original_picture}). Using fallback sources.")
                    original_picture = None
            
            self.picture = original_picture
            # ----------------------

            media_content_id = attributes.get('media_content_id')
            media_channel = attributes.get('media_channel')
            album = attributes.get('media_album_name')
            pos_updated_at_str = attributes.get('media_position_updated_at')
            
            sun_state = await hass.get_state("sun.sun")
            self.is_night = (sun_state == "below_horizon") if sun_state else False

            self.media_position_updated_at = datetime.fromisoformat(pos_updated_at_str.replace('Z', '+00:00')) if pos_updated_at_str else None
            self.title_clean = self.clean_title(self.title_original) if self.config.clean_title else self.title_original
            self.title = self.title_clean 
            
            # Handle TV
            if self.title_original == "TV":
                self.artist = "TV"
                self.title = "TV"
                self.playing_tv = True
                self.picture = "TV_IS_ON_ICON" if self.config.tv_icon_pic else "TV_IS_ON"
                self.lyrics = []
                return self 

            self.playing_tv = False
            self.title = self.title_clean
            self.album = album
            # self.picture already set above

            # Radio Logic
            if media_channel and (media_content_id and (media_content_id.startswith("x-rincon") or media_content_id.startswith("aac://http") or media_content_id.startswith("rtsp://"))): 
                self.playing_radio = True
                self.radio_logo = False
                
                if ('https://tunein' in str(media_content_id) or
                    self.title_original == media_channel or
                    self.title_original == raw_artist or
                    raw_artist == media_channel or
                    raw_artist == 'Live' or
                    raw_artist is None):
                    self.radio_logo = True
                    self.album = media_channel
            else:
                self.playing_radio = False
                self.radio_logo = False

            if self.config.show_lyrics and not self.config.special_mode and not self.playing_tv and not self.playing_radio:
                self.lyrics = await self._get_lyrics(self.artist, self.title_original, self.album, self.media_duration)
                
                if len(self.lyrics) != self.last_lyrics_len:
                    self.last_group_start_index = -1
                    self.last_group_end_index = -1
                    self.last_lyrics_len = len(self.lyrics)
            else:
                self.lyrics = []

            if self.config.temperature_sensor and (self.config.temperature or self.config.special_mode):
                try:
                    temp_state = await hass.get_state(self.config.temperature_sensor, attribute="all")
                    if temp_state:
                        val = float(temp_state['state'])
                        unit = temp_state['attributes'].get('unit_of_measurement', '')
                        self.temperature = f"{int(val)}{unit.lower()}"
                    else:
                        self.temperature = None
                except Exception:
                    self.temperature = None

            return self

        except Exception as e: 
            _LOGGER.exception(f"Error updating Media Data: {e}") 
            return None

    async def _get_lyrics(self, artist: Optional[str], title: str, album: Optional[str], duration: int) -> list[dict]: 
        """Uses the persistent lyrics provider to fetch lyrics."""
        return await self.lyrics_provider.get_lyrics(artist, title, album, duration)


    def format_ai_image_prompt(self, artist: Optional[str], title: str) -> str: 
        """Format prompt for the Pollinations AI image generation API."""
        if not self.config.pollinations:
            self.log("Missing Pollinations AI image generation API. Create API: key https://enter.pollinations.ai/")
            return # Return None explicitly if no key, handled by caller
        
        artist_name = artist if artist else 'Pixoo64' 

        prompts = [
            f"Album cover art for '{title}' by {artist_name}, highly detailed, digital art style",
            f"Vibrant album cover for '{title}' by {artist_name}, reflecting the mood of the music",
            f"Surreal landscape representing the song '{title}' by {artist_name}, bold colors",
            f"Retro pixel art album cover for '{title}' by {artist_name}, 80s aesthetic",
            f"Dreamlike scene inspired by '{title}' by {artist_name}, fantasy art",
            f"Minimalist design for album '{title}' by {artist_name}, elegant",
            f"Dynamic and energetic cover for '{title}' by {artist_name}, motion and vibrant colors",
            f"Whimsical illustration for '{title}' by {artist_name}, imaginative elements",
            f"Dark and moody artwork for '{title}' by {artist_name}, shadows and deep colors",
            f"Futuristic album cover for '{title}' by {artist_name}, sci-fi elements"
        ]

        selected_prompt = random.choice(prompts)
        # URL encode the prompt for safety
        encoded_prompt = urllib.parse.quote(selected_prompt)
        
        model = self.config.ai_fallback if self.config.ai_fallback else "flux"
        seed = random.randint(0, 100000)
        
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model={model}&width=1024&height=1024&nologo=true&seed={seed}&key={self.config.pollinations}"
        
        return url


    def clean_title(self, title: str) -> str: 
        """Clean up the title by removing common patterns."""
        if not title:
            return title

        patterns = [
            r'[\(\[][^)\]]*remaster(?:ed)?[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*remix(?:ed)?[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*version[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*session[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*feat.[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*single[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*edit[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*extended[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*live[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*bonus[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*deluxe[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*mix[^)\]]*[\)\]]',
            r'[\(\[][^)\]]*\d{4}[^)\]]*[\)\]]',
            r'^\d+\s*[\.-]\s*',
            r'\.(mp3|m4a|wav|flac)$',]

        cleaned_title = title
        for pattern in patterns:
            cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.IGNORECASE)

        cleaned_title = ' '.join(cleaned_title.split())
        return cleaned_title


class FallbackService:
    """Handles fallback logic to retrieve album art from various sources if the original picture is not available.""" 

    def __init__(self, config: "Config", image_processor: "ImageProcessor", session: aiohttp.ClientSession, spotify_service: "SpotifyService"): 
        self.config = config
        self.image_processor = image_processor
        self.session = session
        self.spotify_service = spotify_service
        
        self.tidal_token_cache: dict[str, Any] = {
            'token': None,
            'expires': 0
        }
        self.fail_txt = False
        self.fallback = False

    async def get_final_url(self, picture: Optional[str], media_data: "MediaData") -> Optional[dict]: 
        self.fail_txt = False
        self.fallback = False
        media_data.pic_url = None 
        if picture is not None: 
            media_data.pic_url = picture if picture.startswith('http') else f"{self.config.ha_url}{picture}"
        else:
            media_data.pic_url = picture 
        
        if self.config.force_ai and not media_data.radio_logo and not media_data.playing_tv:
            _LOGGER.info("Force AI mode enabled, trying to generate AI album art.") 
            if self.config.info:
                await self.send_info(media_data.artist, "FORCE   AI", media_data.lyrics_font_color)
            return await self._try_ai_generation(media_data)

        if picture == "TV_IS_ON_ICON":
            _LOGGER.info("Using TV icon image as album art.") 
            media_data.pic_url = "TV Icon"
            media_data.pic_source = "Internal"
            if self.config.tv_icon_pic:
                tv_icon_base64 = self.image_processor.gbase64(self.create_tv_icon_image())
                return { 
                    'base64_image': tv_icon_base64,
                    'font_color': '#ff00ff',
                    'brightness': 0.67,
                    'brightness_lower_part': '#ffff00',
                    'background_color': (255, 255, 0),
                    'background_color_rgb': (0, 0, 255),
                    'most_common_color_alternative_rgb': (0,0,0),
                    'most_common_color_alternative': '#ffff00',
                    'color1': '#000000', 'color2': '#000000', 'color3': '#000000'}

        try:
            if not media_data.playing_radio or media_data.radio_logo:
                result = await self.image_processor.get_image(picture, media_data, media_data.spotify_slide_pass)
                if result:
                    _LOGGER.debug("Successfully processed original album art.") 
                    media_data.pic_source = "Original"
                    return result
        except Exception as e: 
            _LOGGER.error(f"Original picture processing failed: {e}") 

        _LOGGER.info(f"Falling back to alternative album art sources for '{media_data.artist} - {media_data.title}'.") 
        self.spotify_first_album = None
        self.spotify_artist_pic = None

        if self.config.info and media_data.info_img:
            await self.send_info_img(media_data.info_img)

        # Spotify
        if self.config.spotify_client_id and self.config.spotify_client_secret:
            if self.config.info: await self.send_info(media_data.artist, "SPOTIFY", media_data.lyrics_font_color)
            try:
                spotify_service = self.spotify_service 
                album_id, first_album = await spotify_service.get_spotify_album_id(media_data)
                
                if first_album:
                    self.spotify_first_album = await spotify_service.get_spotify_album_image_url(first_album)
                
                if album_id:
                    image_url = await spotify_service.get_spotify_album_image_url(album_id)
                    if image_url:
                        result = await self.image_processor.get_image(image_url, media_data, media_data.spotify_slide_pass)
                        if result:
                            media_data.pic_url = image_url
                            media_data.pic_source = "Spotify"
                            return result
                self.spotify_artist_pic = await spotify_service.get_spotify_artist_image_url_by_name(media_data.artist)
            except Exception as e: 
                _LOGGER.error(f"Spotify fallback failed: {e}") 

        # Discogs
        if self.config.discogs:
            if self.config.info: await self.send_info(media_data.artist, "DISCOGS", media_data.lyrics_font_color)
            if discogs_art := await self.search_discogs_album_art(media_data.artist, media_data.title):
                if result := await self.image_processor.get_image(discogs_art, media_data, media_data.spotify_slide_pass):
                    media_data.pic_url = discogs_art
                    media_data.pic_source = "Discogs"
                    return result

        # Last.fm
        if self.config.lastfm:
            if self.config.info: await self.send_info(media_data.artist, "LAST.FM", media_data.lyrics_font_color)
            if lastfm_art := await self.search_lastfm_album_art(media_data.artist, media_data.title):
                if result := await self.image_processor.get_image(lastfm_art, media_data, media_data.spotify_slide_pass):
                    media_data.pic_url = lastfm_art
                    media_data.pic_source = "Last.FM"
                    return result

        # TIDAL
        if self.config.tidal_client_id and self.config.tidal_client_secret:
            if self.config.info: await self.send_info(media_data.artist, "TIDAL", media_data.lyrics_font_color)
            if tidal_art := await self.get_tidal_album_art_url(media_data.artist, media_data.title):
                if result := await self.image_processor.get_image(tidal_art, media_data, media_data.spotify_slide_pass):
                    media_data.pic_url = tidal_art
                    media_data.pic_source = "TIDAL"
                    return result

        # Spotify Artist Pic (Fallback level 2)
        if self.spotify_artist_pic:
            if result := await self.image_processor.get_image(self.spotify_artist_pic, media_data, media_data.spotify_slide_pass):
                return result

        # MusicBrainz
        if self.config.musicbrainz:
            if self.config.info: await self.send_info(media_data.artist, "MUSICBRAINZ", media_data.lyrics_font_color)
            if mb_url := await self.get_musicbrainz_album_art_url(media_data.artist, media_data.title):
                try:
                    result = await asyncio.wait_for(
                        self.image_processor.get_image(mb_url, media_data, media_data.spotify_slide_pass),
                        timeout=10
                    )
                    if result:
                        media_data.pic_url = mb_url
                        media_data.pic_source = "MusicBrainz"
                        return result
                except Exception: pass

        # AI (Last Resort)
        _LOGGER.info("Falling back to AI image generation as last resort.") 
        if self.config.info:
            await self.send_info(media_data.artist, "AI   IMAGE", media_data.lyrics_font_color)
        
        result = await self._try_ai_generation(media_data)
        if result and media_data.pic_source == "AI": return result

        # Spotify Default Album (Last-Last Resort)
        if self.spotify_first_album:
            if result := await self.image_processor.get_image(self.spotify_first_album, media_data, media_data.spotify_slide_pass):
                media_data.pic_url = self.spotify_first_album
                media_data.pic_source = "Spotify (Artist Profile Image)"
                return result

        media_data.pic_url = "Black Screen"
        media_data.pic_source = "Internal"
        return self._get_fallback_black_image_data() 

    async def _try_ai_generation(self, media_data):
        ai_url = media_data.format_ai_image_prompt(media_data.artist, media_data.title)
        try:
            result = await asyncio.wait_for(
                self.image_processor.get_image(ai_url, media_data, media_data.spotify_slide_pass),
                timeout=20
            )
            if result:
                _LOGGER.info("Successfully generated AI album art.") 
                media_data.pic_url = ai_url
                media_data.pic_source = "AI"
                return result
        except asyncio.TimeoutError:
            _LOGGER.warning("AI image generation timed out.") 
        except Exception as e: 
            _LOGGER.error(f"AI image generation failed: {e}") 
        return None

    def _get_fallback_black_image_data(self) -> dict: 
        self.fail_txt = True
        self.fallback = True
        black_screen_base64 = self.image_processor.gbase64(self.create_black_screen()) 
        _LOGGER.info("Ultimate fallback: displaying black screen.") 
        return { 
            'base64_image': black_screen_base64,
            'font_color': '#ff00ff',
            'brightness': 0.67,
            'brightness_lower_part': '#ffff00',
            'background_color': (255, 255, 0),
            'background_color_rgb': (0, 0, 255),
            'most_common_color_alternative_rgb': (0,0,0),
            'most_common_color_alternative': '#ffff00',
            'color1': '#000000',
            'color2': '#000000',
            'color3': '#000000'
        }

    async def send_info_img(self, base64_image: str) -> None: 
        payload = {
            "Command": "Draw/CommandList",
            "CommandList": [
                {"Command": "Draw/ResetHttpGifId"},
                {"Command": "Draw/SendHttpGif",
                    "PicNum": 1, "PicWidth": 64, "PicOffset": 0,
                    "PicID": 0, "PicSpeed": 10000, "PicData": base64_image }]}
        await PixooDevice(self.config, self.session).send_command(payload)

    async def send_info(self, artist: Optional[str], text: str, lyrics_font_color: str) -> None: 
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
        await PixooDevice(self.config, self.session).send_command(payload)

    async def get_musicbrainz_album_art_url(self, ai_artist: str, ai_title: str) -> Optional[str]: 
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
            async with self.session.get(search_url, params=params, headers=headers, timeout=10) as response: 
                response.raise_for_status() 
                data = await response.json()
                if not data.get("releases"):
                    return None
                release_id = data["releases"][0]["id"]
                cover_art_url = f"https://coverartarchive.org/release/{release_id}"
                try: 
                    async with self.session.get(cover_art_url, headers=headers, timeout=20) as art_response: 
                        art_response.raise_for_status() 
                        art_data = await art_response.json()
                        for image in art_data.get("images", []):
                            if image.get("front", False):
                                return image.get("thumbnails", {}).get("250")
                        return None
                except Exception: 
                    return None
        except Exception: 
            return None

    async def search_discogs_album_art(self, ai_artist: str, ai_title: str) -> Optional[str]: 
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
            "per_page": 5 
        }
        try:
            async with self.session.get(base_url, headers=headers, params=params, timeout=10) as response: 
                response.raise_for_status() 
                data = await response.json()
                results = data.get("results", [])
                if not results: return None
                return results[0].get("cover_image")
        except Exception: 
            return None

    async def search_lastfm_album_art(self, ai_artist: str, ai_title: str) -> Optional[str]: 
        base_url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "track.getInfo",
            "api_key": self.config.lastfm,
            "artist": ai_artist,
            "track": ai_title,
            "format": "json"
        }
        try:
            async with self.session.get(base_url, params=params, timeout=10) as response: 
                response.raise_for_status() 
                data = await response.json()
                album_art_url_list = data.get("track", {}).get("album", {}).get("image", []) 
                if album_art_url_list:
                    return album_art_url_list[-1]["#text"] 
                return None
        except Exception: 
            return None

    async def get_tidal_album_art_url(self, artist: str, title: str) -> Optional[str]: 
        base_url = "https://openapi.tidal.com/v2/"
        access_token = await self.get_tidal_access_token()
        if not access_token:
            return None
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        search_params = {
            "countryCode": "US",  
            "include": ["artists", "albums", "tracks"],
        }
        try:
            search_url = f"{base_url}searchresults/{artist} - {title}"
            async with self.session.get(search_url, headers=headers, params=search_params, timeout=10) as response: 
                response.raise_for_status() 
                search_data = await response.json()
                albums = [item for item in search_data.get("included", []) if item.get("type") == "albums"]
                if not albums: return None
                best_album = albums[0] 
                if best_album:
                    image_links = best_album.get("attributes", {}).get("imageLinks", [])
                    if image_links and len(image_links) > 3: 
                        return image_links[3].get("href")
                return None
        except Exception: 
            return None

    async def get_tidal_access_token(self) -> Optional[str]: 
        if self.tidal_token_cache['token'] and time.time() < self.tidal_token_cache['expires']:
            return self.tidal_token_cache['token']
        url = "https://auth.tidal.com/v1/oauth2/token"
        tidal_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.config.tidal_client_id,
            "client_secret": self.config.tidal_client_secret,
        }
        try:
            async with self.session.post(url, headers=tidal_headers, data=payload, timeout=10) as response: 
                response.raise_for_status() 
                response_json = await response.json()
                access_token = response_json["access_token"]
                expiry_time = time.time() + response_json.get("expires_in", 3600) - 60 
                self.tidal_token_cache = {
                    'token': access_token,
                    'expires': expiry_time
                }
                return access_token
        except Exception: 
            return None

    def create_black_screen(self) -> Image.Image: 
        img = Image.new("RGB", (64, 64), (0, 0, 0)) 
        return img 

    def create_tv_icon_image(self) -> Image.Image: 
        image_width = 300
        image_height = 300
        final_width = 64
        final_height = 64
        vertical_offset = 10
        black = (0, 0, 0)
        brown = (139, 69, 19)  
        light_brown = (205, 133, 63) 
        screen_bg = (240, 240, 240) 
        white = (255, 255, 255)
        gray = (150, 150, 150)
        rainbow_colors = [
            (255, 0, 0),     # Red
            (255, 165, 0),   # Orange
            (255, 255, 0),   # Yellow
            (0, 255, 0),     # Green
            (0, 0, 255),     # Blue
            (75, 0, 130),    # Indigo
            (238, 130, 238)  # Violet
        ]
        random.shuffle(rainbow_colors)
        image = Image.new("RGB", (image_width, image_height), black)
        draw = ImageDraw.Draw(image)
        tv_body_padding = 60 + vertical_offset  
        tv_body_rect = [
            tv_body_padding,
            tv_body_padding,
            image_width - tv_body_padding,
            image_height - tv_body_padding - 40
        ]
        tv_body_radius = 20
        draw.rounded_rectangle(tv_body_rect, tv_body_radius, fill=brown)
        screen_padding = tv_body_padding + 15 
        screen_rect = [
            screen_padding,
            screen_padding,
            image_width - screen_padding,
            tv_body_rect[3] - 15
        ]
        draw.rectangle(screen_rect, fill=screen_bg)
        num_bars = len(rainbow_colors)
        bar_width = (screen_rect[2] - screen_rect[0]) // num_bars
        start_x = screen_rect[0]
        for color in rainbow_colors:
            bar_rect = [
                start_x,
                screen_rect[1],
                start_x + bar_width,
                screen_rect[3]
            ]
            draw.rectangle(bar_rect, fill=color)
            start_x += bar_width
        antenna_color = gray
        antenna_thickness = 3
        antenna_length = 50
        antenna_base_x1 = image_width // 2 - 30
        antenna_base_x2 = image_width // 2 + 30
        antenna_base_y = tv_body_padding  
        draw.line(
            (antenna_base_x1, antenna_base_y, antenna_base_x1 - 20, antenna_base_y - antenna_length),
            fill=antenna_color, width=antenna_thickness
        )
        draw.line(
            (antenna_base_x2, antenna_base_y, antenna_base_x2 + 20, antenna_base_y - antenna_length),
            fill=antenna_color, width=antenna_thickness
        )
        highlight_color = white
        highlight_thickness = 4
        highlight_offset = 5
        draw.line(
            (tv_body_rect[0], tv_body_rect[1], tv_body_rect[0] + 20, tv_body_rect[1]),
            fill=highlight_color, width=highlight_thickness
        )
        draw.line(
            (tv_body_rect[0], tv_body_rect[1], tv_body_rect[0], tv_body_rect[1] + 20),
            fill=highlight_color, width=highlight_thickness
        )
        image = image.resize((final_width, final_height), Image.Resampling.BICUBIC)
        return image

class SpotifyService:
    """Service to interact with Spotify API for album art and related data.""" 

    def __init__(self, config: "Config", session: aiohttp.ClientSession): 
        """Initialize SpotifyService object."""
        self.config = config
        self.session = session
        self.spotify_token_cache: dict[str, Any] = { 
            'token': None,
            'expires': 0
        }
        self.spotify_data: Optional[dict] = None 


    async def get_spotify_access_token(self) -> Optional[str]: 
        """Get Spotify API access token using client credentials, caching the token."""
        if self.spotify_token_cache['token'] and time.time() < self.spotify_token_cache['expires']:
            return self.spotify_token_cache['token']

        url = "https://accounts.spotify.com/api/token"
        spotify_headers = {
            "Authorization": "Basic " + base64.b64encode(f"{self.config.spotify_client_id}:{self.config.spotify_client_secret}".encode()).decode(),
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {"grant_type": "client_credentials"}
        try:
            async with self.session.post(url, headers=spotify_headers, data=payload, timeout=10) as response: 
                response.raise_for_status() 
                response_json = await response.json()
                access_token = response_json["access_token"]
                expiry_time = time.time() + response_json.get("expires_in", 3600) - 60 
                self.spotify_token_cache = {
                    'token': access_token,
                    'expires': expiry_time
                }
                return access_token
        except Exception:
            return None


    async def get_spotify_json(self, artist: str, title: str) -> Optional[dict]: 
        """Get raw JSON track search results from Spotify API."""
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
            async with self.session.get(url, headers=spotify_headers, params=payload, timeout=10) as response: 
                response.raise_for_status() 
                return await response.json()
        except Exception: 
            return None


    async def spotify_best_album(self, tracks: list[dict], artist: str) -> tuple[Optional[str], Optional[str]]: 
        """Determine the 'best' album ID and first album ID from Spotify track search results."""
        best_album = None
        earliest_year = float('inf')
        preferred_types = ["single", "album", "compilation"]
        first_album_id = tracks[0]['album']['id'] if tracks else None 
        for track in tracks:
            album = track.get('album')
            album_type = album.get('album_type')
            release_date = album.get('release_date')
            year = int(release_date[:4]) if release_date and release_date[:4].isdigit() else float('inf') 
            artists = album.get('artists', [])
            album_artist = artists[0]['name'] if artists else ""
            if artist.lower() == album_artist.lower():
                if album_type in preferred_types:
                    if year < earliest_year: 
                        earliest_year = year
                        best_album = album
                elif year < earliest_year: 
                    earliest_year = year
                    best_album = album

        if best_album:
            return best_album['id'], first_album_id
        else:
            return None, first_album_id


    async def get_spotify_album_id(self, media_data: "MediaData") -> tuple[Optional[str], Optional[str]]: 
        """Get the Spotify album ID and first album ID for a given artist and title."""
        token = await self.get_spotify_access_token()
        if not token:
            return None, None 
        try:
            self.spotify_data = None 
            response_json = await self.get_spotify_json(media_data.artist, media_data.title)
            self.spotify_data = response_json 
            tracks = response_json.get('tracks', {}).get('items', [])
            if tracks:
                best_album_id, first_album_id = await self.spotify_best_album(tracks, media_data.artist)
                return best_album_id, first_album_id
            else:
                return None, None 

        except Exception: 
            return None, None


    async def get_spotify_album_image_url(self, album_id: str) -> Optional[str]: 
        """Get the album image URL from Spotify API using album ID."""
        token = await self.get_spotify_access_token()
        if not token or not album_id:
            return None

        url = f"https://api.spotify.com/v1/albums/{album_id}"
        spotify_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        try:
            async with self.session.get(url, headers=spotify_headers, timeout=10) as response: 
                response.raise_for_status() 
                response_json = await response.json()
                images = response_json.get('images', [])
                if images:
                    return images[0]['url'] 
                return None
        except Exception: 
            return None


    async def get_spotify_artist_image_url_by_name(self, artist_name: str) -> Optional[str]: 
        """Retrieves the URL of the first image of a Spotify artist given their name."""
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
            async with self.session.get(search_url, headers=spotify_headers, params=search_payload, timeout=10) as response: 
                response.raise_for_status() 
                response_json = await response.json()
                artists = response_json.get('artists', {}).get('items', [])
                if not artists:
                    return None
                artist_id = artists[0]['id']
                return await self.get_spotify_artist_image_url(artist_id)
        except Exception: 
            return None

    async def get_spotify_artist_image_url(self, artist_id: str) -> Optional[str]: 
        """Retrieves the URL of the first image of a Spotify artist given their ID."""
        token = await self.get_spotify_access_token()
        if not token or not artist_id:
            return None

        url = f"https://api.spotify.com/v1/artists/{artist_id}"
        spotify_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        try:
            async with self.session.get(url, headers=spotify_headers, timeout=10) as response: 
                response.raise_for_status() 
                response_json = await response.json()
                images = response_json.get('images', [])
                if images:
                    return images[0]['url'] 
                return None
        except Exception: 
            return None


    """ Spotify Album Art Slide """
    async def get_album_list(self, media_data: "MediaData", returntype: str) -> list[str]: 
        """Retrieves album art URLs, filtering and prioritizing albums."""
        if not self.spotify_data or media_data.playing_tv:
            return []

        try:
            if not isinstance(self.spotify_data, dict):
                return []

            tracks = self.spotify_data.get('tracks', {}).get('items', [])
            albums = {} 
            for track in tracks:
                album = track.get('album', {})
                album_id = album.get('id')
                artists = album.get('artists', [])

                if any(artist.get('name', '').lower() == 'various artists' for artist in artists):
                    continue

                if media_data.artist.lower() not in [artist.get('name', '').lower() for artist in artists]:
                    continue

                if album_id not in albums:
                    albums[album_id] = album

            sorted_albums = sorted(albums.values(), key=lambda x: (
                x.get("album_type") == "single",  
                x.get("album_type") == "album",  
                x.get("album_type") == "compilation" 
            ), reverse=True)

            album_urls = []
            album_base64 = []
            show_lyrics_is_on = True if media_data.lyrics else False
            playing_radio_is_on = True if media_data.playing_radio else False

            for album in sorted_albums:
                images = album.get("images", [])
                if images:
                    album_urls.append(images[0]["url"])
                    if returntype == "b64":
                        base64_data = await self.get_slide_img(images[0]["url"], show_lyrics_is_on, playing_radio_is_on)
                        album_base64.append(base64_data)
            media_data.pic_url = album_urls
            media_data.pic_source = "Spotify (Slide)"
            if returntype == "b64":
                return album_base64
            else:
                media_data.pic_url = album_urls
                return album_urls

        except Exception as e: 
            _LOGGER.error(f"Error processing Spotify data to get album list: {e}") 
            return []


    async def get_slide_img(self, picture: str, show_lyrics_is_on: bool, playing_radio_is_on: bool) -> Optional[str]: 
        """Fetches, processes, and returns base64-encoded image data for Spotify slide."""
        try:
            async with self.session.get(picture, timeout=10) as response: 
                response.raise_for_status() 
                image_raw_data = await response.read()

        except Exception: 
            return None

        try: 
            with Image.open(BytesIO(image_raw_data)) as img:
                img = ensure_rgb(img)

                proc = ImageProcessor(self.config, self.session)

                if self.config.crop_borders:
                    img = proc.crop_image_borders(img, False)

                img = proc.fixed_size(img)
                img = img.resize((64, 64), Image.Resampling.BICUBIC)

                if self.config.limit_color or self.config.contrast or self.config.sharpness or self.config.colors or self.config.kernel:
                    img = proc.filter_image(img)

                if self.config.special_mode:
                    img = proc.special_mode(img)

                if show_lyrics_is_on and not playing_radio_is_on and not self.config.special_mode:
                    enhancer_lp = ImageEnhance.Brightness(img)
                    img = enhancer_lp.enhance(0.55)
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(0.5)

                return proc.gbase64(img)

        except Exception: 
            return None


    async def send_pixoo_animation_frame(self, pixoo_device: "PixooDevice", command: str, pic_num: int, pic_width: int, pic_offset: int, pic_id: int, pic_speed: int, pic_data: str) -> None: 
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
        await pixoo_device.send_command(payload)


    async def spotify_albums_slide(self, pixoo_device: "PixooDevice", media_data: "MediaData") -> None: 
        """Fetches and processes images for Spotify album slide animation."""
        media_data.spotify_slide_pass = True
        album_urls_b64 = await self.get_album_list(media_data, returntype="b64") 
        if not album_urls_b64:
            media_data.spotify_frames = 0
            media_data.spotify_slide_pass = False
            return

        frames = len(album_urls_b64)
        media_data.spotify_frames = frames
        if frames < 2:
            media_data.spotify_slide_pass = False
            media_data.spotify_frames = 0
            return

        pic_offset = 0
        await pixoo_device.send_command({"Command": "Draw/CommandList", "CommandList":
            [{"Command": "Channel/OnOffScreen", "OnOff": 1}, {"Command": "Draw/ResetHttpGifId"}]})

        for album_url_b64 in album_urls_b64:
            try:
                if album_url_b64:
                    pic_speed = 5000  # 5 seconds
                    await self.send_pixoo_animation_frame(
                        pixoo_device=pixoo_device,
                        command="Draw/SendHttpGif",
                        pic_num=frames,
                        pic_width=64,
                        pic_offset=pic_offset,
                        pic_id=0,
                        pic_speed=pic_speed,
                        pic_data=album_url_b64
                    )

                    pic_offset += 1
                else:
                    break 

            except Exception:
                break 


    async def spotify_album_art_animation(self, pixoo_device: "PixooDevice", media_data: "MediaData", start_time=None) -> None: 
        """Creates and sends a static slide show animation with 3 albums to the Pixoo device."""
        if media_data.playing_tv:
            return 

        try:
            album_urls = await self.get_album_list(media_data, returntype="url")
            if not album_urls:
                media_data.spotify_frames = 0
                return

            num_albums = len(album_urls)
            if num_albums < 3:
                media_data.spotify_frames = 0
                media_data.spotify_slide_pass = False
                return

            images = []
            for album_url in album_urls:
                try:
                    async with self.session.get(album_url, timeout=10) as response: 
                        response.raise_for_status() 
                        image_data = await response.read()
                        img = Image.open(BytesIO(image_data))
                        img = img.resize((34, 34), Image.Resampling.BICUBIC)
                        images.append(img)
                except Exception: 
                    return 

            total_frames = min(num_albums, 60)
            media_data.spotify_frames = total_frames

            await pixoo_device.send_command({"Command": "Draw/CommandList", "CommandList":
                [{"Command": "Channel/OnOffScreen", "OnOff": 1}, {"Command": "Draw/ResetHttpGifId"}]})

            pixoo_frames = []

            for index in range(total_frames):
                try:
                    canvas = Image.new("RGB", (64, 64), (0, 0, 0))

                    left_index = (index - 1) % num_albums
                    center_index = index % num_albums
                    right_index = (index + 1) % num_albums

                    x_positions = [1, 16, 51]

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
                        except Exception: 
                            return 

                    base64_image = ImageProcessor(self.config, self.session).gbase64(canvas)
                    pixoo_frames.append(base64_image)

                except Exception: 
                    return 

            pic_offset = 0
            pic_speed = 5000
            for i, frame in enumerate(pixoo_frames):
                await self.send_pixoo_animation_frame(
                    pixoo_device=pixoo_device,
                    command="Draw/SendHttpGif",
                    pic_num=total_frames,
                    pic_width=64,
                    pic_offset=pic_offset,
                    pic_id=0,
                    pic_speed=pic_speed,
                    pic_data=frame
                )

                pic_offset += 1
            media_data.spotify_slide_pass = True 

        except Exception: 
            media_data.spotify_frames = 0
            return

class Pixoo64_Media_Album_Art(hass.Hass):
    """AppDaemon app to display album art on Divoom Pixoo64 and control related features."""

    def __init__(self, *args, **kwargs):
        """Initialize Pixoo64_Media_Album_Art app."""
        super().__init__(*args, **kwargs)
        self.clear_timer_task: Optional[asyncio.Task[None]] = None
        self.callback_timeout: int = 20
        self.current_image_task: Optional[asyncio.Task[None]] = None
        self.debounce_task = None
        self._last_wled_payload = None
        self.last_text_payload_hash = None

    async def initialize(self):
        _LOGGER.info("Initializing Pixoo64 Album Art Display AppDaemon app…")
        
        self.config = Config(self.args)
        
        self.websession = aiohttp.ClientSession()
        self.pixoo_device = PixooDevice(self.config, self.websession)
        self.image_processor = ImageProcessor(self.config, self.websession)
        self.spotify_service = SpotifyService(self.config, self.websession)
        self.media_data = MediaData(self.config, self.image_processor, self.websession)
        self.fallback_service = FallbackService(self.config, self.image_processor, self.websession, self.spotify_service)

        self.listen_state(self._mode_changed, self.config.mode_entity)
        self.listen_state(self._crop_mode_changed, self.config.crop_entity)
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute="media_title")
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute="state")
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute="media_position_updated_at")

        try:
            initial_index = await self.pixoo_device.get_current_channel_index()
            if initial_index == 4:
                _LOGGER.info("Pixoo initialized on Fallback Screen (4). Defaulting internal state to Channel 0.")
                self.select_index = 0
                self.last_valid_index = 0
            else:
                self.select_index = initial_index
                self.last_valid_index = initial_index
                _LOGGER.info(f"Pixoo initialized on Channel {initial_index}.")
        except Exception as e:
            _LOGGER.error(f"Failed to fetch initial channel index: {e}. Defaulting to 0.")
            self.select_index = 0
            self.last_valid_index = 0

        self.media_data_sensor = self.config.pixoo_sensor

        try:
            await self._apply_mode_settings()
        except Exception as e:
            _LOGGER.error(f"Error applying Mode Settings: {e}")

        try:
            await self._apply_crop_settings()
        except Exception as e:
            _LOGGER.error(f"Error applying Crop Settings: {e}")

        if self.entity_exists(self.config.lyrics_sync_entity):
            self.config.lyrics_sync = (await self.get_state(self.config.lyrics_sync_entity)) or self.config.lyrics_sync
            self.listen_state(self._lyrics_sync_changed, self.config.lyrics_sync_entity, attribute="state")

        _LOGGER.info("Initialization complete.")

    async def terminate(self):
        if hasattr(self, 'websession') and self.websession:
            await self.websession.close()
            _LOGGER.info("Closed Pixoo64 aiohttp session.")

    # =========================================================================
    # SETTINGS & CONFIG HANDLERS
    # =========================================================================

    async def _lyrics_sync_changed(self, entity, attribute, old, new, kwargs):
        await self._apply_lyrics_sync()

    async def _apply_lyrics_sync(self):
        self.config.lyrics_sync = (await self.get_state(self.config.lyrics_sync_entity))

    async def _crop_mode_changed(self, entity, attribute, old, new, kwargs):
        await self._apply_crop_settings()

    async def _apply_crop_settings(self):
        """Creates the input_select if missing and applies the crop configuration."""
        options = ["Default", "No Crop", "Crop", "Extra Crop"]
        default = options[0]

        try:
            if not self.entity_exists(self.config.crop_entity):
                await self.set_state(self.config.crop_entity, state=options[0], attributes={"options": options})
                try:
                    await self.call_service("input_select/set_options", entity_id=self.config.crop_entity, options=options)
                except Exception:
                    pass 
            else:
                try:
                    await self.call_service("input_select/set_options", entity_id=self.config.crop_entity, options=options)
                except Exception:
                    pass

            mode = (await self.get_state(self.config.crop_entity)) or default

            m = mode.lower()
            if m == "no crop":
                self.config.crop_borders = False
                self.config.crop_extra = False
            elif m == "crop":
                self.config.crop_borders = True
                self.config.crop_extra = False
            elif m == "extra crop":
                self.config.crop_borders = True
                self.config.crop_extra = True
            elif m == "default":
                self.config.crop_borders = self.config.original_crop_borders
                self.config.crop_extra = self.config.original_crop_extra
            
            self.image_processor.image_cache.clear()
            
        except Exception as e:
            _LOGGER.error(f"Failed to apply crop settings: {e}", exc_info=True)

    async def _mode_changed(self, entity, attribute, old, new, kwargs):
        await self._apply_mode_settings()

    async def _apply_mode_settings(self):
        options = [
                "Default", "Clean", "AI Generation (Flux)", "AI Generation (Turbo)", "Burned", "Burned | Clock",
                "Burned | Clock (Background)", "Burned | Temperature", "Burned | Temperature (Background)", "Burned | Clock & Temperature (Background)",
                "Text", "Text (Background)", "Clock", "Clock (Background)", "Clock | Temperature",
                "Clock | Temperature (Background)", "Clock | Temperature | Text", "Clock | Temperature | Text (Background)",
                "Lyrics", "Lyrics (Background)", "Temperature", "Temperature (Background)",
                "Temperature | Text", "Temperature | Text (Background)", "Special Mode", "Special Mode | Text"
                ]
        default = options[0]
        spotify_api = bool(self.config.spotify_client_id and self.config.spotify_client_secret)
        if spotify_api:
            options.append("Spotify Slider (beta)")
            options.append("Spotify Slider Special Mode with Text (beta)")

        try:
            if not self.entity_exists(self.config.mode_entity):
                await self.set_state(self.config.mode_entity, state=options[0], attributes={"options": options})
                mode = "Default"
            else:
                mode = (await self.get_state(self.config.mode_entity)) or default

            try:
                await self.call_service("input_select/set_options", entity_id=self.config.mode_entity, options=options)
            except Exception:
                pass

            if mode:
                m = mode.lower()
                if not m == "default" and not m == "clean":
                    self.config.show_lyrics     = ("lyrics" in m) if m else False
                    self.config.spotify_slide   = ("slider" in m) if m else False
                    self.config.special_mode    = ("special" in m) if m else False
                    self.config.show_clock      = ("clock" in m) if m else False
                    self.config.temperature     = ("temperature" in m) if m else False
                    self.config.show_text       = ("text" in m) if m else False
                    self.config.text_bg         = ("background" in m) if m else False
                    self.config.force_ai        = ("ai" in m) if m else False
                    self.config.burned          = ("burned" in m) if m else False

                    if self.config.force_ai:
                        if "turbo" in m: self.config.ai_fallback = "turbo"
                        elif "flux" in m: self.config.ai_fallback = "flux"

                    self.config.special_mode_spotify_slider = bool(self.config.spotify_slide and self.config.special_mode and self.config.show_text)

                elif m == "clean":
                    self.config.show_lyrics = False
                    self.config.spotify_slide = False
                    self.config.special_mode = False
                    self.config.show_clock = False
                    self.config.temperature = False
                    self.config.show_text = False
                    self.config.text_bg = False
                    self.config.force_ai = False
                    self.config.ai_fallback = False
                    self.config.special_mode_spotify_slider = False
                    self.config.burned = False

                elif m == "default":
                    self.config.show_lyrics = self.config.original_show_lyrics
                    self.config.spotify_slide = self.config.original_spotify_slide
                    self.config.special_mode = self.config.original_special_mode
                    self.config.show_clock = self.config.original_show_clock
                    self.config.temperature = self.config.original_temperature
                    self.config.show_text = self.config.original_show_text
                    self.config.text_bg = self.config.original_text_bg
                    self.config.force_ai = self.config.original_force_ai
                    self.config.ai_fallback = self.config.original_ai_fallback
                    self.config.burned = self.config.original_burned
                    self.config.special_mode_spotify_slider = self.config.original_special_mode_spotify_slider
                
                self.image_processor.image_cache.clear()
                await self.safe_state_change_callback(self.config.media_player, "state", None, "playing", {})
        
        except Exception as e:
            _LOGGER.warning(f"Error checking mode entity: {e}")

        if self.config.show_lyrics:
            self.run_every(self.calculate_position, datetime.now(), 1) 

    # =========================================================================
    # STATE CALLBACKS & DEBOUNCING
    # =========================================================================

    async def safe_state_change_callback(self, entity: str, attribute: str, old: Any, new: Any, kwargs: Dict[str, Any]) -> None:
        if self.debounce_task and not self.debounce_task.done():
            self.debounce_task.cancel()
        
        self.debounce_task = asyncio.create_task(
            self._run_debounced_callback(entity, attribute, old, new, kwargs)
        )

    async def _run_debounced_callback(self, entity, attribute, old, new, kwargs):
        try:
            await asyncio.sleep(0.5)
            async with asyncio.timeout(self.callback_timeout):
                await self.state_change_callback(entity, attribute, old, new, kwargs)
        except asyncio.TimeoutError:
            _LOGGER.warning("Callback timed out after %s seconds.", self.callback_timeout)
        except asyncio.CancelledError:
            pass 
        except Exception as e:
            _LOGGER.error(f"Error in debounced callback: {e}")

    async def state_change_callback(self, entity: str, attribute: str, old: Any, new: Any, kwargs: Dict[str, Any]) -> None:
        try:
            if attribute == "media_position_updated_at" and not self.config.show_lyrics:
                return
            
            if new == old or (await self.get_state(self.config.toggle)) != "on":
                return 

            media_state_str = await self.get_state(self.config.media_player)
            media_state = media_state_str if media_state_str else "off"
            
            if media_state in ["off", "idle", "pause", "paused"]:
                if self.current_image_task and not self.current_image_task.done():
                    self.current_image_task.cancel()
                    self.current_image_task = None
                
                self.last_text_payload_hash = None
                await asyncio.sleep(6) 
                
                media_state_str_validated = await self.get_state(self.config.media_player)
                media_state_validated = media_state_str_validated if media_state_str_validated else "off"
                
                if media_state_validated in ["playing", "on"]:
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
                self.last_text_payload_hash = None
                await self.set_state(self.media_data_sensor, state="off")
                if self.config.light: await self.control_light('off')
                if self.config.wled: await self.control_wled_light('off')
                return 

            await self.update_attributes(entity, attribute, old, new, kwargs)
        except Exception as e:
            _LOGGER.error(f"Error in state_change_callback: {e}")

    async def update_attributes(self, entity: str, attribute: str, old: Any, new: Any, kwargs: Dict[str, Any]) -> None:
        try:
            media_state_str = await self.get_state(self.config.media_player)
            media_state = media_state_str if media_state_str else "off"
            if media_state not in ["playing", "on"]:
                if self.config.light: await self.control_light('off')
                if self.config.wled: await self.control_wled_light('off')
                return 

            media_data = await self.media_data.update(self)
            if not media_data:
                return

            await self.pixoo_run(media_state, media_data)
        except Exception as e:
            _LOGGER.error(f"Error in update_attributes: {e}", exc_info=True)

    # =========================================================================
    # PIXOO DISPLAY LOGIC
    # =========================================================================

    async def pixoo_run(self, media_state: str, media_data: "MediaData") -> None:
        try:
            async with asyncio.timeout(self.callback_timeout):
                # Ensure we are on the correct channel
                current_device_channel = await self.pixoo_device.get_current_channel_index()
                if current_device_channel != 4:
                    self.select_index = current_device_channel
                    self.last_valid_index = current_device_channel
                else:
                    if hasattr(self, 'last_valid_index') and self.last_valid_index != 4:
                        self.select_index = self.last_valid_index
                    else:
                        self.select_index = 0

                if media_state in ["playing", "on"]:
                    if self.current_image_task:
                        self.current_image_task.cancel()
                        self.current_image_task = None 

                    self.current_image_task = asyncio.create_task(self._process_and_display_image(media_data))
        except asyncio.TimeoutError:
            _LOGGER.warning("Pixoo run timed out after %s seconds.", self.callback_timeout)
        except Exception as e:
            _LOGGER.error(f"Error in pixoo_run: {e}", exc_info=True)
        finally:
            await asyncio.sleep(0.10)

    async def _process_and_display_image(self, media_data: "MediaData") -> None:
        if media_data.picture == "TV_IS_ON":
            payload = ({
                "Command": "Draw/CommandList",
                "CommandList": [
                    {"Command": "Channel/OnOffScreen", "OnOff": 1},
                    {"Command": "Draw/ClearHttpText"},
                    {"Command": "Draw/ResetHttpGifId"},
                    {"Command": "Channel/SetIndex", "SelectIndex": self.select_index}]
            })
            await self.pixoo_device.send_command(payload)
            if self.config.light: await self.control_light('off')
            if self.config.wled: await self.control_wled_light('off')
            self.last_text_payload_hash = None
            return 

        try:
            start_time = time.perf_counter()
            processed_data = await self.fallback_service.get_final_url(media_data.picture, media_data)

            if not processed_data:
                processed_data = self.fallback_service._get_fallback_black_image_data()

            media_data.spotify_frames = 0
            base64_image = processed_data.get('base64_image')
            font_color_from_image_processing = processed_data.get('font_color')
            brightness = processed_data.get('brightness')
            background_color_str = processed_data.get('background_color')
            background_color_rgb = processed_data.get('background_color_rgb')
            most_common_color_alternative_rgb_str = processed_data.get('most_common_color_alternative_rgb')
            most_common_color_alternative_str = processed_data.get('most_common_color_alternative')

            if self.config.light and not media_data.playing_tv:
                await self.control_light('on', background_color_rgb, media_data.is_night)
            
            if self.config.wled and not media_data.playing_tv:
                color1 = processed_data.get('color1')
                color2 = processed_data.get('color2')
                color3 = processed_data.get('color3')
                await self.control_wled_light('on', color1, color2, color3, media_data.is_night)
            
            if media_data.playing_tv:
                if self.config.light: await self.control_light('off')
                if self.config.wled: await self.control_wled_light('off')
            
            sensor_state = f"{media_data.artist} / {media_data.title}"
            new_attributes = {
                "artist": media_data.artist,
                "media_title": media_data.title,
                "font_color": font_color_from_image_processing,
                "background_color_brightness": brightness,
                "background_color": background_color_str,
                "color_alternative_rgb": most_common_color_alternative_str, 
                "background_color_rgb": background_color_rgb,
                "color_alternative": most_common_color_alternative_rgb_str,
                "images_in_cache": media_data.image_cache_count,
                "image_memory_cache": media_data.image_cache_memory,
                "process_duration": media_data.process_duration,
                "spotify_frames": media_data.spotify_frames,
                "pixoo_channel": self.select_index,
                "image_source": media_data.pic_source,
                "image_url": media_data.pic_url,
                "lyrics": media_data.lyrics
            }

            image_payload = {
                "Command": "Draw/CommandList",
                "CommandList": [
                    {"Command": "Channel/OnOffScreen", "OnOff": 1},
                    {"Command": "Draw/ClearHttpText"},
                    {"Command": "Draw/ResetHttpGifId"},
                    {"Command": "Draw/SendHttpGif",
                        "PicNum": 1, "PicWidth": 64, "PicOffset": 0,
                        "PicID": 0, "PicSpeed": 10000, "PicData": base64_image}]}

            spotify_animation_took_over_display = False
            
            # Spotify Slide Logic
            if self.config.spotify_slide and not media_data.radio_logo and not media_data.playing_tv:
                self.spotify_service.spotify_data = await self.spotify_service.get_spotify_json(media_data.artist, media_data.title)
                if self.spotify_service.spotify_data:
                    spotify_anim_start_time = time.perf_counter()
                    if self.config.special_mode:
                        if self.config.special_mode_spotify_slider:
                            await self.spotify_service.spotify_album_art_animation(self.pixoo_device, media_data)
                    else:
                        await self.spotify_service.spotify_albums_slide(self.pixoo_device, media_data)

                    if media_data.spotify_slide_pass:
                        spotify_animation_took_over_display = True
                        spotify_anim_end_time = time.perf_counter()
                        duration = spotify_anim_end_time - spotify_anim_start_time
                        media_data.process_duration = f"{duration:.2f} seconds (Spotify)"
                        new_attributes["process_duration"] = media_data.process_duration
                        new_attributes["spotify_frames"] = media_data.spotify_frames
                    else:
                        await self.pixoo_device.send_command({"Command": "Channel/SetIndex", "SelectIndex": 4})

            # Text Overlay Logic
            text_items_for_display_list = []
            current_text_id = 0
            
            text_overlay_font_color = '#ffff00'
            brightness_factor = 50
            if self.config.force_font_color:
                text_overlay_font_color = self.config.force_font_color
            elif background_color_rgb:
                try:
                    color_font_rgb_calc = tuple(min(255, c + brightness_factor) for c in background_color_rgb)
                    if not self.config.text_bg:
                        opposite_color_rgb = self.compute_opposite_color(color_font_rgb_calc)
                        color_font_rgb_calc = opposite_color_rgb
                    text_overlay_font_color = f'#{color_font_rgb_calc[0]:02x}{color_font_rgb_calc[1]:02x}{color_font_rgb_calc[2]:02x}'
                except Exception:
                    text_overlay_font_color = '#ffff00'
            
            if self.config.special_mode:
                current_text_id += 1
                day_item = { "TextId": current_text_id, "type": 14, "x": 3, "y": 1, "dir": 0, "font": 18, "TextWidth": 33, "Textheight": 6, "speed": 100, "align": 1, "color": text_overlay_font_color}
                text_items_for_display_list.append(day_item)

                current_text_id += 1
                clock_item_special = { "TextId": current_text_id, "type": 5, "x": 0, "y": 1, "dir": 0, "font": 18, "TextWidth": 64, "Textheight": 6, "speed": 100, "align": 2, "color": background_color_str}
                text_items_for_display_list.append(clock_item_special)

                current_text_id += 1
                if media_data.temperature:
                    temp_item_special = {"TextId": current_text_id, "type": 22, "x": 44, "y": 1, "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6, "speed": 100, "align": 1, "color": text_overlay_font_color, "TextString": media_data.temperature}
                else:
                    temp_item_special = {"TextId": current_text_id, "type": 17, "x": 44, "y": 1, "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6, "speed": 100, "align": 3, "color": text_overlay_font_color}
                text_items_for_display_list.append(temp_item_special)

                if (self.config.show_text and not media_data.playing_tv) or (media_data.spotify_slide_pass and self.config.spotify_slide):
                    dir_rtl_artist = 1 if has_bidi(media_data.artist) else 0
                    text_artist_bidi = get_bidi(media_data.artist) if dir_rtl_artist == 1 else media_data.artist
                    current_text_id += 1
                    artist_item = { "TextId": current_text_id, "type": 22, "x": 0, "y": 42, "dir": dir_rtl_artist, "font": 190, "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 2, "TextString": text_artist_bidi, "color": text_overlay_font_color}
                    text_items_for_display_list.append(artist_item)

                    dir_rtl_title = 1 if has_bidi(media_data.title) else 0
                    text_title_bidi = get_bidi(media_data.title) if dir_rtl_title == 1 else media_data.title
                    current_text_id += 1
                    title_item = { "TextId": current_text_id, "type": 22, "x": 0, "y": 52, "dir": dir_rtl_title, "font": 190, "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 2, "TextString": text_title_bidi, "color": background_color_str}
                    text_items_for_display_list.append(title_item)
        
            elif (self.config.show_text or self.config.show_clock or self.config.temperature) and not (self.config.show_lyrics or self.config.spotify_slide):
                if self.config.top_text:
                    y_text = 0
                    y_info = 56
                else:
                    y_text = 48
                    y_info = 3

                text_track = (media_data.artist + " - " + media_data.title)
                if len(text_track) > 14: text_track = text_track + "       "
                text_string_bidi = get_bidi(text_track) if media_data.artist else get_bidi(media_data.title)
                dir_rtl = 1 if has_bidi(text_string_bidi) else 0

                if text_string_bidi and self.config.show_text and not media_data.radio_logo and not media_data.playing_tv:
                    current_text_id += 1
                    text_item = { "TextId": current_text_id, "type": 22, "x": 0, "y": y_text, "dir": dir_rtl, "font": 2, "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 2, "TextString": text_string_bidi, "color": text_overlay_font_color}
                    text_items_for_display_list.append(text_item)

                if self.config.show_clock:
                    current_text_id += 1
                    x_clock = 44 if self.config.clock_align == "Right" else 3
                    clock_item_normal = { "TextId": current_text_id, "type": 5, "x": x_clock, "y": y_info, "dir": 0, "font": 18, "TextWidth": 32, "Textheight": 16, "speed": 100, "align": 1, "color": text_overlay_font_color}
                    text_items_for_display_list.append(clock_item_normal)

                if self.config.temperature:
                    current_text_id += 1
                    x_temp = 3 if self.config.clock_align == "Right" else 40
                    if media_data.temperature:
                        temp_item_normal = {"TextId": current_text_id, "type": 22, "x": x_temp, "y": y_info, "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6, "speed": 100, "align": 1, "color": text_overlay_font_color, "TextString": media_data.temperature}
                    else:
                        temp_item_normal = {"TextId": current_text_id, "type": 17, "x": x_temp, "y": y_info, "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6, "speed": 100, "align": 1, "color": text_overlay_font_color}
                    text_items_for_display_list.append(temp_item_normal)

            if not spotify_animation_took_over_display:
                await self.pixoo_device.send_command(image_payload)
                if text_items_for_display_list:
                    txt_payload = ({ "Command": "Draw/SendHttpItemList", "ItemList": text_items_for_display_list })
                    current_payload_hash = str(txt_payload)
                
                    # Only send if the payload is different from the last one sent
                    if current_payload_hash != self.last_text_payload_hash:
                        await asyncio.sleep(0.10)
                        await self.pixoo_device.send_command(txt_payload)
                        self.last_text_payload_hash = current_payload_hash

            elif spotify_animation_took_over_display and self.config.special_mode and text_items_for_display_list:
                await self.pixoo_device.send_command({ "Command": "Draw/SendHttpItemList", "ItemList": text_items_for_display_list })
            
            end_time = time.perf_counter()
            if not spotify_animation_took_over_display:
                duration = end_time - start_time
                media_data.process_duration = f"{duration:.2f} seconds"
            new_attributes["process_duration"] = media_data.process_duration
            new_attributes["spotify_frames"] = media_data.spotify_frames
            await self.set_state(self.media_data_sensor, state=sensor_state, attributes=new_attributes)

            # Fallback Failure Logic
            if self.fallback_service.fail_txt and self.fallback_service.fallback:
                black_img = self.fallback_service.create_black_screen()
                black_pic = self.image_processor.gbase64(black_img)
                payload_fail_commands = {
                    "Command": "Draw/CommandList",
                    "CommandList": [
                        {"Command": "Channel/OnOffScreen", "OnOff": 1},
                        {"Command": "Draw/ResetHttpGifId"},
                    ]
                }
                await self.pixoo_device.send_command(payload_fail_commands)
                await self.pixoo_device.send_command({
                    "Command": "Draw/SendHttpGif",
                    "PicNum": 1, "PicWidth": 64,
                    "PicOffset": 0, "PicID": 0,
                    "PicSpeed": 1000, "PicData": black_pic
                })
                payloads_text_fail = self.create_payloads(media_data.artist, media_data.title, 11)
                await self.pixoo_device.send_command(payloads_text_fail)
                return

        except asyncio.CancelledError:
            pass
        except Exception as e:
            _LOGGER.error(f"Error in _process_and_display_image: {e}", exc_info=True)
        finally:
            self.current_image_task = None

    # =========================================================================
    # HELPERS & UTILITIES
    # =========================================================================

    def compute_opposite_color(self, color: tuple[int,int,int]) -> tuple[int,int,int]:
        return tuple(255 - c for c in color)

    async def control_light(self, action: str, background_color_rgb: Optional[tuple[int, int, int]] = None, is_night: bool = True) -> None:
        if not is_night and self.config.only_at_night:
            return 
        service_data = {'entity_id': self.config.light}
        if action == 'on':
            service_data.update({'rgb_color': background_color_rgb, 'transition': 1, })
        try:
            await self.call_service(f'light/turn_{action}', **service_data)  
        except Exception as e:
            _LOGGER.error(f"Error controlling Home Assistant light '{self.config.light}': {e}", exc_info=True)

    async def control_wled_light(self, action: str, color1: Optional[str] = None, color2: Optional[str] = None, color3: Optional[str] = None, is_night: bool = True) -> None:
        if not is_night and self.config.only_at_night:
            return
        ip_address = self.config.wled
        if not ip_address:
            return
        
        effect_id = self.config.effect
        segment = {"fx": effect_id}
        clean_colors = [c.lstrip('#') for c in [color1, color2, color3] if c]
        if clean_colors:
            if effect_id == 0:
                segment["col"] = [clean_colors[0]] 
            else:
                segment["col"] = clean_colors
        
        target_signature = (
            action, 
            tuple(clean_colors), 
            effect_id, 
            self.config.brightness,
            self.config.effect_speed,
            self.config.effect_intensity,
            self.config.palette,
            self.config.sound_effect
        )

        # Check Cache
        if self._last_wled_payload == target_signature:
            return

        # Prepare Payload
        if self.config.effect_speed: segment["sx"] = self.config.effect_speed
        if self.config.effect_intensity: segment["ix"] = self.config.effect_intensity
        if self.config.palette: segment["pal"] = self.config.palette
        if self.config.sound_effect: segment["si"] = self.config.sound_effect
        payload = {"on": True, "bri": self.config.brightness, "seg": [segment]}
        if action == "off":
            payload = {"on": False}
        
        url = f"http://{ip_address}/json/state"
        try:
            async with self.websession.post(url, json=payload, timeout=10, ssl=False) as response:
                response.raise_for_status()
                self._last_wled_payload = target_signature
        except Exception:
            pass

    def create_payloads(self, artist: str, title: str, line_length: int) -> dict:
        artist_lines = split_string(artist, line_length)
        title_lines = split_string(title, line_length)
        all_lines = artist_lines + title_lines
        if len(all_lines) > 5:
            all_lines = all_lines[:5]
        start_y = (64 - len(all_lines) * 12) // 2
        item_list = []
        for i, line in enumerate(all_lines):
            text_string = get_bidi(line) if has_bidi(line) else line
            y = start_y + (i * 12)
            dir_rtl = 1 if has_bidi(line) else 0
            item_list.append({
                "TextId": i + 1, "type": 22,
                "x": 0, "y": y, "dir": dir_rtl, "font": 190,  
                "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 2,
                "TextString": text_string,
                "color": "#a0e5ff" if i < len(artist_lines) else "#f9ffa0",  
            })
        return { "Command": "Draw/SendHttpItemList", "ItemList": item_list }

    async def calculate_position(self, kwargs: Dict[str, Any]) -> None:
        await self.media_data.lyrics_provider.calculate_position(self.media_data, self)
