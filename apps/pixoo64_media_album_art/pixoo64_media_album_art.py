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
        media_player: "media_player.living_room"    # The entity ID of your media player.
    pixoo:
        url: "192.168.86.21"                        # The IP address of your Pixoo64 device.


# Full Configuration
# ------------------
pixoo64_media_album_art:
  module: pixoo64_media_album_art
  class: Pixoo64_Media_Album_Art
  
  # --- Home Assistant Configuration ---
  home_assistant:
    ha_url: "http://homeassistant.local:8123"   # Your Home Assistant URL
    media_player: "media_player.era300"         # Your media player entity ID
    toggle: "input_boolean.pixoo64_album_art"   # Main On/Off switch
    pixoo_sensor: "sensor.pixoo64_media_data"   # Sensor to expose data back to HA
    
    # Optional Helpers (Create in HA first)
    lyrics_sync_entity: "input_number.pixoo64_album_art_lyrics_sync"
    mode_select: "input_select.pixoo64_album_art_display_mode"
    crop_select: "input_select.pixoo64_album_art_crop_mode"
    
    # External Sensors & Lights
    temperature_sensor: "sensor.temperature"    # For displaying temperature
    light: "light.living_room"                  # RGB light to sync with album colors

    # --- API Keys (Optional) ---
    # spotify_client_id: "YOUR_ID"
    # spotify_client_secret: "YOUR_SECRET"
    # tidal_client_id: "YOUR_ID"
    # tidal_client_secret: "YOUR_SECRET"
    # last.fm: "YOUR_API_KEY"
    # discogs: "YOUR_TOKEN"
    # pollinations: "YOUR_API_KEY" # Optional for AI art

  # --- Pixoo Device Configuration ---
  pixoo:
    url: "192.168.86.21"                        # IP Address of your Pixoo64
    full_control: True                          # Turn screen on/off with media
    
    # Image Filters
    contrast: True
    sharpness: False
    colors: False
    
    # Display Features
    clock: True
    clock_align: "Right"                        # "Left" or "Right"
    temperature: True
    lyrics: False                               # Show lyrics by default?
    lyrics_font: 2                              # Font ID for lyrics
    
    # --- Text Overlay Settings ---
    show_text:
      enabled: False                            # Show Artist/Title by default
      clean_title: True                         # Remove "Remastered", etc.
      text_background: True                     # Add dark background behind text
      top_text: True                            # Show text at top instead of bottom
      
    # --- Crop Settings ---
    crop_borders:
      enabled: True                             # Crop black borders
      extra: True                               # Aggressive cropping (Face focus)

  # --- WLED Integration (Optional) ---
  wled:
    wled_ip: "192.168.86.55"
    brightness: 255
    effect: 38
    only_at_night: False

  # --- Progress Bar Configuration ---
  progress_bar:
    enabled: True                                # Master switch for the feature
    entity: "input_boolean.pixoo64_progress_bar" # Helper to toggle via dashboard
    color: "match"                               # "match" (auto-contrast) or any hex "#FF0000"

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
import colorsys
import urllib.parse
from appdaemon.plugins.hass import hassapi as hass
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Optional, Tuple
from functools import lru_cache

# Third-party library imports
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageStat, ImageChops, ImageOps

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

def format_memory_size(size):
    return f"{size / 1024:.2f} KB"

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

def _resize_image_sync(image_data: bytes) -> Optional[Image.Image]:
    try:
        img = Image.open(BytesIO(image_data))
        img.load() 
        if img.mode != "RGB":
            img = img.convert("RGB")
        img = img.resize((34, 34), Image.Resampling.BICUBIC)
        return img
    except Exception:
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
            'tv_icon_pic': ('tv_icon', False),
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
        'progress_bar': {
            'progress_bar_enabled': ('enabled', False),
            'progress_bar_entity': ('entity', 'input_boolean.pixoo64_progress_bar'),
            'progress_bar_character': ('character', '-'),
            'progress_bar_font': ('font', 190),
            'progress_bar_resolution': ('resolution', 21),
            'progress_bar_color': ('color', 'match'),
            'progress_bar_y_offset': ('y_offset', 64),
            'progress_bar_exclude_modes': ('exclude_modes', [])
        },
    }

    NESTED_YAML_STRUCTURE_MAP: Dict[str, str] = {
        'show_text': 'pixoo',
        'crop_borders': 'pixoo',
        'progress_bar': 'pixoo64_media_album_art' # Fallback mapping
    }

    def __init__(self, app_args: Dict[str, Any]):
        for section_key_in_defaults, defaults_for_section in self.SECTION_DEFAULTS.items():
            user_data_for_this_section = {}
            # Try to find config in nested structure or root
            parent_yaml_key = self.NESTED_YAML_STRUCTURE_MAP.get(section_key_in_defaults)
            
            # Special handling for progress_bar to allow it at root or inside pixoo
            if section_key_in_defaults == 'progress_bar':
                user_data_for_this_section = app_args.get('progress_bar', {})
            elif parent_yaml_key:
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

        # Store originals
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
    """Handles communication with the Divoom Pixoo device with retry logic.""" 

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

    async def send_command(self, payload_command: dict, retries: int = 3) -> None: 
        """Sends a command with automatic retries on failure."""
        if self.session.closed:
            return

        for attempt in range(1, retries + 1):
            try:
                async with self.session.post(
                    self.config.pixoo_url,
                    headers=self.headers,
                    json=payload_command,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        await asyncio.sleep(0.1)
                        return
                    else:
                        response_text = await response.text() 
                        _LOGGER.warning(f"Pixoo command failed (Attempt {attempt}/{retries}). Status: {response.status}") 
            
            except (aiohttp.ClientError, asyncio.TimeoutError) as e: 
                if attempt == retries:
                    _LOGGER.error(f"Failed to send command to Pixoo after {retries} attempts: {e}")
                else:
                    await asyncio.sleep(0.2 * attempt)
            
            except Exception as e:
                if "Session is closed" not in str(e):
                    _LOGGER.exception(f"Unexpected error sending to Pixoo: {e}")
                return

    async def get_current_channel_index(self) -> int: 
        if self.session.closed: return 0
        
        channel_command = { "Command": "Channel/GetIndex" }
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
        except Exception: 
            return 0

class ImageProcessor:
    """Processes images for display on the Pixoo64 device, including caching and filtering."""

    def __init__(self, config: "Config", session: aiohttp.ClientSession):
        self.config = config
        self.session = session
        self.image_cache: OrderedDict[str, dict] = OrderedDict()
        self.cache_size: int = config.images_cache
        
        self._current_cache_memory: int = 0
        
        self._executor = ThreadPoolExecutor(max_workers=15, thread_name_prefix="PixooImageProc")
        
        self._default_font = ImageFont.load_default()

    def shutdown(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False)
        
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

    def _update_cache_memory_tracker(self, item: dict, add: bool = True):
        size = self._calculate_item_size(item)
        if add:
            self._current_cache_memory += size
        else:
            self._current_cache_memory = max(0, self._current_cache_memory - size)

    async def get_image(self, picture: Optional[str], media_data: "MediaData", spotify_slide: bool = False) -> Optional[dict]:
        if not picture:
            return None

        if self.config.burned:
            cache_key = f"{picture}_{media_data.artist}_{media_data.title}"
        else:
            cache_key = picture

        use_cache = not spotify_slide and not media_data.playing_tv
        cached_data = None

        if use_cache and cache_key in self.image_cache:
            self.image_cache.move_to_end(cache_key)
            cached_data = self.image_cache[cache_key]
            
            media_data.image_cache_memory = format_memory_size(self._current_cache_memory)
            media_data.image_cache_count = self._cache_size
            
        else:
            try:
                url = picture if picture.startswith('http') else f"{self.config.ha_url}{picture}"
                async with self.session.get(url, timeout=30) as response:
                    response.raise_for_status()
                    image_data = await response.read()
                    
                    cached_data = await self.process_image_data(image_data, media_data)
                    
                    if cached_data and not spotify_slide:
                        if len(self.image_cache) >= self.cache_size:
                            _, popped = self.image_cache.popitem(last=False)
                            self._update_cache_memory_tracker(popped, add=False)
                        
                        self.image_cache[cache_key] = cached_data
                        self._update_cache_memory_tracker(cached_data, add=True)
                        
                        media_data.image_cache_memory = format_memory_size(self._current_cache_memory)
                        media_data.image_cache_count = self._cache_size
            except Exception as e:
                _LOGGER.error(f"Error fetching/processing image: {e}")
                return None

        if not cached_data:
            return None

        final_img = cached_data['pil_image'].copy()
        
        # Pass full cached_data for colorful bars
        final_img = self.text_clock_img(final_img, cached_data, media_data)
        
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
        try:
            return await loop.run_in_executor(self._executor, self._process_image, image_data, media_data)
        except Exception as e:
            _LOGGER.exception(f"Error during thread pool image processing: {e}")
            return None

    def _process_image(self, image_data: bytes, media_data: "MediaData") -> Optional[dict]:
        try:
            with Image.open(BytesIO(image_data)) as img:
                img.load() 
                img = ensure_rgb(img)
                
                max_dimension = 640
                if max(img.size) > max_dimension:
                    scale_factor = max_dimension / max(img.size)
                    new_size = (int(img.width * scale_factor), int(img.height * scale_factor))
                    img = img.resize(new_size, Image.Resampling.BICUBIC)

                if (self.config.crop_borders or self.config.special_mode) and not media_data.radio_logo:
                    img = self.crop_image_borders(img, media_data.radio_logo)

                img = self.fixed_size(img)

                if img.width > 64 or img.height > 64:
                    img = img.resize((64, 64), Image.Resampling.BICUBIC)

                if self.config.contrast or self.config.sharpness or self.config.colors or self.config.kernel or self.config.limit_color:
                    img = self.filter_image(img)
                
                if self.config.burned and not media_data.radio_logo:
                    img = self._draw_burned_text(img, media_data.artist, media_data.title_clean)

                if self.config.special_mode:
                    img = self.special_mode(img)
                
                vals = self.img_values(img)
                
                # --- FONT COLOR ASSIGNMENT ---
                if self.config.force_font_color:
                    media_data.lyrics_font_color = self.config.force_font_color
                elif vals.get('font_color'):
                    media_data.lyrics_font_color = vals['font_color']
                elif vals.get('most_common_color_alternative'):
                    media_data.lyrics_font_color = vals['most_common_color_alternative']
                else:
                    media_data.lyrics_font_color = "#FF00FF"

                media_data.color1 = vals['color1']
                media_data.color2 = vals['color2']
                media_data.color3 = vals['color3']

                return {
                    'pil_image': img, 
                    'font_color': vals['font_color'],
                    'brightness': vals['brightness'],
                    'brightness_lower_part': vals['brightness_lower_part'],
                    'background_color': vals['background_color'],
                    'background_color_rgb': vals['background_color_rgb'],
                    'most_common_color_alternative_rgb': vals['most_common_color_alternative_rgb'],
                    'most_common_color_alternative': vals['most_common_color_alternative'],
                    'color1': vals['color1'],
                    'color2': vals['color2'],
                    'color3': vals['color3']
                }

        except Exception as e:
            _LOGGER.error(f"Error processing image: {e}")
            return None

    async def process_slide_image(self, image_data: bytes, show_lyrics_is_on: bool, playing_radio_is_on: bool) -> Optional[str]:
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                self._executor, 
                self._process_slide_image_sync, 
                image_data, show_lyrics_is_on, playing_radio_is_on
            )
        except Exception as e:
            _LOGGER.error(f"Error processing slide image: {e}")
            return None

    def _process_slide_image_sync(self, image_data: bytes, show_lyrics_is_on: bool, playing_radio_is_on: bool) -> Optional[str]:
        try:
            with Image.open(BytesIO(image_data)) as img:
                img = ensure_rgb(img)
                img = self.fixed_size(img)
                img = img.resize((64, 64), Image.Resampling.BICUBIC)

                if self.config.special_mode:
                    img = self.special_mode(img)

                if show_lyrics_is_on and not playing_radio_is_on and not self.config.special_mode:
                    enhancer_lp = ImageEnhance.Brightness(img)
                    img = enhancer_lp.enhance(0.55)
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(0.5)

                return self.gbase64(img)
        except Exception as e:
            _LOGGER.error(f"Sync slide processing error: {e}")
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
        if self.config.colors:
            img = ImageEnhance.Color(img).enhance(1.5)
        if self.config.contrast:
            img = ImageEnhance.Contrast(img).enhance(1.5)
        if self.config.sharpness:
            img = ImageEnhance.Sharpness(img).enhance(4.0)
        if self.config.kernel:
            kernel_5x5 = [-2,  0, -1,  0,  0,
                        0, -2, -1,  0,  0,
                        -1, -1,  1,  1,  1,
                        0,  0,  1,  2,  0,
                        0,  0,  1,  0,  2]
            img = img.filter(ImageFilter.Kernel((5, 5), kernel_5x5, 1, 0))
        
        if img.size != (64, 64):
            img = img.resize((64, 64), Image.Resampling.BILINEAR)

        target_colors = int(self.config.limit_color) if self.config.limit_color else 64

        if self.config.limit_color:
            img = img.quantize(colors=target_colors, method=Image.Quantize.MAXCOVERAGE).convert("RGB")
        return img

    def special_mode(self, img: Image.Image) -> Image.Image:
        if img is None: return None
        output_size = (64, 64)
        album_size = (34, 34) if self.config.show_text else (56, 56)
        
        album_art = img.resize(album_size, Image.Resampling.BICUBIC)

        try:
            left_color = album_art.getpixel((0, album_size[1] // 2))
            right_color = album_art.getpixel((album_size[0] - 1, album_size[1] // 2))
        except Exception:
            left_color = (100, 100, 100)
            right_color = (150, 150, 150)

        if album_size == (34, 34):
            # Gradient Optimization
            gradient_source = Image.new("RGB", (2, 1))
            gradient_source.putpixel((0, 0), left_color)
            gradient_source.putpixel((1, 0), right_color)
            background = gradient_source.resize(output_size, Image.Resampling.BICUBIC)
        else:
            dark_background_color = (
                min(left_color[0], right_color[0]) // 2,
                min(left_color[1], right_color[1]) // 2,
                min(left_color[2], right_color[2]) // 2
            )
            background = Image.new('RGB', output_size, dark_background_color)

        x = (output_size[0] - album_size[0]) // 2
        y = 8 
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

    def text_clock_img(self, img: Image.Image, cached_data: dict, media_data: "MediaData") -> Image.Image:
        
        brightness_lower_part = cached_data.get('brightness_lower_part', 0.5)

        # 1. Apply Lyrics Dimming
        if media_data.lyrics and self.config.show_lyrics and self.config.text_bg and brightness_lower_part != None and not media_data.playing_radio:
            enhancer_lp = ImageEnhance.Brightness(img)
            img = enhancer_lp.enhance(0.55)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(0.5)

        # 2. Apply Clock Overlay
        if bool(self.config.show_clock and self.config.text_bg) and not self.config.show_lyrics:
            if self.config.top_text: lpc = (43, 55, 62, 62) if self.config.clock_align == "Right" else (2, 55, 21, 62)
            else: lpc = (43, 2, 62, 9) if self.config.clock_align == "Right" else (2, 2, 21, 9)
            lower_part_img = img.crop(lpc); enhancer_lp = ImageEnhance.Brightness(lower_part_img); lower_part_img = enhancer_lp.enhance(0.3); img.paste(lower_part_img, lpc)

        # 3. Apply Temperature Overlay
        if bool(self.config.temperature and self.config.text_bg) and not self.config.show_lyrics:
            if self.config.top_text: lpc = (2, 55, 18, 62) if self.config.clock_align == "Right" else (47, 55, 63, 62)
            else: lpc = (2, 2, 18, 9) if self.config.clock_align == "Right" else (47, 2, 63, 9)
            lower_part_img = img.crop(lpc); enhancer_lp = ImageEnhance.Brightness(lower_part_img); lower_part_img = enhancer_lp.enhance(0.3); img.paste(lower_part_img, lpc)

        # 4. Apply Text Background
        if self.config.text_bg and self.config.show_text and not self.config.show_lyrics and not media_data.playing_tv:
            if self.config.top_text: lpc = (0, 0, 64, 16)
            else: lpc = (0, 48, 64, 64)
            lower_part_img = img.crop(lpc); enhancer_lp = ImageEnhance.Brightness(lower_part_img); lower_part_img = enhancer_lp.enhance(brightness_lower_part); img.paste(lower_part_img, lpc)

        # 5. Apply Progress Bar
        if getattr(media_data, 'show_progress_bar', False):
            y_bottom = self.config.progress_bar_y_offset - 1
            if y_bottom >= 63: y_bottom = 63
            y_top = y_bottom - 1 
            
            # --- Draw Background Overlay (Track) with Gradient ---
            try:
                # Top Line (20% Darker -> 0.8 brightness)
                top_box = (0, y_top, 64, y_top + 1)
                top_area = img.crop(top_box)
                top_area = ImageEnhance.Brightness(top_area).enhance(0.8)
                img.paste(top_area, top_box)

                # Bottom Line (50% Darker -> 0.5 brightness)
                bottom_box = (0, y_bottom, 64, y_bottom + 1)
                bottom_area = img.crop(bottom_box)
                bottom_area = ImageEnhance.Brightness(bottom_area).enhance(0.5)
                img.paste(bottom_area, bottom_box)
            except Exception: pass

            # --- DETERMINE VIBRANT COLOR (NO BLACK/WHITE) ---
            bar_color_rgb = cached_data.get('most_common_color_alternative_rgb')
            
            def is_boring(rgb):
                """Returns True if color is Black, White, or Grayscale."""
                if not rgb: return True
                r, g, b = rgb
                # Check for extreme darkness or brightness
                if sum(rgb) < 50: return True   # Too Black
                if sum(rgb) > 700: return True  # Too White
                # Check saturation (Grayscale check)
                if max(rgb) - min(rgb) < 20: return True 
                return False

            # 1. Check the calculated vibrant color
            if is_boring(bar_color_rgb):
                # 2. Try the Font Color
                fc_hex = cached_data.get('font_color')
                if fc_hex and fc_hex.startswith('#'):
                    bar_color_rgb = self._hex_to_rgb(fc_hex)
                
                # 3. If Font Color is ALSO boring, force Cyan
                if is_boring(bar_color_rgb):
                    bar_color_rgb = (0, 255, 255)

            draw = ImageDraw.Draw(img)
            
            duration = float(getattr(media_data, 'media_duration', 0) or 0)
            position = float(getattr(media_data, 'media_position', 0) or 0)
            
            bar_width = 0
            if duration > 0:
                remaining = duration - position
                if remaining <= 10:
                    bar_width = 64
                else:
                    pct = position / duration
                    bar_width = int(64 * pct)
                    if position > 0 and bar_width < 2:
                        bar_width = 2
            else:
                bar_width = 64

            if bar_width > 0:
                bar_width = min(bar_width, 64)
                draw.rectangle([(0, y_top), (bar_width - 1, y_bottom)], fill=bar_color_rgb)
            
        return img

    def img_values(self, img: Image.Image) -> dict:
        full_img = img
        lower_part = img.crop((3, 48, 61, 61))
        
        colors_raw = lower_part.getcolors(maxcolors=1024)
        if colors_raw:
            most_common_colors_lower_part = sorted([(c[1], c[0]) for c in colors_raw], key=lambda x: x[1], reverse=True)
        else:
            most_common_colors_lower_part = []

        most_common_color = self.most_vibrant_color(most_common_colors_lower_part)
        opposite_color = tuple(255 - i for i in most_common_color)
        opposite_color_brightness = int(sum(opposite_color) / 3)
        brightness_lower_part = round(1 - opposite_color_brightness / 255, 2) if 0 <= opposite_color_brightness <= 255 else 0
        
        # Calculate Font Color (High Priority)
        font_color = self.get_optimal_font_color(img)

        # Calculate "Most Common Alternative" (For Progress Bar)
        small_temp_img = full_img.resize((16, 16), Image.Resampling.NEAREST)
        colors_raw_small = small_temp_img.getcolors(maxcolors=256)
        most_common_colors = []
        if colors_raw_small:
            # Filter: Only accept colors with some saturation
            vibrant_candidates = []
            for c in colors_raw_small:
                count, rgb = c
                r, g, b = rgb[:3]
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                if s > 0.15 and v > 0.15: # Ignore Black/Gray/White
                    vibrant_candidates.append(c)
            
            if vibrant_candidates:
                most_common_colors = sorted([(c[1], c[0]) for c in vibrant_candidates], key=lambda x: x[1], reverse=True)
            else:
                most_common_colors = sorted([(c[1], c[0]) for c in colors_raw_small], key=lambda x: x[1], reverse=True)

        most_common_color_alternative_rgb = self.most_vibrant_color(most_common_colors)
        
        # Final Safety: If still grayscale/black, generate random pastel
        if sum(most_common_color_alternative_rgb) < 50 or \
           (max(most_common_color_alternative_rgb) - min(most_common_color_alternative_rgb) < 20):
             most_common_color_alternative_rgb = (
                 random.randint(100, 255), 
                 random.randint(100, 255), 
                 random.randint(100, 255)
             )

        most_common_color_alternative = f'#{most_common_color_alternative_rgb[0]:02x}{most_common_color_alternative_rgb[1]:02x}{most_common_color_alternative_rgb[2]:02x}'
        
        background_color_rgb = most_common_color_alternative_rgb
        background_color = most_common_color_alternative
        brightness = int(sum(most_common_color_alternative_rgb) / 3)

        if self.config.wled:
            color1_hex, color2_hex, color3_hex = self.most_vibrant_colors_wled(small_temp_img)
        else:
            color1_hex = most_common_color_alternative
            color2_hex = most_common_color_alternative
            color3_hex = most_common_color_alternative

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

    def most_vibrant_color(self, most_common_colors: list) -> tuple:
        """Optimized using colorsys to check saturation/value."""
        for color, count in most_common_colors:
            r, g, b = color
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if s < 0.2 or v < 0.2: continue
            if v > 0.9 and s < 0.3: continue
            return color
        return tuple(random.randint(100, 200) for _ in range(3))

    def rgb_to_hex(self, rgb: tuple) -> str:
        return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
    
    def _hex_to_rgb(self, hex_str: str) -> tuple:
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3: hex_str = ''.join([c*2 for c in hex_str])
        try:
            return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        except ValueError:
            return (0, 255, 255)

    def is_strong_color(self, color: tuple) -> bool:
        return any(c > 220 for c in color)

    def color_distance(self, color1: tuple, color2: tuple) -> float:
        return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color1, color2)))

    def is_vibrant_color(self, r: int, g: int, b: int) -> bool:
        """Optimized using colorsys."""
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        return s > 0.2 and v > 0.2

    def generate_close_but_different_color(self, existing_colors: list) -> tuple:
        if not existing_colors:
            return (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
        avg_r = sum(c[0] for c, _ in existing_colors) // len(existing_colors)
        avg_g = sum(c[1] for c, _ in existing_colors) // len(existing_colors)
        avg_b = sum(c[2] for c, _ in existing_colors) // len(existing_colors)
        max_attempts = 50
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
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
        return (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))

    def color_score(self, color_count: tuple) -> float:
        """Optimized using colorsys."""
        color, count = color_count
        r, g, b = color
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        return count * s

    def most_vibrant_colors_wled(self, full_img: Image.Image) -> tuple:
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
        """
        UPDATED: Logic now aggressively prefers vibrant colors over Black/White
        when config.text_bg is False.
        """
        if self.config.force_font_color:
            return self.config.force_font_color
        
        small_thumb = img.resize((25, 25), Image.Resampling.NEAREST)
        colors_raw = small_thumb.getcolors(maxcolors=625) or []
        
        # Helper to calculate vibrancy
        def vibrancy_score(item):
            count, rgb = item
            r, g, b = rgb[:3]
            h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
            # Give high score to high saturation & medium-high brightness
            return (s * v * v) * (math.log(count) + 1)

        sorted_vibrant = sorted(colors_raw, key=vibrancy_score, reverse=True)
        
        # Extract the "best" vibrant color found in the image
        chosen_dominant_color = None
        for _, color in sorted_vibrant:
            rgb = color[:3]
            h, s, v = colorsys.rgb_to_hsv(rgb[0]/255, rgb[1]/255, rgb[2]/255)
            if s > 0.15 and 0.15 < v < 0.95:
                chosen_dominant_color = rgb
                break
        
        if not chosen_dominant_color and colors_raw:
            # Fallback to most common if no vibrant color found
            for count, color in sorted(colors_raw, key=lambda x: x[0], reverse=True):
                if sum(color[:3]) > 50:
                    chosen_dominant_color = color[:3]
                    break

        # --- CASE 1: Text Background IS Enabled ---
        if self.config.text_bg:
            if chosen_dominant_color:
                r, g, b = chosen_dominant_color
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                new_s = max(0.4, min(s, 1.0)) 
                new_v = 1.0
                nr, ng, nb = colorsys.hsv_to_rgb(h, new_s, new_v)
                return f'#{int(nr*255):02x}{int(ng*255):02x}{int(nb*255):02x}'
            return "#00ffff"

        # --- CASE 2: NO Text Background (Need Contrast + COLOR) ---
        else:
            stat = ImageStat.Stat(img)
            avg_bg = tuple(int(x) for x in stat.mean[:3])
            
            candidates = []
            
            # 1. Add extracted image colors
            if chosen_dominant_color:
                candidates.append(chosen_dominant_color)
                r, g, b = chosen_dominant_color
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                
                # Add a "boosted" version (100% value)
                nr, ng, nb = colorsys.hsv_to_rgb(h, s, 1.0)
                candidates.append((int(nr*255), int(ng*255), int(nb*255)))
                
                # Add a complimentary/shifted version
                h_comp = (h + 0.5) % 1.0
                nr, ng, nb = colorsys.hsv_to_rgb(h_comp, s, 1.0)
                candidates.append((int(nr*255), int(ng*255), int(nb*255)))

            # 2. Add Standard Palette
            candidates.extend(COLOR_PALETTE)
            
            # 3. Add Black/White (Last resort)
            candidates.append((255, 255, 255))
            candidates.append((0, 0, 0))

            best_color = None
            max_score = -100

            for color in candidates:
                contrast = self._contrast_ratio(color, avg_bg)
                
                # Check properties
                r, g, b = color
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                is_grayscale = s < 0.1
                
                # Define Minimum Contrast Threshold
                # We allow lower contrast (2.2) if the color is COLORFUL.
                # We demand higher contrast (4.0) if the color is Black/White.
                threshold = 4.0 if is_grayscale else 2.2
                
                if contrast < threshold: 
                    continue

                # --- SCORING ---
                # Base score is contrast
                score = contrast
                
                # Massive bonus for Saturation (Colorfulness)
                # This ensures Cyan/Magenta/Yellow win over White even if White has slightly better contrast.
                score += (s * 25.0) 
                
                # Bonus if it matches the dominant color of the album
                if chosen_dominant_color and self.color_distance(color, chosen_dominant_color) < 30:
                    score += 5.0
                
                if score > max_score:
                    max_score = score
                    best_color = color
            
            if best_color:
                return f'#{best_color[0]:02x}{best_color[1]:02x}{best_color[2]:02x}'
            
            # Absolute fallback if nothing passed the loop
            white_contrast = self._contrast_ratio((255, 255, 255), avg_bg)
            return '#ffffff' if white_contrast > 3.0 else '#000000'

    def get_dominant_border_color(self, img: Image.Image) -> tuple:
        if img.width == 0 or img.height == 0:
            return (0, 0, 0)
            
        img_rgb = img if img.mode == "RGB" else img.convert("RGB")
        thumb = img_rgb.resize((64, 64), Image.Resampling.NEAREST)
        
        h_border = list(thumb.crop((0, 0, 64, 1)).getdata()) + \
                   list(thumb.crop((0, 63, 64, 64)).getdata())
        v_border = list(thumb.crop((0, 0, 1, 64)).getdata()) + \
                   list(thumb.crop((63, 0, 64, 64)).getdata())
                   
        pixels = h_border + v_border
        if not pixels: return (0,0,0)
        
        most_common = Counter(pixels).most_common(1)
        return most_common[0][0]

    def _find_content_bounding_box(self, image_to_scan: Image.Image, border_color_to_detect: tuple, threshold: float) -> Optional[Tuple[int, int, int, int]]:
        try:
            bg = Image.new("RGB", image_to_scan.size, border_color_to_detect)
            diff = ImageChops.difference(image_to_scan, bg)
            diff = ImageOps.grayscale(diff)
            diff = diff.point(lambda p: 255 if p > 30 else 0)
            return diff.getbbox()
        except Exception:
            return None

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
        
        data = list(cropped_detect_window.getdata())
        thresh_sq = thresh * thresh
        
        top_border_rows = 0
        for y in range(local_size_h):
            is_border_row = True
            row_start = y * local_size_w
            for x in range(local_size_w):
                r, g, b = data[row_start + x]
                dist_sq = (r - border_color[0])**2 + (g - border_color[1])**2 + (b - border_color[2])**2
                if dist_sq > thresh_sq:
                    is_border_row = False
                    break
            if is_border_row:
                top_border_rows += 1
            else:
                break
                
        bottom_border_rows = 0
        for y in range(local_size_h - 1, -1, -1):
            is_border_row = True
            row_start = y * local_size_w
            for x in range(local_size_w):
                r, g, b = data[row_start + x]
                dist_sq = (r - border_color[0])**2 + (g - border_color[1])**2 + (b - border_color[2])**2
                if dist_sq > thresh_sq:
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
        threshold_find_bbox_obj = 40
        border_color_for_detect = self.get_dominant_border_color(detect_img_processed) 
        bbox = self._find_content_bounding_box(detect_img_processed, border_color_for_detect, threshold_find_bbox_obj) 
        if bbox is None:
            return None 
        min_x, min_y, max_x, max_y = bbox
        img_w, img_h = detect_img_processed.size
        max_possible_crop = min(img_w, img_h)
        content_w = max_x - min_x + 1
        content_h = max_y - min_y + 1
        current_crop_size = min(content_w, content_h)
        if current_crop_size < 64: current_crop_size = 64
        object_center_x = min_x + content_w // 2
        detect_pixels = detect_img_processed.load()
        thresh_sq = threshold_find_bbox_obj * threshold_find_bbox_obj
        zoom_step = 10 
        while current_crop_size < max_possible_crop:
            t = max(0, min_y) 
            l = max(0, object_center_x - (current_crop_size // 2))
            if t + current_crop_size > img_h: t = img_h - current_crop_size
            if l + current_crop_size > img_w: l = img_w - current_crop_size
            t = max(0, t)
            l = max(0, l)
            r = l + current_crop_size - 1
            b = t + current_crop_size - 1
            corners = [(l, t), (r, t), (l, b), (r, b)]
            is_touching_object = False
            for cx, cy in corners:
                try:
                    px = detect_pixels[cx, cy]
                    dist_sq = sum((c1 - c2) ** 2 for c1, c2 in zip(px, border_color_for_detect))
                    if dist_sq > thresh_sq:
                        is_touching_object = True
                        break
                except Exception: pass
            if is_touching_object:
                current_crop_size += zoom_step
            else:
                break
        current_crop_size += 2
        final_crop_size = min(current_crop_size, max_possible_crop)
        top = max(0, min_y)
        left = max(0, object_center_x - (final_crop_size // 2))
        if top + final_crop_size > img_h: top = img_h - final_crop_size
        if left + final_crop_size > img_w: left = img_w - final_crop_size
        top = max(0, top)
        left = max(0, left)
        return self._balance_border(detect_img_processed, img_to_crop, left, top, final_crop_size, border_color_for_detect, 60)

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

    def _draw_text_with_shadow(self, draw: ImageDraw.ImageDraw, xy: tuple, text: str, font: ImageFont.FreeTypeFont, text_color: tuple, shadow_color: tuple):
        x, y = xy
        draw.text((x + 1, y + 1), text, font=font, fill=shadow_color)
        draw.text((x, y + 1), text, font=font, fill=shadow_color)
        if shadow_color == (255, 255, 255, 128):
            draw.text((x + 1, y - 1), text, font=font, fill=shadow_color)
            draw.text((x - 1, y), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=text_color)

    def _measure_text_bbox(self, text: str, font: ImageFont.FreeTypeFont, draw: Optional[ImageDraw.ImageDraw]) -> tuple[int, int]:
        if draw:
            bbox = draw.textbbox((0, 0), text, font=font)
        else:
            bbox = font.getbbox(text)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def _get_text_dimensions(self, text: str, font: ImageFont.FreeTypeFont, draw: Optional[ImageDraw.ImageDraw] = None) -> tuple[int, int]:
        try:
            return self._measure_text_bbox(text, font, draw)
        except Exception:
            return 0, 0

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

    def _contrast_ratio(self, c1: tuple, c2: tuple) -> float:
        def _luminance(c: tuple) -> float:
            r, g, b = [v / 255 for v in c]
            r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
            g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
            b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
            return 0.2126 * r + 0.7152 * g + 0.0722 * b
        l1, l2 = _luminance(c1) + 0.05, _luminance(c2) + 0.05
        return max(l1, l2) / min(l1, l2)

    def _pick_two_contrasting_colors(self, img: Image.Image, min_ratio: float = 4.5) -> tuple:
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

        # 1. Pick Colors
        artist_rgb, title_rgb = self._pick_two_contrasting_colors(img, 4.5)
        artist_fill = (*artist_rgb, 255)
        title_fill  = (*title_rgb, 255)

        # 2. Calculate Negative Shadows (Inverse of text color) with Alpha
        inv_artist = tuple(255 - c for c in artist_rgb)
        inv_title  = tuple(255 - c for c in title_rgb)
        
        artist_shadow_fill = (*inv_artist, 180)
        title_shadow_fill  = (*inv_title, 180)

        # 3. Layout Setup
        img_copy = img.copy().convert("RGBA")
        layer = ImageDraw.Draw(img_copy)
        font = self._default_font
        pad = 2
        max_w = img.width - (2 * pad)
        spacer = 4

        # Wrap Text
        artist_lines = self._wrap_text(artist, font, max_w, layer) if artist else []
        title_lines  = self._wrap_text(title,  font, max_w, layer) if title else []
        
        if not artist_lines and not title_lines: 
            return img.convert("RGB")

        # Measure Height
        line_h = 11
        total_h = (len(artist_lines) * line_h) + (len(title_lines) * line_h)
        if artist_lines and title_lines: 
            total_h += spacer

        # Center Y
        y = max(pad, (img.height - total_h) // 2)

        # 4. Render using _draw_text_with_shadow
        for line in artist_lines:
            w = layer.textlength(line, font=font)
            x = (img.width - w) // 2
            self._draw_text_with_shadow(layer, (x, y), line, font, artist_fill, artist_shadow_fill)
            y += line_h
        
        if artist_lines and title_lines:
            y += spacer
            
        for line in title_lines:
            w = layer.textlength(line, font=font)
            x = (img.width - w) // 2
            self._draw_text_with_shadow(layer, (x, y), line, font, title_fill, title_shadow_fill)
            y += line_h

        return img_copy.convert("RGB")


class LyricsProvider:
    """Provides lyrics with Smart Scheduling logic (Event Based)."""

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
        words = text.split() 
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
                line = line.strip() 
                if not line: continue 
                
                is_new_block = (line_idx == 0 and block_idx > 0)
                final_render_lines.append((line, is_new_block))

        # Determine font height based on density
        if len(final_render_lines) >= 6:
            font_height = 10
            block_gap = 0
            current_y = 1 
        else:
            font_height = 12
            block_gap = 2
            # Center the block vertically based on line count
            total_needed = (len(final_render_lines) * font_height) + (sum(1 for _, is_new in final_render_lines if is_new) * block_gap)
            current_y = (64 - total_needed) // 2
        
        items = []
        for i, (line_text, is_new_block) in enumerate(final_render_lines):
            if is_bidi_text:
                line_text = line_text.replace("(", "###TEMP###").replace(")", "(").replace("###TEMP###", ")")
            
            if is_new_block: current_y += block_gap
            
            # We pass the calculated height (h) to the display function
            items.append({
                "y": current_y,
                "h": font_height,
                "dir": 1 if has_bidi(line_text) else 0,
                "text": line_text,
            })
            current_y += font_height
            
        return items

    def get_refresh_plan(self, current_pos: float) -> tuple[Optional[list], float]:
        """
        Calculates the current lyric state and the time until the next event.
        Returns: (layout_items or None, delay_in_seconds)
        """
        if not self.visual_timeline:
            return None, None

        active_index = -1
        
        # 1. Find if we are INSIDE a lyric line
        if self.current_frame_index != -1 and self.current_frame_index < len(self.visual_timeline):
            frame = self.visual_timeline[self.current_frame_index]
            if frame['start'] <= current_pos < frame['end']:
                active_index = self.current_frame_index
        
        # If not found, search all
        if active_index == -1:
            for i, frame in enumerate(self.visual_timeline):
                if frame['start'] <= current_pos < frame['end']:
                    active_index = i
                    break
                if frame['start'] > current_pos:
                    break
        
        # 2. Case A: We are displaying a lyric
        if active_index != -1:
            self.current_frame_index = active_index
            frame = self.visual_timeline[active_index]
            
            # Calculate when this line ENDS
            next_event_time = frame['end']
            
            if active_index + 1 < len(self.visual_timeline):
                next_start = self.visual_timeline[active_index + 1]['start']
                if next_start - next_event_time < 0.2:
                    next_event_time = next_start

            delay = max(0.1, next_event_time - current_pos)
            return frame['layout'], delay

        # 3. Case B: We are in a Gap (Silence)
        self.current_frame_index = -1
        
        # Find when the NEXT line starts
        next_event_time = -1
        for frame in self.visual_timeline:
            if frame['start'] > current_pos:
                next_event_time = frame['start']
                break
        
        if next_event_time != -1:
            delay = max(0.1, next_event_time - current_pos)
            return [], delay # Return empty list = Clear screen

        # 4. Case C: Song is over (no more lines)
        return [], None

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
        
        self._clean_title_patterns = [
            re.compile(r'[\(\[][^)\]]*remaster(?:ed)?[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*remix(?:ed)?[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*version[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*session[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*feat.[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*single[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*edit[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*extended[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*live[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*bonus[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*deluxe[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*mix[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'[\(\[][^)\]]*\d{4}[^)\]]*[\)\]]', re.IGNORECASE),
            re.compile(r'^\d+\s*[\.-]\s*', re.IGNORECASE),
            re.compile(r'\.(mp3|m4a|wav|flac)$', re.IGNORECASE)
        ]
        
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
        self.background_color = "#000000"
        self.progress_bar_color = "#FFFFFF"
        self.show_progress_bar = False
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
            
            if not media_state_obj: return None
            state = media_state_obj.get('state')
            if state not in ["playing", "on"]: return None

            attributes = media_state_obj.get('attributes', {})
            raw_title = attributes.get('media_title')
            raw_artist = attributes.get('media_artist')
            app_name = attributes.get('app_name')

            if raw_title is None or str(raw_title).strip() == "":
                if app_name and str(app_name).strip() != "": raw_title = app_name
                else: return None

            # 3. Fallback for Artist
            if (raw_artist is None or str(raw_artist).strip() == "") and app_name:
                raw_artist = app_name

            # 4. ANTI-SPOOFING CHECKS
            t_check = str(raw_title).strip().lower()
            a_check = str(app_name).strip().lower() if app_name else ""
            art_check = str(raw_artist).strip().lower() if raw_artist else ""

            if a_check and t_check == a_check: return None
            if art_check and t_check == art_check: return None

            self.title_original = raw_title
            self.artist = raw_artist if raw_artist else ""
            
            try:
                self.media_position = float(attributes.get('media_position', 0))
                self.media_duration = float(attributes.get('media_duration', 0))
            except (ValueError, TypeError):
                self.media_position = 0
                self.media_duration = 0

            # --- LOGIC: SHOW PROGRESS BAR? ---
            if self.config.progress_bar_enabled:
                pb_state = await hass.get_state(self.config.progress_bar_entity)
                is_toggled_on = (str(pb_state).lower() == 'on') or (pb_state is True)
                
                if is_toggled_on and self.media_duration > 0:
                    self.show_progress_bar = True
                else:
                    self.show_progress_bar = False
            else:
                self.show_progress_bar = False
            
            original_picture = attributes.get('entity_picture')
            if original_picture:
                if re.match(r'^[a-zA-Z]:\\', original_picture) or original_picture.startswith("file://"):
                    _LOGGER.info(f"Local image path detected ({original_picture}). Using fallback sources.")
                    original_picture = None
            self.picture = original_picture

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
                self.artist = "TV"; self.title = "TV"; self.playing_tv = True
                self.picture = "TV_IS_ON_ICON" if self.config.tv_icon_pic else "TV_IS_ON"
                self.lyrics = []
                return self 

            self.playing_tv = False
            self.title = self.title_clean
            self.album = album

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
                    if temp_state and str(temp_state['state']).replace('.', '', 1).isdigit():
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
        return await self.lyrics_provider.get_lyrics(artist, title, album, duration)

    def format_ai_image_prompt(self, artist: Optional[str], title: str) -> str: 
        if not self.config.pollinations: return 
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
        selected_prompt = random.choice(prompts); encoded_prompt = urllib.parse.quote(selected_prompt)
        model = self.config.ai_fallback if self.config.ai_fallback else "flux"; seed = random.randint(0, 100000)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?model={model}&width=1024&height=1024&nologo=true&seed={seed}&key={self.config.pollinations}"
        return url

    def clean_title(self, title: str) -> str: 
        if not title: return title
        cleaned_title = title
        for pattern in self._clean_title_patterns:
            cleaned_title = pattern.sub('', cleaned_title)
        
        cleaned_title = ' '.join(cleaned_title.split())
        return cleaned_title

class FallbackService:
    """Handles fallback logic to retrieve album art from various sources if the original picture is not available.""" 

    def __init__(self, config: "Config", image_processor: "ImageProcessor", session: aiohttp.ClientSession, spotify_service: "SpotifyService", pixoo_device: "PixooDevice"): 
        self.config = config
        self.image_processor = image_processor
        self.session = session
        self.spotify_service = spotify_service
        self.pixoo_device = pixoo_device # <--- STORE THE DEVICE
        
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
        
        if picture:
            media_data.pic_url = picture if picture.startswith('http') else f"{self.config.ha_url}{picture}"
        else:
            media_data.pic_url = None
        
        # 2. Force AI Mode
        if self.config.force_ai and not media_data.radio_logo and not media_data.playing_tv:
            _LOGGER.info("Force AI mode enabled, trying to generate AI album art.") 
            if self.config.info:
                await self.send_info(media_data.artist, "FORCE   AI", media_data.lyrics_font_color)
            return await self._try_ai_generation(media_data)

        # 3. TV Icon Mode
        if picture == "TV_IS_ON_ICON":
            _LOGGER.info("Using TV icon image as album art.") 
            media_data.pic_url = "TV Icon"
            media_data.pic_source = "Internal"
            if self.config.tv_icon_pic:
                tv_icon_base64 = self.image_processor.gbase64(self.create_tv_icon_image())
                return { 
                    'base64_image': tv_icon_base64,
                    'font_color': '#ff00ff', 'brightness': 0.67, 'brightness_lower_part': '#ffff00',
                    'background_color': (255, 255, 0), 'background_color_rgb': (0, 0, 255),
                    'most_common_color_alternative_rgb': (0,0,0), 'most_common_color_alternative': '#ffff00',
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
        
        if self.config.info: await self.send_info(media_data.artist, "SEARCHING...", media_data.lyrics_font_color)

        tasks = []
        providers = []

        if self.config.discogs:
            tasks.append(self.search_discogs_album_art(media_data.artist, media_data.title))
            providers.append("Discogs")
        if self.config.lastfm:
            tasks.append(self.search_lastfm_album_art(media_data.artist, media_data.title))
            providers.append("Last.FM")
        if self.config.tidal_client_id and self.config.tidal_client_secret:
            tasks.append(self.get_tidal_album_art_url(media_data.artist, media_data.title))
            providers.append("TIDAL")
        if self.config.musicbrainz:
            tasks.append(self.get_musicbrainz_album_art_url(media_data.artist, media_data.title))
            providers.append("MusicBrainz")

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception) or not result: continue
                
                provider_name = providers[i]
                if self.config.info: await self.send_info(media_data.artist, provider_name.upper(), media_data.lyrics_font_color)
                
                proc_result = await self.image_processor.get_image(result, media_data, media_data.spotify_slide_pass)
                if proc_result:
                    media_data.pic_url = result
                    media_data.pic_source = provider_name
                    return proc_result

        # 7. Fallback Level 2: Spotify Artist Picture
        if self.spotify_artist_pic:
            if result := await self.image_processor.get_image(self.spotify_artist_pic, media_data, media_data.spotify_slide_pass):
                media_data.pic_source = "Spotify Artist"
                return result

        # 8. AI Generation (Last Resort)
        _LOGGER.info("Falling back to AI image generation as last resort.") 
        if self.config.info:
            await self.send_info(media_data.artist, "AI   IMAGE", media_data.lyrics_font_color)
        
        result = await self._try_ai_generation(media_data)
        if result: 
            media_data.pic_source = "AI"
            return result

        # 9. Fallback Level 3: Spotify First Album
        if self.spotify_first_album:
            if result := await self.image_processor.get_image(self.spotify_first_album, media_data, media_data.spotify_slide_pass):
                media_data.pic_url = self.spotify_first_album
                media_data.pic_source = "Spotify (Artist Profile Image)"
                return result

        # 10. Ultimate Fallback: Black Screen
        media_data.pic_url = "Black Screen"
        media_data.pic_source = "Internal"
        return self._get_fallback_black_image_data() 

    async def _try_ai_generation(self, media_data):
        ai_url = media_data.format_ai_image_prompt(media_data.artist, media_data.title)
        if not ai_url: return None
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
            'font_color': '#ff00ff', 'brightness': 0.67, 'brightness_lower_part': '#ffff00',
            'background_color': (255, 255, 0), 'background_color_rgb': (0, 0, 255),
            'most_common_color_alternative_rgb': (0,0,0), 'most_common_color_alternative': '#ffff00',
            'color1': '#000000', 'color2': '#000000', 'color3': '#000000'
        }

    async def send_info_img(self, base64_image: str) -> None: 
        if not self.pixoo_device: return
        payload = {
            "Command": "Draw/CommandList",
            "CommandList": [
                {"Command": "Draw/ResetHttpGifId"},
                {"Command": "Draw/SendHttpGif",
                    "PicNum": 1, "PicWidth": 64, "PicOffset": 0,
                    "PicID": 0, "PicSpeed": 10000, "PicData": base64_image }]}
        await self.pixoo_device.send_command(payload)

    async def send_info(self, artist: Optional[str], text: str, lyrics_font_color: str) -> None: 
        if not self.pixoo_device: return
        items = [{"TextId": 1, "type": 22, "x": 0, "y": 0, "dir": 0, "font": 190, "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 1, "TextString": "", "color": "#000000"}]
        
        if artist:
            items.append({
                "TextId": 10, "type": 22, "x": 0, "y": 20, "dir": 0, "font": 190, 
                "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 2, 
                "TextString": artist[:15], "color": lyrics_font_color
            })
            
        items.append({
            "TextId": 11, "type": 22, "x": 0, "y": 36, "dir": 0, "font": 190, 
            "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 2, 
            "TextString": text, "color": "#00FF00"
        })
        await self.pixoo_device.send_command({"Command": "Draw/SendHttpItemList", "ItemList": items})
    
    async def get_musicbrainz_album_art_url(self, ai_artist: str, ai_title: str) -> Optional[str]: 
        search_url = "https://musicbrainz.org/ws/2/release/"
        headers = { "Accept": "application/json", "User-Agent": "PixooClient/1.0" }
        params = { "query": f'artist:"{ai_artist}" AND recording:"{ai_title}"', "fmt": "json" }
        try:
            async with self.session.get(search_url, params=params, headers=headers, timeout=10) as response: 
                response.raise_for_status() 
                data = await response.json()
                if not data.get("releases"): return None
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
                except Exception: return None
        except Exception: return None

    async def search_discogs_album_art(self, ai_artist: str, ai_title: str) -> Optional[str]: 
        base_url = "https://api.discogs.com/database/search"
        headers = { "User-Agent": "AlbumArtSearchApp/1.0", "Authorization": f"Discogs token={self.config.discogs}" }
        params = { "artist": ai_artist, "track": ai_title, "type": "release", "format": "album", "per_page": 5 }
        try:
            async with self.session.get(base_url, headers=headers, params=params, timeout=10) as response: 
                response.raise_for_status() 
                data = await response.json()
                results = data.get("results", [])
                if not results: return None
                return results[0].get("cover_image")
        except Exception: return None

    async def search_lastfm_album_art(self, ai_artist: str, ai_title: str) -> Optional[str]: 
        base_url = "http://ws.audioscrobbler.com/2.0/"
        params = { "method": "track.getInfo", "api_key": self.config.lastfm, "artist": ai_artist, "track": ai_title, "format": "json" }
        try:
            async with self.session.get(base_url, params=params, timeout=10) as response: 
                response.raise_for_status() 
                data = await response.json()
                album_art_url_list = data.get("track", {}).get("album", {}).get("image", []) 
                if album_art_url_list:
                    return album_art_url_list[-1]["#text"] 
                return None
        except Exception: return None

    async def get_tidal_album_art_url(self, artist: str, title: str) -> Optional[str]: 
        base_url = "https://openapi.tidal.com/v2/"
        access_token = await self.get_tidal_access_token()
        if not access_token: return None
        headers = { "Authorization": f"Bearer {access_token}", "Content-Type": "application/json" }
        search_params = { "countryCode": "US", "include": ["artists", "albums", "tracks"] }
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
        except Exception: return None

    async def get_tidal_access_token(self) -> Optional[str]: 
        if self.tidal_token_cache['token'] and time.time() < self.tidal_token_cache['expires']:
            return self.tidal_token_cache['token']
        url = "https://auth.tidal.com/v1/oauth2/token"
        tidal_headers = { "Content-Type": "application/x-www-form-urlencoded" }
        payload = { "grant_type": "client_credentials", "client_id": self.config.tidal_client_id, "client_secret": self.config.tidal_client_secret }
        try:
            async with self.session.post(url, headers=tidal_headers, data=payload, timeout=10) as response: 
                response.raise_for_status() 
                response_json = await response.json()
                access_token = response_json["access_token"]
                expiry_time = time.time() + response_json.get("expires_in", 3600) - 60 
                self.tidal_token_cache = { 'token': access_token, 'expires': expiry_time }
                return access_token
        except Exception: return None

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

    def __init__(self, config: "Config", session: aiohttp.ClientSession, image_processor: "ImageProcessor"): 
        """Initialize SpotifyService object."""
        self.config = config
        self.session = session
        self.image_processor = image_processor
        self.spotify_token_cache: dict[str, Any] = { 
            'token': None,
            'expires': 0
        }
        self.spotify_data: Optional[dict] = None 
        
        self._semaphore = asyncio.Semaphore(5)

    async def get_spotify_access_token(self) -> Optional[str]: 
        """Get Spotify API access token using client credentials."""
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
        """Determine the 'best' album ID and first album ID."""
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
        """Get the Spotify album ID and first album ID."""
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

            sorted_albums = sorted_albums[:10]

            album_urls = []
            
            for album in sorted_albums:
                images = album.get("images", [])
                if images:
                    album_urls.append(images[0]["url"])

            media_data.pic_url = album_urls
            media_data.pic_source = "Spotify (Slide)"
            
            if returntype == "url":
                return album_urls

            if returntype == "b64":
                show_lyrics_is_on = True if media_data.lyrics else False
                playing_radio_is_on = True if media_data.playing_radio else False
                
                async def fetch_with_semaphore(url):
                    async with self._semaphore:
                        return await self.get_slide_img(url, show_lyrics_is_on, playing_radio_is_on)

                tasks = [fetch_with_semaphore(url) for url in album_urls]
                results = await asyncio.gather(*tasks)
                
                return [res for res in results if res is not None]

            return []

        except Exception as e: 
            _LOGGER.error(f"Error processing Spotify data to get album list: {e}") 
            return []

    async def get_slide_img(self, picture: str, show_lyrics_is_on: bool, playing_radio_is_on: bool) -> Optional[str]: 
        """Fetches and processes image for Spotify slide using the optimized ImageProcessor."""
        try:
            async with self.session.get(picture, timeout=10) as response: 
                response.raise_for_status() 
                image_raw_data = await response.read()

            return await self.image_processor.process_slide_image(
                image_raw_data, 
                show_lyrics_is_on, 
                playing_radio_is_on
            )

        except Exception as e: 
            _LOGGER.error(f"Error processing slide image: {e}")
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

    async def spotify_albums_slide(self, pixoo_device: "PixooDevice", media_data: "MediaData", prev_channel: int) -> None: 
        """Regular Slide Mode: Uses Parallel Processing and switches to Previous Channel to break animation lock."""
        media_data.spotify_slide_pass = True
        
        try:
            # --- STEP 1: PREVIEW (Immediate Artist Image) ---
            artist_pic_url = await self.get_spotify_artist_image_url_by_name(media_data.artist)
            if artist_pic_url:
                preview_b64 = await self.get_slide_img(artist_pic_url, bool(media_data.lyrics), media_data.playing_radio)
                if preview_b64:
                    # WORKAROUND: Move to previous channel (e.g. Clock) to kill the old animation loop
                    # Then reset and send the 1-frame preview
                    await pixoo_device.send_command({"Command": "Draw/CommandList", "CommandList": [
                        {"Command": "Channel/SetIndex", "SelectIndex": prev_channel}, 
                        {"Command": "Draw/ResetHttpGifId"},
                        {"Command": "Draw/SendHttpGif", "PicNum": 1, "PicWidth": 64, "PicOffset": 0, "PicID": 0, "PicSpeed": 1000, "PicData": preview_b64}
                    ]})

            # --- STEP 2: PARALLEL PROCESSING ---
            album_urls = await self.get_album_list(media_data, returntype="url")
            if not album_urls: return

            async def process_pipeline(url):
                async with self._semaphore:
                    try:
                        async with self.session.get(url, timeout=10) as response:
                            raw_data = await response.read()
                            return await self.image_processor.process_slide_image(raw_data, bool(media_data.lyrics), media_data.playing_radio)
                    except: return None

            tasks = [process_pipeline(url) for url in album_urls[:10]]
            album_urls_b64 = await asyncio.gather(*tasks)
            album_urls_b64 = [res for res in album_urls_b64 if res]

            frames = len(album_urls_b64)
            if frames < 2: return

            # --- STEP 3: SEND FINAL ANIMATION ---
            # Reset again to previous channel before starting the multi-frame sequence
            await pixoo_device.send_command({"Command": "Draw/CommandList", "Command": "Draw/ResetHttpGifId"})

            for pic_offset, b64_frame in enumerate(album_urls_b64):
                await self.send_pixoo_animation_frame(pixoo_device, "Draw/SendHttpGif", frames, 64, pic_offset, 0, 5000, b64_frame)

        except Exception as e:
            _LOGGER.error(f"Error in regular spotify slider: {e}")

    async def spotify_album_art_animation(self, pixoo_device: "PixooDevice", media_data: "MediaData", prev_channel: int) -> None: 
        """Special Gallery Mode: Parallel prep and switches to Previous Channel to break animation lock."""
        if media_data.playing_tv: return 

        try:
            # --- STEP 1: PREVIEW (Artist Image) ---
            artist_img = None
            artist_pic_url = await self.get_spotify_artist_image_url_by_name(media_data.artist)
            if artist_pic_url:
                async with self.session.get(artist_pic_url, timeout=5) as response:
                    raw_data = await response.read()
                    loop = asyncio.get_event_loop()
                    artist_img = await loop.run_in_executor(self.image_processor._executor, _resize_image_sync, raw_data)
                    
                    if artist_img:
                        preview_canvas = Image.new("RGB", (64, 64), (0, 0, 0))
                        preview_canvas.paste(artist_img, (16, 8)) 
                        preview_b64 = self.image_processor.gbase64(preview_canvas)
                        
                        # WORKAROUND: Break loop by switching to prev_channel
                        await pixoo_device.send_command({"Command": "Draw/CommandList", "CommandList": [
                        #    {"Command": "Channel/SetIndex", "SelectIndex": prev_channel},
                            {"Command": "Draw/ResetHttpGifId"},
                            {"Command": "Draw/SendHttpGif", "PicNum": 1, "PicWidth": 64, "PicOffset": 0, "PicID": 0, "PicSpeed": 1000, "PicData": preview_b64}
                        ]})
                        

            # --- STEP 2: PARALLEL PREPARATION ---
            album_urls = await self.get_album_list(media_data, returntype="url")
            if not album_urls: return

            def prepare_album_variants(raw_data):
                try:
                    img = Image.open(BytesIO(raw_data))
                    img.load()
                    img = img.convert("RGB").resize((34, 34), Image.Resampling.BICUBIC)
                    active = img.copy()
                    draw = ImageDraw.Draw(active); draw.rectangle([0, 0, 33, 33], outline="black", width=1)
                    inactive = img.filter(ImageFilter.GaussianBlur(2))
                    inactive = ImageEnhance.Brightness(inactive).enhance(0.5)
                    return {"active": active, "inactive": inactive}
                except: return None

            async def download(url):
                try:
                    async with self.session.get(url, timeout=10) as resp: return await resp.read()
                except: return None

            raw_datas = await asyncio.gather(*[download(u) for u in album_urls[:10]])
            raw_datas = [d for d in raw_datas if d]

            loop = asyncio.get_event_loop()
            tasks = [loop.run_in_executor(self.image_processor._executor, prepare_album_variants, d) for d in raw_datas]
            prepared_albums = await asyncio.gather(*tasks)
            prepared_albums = [a for a in prepared_albums if a]

            if artist_img:
                a_img = artist_img.copy()
                draw = ImageDraw.Draw(a_img); draw.rectangle([0,0,33,33], outline="black", width=1)
                i_img = artist_img.filter(ImageFilter.GaussianBlur(2))
                i_img = ImageEnhance.Brightness(i_img).enhance(0.5)
                prepared_albums.insert(0, {"active": a_img, "inactive": i_img})

            if len(prepared_albums) < 3: return

            # --- STEP 3: ASSEMBLY & SEND ---
            total_frames = min(len(prepared_albums), 10)
            pixoo_frames = []
            x_pos = [1, 16, 51]

            for i in range(total_frames):
                canvas = Image.new("RGB", (64, 64), (0, 0, 0))
                l, c, r = (i-1)%len(prepared_albums), i%len(prepared_albums), (i+1)%len(prepared_albums)
                canvas.paste(prepared_albums[l]["inactive"], (x_pos[0], 8))
                canvas.paste(prepared_albums[c]["active"], (x_pos[1], 8))
                canvas.paste(prepared_albums[r]["inactive"], (x_pos[2], 8))
                pixoo_frames.append(self.image_processor.gbase64(canvas))

            for offset, frame in enumerate(pixoo_frames):
                await self.send_pixoo_animation_frame(pixoo_device, "Draw/SendHttpGif", total_frames, 64, offset, 0, 5000, frame)
            
            media_data.spotify_slide_pass = True 

        except Exception as e:
            _LOGGER.error(f"Spotify Animation Error: {e}")

class ProgressBarManager:
    """Manages the calculation, state, and creation of the progress bar entity."""

    def __init__(self, config: "Config", hass: "hass.Hass"):
        self.config = config
        self.hass = hass
        self.current_bar_str = ""
        self.ensure_entity_exists()

    def ensure_entity_exists(self):
        """Checks if the control input_boolean exists. Creates or updates it."""
        entity_id = self.config.progress_bar_entity
        
        attributes = {
            "friendly_name": "Pixoo64 Progress Bar",
            "icon": "mdi:progress-clock",
            "conf_character": self.config.progress_bar_character,
            "conf_resolution": self.config.progress_bar_resolution,
            "conf_font": self.config.progress_bar_font,
            "conf_color": self.config.progress_bar_color,
            "conf_y_position": self.config.progress_bar_y_offset,
            "conf_excluded_modes": self.config.progress_bar_exclude_modes
        }

        default_state = "on" if self.config.progress_bar_enabled else "off"

        if not self.hass.entity_exists(entity_id):
            self.hass.set_state(entity_id, state=default_state, attributes=attributes)
        else:
            current_state = self.hass.get_state(entity_id)
            if str(current_state).lower() not in ['on', 'off']:
                current_state = default_state
            self.hass.set_state(entity_id, state=current_state, attributes=attributes)

    def calculate(self, position: float, duration: float) -> tuple[str, float]:
        """Returns: (string_to_display, delay_in_seconds)"""
        if duration <= 0: return "", None

        max_chars = self.config.progress_bar_resolution
        remaining = duration - position
        
        # --- LOGIC 1: Force Full Bar if within last 10 seconds ---
        if remaining <= 10:
            chars_needed = max_chars
            self.current_bar_str = self.config.progress_bar_character * chars_needed
            return self.current_bar_str, None # Stop updating, we stay full until end

        # Standard calculation
        ratio = position / duration
        if ratio > 1: ratio = 1
        chars_needed = int(ratio * max_chars)

        # --- LOGIC 2: Force at least 1 char if track started ---
        if position > 0 and chars_needed < 1:
            chars_needed = 1

        self.current_bar_str = self.config.progress_bar_character * chars_needed

        # Calculate standard delay for next character
        next_char_index = chars_needed + 1
        delay = None
        
        if next_char_index <= max_chars:
            target_time = (next_char_index / max_chars) * duration
            delay = target_time - position
            if delay < 0.2: delay = 0.2 

        # --- LOGIC 3: Schedule update for the 10-second mark ---
        time_until_ten_seconds_left = remaining - 10
        if time_until_ten_seconds_left > 0:
            if delay is None or delay > time_until_ten_seconds_left:
                delay = time_until_ten_seconds_left

        return self.current_bar_str, delay

    async def get_payload_item(self, media_data: "MediaData") -> list:
        """Returns a LIST of Pixoo JSON items (Double Layer for bold effect)."""
        
        if not self.config.progress_bar_enabled: return []
        
        should_show = getattr(media_data, 'show_progress_bar', False)
        
        if not should_show or not self.current_bar_str:
            return []

        text_to_send = self.current_bar_str
        
        # --- COLOR LOGIC ---
        color = self.config.progress_bar_color
        if color == 'match':
            # This relies on ImageProcessor setting 'lyrics_font_color' to the vibrant color
            color = media_data.lyrics_font_color 
        
        items = []

        # Layer 1
        items.append({
            "TextId": 20, "type": 22, 
            "x": 0,
            "y": self.config.progress_bar_y_offset-7,
            "dir": 0, "font": self.config.progress_bar_font, 
            "TextWidth": 64, "Textheight": 10, "speed": 100, "align": 1,
            "TextString": text_to_send, "color": color
        })

        # Layer 2 (Pseudo-Bold)
        items.append({
            "TextId": 21, "type": 22, 
            "x": 2, 
            "y": self.config.progress_bar_y_offset-7,
            "dir": 0, "font": self.config.progress_bar_font, 
            "TextWidth": 64, "Textheight": 10, "speed": 100, "align": 1,
            "TextString": text_to_send, "color": color
        })

        return items

class NotificationManager:
    """Manages visual and audio notifications via HA Events with dynamic layout."""
    
    THEMES = {
        # --- Basic Types ---
        "info":    {"color": (0, 191, 255), "hex": "#00BFFF"},   # Deep Sky Blue
        "success": {"color": (50, 205, 50), "hex": "#32CD32"},   # Lime Green
        "warning": {"color": (255, 165, 0), "hex": "#FFA500"},   # Orange
        "error":   {"color": (255, 69, 0),  "hex": "#FF4500"},   # Orange Red
        "text":    {"color": (255, 255, 255), "hex": "#FFFFFF"}, # White
        
        # --- New Requested Types ---
        "v":       {"color": (50, 205, 50), "hex": "#32CD32"},   # Lime Green
        "x":       {"color": (255, 0, 0),   "hex": "#FF0000"},   # Red
        "alert":   {"color": (255, 69, 0),  "hex": "#FF4500"},   # Red-Orange
        "weather": {"color": (135, 206, 235), "hex": "#87CEEB"}, # Sky Blue
        "attack":  {"color": (255, 0, 0),   "hex": "#FF0000"},   # Red
        
        # --- Smart Home & Appliances ---
        "boiler":  {"color": (255, 69, 0),  "hex": "#FF4500"},   # Orange Red
        "shutter": {"color": (192, 192, 192), "hex": "#C0C0C0"}, # Silver
        "car":     {"color": (0, 255, 255), "hex": "#00FFFF"},   # Cyan
        "washer":  {"color": (0, 191, 255), "hex": "#00BFFF"},   # Deep Sky Blue
        "trash":   {"color": (50, 205, 50), "hex": "#32CD32"},   # Lime Green
        "door":    {"color": (255, 215, 0), "hex": "#FFD700"},   # Gold
        "lock":    {"color": (255, 0, 0),   "hex": "#FF0000"},   # Red
        "mail":    {"color": (255, 255, 224), "hex": "#FFFFE0"}, # Light Yellow
        "fire":    {"color": (255, 140, 0), "hex": "#FF8C00"},   # Dark Orange
        "water":   {"color": (30, 144, 255), "hex": "#1E90FF"},  # Dodger Blue
        "battery": {"color": (220, 20, 60), "hex": "#DC143C"},   # Crimson
        "wifi":    {"color": (255, 0, 0),   "hex": "#FF0000"},   # Red
        
        # --- Lifestyle & Utilities ---
        "timer":   {"color": (255, 255, 255), "hex": "#FFFFFF"}, # White
        "time":    {"color": (255, 255, 255), "hex": "#FFFFFF"}, # Alias
        "phone":   {"color": (0, 255, 0),     "hex": "#00FF00"}, # Green
        "calendar":{"color": (255, 255, 0),   "hex": "#FFFF00"}, # Yellow
        "camera":  {"color": (192, 192, 192), "hex": "#C0C0C0"}, # Silver
        "music":   {"color": (255, 105, 180), "hex": "#FF69B4"}, # Hot Pink
        "sun":     {"color": (255, 215, 0),   "hex": "#FFD700"}, # Gold
        "moon":    {"color": (147, 112, 219), "hex": "#9370DB"}, # Medium Purple
        "sleep":   {"color": (147, 112, 219), "hex": "#9370DB"}, # Alias
    }

    # Configuration for animations: (Total Frames, Speed in ms)
    ANIMATIONS = {
        "alert":   (2, 200),  # Wiggle fast
        "phone":   (2, 200),  # Wiggle fast
        "attack":  (2, 500),  # Flash Red/Yellow
        "error":   (2, 500),  # Flash Red/DarkRed
        "warning": (2, 500),  # Flash Orange/Yellow
        "weather": (2, 800),  # Bobbing cloud
        "wifi":    (3, 300),  # Signal expanding
        "timer":   (4, 150),  # Spinning hands
        "time":    (4, 150),
        "music":   (2, 400),  # Note bouncing
    }

    # Layout configurations based on line count (Icon mode only)
    LAYOUTS = {
        1: {"icon_cy": 25, "text_start_y": 48}, 
        2: {"icon_cy": 20, "text_start_y": 40}, 
        3: {"icon_cy": 15, "text_start_y": 30}, 
        4: {"icon_cy": 11, "text_start_y": 22}  
    }

    def __init__(self, config: "Config", pixoo: "PixooDevice", image_processor: "ImageProcessor"):
        self.config = config
        self.pixoo = pixoo
        self.proc = image_processor
        self.is_active = False

    async def display(self, event_data: dict):
        """Main entry point for displaying a notification."""
        try:
            self.is_active = True
            
            message = event_data.get("message", "")
            notif_type = event_data.get("type", "text").lower()
            duration = int(event_data.get("duration", 5))
            custom_color = event_data.get("color", None)

            if not message: return

            # --- Audio Trigger ---
            await self._trigger_buzzer(event_data)

            if notif_type == "text":
                max_lines = 6 
            else:
                max_lines = 4

            # --- DYNAMIC WRAP LIMIT ---
            wrap_limit = 11 if has_bidi(message) else 12

            raw_lines = textwrap.wrap(message, width=wrap_limit)
            lines = []
            for line in raw_lines:
                if has_bidi(line):
                    lines.append(get_bidi(line))
                else:
                    lines.append(line)

            if len(lines) > max_lines: lines = lines[:max_lines]
            if not lines: lines = [""]
            
            line_count = len(lines)
            
            if notif_type == "text":
                total_text_height = line_count * 10
                text_start_y = (64 - total_text_height) // 2
                icon_cy = 0 
            else:
                layout = self.LAYOUTS.get(line_count, self.LAYOUTS[2])
                icon_cy = layout["icon_cy"]
                text_start_y = layout["text_start_y"]

            theme = self.THEMES.get(notif_type, self.THEMES["info"])
            hex_color = custom_color if custom_color else theme["hex"]
            
            if notif_type == "text":
                rgb_color = self._hex_to_rgb(hex_color)
            else:
                rgb_color = theme["color"]

            # --- ANIMATION GENERATION ---
            anim_config = self.ANIMATIONS.get(notif_type, (1, 1000))
            total_frames = anim_config[0]
            anim_speed = anim_config[1]
            
            generated_frames_b64 = []

            for i in range(total_frames):
                bg_image = self._draw_background(notif_type, rgb_color, icon_cy, i)
                generated_frames_b64.append(self.proc.gbase64(bg_image))

            # Send Reset Command First
            await self.pixoo.send_command({
                "Command": "Draw/CommandList",
                "CommandList": [
                    {"Command": "Channel/OnOffScreen", "OnOff": 1},
                    {"Command": "Draw/ClearHttpText"},
                    {"Command": "Draw/ResetHttpGifId"},
                ]
            })

            # Send Frames
            for i, b64_frame in enumerate(generated_frames_b64):
                await self.pixoo.send_command({
                    "Command": "Draw/SendHttpGif",
                    "PicNum": total_frames,
                    "PicWidth": 64,
                    "PicOffset": i,
                    "PicID": 0,
                    "PicSpeed": anim_speed,
                    "PicData": b64_frame
                })

            await asyncio.sleep(0.2)

            text_items = self._create_text_items(lines, hex_color, text_start_y)
            if text_items:
                await self.pixoo.send_command({
                    "Command": "Draw/SendHttpItemList",
                    "ItemList": text_items
                })

            await asyncio.sleep(duration)

        except Exception as e:
            _LOGGER.error(f"Notification error: {e}")
        finally:
            self.is_active = False

    async def _trigger_buzzer(self, data: dict):
        """Handles the buzzer logic if requested."""
        if not data.get("play_buzzer", False):
            return

        active_time = int(data.get("buzzer_active", 500))
        off_time = int(data.get("buzzer_off", 500))
        total_time = int(data.get("buzzer_total", 3000))

        try:
            await self.pixoo.send_command({
                "Command": "Device/PlayBuzzer",
                "ActiveTimeInCycle": active_time,
                "OffTimeInCycle": off_time,
                "PlayTotalTime": total_time
            })
        except Exception as e:
            _LOGGER.warning(f"Failed to play buzzer: {e}")

    @lru_cache(maxsize=64)
    def _draw_background(self, n_type: str, color: tuple, cy: int, frame_num: int = 0) -> Image.Image:
        """Draws the border and icon based on notification type and frame number."""
        img = Image.new("RGB", (64, 64), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw Border
        draw.rectangle([0, 0, 63, 63], outline=color, width=1)
        
        if n_type == "text": 
            return img

        cx = 32 # Center X

        # --- ANIMATION LOGIC: Calculate Shift/Color based on frame_num ---
        shift_x = 0
        shift_y = 0
        
        # Wiggle Logic (Alert, Phone)
        if n_type in ["alert", "phone"]:
            if frame_num == 0: shift_x = 0
            elif frame_num == 1: shift_x = -1 if n_type == "alert" else 1
        
        # Flash Color Logic (Attack, Error)
        active_color = color
        if n_type == "attack" and frame_num == 1:
            active_color = (255, 255, 0) # Flash Yellow
        elif n_type in ["error", "warning"] and frame_num == 1:
            # Dim the color significantly for a flashing effect
            active_color = tuple(c // 2 for c in color)

        # Bobbing Logic (Weather, Music)
        if n_type in ["weather", "music"]:
            if frame_num == 1: shift_y = -1

        cx += shift_x
        cy += shift_y

        # --- DRAWING SHAPES ---

        if n_type == "v":
            points = [(cx-8, cy), (cx-2, cy+8), (cx+10, cy-8)]
            draw.line(points, fill=active_color, width=3)

        elif n_type == "x":
            s = 7
            draw.line([(cx-s, cy-s), (cx+s, cy+s)], fill=active_color, width=3)
            draw.line([(cx+s, cy-s), (cx-s, cy+s)], fill=active_color, width=3)

        elif n_type == "info":
            draw.ellipse([cx-9, cy-9, cx+9, cy+9], outline=active_color, width=1)
            draw.rectangle([cx-1, cy-2, cx+1, cy+5], fill=active_color) 
            draw.rectangle([cx-1, cy-5, cx+1, cy-4], fill=active_color)

        elif n_type == "success":
            points = [(cx-6, cy), (cx-2, cy+6), (cx+7, cy-5)]
            draw.line(points, fill=active_color, width=2)

        elif n_type in ["warning", "alert"]:
            # Alert Bell / Warning Triangle
            if n_type == "alert":
                draw.arc([cx-6, cy-5, cx+6, cy+5], 180, 0, fill=active_color, width=1)
                draw.line([(cx-6, cy), (cx-8, cy+6)], fill=active_color, width=1)
                draw.line([(cx+6, cy), (cx+8, cy+6)], fill=active_color, width=1)
                draw.line([(cx-8, cy+6), (cx+8, cy+6)], fill=active_color, width=1)
                # Animate clapper
                clapper_x = cx + (2 if frame_num == 1 else 0)
                draw.line([(clapper_x-1, cy+6), (clapper_x+1, cy+6)], fill=active_color, width=1)
                draw.point((clapper_x, cy+8), fill=active_color)
            else:
                points = [(cx, cy-9), (cx-10, cy+8), (cx+10, cy+8)]
                draw.polygon(points, outline=active_color, fill=None)
                draw.line([(cx, cy-3), (cx, cy+3)], fill=active_color, width=1)
                draw.point((cx, cy+5), fill=active_color)

        elif n_type == "error":
            s = 5
            draw.line([(cx-s, cy-s), (cx+s, cy+s)], fill=active_color, width=2)
            draw.line([(cx+s, cy-s), (cx-s, cy+s)], fill=active_color, width=2)

        elif n_type == "weather":
            # Sun
            draw.ellipse([cx+2, cy-8, cx+8, cy-2], outline=(255, 215, 0), width=1)
            # Cloud
            draw.arc([cx-8, cy-2, cx+2, cy+6], 90, 270, fill=active_color, width=1)
            draw.arc([cx-2, cy-4, cx+8, cy+6], 180, 0, fill=active_color, width=1)
            draw.line([(cx-8, cy+2), (cx+8, cy+2)], fill=active_color, width=1)

        elif n_type == "attack":
            # Rocket
            draw.line([(cx, cy-9), (cx-3, cy-4)], fill=active_color, width=1)
            draw.line([(cx, cy-9), (cx+3, cy-4)], fill=active_color, width=1)
            draw.rectangle([cx-3, cy-4, cx+3, cy+4], outline=active_color, width=1)
            draw.line([(cx-3, cy+4), (cx-6, cy+8)], fill=active_color, width=1)
            draw.line([(cx+3, cy+4), (cx+6, cy+8)], fill=active_color, width=1)
            # Animate Fire
            fire_color = (255, 165, 0) if frame_num == 0 else (255, 255, 0)
            draw.line([(cx-1, cy+4), (cx-1, cy+7)], fill=fire_color, width=1)
            draw.line([(cx+1, cy+4), (cx+1, cy+7)], fill=fire_color, width=1)

        elif n_type == "wifi":
            draw.point((cx, cy+6), fill=active_color)
            if frame_num >= 1:
                draw.arc([cx-4, cy, cx+4, cy+8], 225, 315, fill=active_color, width=1)
            if frame_num >= 2:
                draw.arc([cx-8, cy-4, cx+8, cy+4], 225, 315, fill=active_color, width=1)

        elif n_type in ["timer", "time"]:
            draw.ellipse([cx-9, cy-9, cx+9, cy+9], outline=active_color, width=1)
            # Spinning Hand
            import math
            angle = frame_num * 90 # 0, 90, 180, 270
            rad = math.radians(angle - 90) # Correct PIL coord system
            end_x = cx + 6 * math.cos(rad)
            end_y = cy + 6 * math.sin(rad)
            draw.line([(cx, cy), (end_x, end_y)], fill=active_color, width=1)
        
        elif n_type == "boiler": 
            draw.rectangle([cx-5, cy-8, cx+5, cy+8], outline=active_color, width=1)
            draw.line([(cx+1, cy-4), (cx-2, cy), (cx+2, cy), (cx-1, cy+5)], fill=active_color, width=1)
            draw.point((cx, cy+6), fill=active_color)

        elif n_type == "shutter": 
            draw.rectangle([cx-8, cy-8, cx+8, cy+8], outline=active_color, width=1)
            for y_line in range(cy-5, cy+7, 3):
                draw.line([(cx-6, y_line), (cx+6, y_line)], fill=active_color, width=1)

        elif n_type == "car": 
            draw.rectangle([cx-9, cy, cx+9, cy+6], outline=active_color, width=1)
            draw.line([(cx-9, cy), (cx-5, cy-5), (cx+5, cy-5), (cx+9, cy)], fill=active_color, width=1)
            draw.ellipse([cx-7, cy+5, cx-4, cy+8], fill=active_color)
            draw.ellipse([cx+4, cy+5, cx+7, cy+8], fill=active_color)

        elif n_type == "washer": 
            draw.rectangle([cx-8, cy-8, cx+8, cy+8], outline=active_color, width=1)
            draw.ellipse([cx-5, cy-5, cx+5, cy+5], outline=active_color, width=1)
            draw.point((cx+6, cy-6), fill=active_color) 

        elif n_type == "trash": 
            draw.line([(cx-5, cy+8), (cx+5, cy+8), (cx+7, cy-4), (cx-7, cy-4), (cx-5, cy+8)], fill=active_color, width=1)
            draw.line([(cx-8, cy-4), (cx+8, cy-4)], fill=active_color, width=1)
            draw.rectangle([cx-2, cy-6, cx+2, cy-4], fill=active_color)

        elif n_type == "door": 
            draw.rectangle([cx-6, cy-9, cx+6, cy+9], outline=active_color, width=1)
            draw.line([(cx-6, cy-9), (cx+2, cy-6)], fill=active_color, width=1)
            draw.line([(cx+2, cy-6), (cx+2, cy+9)], fill=active_color, width=1)
            draw.line([(cx+2, cy+9), (cx-6, cy+9)], fill=active_color, width=1)

        elif n_type == "lock": 
            draw.rectangle([cx-6, cy-2, cx+6, cy+7], fill=active_color)
            draw.arc([cx-5, cy-8, cx+5, cy-1], 180, 0, fill=active_color, width=1)

        elif n_type == "mail": 
            draw.rectangle([cx-9, cy-6, cx+9, cy+6], outline=active_color, width=1)
            draw.line([(cx-9, cy-6), (cx, cy+2), (cx+9, cy-6)], fill=active_color, width=1)

        elif n_type == "battery": 
            draw.rectangle([cx-8, cy-4, cx+6, cy+4], outline=active_color, width=1)
            draw.rectangle([cx-7, cy-3, cx-2, cy+3], fill=active_color) 
            draw.rectangle([cx+6, cy-2, cx+8, cy+2], fill=active_color) 

        elif n_type == "fire": 
            draw.polygon([(cx, cy-8), (cx+5, cy+2), (cx+3, cy+8), (cx-3, cy+8), (cx-5, cy+2)], outline=active_color, fill=None)
            draw.point((cx, cy+5), fill=active_color)

        elif n_type == "water": 
            draw.polygon([(cx, cy-8), (cx+5, cy+2), (cx, cy+8), (cx-5, cy+2)], outline=active_color, fill=active_color)

        elif n_type == "sleep": 
            draw.arc([cx-6, cy-6, cx+6, cy+6], 90, 270, fill=active_color, width=2)
            draw.line([(cx, cy-6), (cx, cy+6)], fill=active_color, width=1)
            
        elif n_type == "phone":
            draw.arc([cx-8, cy-4, cx+8, cy+12], 0, 180, fill=active_color, width=2)
            draw.rectangle([cx-9, cy-4, cx-6, cy], fill=active_color)
            draw.rectangle([cx+6, cy-4, cx+9, cy], fill=active_color)

        elif n_type == "calendar":
            draw.rectangle([cx-8, cy-7, cx+8, cy+8], outline=active_color, width=1)
            draw.line([(cx-8, cy-3), (cx+8, cy-3)], fill=active_color, width=1)
            draw.point((cx-4, cy+1), fill=active_color)
            draw.point((cx, cy+1), fill=active_color)
            draw.point((cx+4, cy+1), fill=active_color)
            draw.point((cx-4, cy+5), fill=active_color)
            draw.point((cx, cy+5), fill=active_color)

        elif n_type == "camera":
            draw.rectangle([cx-8, cy-5, cx+8, cy+6], outline=active_color, width=1)
            draw.rectangle([cx-2, cy-8, cx+2, cy-5], fill=active_color)
            draw.ellipse([cx-3, cy-2, cx+3, cy+4], outline=active_color, width=1)

        elif n_type == "music":
            draw.ellipse([cx-7, cy+3, cx-3, cy+7], fill=active_color)
            draw.ellipse([cx+3, cy+3, cx+7, cy+7], fill=active_color)
            draw.line([(cx-3, cy+5), (cx-3, cy-6)], fill=active_color, width=1)
            draw.line([(cx+7, cy+5), (cx+7, cy-6)], fill=active_color, width=1)
            draw.line([(cx-3, cy-6), (cx+7, cy-6)], fill=active_color, width=2)

        elif n_type == "sun":
            draw.ellipse([cx-4, cy-4, cx+4, cy+4], fill=active_color)
            s = 7
            draw.line([(cx, cy-s), (cx, cy-s-2)], fill=active_color, width=1)
            draw.line([(cx, cy+s), (cx, cy+s+2)], fill=active_color, width=1)
            draw.line([(cx-s, cy), (cx-s-2, cy)], fill=active_color, width=1)
            draw.line([(cx+s, cy), (cx+s+2, cy)], fill=active_color, width=1)
            draw.point((cx-5, cy-5), fill=active_color)
            draw.point((cx+5, cy-5), fill=active_color)
            draw.point((cx-5, cy+5), fill=active_color)
            draw.point((cx+5, cy+5), fill=active_color)

        elif n_type == "moon":
            draw.arc([cx-6, cy-6, cx+6, cy+6], 90, 270, fill=active_color, width=2)
            draw.line([(cx, cy-6), (cx, cy+6)], fill=active_color, width=1)

        return img

    def _create_text_items(self, lines: list, color: str, start_y: int) -> list:
        items = []
        ids_to_clear = [1, 2, 3, 4, 5, 6, 10, 11, 20, 21, 22, 25, 26, 27, 28, 29, 30] 
        for tid in ids_to_clear:
            items.append({
                "TextId": tid, "type": 22, "x": 0, "y": 0, "dir": 0, "font": 190,
                "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 1,
                "TextString": "", "color": "#000000"
            })

        line_height = 10 
        for i, line in enumerate(lines):
            rtl = 1 if has_bidi(line) else 0
            items.append({
                "TextId": 25 + i, "type": 22, "x": 0, "y": start_y + (i * line_height),
                "dir": rtl, "font": 190, "TextWidth": 64, "Textheight": 16,
                "speed": 100, "align": 2, "TextString": line, "color": color
            })
        return items

    def _hex_to_rgb(self, hex_str: str) -> tuple:
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3: hex_str = ''.join([c*2 for c in hex_str])
        try:
            return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        except ValueError:
            return (255, 255, 255)

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
        
        # Scheduler variables
        self.lyrics_active_mode = False 
        self.scheduler_generation_id = 0 
        
        # Progress Bar variables
        self.progress_manager = None
        self.progress_timer_gen_id = 0

    async def initialize(self):
        _LOGGER.info("Initializing Pixoo64 Album Art Display AppDaemon app…")
        
        self.config = Config(self.args)
        
        self.websession = aiohttp.ClientSession()
        self.is_art_visible = False
        self.pixoo_device = PixooDevice(self.config, self.websession)
        
        self.image_processor = ImageProcessor(self.config, self.websession)
        self.spotify_service = SpotifyService(self.config, self.websession, self.image_processor)

        self.media_data = MediaData(self.config, self.image_processor, self.websession)
        self.fallback_service = FallbackService(self.config, self.image_processor, self.websession, self.spotify_service, self.pixoo_device)
        self.notification_manager = NotificationManager(self.config, self.pixoo_device, self.image_processor)

        self.listen_state(self._mode_changed, self.config.mode_entity)
        self.listen_state(self._crop_mode_changed, self.config.crop_entity)
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute="media_title")
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute="state")
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute="media_position")
        self.listen_event(self.on_pixoo_notify, "pixoo_notify")

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

        # --- Progress Bar Init ---
        self.progress_manager = ProgressBarManager(self.config, self)
        self.listen_state(self._progress_bar_toggle_changed, self.config.progress_bar_entity)

        # *** KICKSTART LOOP IF PLAYING ***
        current_state = await self.get_state(self.config.media_player)
        if current_state in ["playing", "on"]:
            self.progress_timer_gen_id += 1
            await self._update_progress_bar_loop()

        _LOGGER.info("Initialization complete.")

    async def terminate(self):
        self._stop_lyrics_scheduler()
    
        # Properly shutdown the thread pool executor
        if hasattr(self, 'image_processor'):
            self.image_processor.shutdown()

        if self.current_image_task and not self.current_image_task.done():
            self.current_image_task.cancel()
            
        if self.debounce_task and not self.debounce_task.done():
            self.debounce_task.cancel()

        if hasattr(self, 'websession') and self.websession and not self.websession.closed:
            await self.websession.close()

    # =========================================================================
    # SETTINGS & CONFIG HANDLERS
    # =========================================================================

    async def _lyrics_sync_changed(self, entity, attribute, old, new, kwargs):
        await self._apply_lyrics_sync()
        # Trigger resync if active
        if self.lyrics_active_mode:
            await self._calculate_and_schedule_next()

    async def _apply_lyrics_sync(self):
        self.config.lyrics_sync = (await self.get_state(self.config.lyrics_sync_entity))

    async def _crop_mode_changed(self, entity, attribute, old, new, kwargs):
        await self._apply_crop_settings()

    async def _apply_crop_settings(self):
        options = ["Default", "No Crop", "Crop", "Extra Crop"]
        default = options[0]

        try:
            # 1. Handle Entity Creation/Options
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

            # 2. Apply Logic
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
            
            # 3. Clear Cache so the image is forced to re-process with new settings
            self.image_processor.image_cache.clear()
            
            # 4. FORCE REFRESH 
            current_state = await self.get_state(self.config.media_player)
            if current_state in ["playing", "on"]:
                # Trigger the main callback manually to redraw the screen immediately
                await self.safe_state_change_callback(self.config.media_player, "state", None, "playing", {})
            
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
                    self.config.show_lyrics      = ("lyrics" in m) if m else False
                    self.config.spotify_slide    = ("slider" in m) if m else False
                    self.config.special_mode     = ("special" in m) if m else False
                    self.config.show_clock       = ("clock" in m) if m else False
                    self.config.temperature      = ("temperature" in m) if m else False
                    self.config.show_text        = ("text" in m) if m else False
                    self.config.text_bg          = ("background" in m) if m else False
                    self.config.force_ai         = ("ai" in m) if m else False
                    self.config.burned           = ("burned" in m) if m else False

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
                
                # Check mode change
                await self._start_or_stop_lyrics_scheduler()
                
                # Refresh display if playing
                current_state = await self.get_state(self.config.media_player)
                if current_state in ["playing", "on"]:
                    await self.safe_state_change_callback(self.config.media_player, "state", None, "playing", {})
        
        except Exception as e:
            _LOGGER.warning(f"Error checking mode entity: {e}")

    # =========================================================================
    # LYRICS SCHEDULER
    # =========================================================================

    def _stop_lyrics_scheduler(self):
        """Disables the lyrics scheduler."""
        self.lyrics_active_mode = False
        self.scheduler_generation_id += 1 # Invalidate any pending timers

    async def _start_or_stop_lyrics_scheduler(self):
        """Decides whether to Start or Stop based on ALL conditions."""
        
        # 1. Validation
        should_run = True
        
        if not self.config.show_lyrics:
            should_run = False
        
        if not self.media_data.lyrics:
            should_run = False
            
        state = await self.get_state(self.config.media_player)
        if str(state).lower() not in ["playing", "on"]:
            should_run = False

        # 2. Action
        if should_run:
            self.lyrics_active_mode = True
            await self._calculate_and_schedule_next()
        else:
            self._stop_lyrics_scheduler()

    async def _timer_callback_wrapper(self, kwargs):
        gen_id = kwargs.get('gen_id')
        if gen_id != self.scheduler_generation_id:
            return
        await self._calculate_and_schedule_next()

    async def _calculate_and_schedule_next(self):
        # Gatekeeper
        if hasattr(self, 'notification_manager') and self.notification_manager.is_active:
            return
        if not self.lyrics_active_mode:
            return

        self.scheduler_generation_id += 1
        current_gen_id = self.scheduler_generation_id

        # Calculate precise position
        if not self.media_data.media_position_updated_at:
            current_track_pos = self.media_data.media_position 
        else:
            now_utc = datetime.now(timezone.utc)
            elapsed = (now_utc - self.media_data.media_position_updated_at).total_seconds()
            sync_offset = float(self.config.lyrics_sync) if self.config.lyrics_sync else 0.0
            current_track_pos = self.media_data.media_position + elapsed - sync_offset

        # Get Plan from Provider
        layout_items, delay = self.media_data.lyrics_provider.get_refresh_plan(current_track_pos)

        # Execute Plan
        if layout_items is not None:
            pixoo_items = []
            font_color = self.media_data.lyrics_font_color
            
            for i in range(6):
                if i < len(layout_items):
                    item = layout_items[i]
                    
                    # Boundary check
                    calc_height = item['h']
                    if item['y'] + calc_height > 64:
                        calc_height = 64 - item['y']

                    pixoo_items.append({
                        "TextId": i + 1, 
                        "type": 22, 
                        "x": 0, 
                        "y": item['y'],
                        "dir": item['dir'], 
                        "font": self.config.lyrics_font, 
                        "TextWidth": 64, 
                        "Textheight": calc_height,
                        "speed": 0,
                        "align": 2,
                        "TextString": item['text'], 
                        "color": font_color
                    })
                else:
                    # Clear unused slots by moving them OFF SCREEN
                    pixoo_items.append({
                        "TextId": i + 1, 
                        "type": 22, 
                        "x": 0, 
                        "y": 0,
                        "dir": 0,
                        "font": self.config.lyrics_font, 
                        "TextWidth": 64, 
                        "Textheight": 12, 
                        "speed": 0,  
                        "align": 2, 
                        "TextString": "", 
                        "color": font_color
                    })

            # Append progress bar if enabled
            progress_items = await self.progress_manager.get_payload_item(self.media_data)
            if progress_items:
                pixoo_items.extend(progress_items)
            
            # Send to Pixoo
            # We ignore hash check if delay is None (implies a Seek/Jump event) to force update
            current_hash = hash(str(pixoo_items))
            
            if current_hash != self.last_text_payload_hash or delay is None:
                await self.pixoo_device.send_command({
                    "Command": "Draw/SendHttpItemList", 
                    "ItemList": pixoo_items
                })
                self.last_text_payload_hash = current_hash

        # Schedule Next Run
        if delay is not None:
            self.run_in(self._timer_callback_wrapper, delay, gen_id=current_gen_id)
        else:
            self.run_in(self._timer_callback_wrapper, 5, gen_id=current_gen_id)
    
    # ==========================
    # PROGRESS BAR LOGIC
    # ==========================

    async def _progress_bar_toggle_changed(self, entity, attribute, old, new, kwargs):
        """Handle manual toggle of progress bar."""
        # 1. Update the loop (start or stop timers)
        await self._update_progress_bar_loop()
        
        # 2. Check if media is currently playing
        state = await self.get_state(self.config.media_player)
        
        if state in ["playing", "on"]:
            # 3. Force Full Refresh
            # Send old=None to bypass the "if new == old" check and force a refresh
            await self.state_change_callback(self.config.media_player, "state", None, state, {})


        state = await self.get_state(self.config.media_player)
        if state not in ["playing", "on"]: return

        if self.config.progress_bar_enabled:
            pb_state = await self.get_state(self.config.progress_bar_entity)
            if str(pb_state).lower() != 'on':
                return 

        current_mode = await self.get_state(self.config.mode_entity)
        if current_mode in self.config.progress_bar_exclude_modes: return

        if not self.media_data.media_position_updated_at:
            current_pos = self.media_data.media_position
        else:
            now = datetime.now(timezone.utc)
            elapsed = (now - self.media_data.media_position_updated_at).total_seconds()
            current_pos = self.media_data.media_position + elapsed

        bar_str, delay = self.progress_manager.calculate(current_pos, self.media_data.media_duration)

        if self.is_art_visible:
            await self._rebuild_and_send_text_layer()

        if delay:
            self.progress_timer_gen_id += 1
            self.run_in(self._progress_bar_timer_callback, delay, gen_id=self.progress_timer_gen_id)

    async def _progress_bar_timer_callback(self, kwargs):
        if kwargs.get('gen_id') != self.progress_timer_gen_id: return
        await self._update_progress_bar_loop()

    async def _update_progress_bar_loop(self):
        # Guard clause for notifications
        if hasattr(self, 'notification_manager') and self.notification_manager.is_active:
            return 

        state = await self.get_state(self.config.media_player)
        if state not in ["playing", "on"]: return

        if self.config.progress_bar_enabled:
            pb_state = await self.get_state(self.config.progress_bar_entity)
            if str(pb_state).lower() != 'on':
                return 

        current_mode = await self.get_state(self.config.mode_entity)
        if current_mode in self.config.progress_bar_exclude_modes: return

        if not self.media_data.media_position_updated_at:
            current_pos = self.media_data.media_position
        else:
            now = datetime.now(timezone.utc)
            elapsed = (now - self.media_data.media_position_updated_at).total_seconds()
            current_pos = self.media_data.media_position + elapsed

        bar_str, delay = self.progress_manager.calculate(current_pos, self.media_data.media_duration)

        # Update the screen if needed
        if self.is_art_visible:
            await self._rebuild_and_send_text_layer()

        # Schedule next update
        if delay:
            self.progress_timer_gen_id += 1
            self.run_in(self._progress_bar_timer_callback, delay, gen_id=self.progress_timer_gen_id)

    async def _rebuild_and_send_text_layer(self):
        """Re-sends the text list including the progress bar without reprocessing image."""
        if hasattr(self, 'notification_manager') and self.notification_manager.is_active:
            return
            
        font_color = self.media_data.lyrics_font_color
        bg_color = getattr(self.media_data, 'background_color', '#000000') 

        items = await self._build_text_items_list(self.media_data, font_color, bg_color)
        
        if items:
            payload = { "Command": "Draw/SendHttpItemList", "ItemList": items }
            current_hash = hash(str(payload))
            
            if current_hash != self.last_text_payload_hash:
                await self.pixoo_device.send_command(payload)
                self.last_text_payload_hash = current_hash
        
    # =========================================================================
    # STATE CALLBACKS & DEBOUNCING
    # =========================================================================

    async def safe_state_change_callback(self, entity: str, attribute: str, old: Any, new: Any, kwargs: Dict[str, Any]) -> None:
        # Cancel existing debounce
        if self.debounce_task and not self.debounce_task.done():
            self.debounce_task.cancel()
        
        if self.current_image_task and not self.current_image_task.done():
            self.current_image_task.cancel()
        
        self.debounce_task = asyncio.create_task(
            self._run_debounced_callback(entity, attribute, old, new, kwargs)
        )
        
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
            # 1. HANDLE POSITION SEEKING
            if attribute == "media_position":
                await self.media_data.update(self)
                
                # Reset the Progress Bar timer and force an immediate redraw
                self.progress_timer_gen_id += 1
                await self._update_progress_bar_loop()

                # If lyrics are on, force the scheduler to jump to the new time
                if self.lyrics_active_mode:
                    self.scheduler_generation_id += 1
                    await self._calculate_and_schedule_next()
                
                return

            # 2. STANDARD STATE CHECKS
            if new == old or (await self.get_state(self.config.toggle)) != "on":
                return 

            if attribute == "state":
                current_media_state = str(new).lower()
            else:
                s = await self.get_state(self.config.media_player)
                current_media_state = str(s).lower() if s else "off"
            
            # 3. HANDLE PAUSE / STOP
            if current_media_state in ["off", "idle", "pause", "paused"]:
                self._stop_lyrics_scheduler()
                self.progress_timer_gen_id += 1
                
                self.last_text_payload_hash = None
                await asyncio.sleep(5) 
                
                rechecked_state = await self.get_state(self.config.media_player)
                rechecked_state_str = str(rechecked_state).lower() if rechecked_state else "off"
                
                if rechecked_state_str in ["playing", "on"]:
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
                self.is_art_visible = False
                await self.set_state(self.media_data_sensor, state="off")
                if self.config.light: await self.control_light('off')
                if self.config.wled: await self.control_wled_light('off')
                return 

            # Full refresh for track change or play state change
            await self.update_attributes(entity, attribute, old, new, kwargs)
            
        except Exception as e:
            _LOGGER.error(f"Error in state_change_callback: {e}")

    async def update_attributes(self, entity: str, attribute: str, old: Any, new: Any, kwargs: Dict[str, Any]) -> None:
        if hasattr(self, 'notification_manager') and self.notification_manager.is_active:
            return
        try:
            media_state_str = await self.get_state(self.config.media_player)
            media_state = media_state_str if media_state_str else "off"
            
            if media_state not in ["playing", "on"]:
                self._stop_lyrics_scheduler()
                if self.config.light: await self.control_light('off')
                if self.config.wled: await self.control_wled_light('off')
                return 

            # Update Media Data
            media_data = await self.media_data.update(self)
            
            # Re-evaluate scheduling (handles new track, seek, etc)
            await self._start_or_stop_lyrics_scheduler()

            # *** KICKSTART PROGRESS BAR LOOP ***
            self.progress_timer_gen_id += 1
            await self._update_progress_bar_loop()
            
            if not media_data:
                return

            await self.pixoo_run(media_state, media_data)
        except Exception as e:
            _LOGGER.error(f"Error in update_attributes: {e}", exc_info=True)

    # =========================================================================
    # PIXOO DISPLAY LOGIC
    # =========================================================================

    async def pixoo_run(self, media_state: str, media_data: "MediaData") -> None:
        if hasattr(self, 'notification_manager') and self.notification_manager.is_active:
                return
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

    async def _build_text_items_list(self, media_data: "MediaData", font_color: str, bg_color: str) -> list:
        """Helper function that constructs the list of text elements."""
        text_items_for_display_list = []
        current_text_id = 0
        
        # 1. Special Mode Logic
        if self.config.special_mode:
            current_text_id += 1
            day_item = { "TextId": current_text_id, "type": 14, "x": 3, "y": 1, "dir": 0, "font": 18, "TextWidth": 33, "Textheight": 6, "speed": 100, "align": 1, "color": font_color}
            text_items_for_display_list.append(day_item)

            current_text_id += 1
            clock_item_special = { "TextId": current_text_id, "type": 5, "x": 0, "y": 1, "dir": 0, "font": 18, "TextWidth": 64, "Textheight": 6, "speed": 100, "align": 2, "color": bg_color}
            text_items_for_display_list.append(clock_item_special)

            current_text_id += 1
            if media_data.temperature:
                temp_item_special = {"TextId": current_text_id, "type": 22, "x": 42, "y": 1, "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6, "speed": 100, "align": 1, "color": font_color, "TextString": media_data.temperature}
            else:
                temp_item_special = {"TextId": current_text_id, "type": 17, "x": 42, "y": 1, "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6, "speed": 100, "align": 3, "color": font_color}
            text_items_for_display_list.append(temp_item_special)

            if (self.config.show_text and not media_data.playing_tv) or (media_data.spotify_slide_pass and self.config.spotify_slide):
                dir_rtl_artist = 1 if has_bidi(media_data.artist) else 0
                text_artist_bidi = get_bidi(media_data.artist) if dir_rtl_artist == 1 else media_data.artist
                current_text_id += 1
                artist_item = { "TextId": current_text_id, "type": 22, "x": 0, "y": 42, "dir": dir_rtl_artist, "font": 190, "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 2, "TextString": text_artist_bidi, "color": font_color}
                text_items_for_display_list.append(artist_item)

                dir_rtl_title = 1 if has_bidi(media_data.title) else 0
                text_title_bidi = get_bidi(media_data.title) if dir_rtl_title == 1 else media_data.title
                current_text_id += 1
                title_item = { "TextId": current_text_id, "type": 22, "x": 0, "y": 52, "dir": dir_rtl_title, "font": 190, "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 2, "TextString": text_title_bidi, "color": bg_color}
                text_items_for_display_list.append(title_item)
        
        # 2. Standard Mode Logic
        elif (self.config.show_text or self.config.show_clock or self.config.temperature) and not (self.config.show_lyrics or self.config.spotify_slide):
            if self.config.top_text:
                y_text = 0
                y_info = 56
            else:
                y_text = 48
                y_info = 3

            text_track = (media_data.artist + " - " + media_data.title)
            if len(text_track) > 14: text_track = text_track + "        "
            text_string_bidi = get_bidi(text_track) if media_data.artist else get_bidi(media_data.title)
            dir_rtl = 1 if has_bidi(text_string_bidi) else 0

            if text_string_bidi and self.config.show_text and not media_data.radio_logo and not media_data.playing_tv:
                current_text_id += 1
                text_item = { "TextId": current_text_id, "type": 22, "x": 0, "y": y_text, "dir": dir_rtl, "font": 2, "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 2, "TextString": text_string_bidi, "color": font_color}
                text_items_for_display_list.append(text_item)

            if self.config.show_clock:
                current_text_id += 1
                x_clock = 44 if self.config.clock_align == "Right" else 3
                clock_item_normal = { "TextId": current_text_id, "type": 5, "x": x_clock, "y": y_info, "dir": 0, "font": 18, "TextWidth": 32, "Textheight": 16, "speed": 100, "align": 1, "color": font_color}
                text_items_for_display_list.append(clock_item_normal)

            if self.config.temperature:
                current_text_id += 1
                x_temp = 3 if self.config.clock_align == "Right" else 40
                if media_data.temperature:
                    temp_item_normal = {"TextId": current_text_id, "type": 22, "x": x_temp, "y": y_info, "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6, "speed": 100, "align": 1, "color": font_color, "TextString": media_data.temperature}
                else:
                    temp_item_normal = {"TextId": current_text_id, "type": 17, "x": x_temp, "y": y_info, "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6, "speed": 100, "align": 1, "color": font_color}
                text_items_for_display_list.append(temp_item_normal)

        progress_items_list = await self.progress_manager.get_payload_item(media_data)
        if progress_items_list:
            text_items_for_display_list.extend(progress_items_list)

        return text_items_for_display_list

    async def _process_and_display_image(self, media_data: "MediaData") -> None:
        if media_data.picture == "TV_IS_ON":
            payload = {"Command": "Channel/SetIndex", "SelectIndex": self.select_index}
            await self.pixoo_device.send_command(payload)
                
            if self.config.light: await self.control_light('off')
            if self.config.wled: await self.control_wled_light('off')
                
            self.last_text_payload_hash = None
            self.is_art_visible = False
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

            final_bar_color = self.config.progress_bar_color
            if final_bar_color == 'match':
                final_bar_color = getattr(media_data, 'lyrics_font_color', font_color_from_image_processing)

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
                "pixoo64_channel": self.select_index if self.select_index != 0 else "0",
                "image_source": media_data.pic_source,
                "image_url": media_data.pic_url,
                "lyrics": media_data.lyrics,
                "progress_bar_active": getattr(media_data, 'show_progress_bar', False),
                "progress_bar_color": final_bar_color if getattr(media_data, 'show_progress_bar', False) else "inactive"
            }
            
            image_payload = {
                "Command": "Draw/CommandList",
                "CommandList": [
                    {"Command": "Channel/OnOffScreen", "OnOff": 1},
                #    {"Command": "Draw/ClearHttpText"},
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
                            await self.spotify_service.spotify_album_art_animation(self.pixoo_device, media_data, self.select_index)
                    else:
                        await self.spotify_service.spotify_albums_slide(self.pixoo_device, media_data, self.select_index)

                    if media_data.spotify_slide_pass:
                        spotify_animation_took_over_display = True
                        self.is_art_visible = True
                        spotify_anim_end_time = time.perf_counter()
                        duration = spotify_anim_end_time - spotify_anim_start_time
                        media_data.process_duration = f"{duration:.2f} seconds (Spotify)"
                        new_attributes["process_duration"] = media_data.process_duration
                        new_attributes["spotify_frames"] = media_data.spotify_frames
                    else:
                        # await self.pixoo_device.send_command({"Command": "Channel/SetIndex", "SelectIndex": 4})
                        await self.pixoo_device.send_command({"Command": "Channel/SetIndex", "SelectIndex": self.select_index})
                        # await self.pixoo_device.send_command({"Command": "Draw/ResetHttpGifId"})

            # --- TEXT LAYER CONSTRUCTION ---
            if self.config.force_font_color:
                text_overlay_font_color = self.config.force_font_color
            elif font_color_from_image_processing:
                text_overlay_font_color = font_color_from_image_processing
            else:
                text_overlay_font_color = '#ffff00'

            media_data.background_color = background_color_str
            media_data.lyrics_font_color = text_overlay_font_color 
            
            text_items_for_display_list = await self._build_text_items_list(
                media_data, 
                text_overlay_font_color, 
                background_color_str
            )
            
            if not spotify_animation_took_over_display:
                await self.pixoo_device.send_command(image_payload)
                self.is_art_visible = True
                self.last_text_payload_hash = None 

                if text_items_for_display_list:
                    txt_payload = ({ "Command": "Draw/SendHttpItemList", "ItemList": text_items_for_display_list })
                    current_payload_hash = str(txt_payload)
                
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
            
            # Update Sensor
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
                self.is_art_visible = True
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

        if self._last_wled_payload == target_signature:
            return

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

    async def on_pixoo_notify(self, event_name, data, kwargs):
        """Callback for HA Event 'pixoo_notify' with Smart Restore."""

        previous_channel = 0 
        try:
            previous_channel = await self.pixoo_device.get_current_channel_index()
        except Exception as e:
            _LOGGER.warning(f"Could not get current channel, defaulting to 0: {e}")

        if self.current_image_task and not self.current_image_task.done():
            self.current_image_task.cancel()
            self.current_image_task = None

        await self.notification_manager.display(data)
        
        current_state = await self.get_state(self.config.media_player)
        
        if current_state in ["playing", "on"]:

            await self.state_change_callback(self.config.media_player, "state", None, current_state, {})
            await asyncio.sleep(0.5)
            await self._rebuild_and_send_text_layer()
        
        else:
            await self.pixoo_device.send_command({
                "Command": "Draw/CommandList", 
                "CommandList": [
                    {"Command": "Draw/ClearHttpText"},  
                    {"Command": "Draw/ResetHttpGifId"},
                    {"Command": "Channel/SetIndex", "SelectIndex": previous_channel}
                ]
            })
