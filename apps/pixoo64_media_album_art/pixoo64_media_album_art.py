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
        pollinations: False                         # Your pollinations API key (Optional use for quick access). Obtain from https://auth.pollinations.ai/
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
#import async_timeout
import base64
import json
import logging
import math
import random
import re
import sys
import time
import traceback
import textwrap 
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

import logging
_LOGGER = logging.getLogger(__name__)

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

COLOR_PALETTE = [
    # Reds / Oranges
    (255, 0, 0), (255, 51, 51), (255, 99, 71), (255, 140, 0),
    (255, 165, 0), (255, 185, 15), (255, 215, 0), (255, 255, 0),

    # Yellows / Greens
    (204, 255, 0), (173, 255, 47), (127, 255, 0), (50, 205, 50),
    (34, 139, 34), (64, 255, 128), (0, 255, 127), (0, 255, 0),

    # Cyans / Blues
    (0, 255, 255), (0, 204, 255), (0, 191, 255), (30, 144, 255),
    (65, 105, 225), (0, 0, 255), (18, 10, 255), (75, 0, 130),

    # Violets / Magentas
    (138, 43, 226), (148, 0, 211), (153, 50, 204), (186, 85, 211),
    (238, 130, 238), (255, 0, 255), (221, 0, 221), (255, 20, 147),
    (255, 64, 160),

    # Warm Browns / Extras
    (210, 105, 30), (160, 82, 45), (255, 69, 0), (255, 35, 97),
    (255, 0, 127), (0, 128, 192), (0, 255, 192), (192, 0, 255),
    ]

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
        except Image.Error as e:
            _LOGGER.error(f"Error in img_adptive: {e}", exc_info=True) 
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
        _LOGGER.error("To display RTL text you need to add bidi-algorithm package. You can ignore this error if you don't need RTL support.")
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
    except (UnidentifiedImageError, OSError) as e:
        _LOGGER.error(f"Error converting image to RGB: {e}", exc_info=True)
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
            'font': 190, 
            'special_mode_spotify_slider': False,
            'force_font_color': None, 
            'burned': False,
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
        # Loop through sections and apply defaults
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

        # Post-process specific clamping (as before)
        self.images_cache = max(1, min(int(self.images_cache) if self.images_cache is not None else 1, 300))
        self.sound_effect = max(0, min(int(self.sound_effect) if self.sound_effect is not None else 0, 3))

        self._fix_config_args(getattr(self, 'url', None)) # Pass the pixoo URL
        self._validate_config()

        # Save original config snapshot
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

    def _fix_config_args(self, pixoo_url_raw: Optional[str]):
        """Fixes and formats configuration arguments."""
        if pixoo_url_raw: # Only process if a URL was provided or defaulted (and not None)
            pixoo_url = f"http://{pixoo_url_raw}" if not pixoo_url_raw.startswith('http') else pixoo_url_raw
            self.pixoo_url: str = f"{pixoo_url}:80/post" if not pixoo_url.endswith(':80/post') else pixoo_url
        else:
            self.pixoo_url: Optional[str] = None # Explicitly None if not provided

        if self.ai_fallback not in ["flux", "turbo"]:
            self.ai_fallback = "turbo" # Default if invalid

    def _validate_config(self):
        """Validates configuration parameters and logs warnings/errors if needed."""
        _LOGGER.info("Validating configuration...")
        if not self.pixoo_url:
            _LOGGER.error(
                "Pixoo IP address/hostname ('pixoo: url') is MISSING."
                " This is required for the script to function.")
            return

        # --- Home Assistant Section ---
        if not self.ha_url: # Default is 'http://homeassistant.local:8123'
            _LOGGER.warning("Home Assistant URL ('home_assistant: ha_url') is not configured. Using default: %s. Please verify if this is correct.", self.SECTION_DEFAULTS['home_assistant']['ha_url'])
        if not self.media_player: # Default is 'media_player.living_room'
            _LOGGER.warning("Media player entity ID ('home_assistant: media_player') is not configured. Using default: %s. Please verify if this is correct.", self.SECTION_DEFAULTS['home_assistant']['media_player'])

        # --- Conditionally Required (API Keys for Fallbacks/Features) ---
        if self.spotify_slide:
            if not self.spotify_client_id or not self.spotify_client_secret:
                _LOGGER.error("Spotify Slide is enabled ('pixoo: spotify_slide: True'), but 'spotify_client_id' or 'spotify_client_secret' is MISSING in 'home_assistant' section. Spotify Slide will not work.")
        elif self.spotify_client_id and not self.spotify_client_secret:
            _LOGGER.warning("'spotify_client_id' is provided but 'spotify_client_secret' is MISSING. Spotify fallback/features may not work completely.")
        elif not self.spotify_client_id and self.spotify_client_secret:
            _LOGGER.warning("'spotify_client_secret' is provided but 'spotify_client_id' is MISSING. Spotify fallback/features may not work completely.")

        if self.tidal_client_id and not self.tidal_client_secret:
            _LOGGER.warning("TIDAL Client ID ('tidal_client_id') is provided, but 'tidal_client_secret' is MISSING. TIDAL fallback will not work.")
        elif not self.tidal_client_id and self.tidal_client_secret:
            _LOGGER.warning("TIDAL Client Secret ('tidal_client_secret') is provided, but 'tidal_client_id' is MISSING. TIDAL fallback will not work.")

        # --- WLED ---
        if getattr(self, 'wled', None):
            pass
        elif (self.brightness != self.SECTION_DEFAULTS['wled']['brightness'] or
            self.effect != self.SECTION_DEFAULTS['wled']['effect'] or
            self.effect_speed != self.SECTION_DEFAULTS['wled']['effect_speed']):
            _LOGGER.warning("WLED parameters (brightness, effect, etc.) are configured, but 'wled_ip' is MISSING in 'wled' section. WLED features will not work.")

        # Post-processing for force_font_color
        if hasattr(self, 'force_font_color'):
            current_color_val = self.force_font_color

            if current_color_val is False:
                self.force_font_color = None
            elif isinstance(current_color_val, str):
                # Validate it's 6 chars and all are hex digits
                if len(current_color_val) == 6:
                    is_valid_6_char_hex = True
                    for char_code in current_color_val:
                        if char_code.lower() not in "0123456789abcdef":
                            is_valid_6_char_hex = False
                            break
                    
                    if is_valid_6_char_hex:
                        self.force_font_color = "#" + current_color_val
                    else:
                        self.force_font_color = None
                
                elif not current_color_val.startswith('#'):
                    self.force_font_color = None

        if not (0 <= self.brightness <= 255):
            _LOGGER.warning(f"Invalid WLED brightness value: {self.brightness}. Value should be between 0 and 255. Defaulting to 255.")
            self.brightness = 255
        if not (0 <= self.effect <= 186):
            _LOGGER.warning(f"Invalid WLED effect value: {self.effect}. Value should be between 0 and 186. Defaulting to 38.")
            self.effect = 38
        # ... (other existing range checks for WLED params like effect_speed, intensity, palette, sound_effect)
        if not (0 <= self.effect_speed <= 255):
            _LOGGER.warning(f"Invalid WLED effect speed value: {self.effect_speed}. Value should be between 0 and 255. Defaulting to 60.")
            self.effect_speed = 60
        if not (0 <= self.effect_intensity <= 255):
            _LOGGER.warning(f"Invalid WLED effect intensity value: {self.effect_intensity}. Value should be between 0 and 255. Defaulting to 128.")
            self.effect_intensity = 128
        if not (0 <= self.palette <= 70):
            _LOGGER.warning(f"Invalid WLED palette value: {self.palette}. Value should be between 0 and 70. Defaulting to 0.")
            self.palette = 0
        if not (0 <= self.sound_effect <= 3): # sound_effect was clamped in init, this is a check
            _LOGGER.warning(f"Invalid WLED sound effect value: {self.sound_effect}. Value should be between 0 and 3. Defaulting to 0.")
            # self.sound_effect = 0 # Already done in __init__ if invalid

        if self.clock_align not in ["Left", "Right"]:
            _LOGGER.warning(f"Invalid clock alignment value: {self.clock_align}. Defaulting to 'Right'.")
            self.clock_align = "Right"

        if self.ai_fallback not in ["flux", "turbo"]: # ai_fallback is defaulted in _fix_config_args if invalid
            _LOGGER.warning(f"Invalid AI fallback model: {self.ai_fallback}. Defaulting to 'turbo'.")
            # self.ai_fallback = "turbo" # Already done

        if self.lyrics_font not in [2, 4, 32, 52, 58, 62, 48, 80, 158, 186, 190, 590]:
            _LOGGER.warning(f"Lyrics font ID: {self.lyrics_font} might not be optimal. Recommended values: 2, 4, 32, 52, 58, 62, 48, 80, 158, 186, 190, 590. Check Divoom documentation for more.")

        _LOGGER.info("Configuration validation complete.")

class PixooDevice:
    """Handles communication with the Divoom Pixoo device.""" 

    def __init__(self, config: "Config"): 
        """Initialize PixooDevice object."""
        self.config = config
        self.select_index: Optional[int] = None 
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Connection": "keep-alive",
            "User-Agent": "PixooClient/1.0"
        }


    async def send_command(self, payload_command: dict) -> None: 
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.pixoo_url,
                    headers=self.headers,
                    json=payload_command,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        response_text = await response.text() 
                        _LOGGER.error(f"Failed to send command to Pixoo. Status: {response.status}, Response: {response_text}") 
                    else:
                        await asyncio.sleep(0.25) # Consider making this sleep configurable
        except aiohttp.ClientError as e: 
            _LOGGER.error(f"Error sending command to Pixoo: {e}") 
        except asyncio.TimeoutError: # Catch specific timeout error
            _LOGGER.error(f"Timeout sending command to Pixoo after 10 seconds.") 
        except Exception as e: # Catch any other unexpected exceptions
            _LOGGER.exception(f"Unexpected error sending command to Pixoo: {e}") 


    async def get_current_channel_index(self) -> int: 
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
                    response.raise_for_status() 
                    response_text = await response.text()
                    response_data = json.loads(response_text)
                    print(response_data)
                    return response_data.get('SelectIndex', 1)
        except aiohttp.ClientError as e: 
            _LOGGER.error(f"Failed to get channel index from Pixoo: {e}") 
        except json.JSONDecodeError as e: 
            _LOGGER.error(f"Failed to decode JSON response when getting channel index: {e}") 
        except asyncio.TimeoutError: 
            _LOGGER.error(f"Timeout getting channel index from Pixoo after 5 seconds.") 
        except Exception as e: 
            _LOGGER.exception(f"Unexpected error getting channel index from Pixoo: {e}") 
        return 1  # Default fallback value if any error occurs


class ImageProcessor:
    """Processes images for display on the Pixoo64 device, including caching and filtering.""" 
    def __init__(self, config: "Config"): 
        """Initialize ImageProcessor object."""
        self.config = config
        self.image_cache: OrderedDict[str, dict] = OrderedDict() 
        self.cache_size: int = config.images_cache 
        self.lyrics_font_color: str = "#FF00AA" 
        

    @property
    def _cache_size(self) -> int: 
        """Helper property to get current cache size."""
        return len(self.image_cache)

    def _calculate_item_size(self, item: dict) -> int: 
        """Calculates the approximate memory size of a single cache item."""
        size = 0

        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, str):
                    size += sys.getsizeof(value)
                elif isinstance(value, (int, float, bool)):
                    size += sys.getsizeof(value)
                elif isinstance(value, tuple):
                    size += sys.getsizeof(value)
                elif isinstance(value, list):
                    for list_item in value:
                        size += sys.getsizeof(list_item)
        return size

    def _calculate_cache_memory_size(self) -> float:
        """Calculates the total approximate memory size of the cache in bytes."""
        total_size = 0
        for item in self.image_cache.values():
            total_size += self._calculate_item_size(item)
        return total_size

    async def get_image(self, picture: Optional[str], media_data: "MediaData", spotify_slide: bool = False) -> Optional[dict]: 
        if not picture:
            return None

        cache_key = f"{media_data.artist} - {media_data.album}"
        use_cache = media_data.album is not None

        if not use_cache: # If the album name is None, do not use the cache.
            try:
                async with aiohttp.ClientSession() as session:
                    #url = picture if picture.startswith('http') else f"{self.config.ha_url}{picture}"
                    if picture is not None and picture.startswith('http'):
                        url = picture
                    else:
                        url = f"{self.config.ha_url}{picture}"
                    try: 
                        async with session.get(url, timeout=10) as response: 
                            response.raise_for_status() 
                            image_data = await response.read()
                            processed_data = await self.process_image_data(image_data, media_data)  # Process image *before* caching
                            return processed_data
                    except aiohttp.ClientError as e: 
                        _LOGGER.error(f"Error fetching image from URL {url}: {e}") 
                        return None
            except Exception as e: 
                _LOGGER.exception(f"Unexpected error in get_image when album is None: {e}") 
                return None

        # Check cache; if found, return directly with all data.
        if use_cache and cache_key in self.image_cache and not spotify_slide and not media_data.playing_tv and not self.config.burned:
            _LOGGER.debug(f"Image found in cache for album: {cache_key}") 
            cached_item = self.image_cache.pop(cache_key)
            self.image_cache[cache_key] = cached_item
            return cached_item

        try:
            async with aiohttp.ClientSession() as session:
                url = picture if picture.startswith('http') else f"{self.config.ha_url}{picture}"
                try: 
                    async with session.get(url, timeout=30) as response: 
                        response.raise_for_status() 
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
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"Error fetching image from URL {url}: {e}") 
                    return None
        except Exception as e: 
            _LOGGER.exception(f"Unexpected error in get_image when album is cached: {e}") 
            return None

    async def process_image_data(self, image_data: bytes, media_data: "MediaData") -> Optional[dict]: 
        """Processes raw image data using thread pool for non-blocking operation."""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            try: 
                result = await loop.run_in_executor(
                    executor,
                    self._process_image,
                    image_data,
                    media_data
                )
                return result
            except Exception as e: 
                _LOGGER.exception(f"Error during thread pool image processing: {e}") 
                return None

    def _process_image(self, image_data: bytes, media_data: "MediaData") -> Optional[dict]: 
        """Processes image data (non-async part, runs in thread pool)."""
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
            _LOGGER.error(f"Error processing image: {e}") 
            return None

    def fixed_size(self, img: Image.Image) -> Image.Image: 
        """Ensure the image is square."""
        width, height = img.size
        if width == height:
            return img
        elif height < width:
            # Calculate the border size
            border_size = (width - height) // 2
            try:
                background_color = img.getpixel((0, 0)) 
            except Exception: 
                background_color = (0, 0, 0) # Default black if pixel access fails
                _LOGGER.warning("Could not get pixel from image for background color, using black as default.") 
            new_img = Image.new("RGB", (width, width), background_color)  # Create a square image
            new_img.paste(img, (0, border_size))  # Paste the original image onto the new image
            img = new_img  # Update img to the new image
        elif width != height:
            new_size = min(width, height)
            left = (width - new_size) // 2
            top = (height - new_size) // 2
            img = img.crop((left, top, left + new_size, top + new_size))
        return img

    def filter_image(self, img: Image.Image) -> Image.Image: 
        """Apply configured image filters to the image."""
        img = img.resize((64, 64), Image.Resampling.LANCZOS)

        # sharpened_image = img.filter(ImageFilter.UnsharpMask(radius=4, percent=200, threshold=3))
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
        """Apply special mode image processing."""
        if img is None:
            _LOGGER.error("Error: Provided image is None in special_mode.") 
            return None

        output_size = (64, 64)
        album_size = (34, 34) if self.config.show_text else (56, 56)
        album_art = img.resize(album_size, Image.Resampling.LANCZOS)

        # Get the colors for the gradient
        try: 
            left_color = album_art.getpixel((0, album_size[1] // 2))
            right_color = album_art.getpixel((album_size[0] - 1, album_size[1] // 2))
        except Exception as e: 
            _LOGGER.warning(f"Could not get pixel from album_art for gradient colors, using default. Error: {e}") # Log warning
            left_color = (100, 100, 100) # Default grey color
            right_color = (150, 150, 150) # Default light grey color

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

    def gbase64(self, img: Image.Image) -> Optional[str]: 
        """Convert PIL Image to base64 encoded string."""
        try:
            pixels = [item for p in list(img.getdata()) for item in p] 
            b64 = base64.b64encode(bytearray(pixels))
            gif_base64 = b64.decode("utf-8")
            return gif_base64
        except Exception as e: 
            _LOGGER.error(f"Error converting image to base64: {e}") 
            return None

    def text_clock_img(self, img: Image.Image, brightness_lower_part: float, media_data: "MediaData") -> Image.Image: 
        """Add text and clock elements to the image."""
        if media_data.playing_tv or self.config.special_mode or self.config.spotify_slide:
            return img

        # Check if there are no lyrics before proceeding
        if media_data.lyrics and self.config.show_lyrics and self.config.text_bg and brightness_lower_part != None and not media_data.playing_radio:
            enhancer_lp = ImageEnhance.Brightness(img)
            img = enhancer_lp.enhance(0.55)  
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(0.5)
            return img

        if bool(self.config.show_clock and self.config.text_bg) and not self.config.show_lyrics:
            lpc = (43, 2, 62, 9) if self.config.clock_align == "Right" else (2, 2, 21, 9)
            lower_part_img = img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(0.3)
            img.paste(lower_part_img, lpc)

        if bool(self.config.temperature and self.config.text_bg) and not self.config.show_lyrics:
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

    def img_values(self, img: Image.Image) -> tuple[str, float, float, str, tuple[int, int, int], tuple[int, int, int], str, str, str, str]: 
        """Extract color values and brightness from the image."""
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

        if self.config.wled:
            color1, color2, color3 = self.most_vibrant_colors_wled(small_temp_img)
        else:
            color1 = color2 = color3 = '%02x%02x%02x' % most_common_color_alternative_rgb

        return (
            font_color,
            brightness,
            brightness_lower_part,
            background_color,
            background_color_rgb,
            recommended_font_color_rgb,
            most_common_color_alternative,
            color1, color2, color3
        )

    def most_vibrant_color(self, most_common_colors: list[tuple[tuple[int, int, int], int]]) -> tuple[int, int, int]: 
        """Finds the most vibrant color from a list of colors."""
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
        """Return #RRGGBB"""
        return '#{:02x}{:02x}{:02x}'.format(*rgb)


    def is_strong_color(self, color: tuple[int, int, int]) -> bool: 
        """Check if at least one RGB component is greater than 220."""
        return any(c > 220 for c in color)

    def color_distance(self, color1: tuple[int, int, int], color2: tuple[int, int, int]) -> float: 
        """Calculate the Euclidean distance between two colors."""
        return math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color1, color2)))

    def is_vibrant_color(self, r: int, g: int, b: int) -> bool: 
        """Simplified vibrancy check, looking for a significant difference between components."""
        return (max(r, g, b) - min(r, g, b) > 50)

    def generate_close_but_different_color(self, existing_colors: list[tuple[tuple[int, int, int], int]]) -> tuple[int, int, int]: 
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

    def color_score(self, color_count: tuple[tuple[int, int, int], int]) -> float: 
        """Calculate a score for a color based on frequency and saturation."""
        color, count = color_count
        max_val = max(color)
        min_val = min(color)
        saturation = (max_val - min_val) / max_val if max_val > 0 else 0
        return count * saturation

    def most_vibrant_colors_wled(self, full_img: Image.Image) -> tuple[str, str, str]: 
        """Extract the three most dominant vibrant colors for WLED, ensuring diverse hues and strong colors."""
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

    def get_optimal_font_color(self, img: Image.Image) -> str: 
        """Determine a colorful, readable font color."""

        if self.config.force_font_color:
            return self.config.force_font_color
        
        # Resize for faster processing
        small_img = img.resize((16, 16), Image.Resampling.LANCZOS)

        # Get all unique colors in the image (palette)
        image_palette = set(small_img.getdata())

        # Calculate luminance to analyze image brightness
        def luminance(color: tuple[int, int, int]) -> float: 
            r, g, b = color
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        # Calculate average brightness of the image palette
        avg_brightness = sum(luminance(color) for color in image_palette) / len(image_palette)

        # Define the contrast ratio calculation
        def contrast_ratio(color1: tuple[int, int, int], color2: tuple[int, int, int]) -> float: 
            L1 = luminance(color1) + 0.05
            L2 = luminance(color2) + 0.05
            return max(L1, L2) / min(L1, L2)

        # Check if the color is sufficiently distinct from all colors in the image
        def is_distinct_color(color: tuple[int, int, int], threshold: int = 110) -> bool: 
            return all(self.color_distance(color, img_color) > threshold for img_color in image_palette) # Using self.color_distance

        # Define a set of colorful candidate colors (modified for brightness)
        candidate_colors = COLOR_PALETTE
        random.shuffle(candidate_colors)
        best_color = None
        max_saturation = -1 

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

    def get_dominant_border_color(self, img: Image.Image) -> tuple[int, int, int]:
        """Get the dominant color from the image borders using collections.Counter."""
        width, height = img.size
        if width == 0 or height == 0:
            _LOGGER.debug("get_dominant_border_color: Empty image provided.")
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

        if width > 0 and end_y_for_cols > start_y_for_cols : # only if there's a vertical strip to read
            left_col_img = img_rgb.crop((0, start_y_for_cols, 1, end_y_for_cols))
            all_border_pixels.extend(list(left_col_img.getdata()))

        if width > 1 and end_y_for_cols > start_y_for_cols:
            right_col_img = img_rgb.crop((width - 1, start_y_for_cols, width, end_y_for_cols))
            all_border_pixels.extend(list(right_col_img.getdata()))
        
        if not all_border_pixels:
            # This can happen for 1x1 images or if logic somehow fails for tiny images
            if width > 0 and height > 0:
                try:
                    return img_rgb.getpixel((0, 0)) # Fallback to top-left pixel
                except IndexError: # Should not happen if width/height > 0
                    _LOGGER.warning("get_dominant_border_color: Could not getpixel for fallback on small image.")
                    return (0, 0, 0)
            _LOGGER.debug("get_dominant_border_color: No border pixels collected.")
            return (0, 0, 0)

        counts = Counter(all_border_pixels)
        return counts.most_common(1)[0][0]

    def _find_content_bounding_box(self,
                                image_to_scan: Image.Image, # Assumed to be RGB
                                border_color_to_detect: tuple[int, int, int],
                                threshold: float
                                ) -> Optional[Tuple[int, int, int, int]]:
        """
        Finds the bounding box of content by identifying pixels different from the border_color.
        Returns (min_x, min_y, max_x, max_y) or None if no content.
        Assumes image_to_scan is already in RGB mode.
        """
        width, height = image_to_scan.size
        if width == 0 or height == 0:
            _LOGGER.debug("_find_content_bounding_box: Empty image provided.")
            return None
        try:
            pix = image_to_scan.load()
        except Exception as e:
            _LOGGER.error(f"_find_content_bounding_box: Could not load pixels: {e}")
            return None

        min_x, min_y = width, height
        max_x, max_y = -1, -1
        content_found = False

        # Pre-calculate for minor optimization if your Python version benefits
        # border_r, border_g, border_b = border_color_to_detect

        for y_coord in range(height):
            for x_coord in range(width):
                try:
                    pixel_data = pix[x_coord, y_coord]
                    r, g, b = pixel_data[0], pixel_data[1], pixel_data[2]

                except (IndexError, TypeError) as e: # TypeError if pixel_data is an int (e.g. paletted)
                    # This shouldn't happen if image_to_scan is properly converted to RGB beforehand
                    _LOGGER.warning(f"_find_content_bounding_box: Pixel at ({x_coord},{y_coord}) not RGB. Mode: {image_to_scan.mode}. Pixel: {pixel_data}. Error: {e}")
                    continue

                # Using math.hypot is fine and clear
                if math.hypot(r - border_color_to_detect[0],
                            g - border_color_to_detect[1],
                            b - border_color_to_detect[2]) > threshold:
                    min_x = min(min_x, x_coord)
                    max_x = max(max_x, x_coord)
                    min_y = min(min_y, y_coord)
                    max_y = max(max_y, y_coord)
                    content_found = True

        if not content_found:
            _LOGGER.debug(f"_find_content_bounding_box: No content found distinct from border color {border_color_to_detect} with threshold {threshold}")
            return None

        return min_x, min_y, max_x, max_y

    def _balance_border(self, detect: Image.Image, orig: Image.Image,
                        left: int, top: int, size: int, # left, top, size define the content window found in 'detect'
                        border_color: tuple, thresh: float) -> Image.Image:
        """
        Splits any one-sided border equally between top and bottom by shifting the crop window.
        The crop is applied to 'orig'. 'detect' (assumed RGB) is used for border analysis.
        'size' is the target dimension of the square crop.
        """
        orig_width, orig_height = orig.size
        detect_width, detect_height = detect.size # detect image dimensions


        eff_detect_left = max(0, left)
        eff_detect_top = max(0, top)

        eff_detect_right = min(left + size, detect_width)
        eff_detect_bottom = min(top + size, detect_height)

        if eff_detect_right <= eff_detect_left or eff_detect_bottom <= eff_detect_top:
            _LOGGER.warning(f"Invalid crop window for _balance_border on 'detect' image: ({eff_detect_left}, {eff_detect_top}, {eff_detect_right}, {eff_detect_bottom}). Cropping 'orig' with unshifted values.")
            final_left_orig = max(0, min(left, orig_width - size))
            final_top_orig = max(0, min(top, orig_height - size))
            actual_crop_dim_orig = min(size, orig_width - final_left_orig, orig_height - final_top_orig)
            if actual_crop_dim_orig < 1: return orig # Return full original if crop is invalid
            return orig.crop((final_left_orig, final_top_orig, final_left_orig + actual_crop_dim_orig, final_top_orig + actual_crop_dim_orig))

        cropped_detect_window = detect.crop((eff_detect_left, eff_detect_top, eff_detect_right, eff_detect_bottom))
        
        local_size_w = cropped_detect_window.width
        local_size_h = cropped_detect_window.height

        if local_size_w == 0 or local_size_h == 0:
            _LOGGER.warning("Cropped detect window for _balance_border is empty. Cropping 'orig' with unshifted values.")
            final_left_orig = max(0, min(left, orig_width - size))
            final_top_orig = max(0, min(top, orig_height - size))
            actual_crop_dim_orig = min(size, orig_width - final_left_orig, orig_height - final_top_orig)
            if actual_crop_dim_orig < 1: return orig
            return orig.crop((final_left_orig, final_top_orig, final_left_orig + actual_crop_dim_orig, final_top_orig + actual_crop_dim_orig))

        try:
            pix_detect = cropped_detect_window.load()
        except Exception as e:
            _LOGGER.error(f"_balance_border: Could not load pixels from cropped_detect_window: {e}")
            # Fallback as above
            final_left_orig = max(0, min(left, orig_width - size))
            final_top_orig = max(0, min(top, orig_height - size))
            actual_crop_dim_orig = min(size, orig_width - final_left_orig, orig_height - final_top_orig)
            if actual_crop_dim_orig < 1: return orig
            return orig.crop((final_left_orig, final_top_orig, final_left_orig + actual_crop_dim_orig, final_top_orig + actual_crop_dim_orig))


        top_border_rows = 0
        for y in range(local_size_h):
            is_border_row = True
            for x in range(local_size_w):
                r, g, b = pix_detect[x,y][:3] # Safe slice if alpha might be present
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

        new_top_orig = top # This 'top' is the original top of the content box in 'orig'

        if top_border_rows > 0 and bottom_border_rows == 0:
            shift = top_border_rows // 2
            new_top_orig = top + shift # Shift crop window down
        elif bottom_border_rows > 0 and top_border_rows == 0:
            shift = bottom_border_rows // 2
            new_top_orig = top - shift # Shift crop window up
        
        # Ensure final crop is within bounds of 'orig'
        final_left = max(0, min(left, orig_width - target_crop_dim))
        final_top = max(0, min(new_top_orig, orig_height - target_crop_dim)) # Use potentially shifted new_top
        
        actual_final_w = min(target_crop_dim, orig_width - final_left)
        actual_final_h = min(target_crop_dim, orig_height - final_top)
        actual_final_dim = min(actual_final_w, actual_final_h) # Keep it square

        if actual_final_dim < 1:
            _LOGGER.warning(f"Calculated final crop dimension in _balance_border is invalid ({actual_final_dim}). Returning original image.")
            return orig

        return orig.crop((final_left, final_top, final_left + actual_final_dim, final_top + actual_final_dim))

    def _perform_border_crop(self, img_to_crop: Image.Image) -> Optional[Image.Image]:
        _LOGGER.debug("Performing standard border crop.")

        detect_img = img_to_crop.convert("RGB") if img_to_crop.mode != "RGB" else img_to_crop.copy()

        border_color = self.get_dominant_border_color(detect_img) # Uses the RGB 'detect_img'
        threshold = 20

        bbox = self._find_content_bounding_box(detect_img, border_color, threshold) # Uses RGB 'detect_img'

        if bbox is None:
            _LOGGER.debug("Border crop: No content found.")
            return None # No content found, or image was entirely border

        min_x, min_y, max_x, max_y = bbox
        content_w = max_x - min_x + 1
        content_h = max_y - min_y + 1

        # Determine crop size (at least 64x64, or content size, whichever is larger, but square)
        crop_dim = max(64, max(content_w, content_h))

        # Center the crop on the content
        center_x = min_x + content_w // 2
        center_y = min_y + content_h // 2
        half_crop_dim = crop_dim // 2

        # Calculate top-left corner of the crop (these are for 'detect_img' and 'img_to_crop')
        left = max(0, center_x - half_crop_dim)
        top = max(0, center_y - half_crop_dim)

        # Ensure the crop does not go out of bounds (right/bottom)
        img_width, img_height = detect_img.size
        if left + crop_dim > img_width:
            left = img_width - crop_dim
        if top + crop_dim > img_height:
            top = img_height - crop_dim
        
        left = max(0, left) # Ensure left/top are not negative
        top = max(0, top)

        actual_crop_size = min(crop_dim, img_width - left, img_height - top)
        if actual_crop_size < 1:
            _LOGGER.warning(f"Border crop: Calculated crop size is invalid ({actual_crop_size}). Bbox: {bbox}, img_size: {detect_img.size}")
            return img_to_crop # Return original if crop is invalid

        return self._balance_border(detect_img, img_to_crop, left, top, actual_crop_size, border_color, threshold)

    def _perform_object_focus_crop(self, img_to_crop: Image.Image) -> Optional[Image.Image]:
        _LOGGER.debug("Performing object focus crop.")
        
        base_for_detect = img_to_crop.convert("RGB") if img_to_crop.mode != "RGB" else img_to_crop.copy()

        # Process this base image for better object detection
        detect_img_processed = base_for_detect.filter(ImageFilter.BoxBlur(5))
        detect_img_processed = ImageEnhance.Brightness(detect_img_processed).enhance(1.95)
        threshold_find_bbox_obj = 50

        border_color_for_detect = self.get_dominant_border_color(detect_img_processed) # Use processed image
        bbox = self._find_content_bounding_box(detect_img_processed, border_color_for_detect, threshold_find_bbox_obj) # Use processed image

        if bbox is None:
            _LOGGER.debug("Object focus: No salient content found with threshold %s.", threshold_find_bbox_obj)
            return None # Fallback will be handled by caller

        min_x_orig_bbox, min_y_orig_bbox, max_x_orig_bbox, max_y_orig_bbox = bbox
        expansion_pixels = -10 # Shrink the bounding box slightly
        
        # Apply expansion to the bbox coordinates, relative to detect_img_processed
        min_x = max(0, min_x_orig_bbox - expansion_pixels)
        min_y = max(0, min_y_orig_bbox - expansion_pixels)
        max_x = min(detect_img_processed.width - 1, max_x_orig_bbox + expansion_pixels)
        max_y = min(detect_img_processed.height - 1, max_y_orig_bbox + expansion_pixels)

        content_w = max_x - min_x + 1
        content_h = max_y - min_y + 1

        if content_w <= 0 or content_h <= 0:
            _LOGGER.warning(f"Object focus: BBox invalid after expansion. Original: {bbox}, Expanded: {(min_x,min_y,max_x,max_y)}")
            return img_to_crop # Return original if logic leads to invalid box

        # Target square crop dimension
        crop_dim = max(64, max(content_w, content_h))

        # Center the crop on the (potentially expanded/shrunk) content box
        center_x = min_x + content_w // 2
        center_y = min_y + content_h // 2
        half_crop_dim = crop_dim // 2

        # Top-left for the crop window, relative to detect_img_processed / img_to_crop
        left = max(0, center_x - half_crop_dim)
        top = max(0, center_y - half_crop_dim)

        img_width, img_height = base_for_detect.size # Use dimensions of the original RGB base
        if left + crop_dim > img_width: left = img_width - crop_dim
        if top + crop_dim > img_height: top = img_height - crop_dim
        left = max(0, left)
        top = max(0, top)
        
        # 'actual_crop_size' is the target square dimension for the final crop
        actual_crop_size = min(crop_dim, img_width - left, img_height - top)
        if actual_crop_size < 1:
            _LOGGER.warning(f"Object focus: Calculated crop size invalid ({actual_crop_size}).")
            return img_to_crop

        threshold_balance_obj = 60

        return self._balance_border(detect_img_processed, img_to_crop, left, top, actual_crop_size,
                                    border_color_for_detect, threshold_balance_obj)

    def crop_image_borders(self, img: Image.Image, radio_logo: bool) -> Image.Image:
        """Crop borders from the image. Dispatches to specific cropping methods."""
        # This check should use self.config
        if radio_logo or not self.config.crop_borders:
            return img

        cropped_image: Optional[Image.Image] = None

        if self.config.crop_extra or self.config.special_mode: 
            _LOGGER.debug("Attempting object focus crop (extra_crop or special_mode).")
            cropped_image = self._perform_object_focus_crop(img)
            if cropped_image is None: 
                _LOGGER.debug("Object focus crop failed or found no content, falling back to standard border crop.")
                cropped_image = self._perform_border_crop(img)
        else:
            _LOGGER.debug("Attempting standard border crop (crop_borders is true, but not extra_crop/special_mode).")
            cropped_image = self._perform_border_crop(img)

        if cropped_image is None: # If all attempts fail (e.g., _perform_border_crop also found no content)
            _LOGGER.debug("All cropping attempts failed or found no significant content, returning original image.")
            return img

        return cropped_image

    def _draw_text_with_outline(self, draw: ImageDraw.ImageDraw, xy: tuple, text: str, font: ImageFont.FreeTypeFont,
                                text_color: tuple, outline_color: tuple, outline_width: int = 1):
        """Draws text with an outline."""
        x, y = xy
        # Outline
        for i in range(-outline_width, outline_width + 1):
            for j in range(-outline_width, outline_width + 1):
                if i == 0 and j == 0:
                    continue  # Skip the center for the outline pass
                draw.text((x + i, y + j), text, font=font, fill=outline_color)
        # Main text
        draw.text((x, y), text, font=font, fill=text_color)

    def _draw_text_with_shadow(self,
                            draw: ImageDraw.ImageDraw,
                            xy: tuple,
                            text: str,
                            font: ImageFont.FreeTypeFont,
                            text_color: tuple,
                            shadow_color: tuple):
        """Draws text with a shadow."""
        x, y = xy
        
        # Draw shadow
        draw.text((x + 1, y + 1), text, font=font, fill=shadow_color)
        draw.text((x, y + 1), text, font=font, fill=shadow_color)
        if shadow_color == (255, 255, 255, 128):
            draw.text((x + 1, y - 1), text, font=font, fill=shadow_color)
            draw.text((x - 1, y), text, font=font, fill=shadow_color)
        # Draw main text on top
        draw.text((x, y), text, font=font, fill=text_color)

    def _get_text_dimensions(self, text: str, font: ImageFont.FreeTypeFont, draw: Optional[ImageDraw.ImageDraw] = None) -> tuple[int, int]:
        """
        Helper to get text width and height, preferring draw.textbbox if available,
        then font.getbbox, then falling back to draw.textsize.
        Returns (width, height).
        """
        try:
            if draw: # draw.textbbox is generally preferred for accuracy with PIL 9.2.0+
                bbox = draw.textbbox((0, 0), text, font=font)
                return bbox[2] - bbox[0], bbox[3] - bbox[1]
            else: # If draw object isn't passed, use font.getbbox
                bbox = font.getbbox(text)
                return bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError: # Fallback for older Pillow versions or if methods are missing
            _LOGGER.debug(f"Falling back to draw.textsize for font metrics for text: '{text[:20]}...'")
            if draw:
                try:
                    # This is the one that will likely fail on Pillow 10+ if getbbox also failed (which is unlikely)
                    return draw.textsize(text, font=font)
                except AttributeError: # If draw.textsize is also gone
                    _LOGGER.warning("draw.textsize also missing. Text dimensioning will be inaccurate.")
                    # As a last resort, estimate based on number of chars and font size
                    # This is very rough.
                    return len(text) * (font.size // 2 if hasattr(font, 'size') else 5), (font.size if hasattr(font, 'size') else 10)

            else: # No draw object and getbbox failed
                _LOGGER.warning("font.getbbox failed and no draw object for textsize. Text dimensioning will be inaccurate.")
                return len(text) * (font.size // 2 if hasattr(font, 'size') else 5), (font.size if hasattr(font, 'size') else 10)
        except Exception as e:
            _LOGGER.error(f"Unexpected error getting text dimensions for '{text[:20]}...': {e}")
            return 0,0

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
        if not text:
            return []
        _LOGGER.debug(f"WrapText: Input='{text}', MaxWidthPx={max_width}, Font='{font.path if hasattr(font, 'path') else 'Default'}' size {font.size if hasattr(font,'size') else 'N/A'}")

        avg_char_width_fallback = 5
        avg_char_width = avg_char_width_fallback
        try:
            char_width_sample, _ = self._get_text_dimensions("x", font, draw)
            if char_width_sample > 0:
                avg_char_width = char_width_sample
        except Exception as e:
            _LOGGER.warning(f"WrapText: Error getting 'x' width for avg_char_width: {e}. Using fallback {avg_char_width_fallback}.")
        
        # Ensure wrap_width for textwrap is at least 1, based on estimated chars
        wrap_width_chars = max(1, max_width // avg_char_width if avg_char_width > 0 else 10)
        _LOGGER.debug(f"WrapText: avg_char_width={avg_char_width}, est. wrap_width_chars={wrap_width_chars}")

        raw_lines = text.splitlines()
        processed_lines = []

        for raw_line_idx, raw_line in enumerate(raw_lines):
            _LOGGER.debug(f"WrapText: Processing raw_line {raw_line_idx+1}/{len(raw_lines)}: '{raw_line}'")
            if not raw_line.strip():
                _LOGGER.debug("WrapText: Skipping empty raw_line.")
                continue

            current_line_width_px, _ = self._get_text_dimensions(raw_line, font, draw)

            if current_line_width_px <= max_width:
                processed_lines.append(raw_line)
                _LOGGER.debug(f"WrapText: Raw_line '{raw_line}' fits as is ({current_line_width_px}px).")
                continue
            
            _LOGGER.debug(f"WrapText: Raw_line '{raw_line}' too wide ({current_line_width_px}px). Attempting wrap.")
            # Attempt with textwrap first
            attempt_textwrap = True 
            if attempt_textwrap and max_width > avg_char_width * 3: # Only if reasonable space
                try:
                    wrapped_sub_lines = textwrap.wrap(raw_line, width=wrap_width_chars, break_long_words=True, replace_whitespace=False, drop_whitespace=False)
                    _LOGGER.debug(f"WrapText: Textwrap (char_width={wrap_width_chars}) for '{raw_line}' -> {wrapped_sub_lines}")
                    
                    temp_textwrap_lines = []
                    textwrap_failed_to_fit = False
                    for sub_line in wrapped_sub_lines:
                        if not sub_line.strip(): continue
                        sub_line_pixel_width, _ = self._get_text_dimensions(sub_line, font, draw)
                        if sub_line_pixel_width <= max_width:
                            temp_textwrap_lines.append(sub_line)
                        else:
                            _LOGGER.debug(f"WrapText: Textwrap sub_line '{sub_line}' still too wide ({sub_line_pixel_width}px). Textwrap strategy failed for this raw_line.")
                            textwrap_failed_to_fit = True
                            break 
                    
                    if not textwrap_failed_to_fit:
                        processed_lines.extend(temp_textwrap_lines)
                        _LOGGER.debug(f"WrapText: Textwrap successful for raw_line '{raw_line}'. Result: {temp_textwrap_lines}")
                        continue # Move to next raw_line
                except Exception as e:
                    _LOGGER.warning(f"WrapText: textwrap.wrap failed for '{raw_line}': {e}. Falling to manual.")
            
            # Fallback to Manual Word/Character Wrapping Logic for the current raw_line
            _LOGGER.debug(f"WrapText: Using manual word/char wrap for raw_line: '{raw_line}'")
            words = raw_line.split(' ')
            current_manual_line = ""
            for word_idx, word in enumerate(words):
                if not word: continue

                word_pixel_width, _ = self._get_text_dimensions(word, font, draw)

                if word_pixel_width > max_width:
                    _LOGGER.debug(f"WrapText: Word '{word}' too wide ({word_pixel_width}px). Char wrapping.")
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
        _LOGGER.debug(f"WrapText: Final Output for original '{text}': {final_cleaned_lines}")
        return final_cleaned_lines

    def _char_wrap_long_word(self, word: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
        _LOGGER.debug(f"CharWrap: Word='{word}', MaxWidthPx={max_width}")
        lines = []
        if not word: return lines
        
        current_char_line = ""
        for char_idx, char in enumerate(word):
            test_char_line = current_char_line + char
            char_line_w, _ = self._get_text_dimensions(test_char_line, font, draw)

            if char_line_w <= max_width:
                current_char_line = test_char_line
            else:
                # Current char makes it too long. Add previous line (if any)
                if current_char_line: # This implies current_char_line (without current char) was fitting
                    lines.append(current_char_line)
                
                # Start new line with the current char
                current_char_line = char
                # Check if the single char itself is too wide
                single_char_w, _ = self._get_text_dimensions(char, font, draw)
                if single_char_w > max_width:
                    _LOGGER.warning(f"CharWrap: Single char '{char}' ({single_char_w}px) wider than max_width {max_width}. Will overflow.")
                    # Add it anyway, it will overflow, then reset current_char_line to prevent it from being added again
                    lines.append(char)
                    current_char_line = "" 

        if current_char_line: # Add any remaining part
            lines.append(current_char_line)
        _LOGGER.debug(f"CharWrap: Result for '{word}': {lines}")
        return lines

    def _contrast_ratio(self,
                        c1: tuple[int, int, int],
                        c2: tuple[int, int, int]) -> float:
        """WCAG contrast ratio between two sRGB colours."""
        def _luminance(c: tuple[int, int, int]) -> float:
            r, g, b = [v / 255 for v in c]
            r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
            g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
            b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        l1, l2 = _luminance(c1) + 0.05, _luminance(c2) + 0.05
        return max(l1, l2) / min(l1, l2)

    def _pick_two_contrasting_colors(self,
                                    img: Image.Image,
                                    min_ratio: float = 4.5
                                    ) -> tuple[tuple[int, int, int],
                                                tuple[int, int, int]]:
        """
        Return two vivid colours that both reach *min_ratio* contrast against
        the average background and are visually distinct from each other.
        """
        # 1) average-colour background
        thumb = img.resize((16, 16), Image.Resampling.LANCZOS)
        pixels = list(thumb.getdata())
        bg = tuple(sum(ch) // len(pixels) for ch in zip(*pixels))  # (r,g,b)

        # 2) palette to try
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

        # 3) fall-backs
        if first is None:                       # nothing passed → choose best bw
            first = (255, 255, 255) if \
                self._contrast_ratio((255, 255, 255), bg) >= \
                self._contrast_ratio((0, 0, 0), bg) else (0, 0, 0)
        if second is None:
            alt = (0, 0, 0) if first == (255, 255, 255) else (255, 255, 255)
            second = alt if self._contrast_ratio(alt, bg) >= min_ratio else first

        return first, second


    def _draw_burned_text(self,
                        img: Image.Image,
                        artist: str,
                        title: str) -> Image.Image:
        """Draw artist & title in 'burned' mode with a dynamic, contrast-aware shadow"""
        if not (artist or title):
            return img


        # ── 1. TEXT FILL COLOR SELECTION ───────────────────────────────────
        artist_rgb_text, title_rgb_text = self._pick_two_contrasting_colors(img, 4.5)
        # Add alpha for drawing
        artist_fill  = (*artist_rgb_text, 255)
        title_fill   = (*title_rgb_text, 255)

        # ── 2. DYNAMIC SHADOW COLOR SELECTION ────────────────────────────────
        def _calculate_perceptual_luminance(rgb_color: tuple[int, int, int]) -> float:
            r, g, b = rgb_color
            return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

        # A. Determine initial shadow base (black/white) based on image background brightness
        thumb_for_bg_analysis = img.resize((8, 8), Image.Resampling.LANCZOS).convert("RGB")
        pixels_for_bg_analysis = list(thumb_for_bg_analysis.getdata())
        
        avg_img_rgb: tuple[int, int, int]
        if not pixels_for_bg_analysis:
            _LOGGER.warning("_draw_burned_text: Could not get pixels for background analysis. Defaulting shadow logic.")
            avg_img_rgb = (128, 128, 128)
        else:
            r_sum = sum(p[0] for p in pixels_for_bg_analysis)
            g_sum = sum(p[1] for p in pixels_for_bg_analysis)
            b_sum = sum(p[2] for p in pixels_for_bg_analysis)
            num_pixels = len(pixels_for_bg_analysis)
            avg_img_rgb = (r_sum // num_pixels, g_sum // num_pixels, b_sum // num_pixels)

        avg_img_luminance = _calculate_perceptual_luminance(avg_img_rgb)

        # Initial shadow choice based on background
        shadow_base_rgb_for_bg: tuple[int, int, int]
        if avg_img_luminance > 0.5:  # Background is generally light
            shadow_base_rgb_for_bg = (0, 0, 0)      # Try dark shadow
        else:  # Background is generally dark
            shadow_base_rgb_for_bg = (255, 255, 255)  # Try light shadow
        
        # B. Adjust shadow to contrast with TEXT FILL colors
        SHADOW_TEXT_MIN_CONTRAST_RATIO = 4.5
        final_shadow_base_rgb = shadow_base_rgb_for_bg

        cr_artist_shadow = self._contrast_ratio(final_shadow_base_rgb, artist_rgb_text)
        cr_title_shadow  = self._contrast_ratio(final_shadow_base_rgb, title_rgb_text)

        # If initial shadow (based on BG) doesn't contrast enough with EITHER text color
        if cr_artist_shadow < SHADOW_TEXT_MIN_CONTRAST_RATIO or \
            cr_title_shadow < SHADOW_TEXT_MIN_CONTRAST_RATIO:
            
            _LOGGER.debug(
                f"Initial shadow '{final_shadow_base_rgb}' (for BG lum {avg_img_luminance:.2f}) "
                f"low contrast with text. ArtistCR: {cr_artist_shadow:.2f} (vs {artist_rgb_text}), "
                f"TitleCR: {cr_title_shadow:.2f} (vs {title_rgb_text}). Attempting to flip shadow."
            )
            
            # Flip the shadow color
            flipped_shadow_base_rgb = (0,0,0) if final_shadow_base_rgb == (255,255,255) else (255,255,255)
            
            # Check contrast of flipped shadow with text
            cr_artist_shadow_flipped = self._contrast_ratio(flipped_shadow_base_rgb, artist_rgb_text)
            cr_title_shadow_flipped  = self._contrast_ratio(flipped_shadow_base_rgb, title_rgb_text)

            final_shadow_base_rgb = flipped_shadow_base_rgb
            _LOGGER.debug(
                f"Flipped shadow to '{final_shadow_base_rgb}'. "
                f"New ArtistCR: {cr_artist_shadow_flipped:.2f}, "
                f"New TitleCR: {cr_title_shadow_flipped:.2f}."
            )

            if cr_artist_shadow_flipped < SHADOW_TEXT_MIN_CONTRAST_RATIO or \
                cr_title_shadow_flipped < SHADOW_TEXT_MIN_CONTRAST_RATIO:
                _LOGGER.warning(
                    f"Even flipped shadow '{final_shadow_base_rgb}' has low contrast with text. "
                    f"ArtistCR: {cr_artist_shadow_flipped:.2f}, TitleCR: {cr_title_shadow_flipped:.2f}. "
                    f"Proceeding with this shadow; text visibility might be suboptimal."
                )

        shadow_alpha = 128  # Semi-transparent shadow (0-255)
        dynamic_shadow_color = (*final_shadow_base_rgb, shadow_alpha) # RGBA

        # ── 3. LAYOUT VARS and DRAWING SETUP ──────────────────────────────────
        pad = 2
        max_h = img.height - 2 * pad
        max_w = img.width  - 2 * pad
        spacer_px, inter_px = 4, 2

        img_copy = img.copy().convert("RGBA") # Draw on RGBA for shadow alpha
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
            
            self._draw_text_with_shadow(draw=layer,
                                        xy=(x_current_pos, y_current_pos),
                                        text=text_line_content,
                                        font=font,
                                        text_color=main_text_color_fill,
                                        shadow_color=dynamic_shadow_color)
            return h

        for i, line_content in enumerate(art_lines):
            line_height = _blit_text_line_with_shadow(line_content, artist_fill, y)
            y += line_height + (inter_px if i < len(art_lines) - 1 else 0)

        if art_lines and tit_lines: y += spacer_px

        for i, line_content in enumerate(tit_lines):
            line_height = _blit_text_line_with_shadow(line_content, title_fill, y)
            y += line_height + (inter_px if i < len(tit_lines) - 1 else 0)

        return img_copy.convert("RGB")



class MediaData:
    """Data class to hold and update media information.""" 

    def __init__(self, config: "Config", image_processor: "ImageProcessor"): 
        """Initialize MediaData object."""
        self.config = config
        self.image_processor = image_processor
        self.fallback: bool = False
        self.fail_txt: bool = False
        self.playing_radio: bool = False
        self.radio_logo: bool = False
        self.spotify_slide_pass: bool = False
        self.playing_tv: bool = False
        self.image_cache_count: int = 0
        self.image_cache_memory: str = "0 KB" 
        self.media_position: int = 0
        self.media_duration: int = 0
        self.process_duration: str = "0 seconds" 
        self.spotify_frames: int = 0
        self.media_position_updated_at: Optional[datetime] = None 
        self.spotify_data: Optional[dict] = None 
        self.artist: str = ""
        self.title: str = ""
        self.album: Optional[str] = None 
        self.lyrics: list[dict] = [] 
        self.picture: Optional[str] = None 
        self.select_index_original: Optional[int] = None 
        self.lyrics_font_color: str = "#FFA000"
        self.color1: str = "00FFAA"
        self.color2: str = "AA00FF"
        self.color3: str = "FFAA00"
        self.temperature: Optional[str] = None 
        self.info_img: Optional[str] = None 
        self.is_night: bool = False
        self.pic_source: str = None
        self.pic_url: str = None


    async def update(self, hass: "hass.Hass") -> Optional["MediaData"]: 
        """Update media data from Home Assistant state."""
        try:
            self.select_index_original = await hass.get_state(self.config.pixoo_sensor, attribute="pixoo_channel")
            sun_state = await hass.get_state("sun.sun") # Get full state object for better check
            self.is_night = sun_state == "below_horizon" if sun_state else False # Safe check if sun state is None

            media_state_str = await hass.get_state(self.config.media_player) # Get raw state string first
            media_state = media_state_str if media_state_str else "off" # Handle None state
            if media_state not in ["playing", "on"]:
                return None

            title = await hass.get_state(self.config.media_player, attribute="media_title")
            if not title:
                return None

            title = self.clean_title(title) if self.config.clean_title else title

            if self.config.show_lyrics and not self.config.special_mode:
                artist = await hass.get_state(self.config.media_player, attribute="media_artist")
                self.lyrics = await self._get_lyrics(artist, title)
            else:
                self.lyrics = []

            self.media_position = await hass.get_state(self.config.media_player, attribute="media_position", default=0)
            media_position_updated_at_str = await hass.get_state(self.config.media_player, attribute="media_position_updated_at") # Get as string first
            self.media_position_updated_at = datetime.fromisoformat(media_position_updated_at_str.replace('Z', '+00:00')) if media_position_updated_at_str else None # Handle None and convert
            self.media_duration = await hass.get_state(self.config.media_player, attribute="media_duration", default=0)
            original_title = title
            title = self.clean_title(title) if self.config.clean_title else title
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
                self.title_clean = self.clean_title(title)

                if media_channel and (media_content_id and (media_content_id.startswith("x-rincon") or media_content_id.startswith("aac://http") or media_content_id.startswith("rtsp://"))): 
                    self.playing_radio = True
                    self.radio_logo = False
                    self.picture = original_picture

                    if ('https://tunein' in media_content_id or
                        original_title == media_channel or
                        original_title == original_artist or
                        original_artist == media_channel or
                        original_artist == 'Live' or
                        original_artist is None):
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

            if self.config.temperature_sensor:
                temperature = await hass.get_state(self.config.temperature_sensor)
                temperature_unit = await hass.get_state(self.config.temperature_sensor, attribute="unit_of_measurement") # Get unit separately
                try:
                    temperature_val = float(temperature) if temperature else None # Handle None temperature value
                    if temperature_val is not None and temperature_unit: # Check for both value and unit
                        self.temperature = f"{int(temperature_val)}{temperature_unit.lower()}"
                    else:
                        self.temperature = None # Reset to None if no valid temp or unit
                except (ValueError, TypeError): # Catch potential conversion errors
                    self.temperature = None
                    _LOGGER.warning(f"Could not parse temperature value '{temperature}' from {self.config.temperature_sensor}.") # Log warning if parsing fails

            return self

        except Exception as e: 
            _LOGGER.exception(f"Error updating Media Data: {e}") 
            return None


    async def _get_lyrics(self, artist: Optional[str], title: str) -> list[dict]: 
        """Fetch lyrics using LyricsProvider (assuming it's now a method or accessible)."""
        lyrics_provider = LyricsProvider(self.config, self.image_processor)
        return await lyrics_provider.get_lyrics(artist, title) 


    def format_ai_image_prompt(self, artist: Optional[str], title: str) -> str: 
        """Format prompt for AI image generation."""
        # List of prompt templates
        artist_name = artist if artist else 'Pixoo64' # Use artist or default 'Pixoo64'

        prompts = [
            f"Create an image inspired by the music artist {artist_name}, titled: '{title}'. The artwork should feature an accurate likeness of the artist and creatively interpret the title into a visual imagery.",
            f"Design a vibrant album cover for '{title}' by {artist_name}, incorporating elements that reflect the mood and theme of the music.",
            f"Imagine a surreal landscape that represents the essence of '{title}' by {artist_name}. Use bold colors and abstract shapes.",
            f"Create a retro-style album cover for '{title}' by {artist_name}, featuring pixel art and nostalgic elements from the 80s.",
            f"Illustrate a dreamlike scene inspired by '{title}' by {artist_name}, blending fantasy and reality in a captivating way.",
            f"Generate a minimalist design for '{title}' by {artist_name}, focusing on simplicity and elegance in the artwork.",
            f"Craft a dynamic and energetic cover for '{title}' by {artist_name}, using motion and vibrant colors to convey excitement.",
            f"Produce a whimsical and playful illustration for '{title}' by {artist_name}, incorporating fun characters and imaginative elements.",
            f"Create a dark and moody artwork for '{title}' by {artist_name}, using shadows and deep colors to evoke emotion.",
            f"Design a futuristic album cover for '{title}' by {artist_name}, featuring sci-fi elements and innovative designs."
        ]

        # Randomly select a prompt
        prompt = random.choice(prompts)
        prompt = f"https://pollinations.ai/p/{prompt}?model={self.config.ai_fallback}"
        if self.config.pollinations:
            prompt = f"{prompt}&token={self.config.pollinations}" 
        return prompt


    def clean_title(self, title: str) -> str: 
        """Clean up the title by removing common patterns."""
        if not title:
            return title

        # Patterns to remove
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

        # Apply each pattern
        cleaned_title = title
        for pattern in patterns:
            cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.IGNORECASE)

        # Remove extra whitespace
        cleaned_title = ' '.join(cleaned_title.split())
        return cleaned_title

class FallbackService:
    """Handles fallback logic to retrieve album art from various sources if the original picture is not available.""" 

    def __init__(self, config: "Config", image_processor: "ImageProcessor"): 
        """Initialize FallbackService object."""
        self.config = config
        self.image_processor = image_processor
        
        # Tidal Token Cache
        self.tidal_token_cache: dict[str, Any] = {
            'token': None,
            'expires': 0
        }
        self.tidal_client_token: Optional[str] = None 


    async def get_final_url(self, picture: Optional[str], media_data: "MediaData") -> Optional[dict]: 
        """Determine and retrieve the final album art URL, using fallback strategies if needed."""
        self.fail_txt = False
        self.fallback = False
        media_data.pic_url = None # Initialize to None

        if picture is not None: # Check if picture is not None before using startswith
            media_data.pic_url = picture if picture.startswith('http') else f"{self.config.ha_url}{picture}"
        else:
            _LOGGER.debug("Picture is None, skipping URL prefixing.")
            media_data.pic_url = picture # picture is already None, so assign None to pic_url as well
        #media_data.pic_url = picture if picture.startswith('http') else f"{self.config.ha_url}{picture}"
        
        if self.config.force_ai and not media_data.radio_logo and not media_data.playing_tv:
            _LOGGER.info("Force AI mode enabled, trying to generate AI album art.") 
            if self.config.info:
                await self.send_info(media_data.artist, "FORCE   AI", media_data.lyrics_font_color)
            ai_url = media_data.format_ai_image_prompt(media_data.artist, media_data.title)
            try:
                result = await asyncio.wait_for(
                    self.image_processor.get_image(ai_url, media_data, media_data.spotify_slide_pass),
                    timeout=25
                )
                if result:
                    _LOGGER.info("Successfully generated AI album art.") 
                    media_data.pic_url = ai_url
                    media_data.pic_source = "AI"
                    return result
            except asyncio.TimeoutError:
                _LOGGER.warning("AI image generation timed out after 25 seconds.") 
            except Exception as e: 
                _LOGGER.error(f"AI image generation failed: {e}") 
                return self._get_fallback_black_image_data() # Return black image data on AI failure

        else: # Main fallback logic if force_ai is not enabled
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
                        'most_common_color_alternative': '#ffff00'}

            # Process original picture
            try:
                if not media_data.playing_radio or media_data.radio_logo:
                    result = await self.image_processor.get_image(picture, media_data, media_data.spotify_slide_pass)
                    if result:
                        _LOGGER.debug("Successfully processed original album art.") 
                        media_data.pic_source = "Original"
                        return result
            except Exception as e: 
                _LOGGER.error(f"Original picture processing failed: {e}") 

            """ Fallback begins """
            _LOGGER.info(f"Falling back to alternative album art sources for '{media_data.artist} - {media_data.title}'.") 
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
                                _LOGGER.info("Successfully retrieved album art from Spotify.") 
                                media_data.pic_url = image_url
                                media_data.pic_source = "Spotify"
                                return result
                        else:
                            _LOGGER.warning("Failed to process Spotify album art image.") 

                    # Get Artist Picture If Album Art Was Not Found
                    self.spotify_artist_pic = await spotify_service.get_spotify_artist_image_url_by_name(media_data.artist)

                except Exception as e: 
                    _LOGGER.error(f"Spotify fallback failed: {e}") 

            # Try Discogs:
            if self.config.discogs:
                if self.config.info:
                    await self.send_info(media_data.artist, "DISCOGS", media_data.lyrics_font_color)
                try:
                    discogs_art = await self.search_discogs_album_art(media_data.artist, media_data.title)
                    if discogs_art:
                        result = await self.image_processor.get_image(discogs_art, media_data, media_data.spotify_slide_pass)
                        if result:
                            _LOGGER.info("Successfully retrieved album art from Discogs.") 
                            media_data.pic_url = discogs_art
                            media_data.pic_source = "Discogs"
                            return result
                        else:
                            _LOGGER.warning("Failed to process Discogs album art image.") 
                except Exception as e: 
                    _LOGGER.error(f"Discogs fallback failed: {e}") 

            # Try Last.fm:
            if self.config.lastfm:
                if self.config.info:
                    await self.send_info(media_data.artist, "LAST.FM", media_data.lyrics_font_color)
                try:
                    lastfm_art = await self.search_lastfm_album_art(media_data.artist, media_data.title)
                    if lastfm_art:
                        result = await self.image_processor.get_image(lastfm_art, media_data, media_data.spotify_slide_pass)
                        if result:
                            _LOGGER.info("Successfully retrieved album art from Last.fm.") 
                            media_data.pic_url = lastfm_art
                            media_data.pic_source = "Last.FM"
                            return result
                        else:
                            _LOGGER.warning("Failed to process Last.fm album art image.") 
                except Exception as e: 
                    _LOGGER.error(f"Last.fm fallback failed: {e}") 

            # Try TIDAL
            if self.config.tidal_client_id and self.config.tidal_client_secret:
                if self.config.info:
                    await self.send_info(media_data.artist, "TIDAL", media_data.lyrics_font_color)
                try:
                    tidal_art = await self.get_tidal_album_art_url(media_data.artist, media_data.title)
                    if tidal_art:
                        result = await self.image_processor.get_image(tidal_art, media_data, media_data.spotify_slide_pass)
                        if result:
                            _LOGGER.info("Successfully retrieved album art from TIDAL.") 
                            media_data.pic_url = tidal_art
                            media_data.pic_source = "TIDAL"
                            return result
                        else:
                            _LOGGER.warning("Failed to process TIDAL album art image.") 
                except Exception as e: 
                    _LOGGER.error(f"TIDAL fallback failed: {e}") 

            # Show Artist Picture if all API keys method fail
            if self.spotify_artist_pic:
                result = await self.image_processor.get_image(self.spotify_artist_pic, media_data, media_data.spotify_slide_pass)
                if result:
                    _LOGGER.info("Successfully retrieved artist image from Spotify.") 
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
                                _LOGGER.info("Successfully retrieved album art from MusicBrainz.") 
                                media_data.pic_url = mb_url
                                media_data.pic_source = "MusicBrainz"
                                return result
                            else:
                                _LOGGER.warning("Failed to process MusicBrainz album art image.") 
                        except asyncio.TimeoutError:
                            _LOGGER.warning("MusicBrainz request timed out after 10 seconds.") 
                        except Exception as e: 
                            _LOGGER.error(f"MusicBrainz fallback failed: {e}") 

                except Exception as e: 
                    _LOGGER.error(f"MusicBrainz fallback failed: {e}") 


            # Fallback to AI generation (Last resort before black screen)
            _LOGGER.info("Falling back to AI image generation as last resort.") 
            if self.config.info:
                await self.send_info(media_data.artist, "AI   IMAGE", media_data.lyrics_font_color)
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
                _LOGGER.warning("AI image generation timed out after 20 seconds.") 
            except Exception as e: 
                _LOGGER.error(f"AI image generation failed: {e}") 
                return self._get_fallback_black_image_data() # Return black image data on AI failure


            # Last try on spotify (Using first album if other Spotify methods failed)
            if self.spotify_first_album:
                if self.config.info:
                    await self.send_info(media_data.artist, "SPOTIFY", media_data.lyrics_font_color)
                try:
                    result = await self.image_processor.get_image(self.spotify_first_album, media_data, media_data.spotify_slide_pass)
                    if result:
                        _LOGGER.info("Successfully retrieved default album art from Spotify.") 
                        media_data.pic_url = self.spotify_first_album
                        media_data.pic_source = "Spotify (Artist Profile Image)"
                        return result

                except Exception as e: 
                    _LOGGER.error(f"Spotify fallback (first album) failed: {e}") 


        # Ultimate fallback (Black screen)
        media_data.pic_url = "Black Screen"
        media_data.pic_source = "Internal"
        return self._get_fallback_black_image_data() # Call helper method to get black image data


    def _get_fallback_black_image_data(self) -> dict: 
        """Helper method to get data for fallback black screen image."""
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
            'most_common_color_alternative': '#ffff00'}


    async def send_info_img(self, base64_image: str) -> None: 
        """Send info image to Pixoo device."""
        payload = {
            "Command": "Draw/CommandList",
            "CommandList": [
                {"Command": "Draw/ResetHttpGifId"},
                {"Command": "Draw/SendHttpGif",
                    "PicNum": 1, "PicWidth": 64, "PicOffset": 0,
                    "PicID": 0, "PicSpeed": 10000, "PicData": base64_image }]}
        await PixooDevice(self.config).send_command(payload)


    async def send_info(self, artist: Optional[str], text: str, lyrics_font_color: str) -> None: 
        """Send info text to Pixoo device."""
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


    async def get_musicbrainz_album_art_url(self, ai_artist: str, ai_title: str) -> Optional[str]: 
        """Get album art URL from MusicBrainz asynchronously."""
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
                try: 
                    async with session.get(search_url, params=params, headers=headers, timeout=10) as response: 
                        response.raise_for_status() 
                        data = await response.json()
                        if not data.get("releases"):
                            _LOGGER.info("No releases found in MusicBrainz for the given query.") 
                            return None

                        release_id = data["releases"][0]["id"]

                        # Get the cover art
                        cover_art_url = f"https://coverartarchive.org/release/{release_id}"
                        try: 
                            async with session.get(cover_art_url, headers=headers, timeout=20) as art_response: 
                                art_response.raise_for_status() 
                                art_data = await art_response.json()
                                # Look for front cover and get 250px thumbnail
                                for image in art_data.get("images", []):
                                    if image.get("front", False):
                                        return image.get("thumbnails", {}).get("250")

                                _LOGGER.info("No front cover found in MusicBrainz Cover Art Archive.") 
                                return None
                        except aiohttp.ClientError as e: 
                            _LOGGER.error(f"MusicBrainz - Cover Art Archive API error for release ID {release_id}: {e}") 
                            return None
                        except json.JSONDecodeError as e: 
                            _LOGGER.error(f"MusicBrainz - Cover Art Archive JSON decode error for release ID {release_id}: {e}") 
                            return None

                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"MusicBrainz API error: {e}") 
                    return None
                except json.JSONDecodeError as e: 
                    _LOGGER.error(f"MusicBrainz JSON decode error: {e}") 
                    return None


        except asyncio.TimeoutError:
            _LOGGER.warning("MusicBrainz request timed out.") 
            return None
        except Exception as e: 
            _LOGGER.error(f"Error while fetching MusicBrainz album art URL: {e}") 
            return None


    async def search_discogs_album_art(self, ai_artist: str, ai_title: str) -> Optional[str]: 
        """Search Discogs API for album art URL."""
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

        try:
            async with aiohttp.ClientSession() as session:
                try: 
                    async with session.get(base_url, headers=headers, params=params, timeout=10) as response: 
                        response.raise_for_status() 
                        data = await response.json()
                        results = data.get("results", [])
                        if not results:
                            _LOGGER.info(f"No album art results found on Discogs for '{ai_artist} - {ai_title}'.") 
                            return None

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
                                _LOGGER.debug(f"Found Discogs album art URL: {album_art_url}") 
                                return album_art_url
                            else:
                                _LOGGER.info("No cover image URL found in best Discogs result.") 
                                return None
                        else:
                            _LOGGER.info("No suitable album release found on Discogs.") 
                            return None
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"Discogs API request failed: {response.status} - {response.reason}") 
                    return None
                except json.JSONDecodeError as e: 
                    _LOGGER.error(f"Discogs JSON decode error: {e}") 
                    return None


        except asyncio.TimeoutError:
            _LOGGER.warning("Discogs request timed out.") 
            return None
        except Exception as e: 
            _LOGGER.error(f"Error while searching Discogs for album art: {e}") 
            return None


    async def search_lastfm_album_art(self, ai_artist: str, ai_title: str) -> Optional[str]: 
        """Search Last.fm API for album art URL."""
        base_url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "track.getInfo",
            "api_key": self.config.lastfm,
            "artist": ai_artist,
            "track": ai_title,
            "format": "json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                try: 
                    async with session.get(base_url, params=params, timeout=10) as response: 
                        response.raise_for_status() 
                        data = await response.json()
                        album_art_url_list = data.get("track", {}).get("album", {}).get("image", []) 
                        if album_art_url_list:
                            album_art_url = album_art_url_list[-1]["#text"] # Get the last (largest) image URL
                            _LOGGER.debug(f"Found Last.fm album art URL: {album_art_url}") 
                            return album_art_url
                        else:
                            _LOGGER.info(f"No album art found on Last.fm for '{ai_artist} - {ai_title}'.") 
                            return None
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"Last.fm API request failed: {e}") 
                    return None
                except json.JSONDecodeError as e: 
                    _LOGGER.error(f"Last.fm JSON decode error: {e}") 
                    return None

        except asyncio.TimeoutError:
            _LOGGER.warning("Last.fm request timed out.") 
            return None
        except Exception as e: 
            _LOGGER.error(f"Error while searching Last.fm for album art: {e}") 
            return None


    async def get_tidal_album_art_url(self, artist: str, title: str) -> Optional[str]: 
        """Retrieves the album art URL from TIDAL API using artist and track title."""
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
            async with aiohttp.ClientSession() as session:
                # 1. Search for tracks using the title and artist
                search_url = f"{base_url}searchresults/{artist} - {title}"
                try: 
                    async with session.get(search_url, headers=headers, params=search_params, timeout=10) as response: 
                        response.raise_for_status() 
                        search_data = await response.json()
                        # Directly search for albums in the "included" array
                        albums = [item for item in search_data.get("included", []) if item.get("type") == "albums"]
                        if not albums:
                            _LOGGER.info(f"No albums found on TIDAL for '{artist} - {title}'.") 
                            return None

                        best_album = albums[0] # Taking the first album

                        if best_album:
                            # Extract and return image URLs from albums object
                            image_links = best_album.get("attributes", {}).get("imageLinks", [])
                            if image_links and len(image_links) > 3: # Check if image_links and index 3 exist to prevent IndexError
                                album_art_url = image_links[3].get("href")
                                _LOGGER.debug(f"Found TIDAL album art URL: {album_art_url}") 
                                return album_art_url
                            else:
                                _LOGGER.info("No suitable image links found in best TIDAL album result.") 
                                return None

                        else:
                            _LOGGER.info(f"No album found on TIDAL that matches '{artist} - {title}'.") 
                            return None
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"TIDAL API request failed: {e}") 
                    return None
                except json.JSONDecodeError as e: 
                    _LOGGER.error(f"TIDAL JSON decode error: {e}") 
                    return None


        except asyncio.TimeoutError:
            _LOGGER.warning("TIDAL request timed out.") 
            return None
        except Exception as e: 
            _LOGGER.error(f"Error while getting TIDAL album art URL: {e}") 
            return None


    async def get_tidal_access_token(self) -> Optional[str]: 
        """Get TIDAL API access token using client credentials."""
        if self.tidal_token_cache['token'] and time.time() < self.tidal_token_cache['expires']:
            _LOGGER.debug("Using cached TIDAL access token.") 
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
            async with aiohttp.ClientSession() as session:
                try: 
                    async with session.post(url, headers=tidal_headers, data=payload, timeout=10) as response: 
                        response.raise_for_status() 
                        response_json = await response.json()
                        access_token = response_json["access_token"]
                        expiry_time = time.time() + response_json.get("expires_in", 3600) - 60 # Subtract 60 seconds for safety margin
                        self.tidal_token_cache = {
                            'token': access_token,
                            'expires': expiry_time
                        }
                        _LOGGER.debug("Successfully retrieved new TIDAL access token and stored in cache.") 
                        return access_token
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"TIDAL - Error getting access token from API: {e}") 
                    return None
                except json.JSONDecodeError as e: 
                    _LOGGER.error(f"TIDAL - JSON decode error when getting access token: {e}") 
                    return None


        except asyncio.TimeoutError:
            _LOGGER.warning("TIDAL access token request timed out.") 
            return None
        except Exception as e: 
            _LOGGER.error(f"TIDAL - Error while getting access token: {e}") 
            return None


    def create_black_screen(self) -> Image.Image: 
        """Create a black PIL Image."""
        img = Image.new("RGB", (64, 64), (0, 0, 0)) 
        return img 


    def create_tv_icon_image(self) -> Image.Image: 
        """Create a TV icon."""
        # Image dimensions for drawing
        image_width = 300
        image_height = 300

        # Final image size
        final_width = 64
        final_height = 64

        # Vertical Offset for Centering (adjust this)
        vertical_offset = 10

        # Colors
        black = (0, 0, 0)
        brown = (139, 69, 19)  # SaddleBrown
        light_brown = (205, 133, 63) # Peru
        screen_bg = (240, 240, 240) # Off-white for screen background
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
        # Create a new image with black background
        image = Image.new("RGB", (image_width, image_height), black)
        draw = ImageDraw.Draw(image)

        # --- TV Body ---
        tv_body_padding = 60 + vertical_offset  # Apply offset to top padding
        tv_body_rect = [
            tv_body_padding,
            tv_body_padding,
            image_width - tv_body_padding,
            image_height - tv_body_padding - 40
        ]
        tv_body_radius = 20
        draw.rounded_rectangle(tv_body_rect, tv_body_radius, fill=brown)

        # --- Screen Area ---
        screen_padding = tv_body_padding + 15 # Screen padding is relative to the *shifted* body padding
        screen_rect = [
            screen_padding,
            screen_padding,
            image_width - screen_padding,
            tv_body_rect[3] - 15
        ]
        draw.rectangle(screen_rect, fill=screen_bg)

        # --- Rainbow Color Bars ---
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

        # --- Antennas ---
        antenna_color = gray
        antenna_thickness = 3
        antenna_length = 50
        antenna_base_x1 = image_width // 2 - 30
        antenna_base_x2 = image_width // 2 + 30
        antenna_base_y = tv_body_padding  # Antenna base is also relative to the *shifted* body padding

        # Left antenna
        draw.line(
            (antenna_base_x1, antenna_base_y, antenna_base_x1 - 20, antenna_base_y - antenna_length),
            fill=antenna_color, width=antenna_thickness
        )
        # Right antenna
        draw.line(
            (antenna_base_x2, antenna_base_y, antenna_base_x2 + 20, antenna_base_y - antenna_length),
            fill=antenna_color, width=antenna_thickness
        )

        # --- Shiny Highlights ---
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

        image = image.resize((final_width, final_height), Image.Resampling.LANCZOS)

        return image


class LyricsProvider:
    """Provides lyrics for the currently playing track."""

    def __init__(self, config: "Config", image_processor: "ImageProcessor"):
        """Initialize LyricsProvider object."""
        self.config = config
        self.lyrics: list[dict] = []
        self.len_lines: int = 0
        self.image_processor = image_processor
        # Remember the last lyric timestamp we sent, to avoid duplicates
        self._last_sent_second: Optional[int] = None

    async def get_lyrics(self, artist: Optional[str], title: str) -> list[dict]:
        """Fetch lyrics for the given artist and title from Textyl API."""
        lyrics_url = f"http://api.textyl.co/api/lyrics?q={artist} - {title}"
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(lyrics_url, timeout=10) as response:
                    response.raise_for_status()
                    lyrics_data = await response.json()
                    processed = [
                        {'seconds': line['seconds'], 'lyrics': line['lyrics']}
                        for line in lyrics_data
                    ]
                    self.lyrics = processed
                    _LOGGER.info(f"Retrieved lyrics for '{artist} - {title}'.")
                    return processed
        except Exception as e:
            _LOGGER.error(f"Failed to fetch lyrics for '{artist} - {title}': {e}")
            self.lyrics = []
            return []

    async def calculate_position(self, media_data: "MediaData", hass: "hass.Hass") -> None:
        """Calculate and display lyrics based on media position."""
        if not media_data.lyrics or not self.config.show_lyrics:
            return

        lyrics_delay = int(float(self.config.lyrics_sync))
        if media_data.media_position_updated_at:
            now = datetime.now(timezone.utc)
            elapsed = (now - media_data.media_position_updated_at).total_seconds()
            current_pos = min(media_data.media_position + elapsed, media_data.media_duration)
            current_sec = int(current_pos)

            for idx, item in enumerate(media_data.lyrics):
                lyric_sec = item['seconds']
                # Only send once per lyric timestamp
                if current_sec == lyrics_delay + lyric_sec and lyric_sec != self._last_sent_second:
                    self._last_sent_second = lyric_sec
                    await self.create_lyrics_payloads(
                        item['lyrics'],
                        line_length=11,
                        lyrics_font_color=media_data.lyrics_font_color
                    )

                    # Determine how long to display before clearing
                    next_sec = media_data.lyrics[idx + 1]['seconds'] if idx + 1 < len(media_data.lyrics) else None
                    duration = (next_sec - lyric_sec) if next_sec else 10
                    if duration > 9:
                        # small sleep to let it render fully
                        await asyncio.sleep(self.len_lines * 1.8)
                        await PixooDevice(self.config).send_command({"Command": "Draw/ClearHttpText"})
                    break

    async def create_lyrics_payloads(self, lyrics: str, line_length: int, lyrics_font_color: str) -> None:
        """Create and send lyrics payloads to Pixoo device."""
        if not lyrics:
            return

        # split_string, get_bidi, and has_bidi are helpers defined elsewhere in your script
        all_lines = split_string(get_bidi(lyrics) if has_bidi(lyrics) else lyrics, line_length)
        if len(all_lines) > 6:
            all_lines = all_lines[:6]

        self.len_lines = len(all_lines)
        font_height = 10 if self.len_lines == 6 else 12
        start_y = (64 - self.len_lines * font_height) // 2

        item_list = []
        for i, line in enumerate(all_lines):
            y = start_y + i * font_height
            rtl = 1 if has_bidi(line) else 0
            item_list.append({
                "TextId": i + 1,
                "type": 22,
                "x": 0,
                "y": y,
                "dir": rtl,
                "font": self.config.lyrics_font,
                "TextWidth": 64,
                "Textheight": 16,
                "speed": 100,
                "align": 2,
                "TextString": line,
                "color": lyrics_font_color,
            })

        lyrics_payload = {
            "Command": "Draw/SendHttpItemList",
            "ItemList": item_list
        }

        payload = ({"Command": "Draw/CommandList", "CommandList": [ {"Command": "Draw/ClearHttpText"}, lyrics_payload ]})
        await PixooDevice(self.config).send_command(payload)


class SpotifyService:
    """Service to interact with Spotify API for album art and related data.""" 

    def __init__(self, config: "Config"): 
        """Initialize SpotifyService object."""
        self.config = config
        self.spotify_token_cache: dict[str, Any] = { 
            'token': None,
            'expires': 0
        }
        self.spotify_data: Optional[dict] = None 


    async def get_spotify_access_token(self) -> Optional[str]: 
        """Get Spotify API access token using client credentials, caching the token."""
        if self.spotify_token_cache['token'] and time.time() < self.spotify_token_cache['expires']:
            _LOGGER.debug("Using cached Spotify access token.") 
            return self.spotify_token_cache['token']

        url = "https://accounts.spotify.com/api/token"
        spotify_headers = {
            "Authorization": "Basic " + base64.b64encode(f"{self.config.spotify_client_id}:{self.config.spotify_client_secret}".encode()).decode(),
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {"grant_type": "client_credentials"}
        try:
            async with aiohttp.ClientSession() as session:
                try: 
                    async with session.post(url, headers=spotify_headers, data=payload, timeout=10) as response: 
                        response.raise_for_status() 
                        response_json = await response.json()
                        access_token = response_json["access_token"]
                        expiry_time = time.time() + response_json.get("expires_in", 3600) - 60 # Subtract 60 seconds for safety margin
                        self.spotify_token_cache = {
                            'token': access_token,
                            'expires': expiry_time
                        }
                        _LOGGER.debug("Successfully retrieved new Spotify access token and stored in cache.") 
                        return access_token
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"Spotify - Error getting access token from API: {e}") 
                    return None
                except json.JSONDecodeError as e:
                    _LOGGER.error(f"Spotify - JSON decode error when getting access token: {e}") 
                    return None

        except asyncio.TimeoutError:
            _LOGGER.warning("Spotify access token request timed out.") 
            return None
        except Exception as e: 
            _LOGGER.error(f"Spotify - Error getting access token: {e}")
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
            async with aiohttp.ClientSession() as session:
                try: 
                    async with session.get(url, headers=spotify_headers, params=payload, timeout=10) as response: 
                        response.raise_for_status() 
                        response_json = await response.json()
                        tracks = response_json.get('tracks', {}).get('items', [])
                        if tracks:
                            _LOGGER.debug(f"Successfully retrieved Spotify track search results for '{artist} - {title}'.") 
                            return response_json
                        else:
                            _LOGGER.info(f"No tracks found on Spotify for '{artist} - {title}'.") 
                            return None
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"Spotify API track search request failed for '{artist} - {title}': {e}") 
                    return None
                except json.JSONDecodeError as e: 
                    _LOGGER.error(f"Spotify JSON decode error for track search '{artist} - {title}': {e}") 
                    return None


        except asyncio.TimeoutError:
            _LOGGER.warning(f"Spotify track search request timed out for '{artist} - {title}'.") 
            return None
        except (IndexError, KeyError) as e: 
            _LOGGER.error(f"Error parsing Spotify track info (IndexError/KeyError): {e}") 
            return None
        except Exception as e: 
            _LOGGER.error(f"Error getting Spotify track JSON: {e}") 
            return None
        finally:
            await asyncio.sleep(0.5) # Keep delay - might be needed to avoid rate limiting


    async def spotify_best_album(self, tracks: list[dict], artist: str) -> tuple[Optional[str], Optional[str]]: 
        """Determine the 'best' album ID and first album ID from Spotify track search results."""
        best_album = None
        earliest_year = float('inf')
        preferred_types = ["single", "album", "compilation"]
        first_album_id = tracks[0]['album']['id'] if tracks else None # Get first album ID or None if no tracks
        for track in tracks:
            album = track.get('album')
            album_type = album.get('album_type')
            release_date = album.get('release_date')
            year = int(release_date[:4]) if release_date and release_date[:4].isdigit() else float('inf') # Safe year parsing
            artists = album.get('artists', [])
            album_artist = artists[0]['name'] if artists else ""
            if artist.lower() == album_artist.lower():
                #Corrected Prioritization:
                if album_type in preferred_types:
                    if year < earliest_year:  # Only choose the album if its year is earlier.
                        earliest_year = year
                        best_album = album
                elif year < earliest_year: # If not preferred type, choose based on year alone.
                    earliest_year = year
                    best_album = album

        if best_album:
            _LOGGER.debug(f"Determined best album ID from Spotify: {best_album['id']}")
            return best_album['id'], first_album_id
        else:
            if tracks:
                _LOGGER.info("Most likely album art from Spotify might not be the most accurate match.") 
                return None, first_album_id # Return first album ID even if best album not found based on logic
            else:
                _LOGGER.info("No suitable album found on Spotify to determine best album.") 
                return None, first_album_id


    async def get_spotify_album_id(self, artist: str, title: str) -> tuple[Optional[str], Optional[str]]: 
        """Get the Spotify album ID and first album ID for a given artist and title."""
        token = await self.get_spotify_access_token()
        if not token:
            return None, None # Return None for both if no token
        try:
            self.spotify_data = None # Reset spotify_data before new search
            response_json = await self.get_spotify_json(artist, title)
            self.spotify_data = response_json # Store response in instance variable - might be unused after this method?
            tracks = response_json.get('tracks', {}).get('items', [])
            if tracks:
                best_album_id, first_album_id = await self.spotify_best_album(tracks, artist)
                return best_album_id, first_album_id
            else:
                _LOGGER.info(f"No tracks found on Spotify for '{artist} - {title}' to get album ID.") 
                return None, None # Return None for both if no tracks

        except (IndexError, KeyError) as e: 
            _LOGGER.error(f"Error parsing Spotify track info to get album ID (IndexError/KeyError): {e}") 
            return None, None
        except Exception as e: 
            _LOGGER.error(f"Error getting Spotify album ID: {e}") 
            return None, None
        finally:
            await asyncio.sleep(0.5) # Keep delay - might be needed to avoid rate limiting


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
            async with aiohttp.ClientSession() as session:
                try: 
                    async with session.get(url, headers=spotify_headers, timeout=10) as response: 
                        response.raise_for_status() 
                        response_json = await response.json()
                        images = response_json.get('images', [])
                        if images:
                            album_image_url = images[0]['url'] # Get first (largest) image URL
                            _LOGGER.debug(f"Retrieved Spotify album image URL: {album_image_url}") 
                            return album_image_url
                        else:
                            _LOGGER.info(f"Album image not found on Spotify for album ID '{album_id}'.") 
                            return None
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"Spotify API album data request failed for album ID '{album_id}': {e}") 
                    return None
                except json.JSONDecodeError as e: 
                    _LOGGER.error(f"Spotify JSON decode error for album data request for album ID '{album_id}': {e}") 
                    return None

        except asyncio.TimeoutError:
            _LOGGER.warning(f"Spotify album data request timed out for album ID '{album_id}'.") 
            return None
        except (IndexError, KeyError): 
            _LOGGER.info("Album image not found in Spotify response.") 
            return None
        except Exception as e: 
            _LOGGER.error(f"Error getting Spotify album image URL for album ID '{album_id}': {e}") 
            return None
        finally:
            await asyncio.sleep(0.5) # Keep delay - might be needed to avoid rate limiting


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
            async with aiohttp.ClientSession() as session:
                try: 
                    async with session.get(search_url, headers=spotify_headers, params=search_payload, timeout=10) as response: 
                        response.raise_for_status() 
                        response_json = await response.json()
                        if response.status != 200:
                            _LOGGER.error(f"Failed to search artist on Spotify for artist name '{artist_name}': {response.status} - {response_json}") 
                            return None

                        artists = response_json.get('artists', {}).get('items', [])
                        if not artists:
                            _LOGGER.info(f"No artist found on Spotify with the name: '{artist_name}'.") 
                            return None

                        artist_id = artists[0]['id']
                        return await self.get_spotify_artist_image_url(artist_id)
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"Spotify API artist search request failed for artist name '{artist_name}': {e}") 
                    return None
                except json.JSONDecodeError as e: 
                    _LOGGER.error(f"Spotify JSON decode error for artist search for artist name '{artist_name}': {e}") 
                    return None


        except asyncio.TimeoutError:
            _LOGGER.warning(f"Spotify artist search request timed out for artist name '{artist_name}'.") 
            return None
        except (IndexError, KeyError) as e: 
            _LOGGER.info(f"Error parsing Spotify artist search data (IndexError/KeyError) for artist name '{artist_name}': {e}") 
            return None
        except Exception as e: 
            _LOGGER.error(f"Error getting Spotify artist image URL by name for artist name '{artist_name}': {e}") 
            return None
        finally:
            await asyncio.sleep(0.5)

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
            async with aiohttp.ClientSession() as session:
                try: 
                    async with session.get(url, headers=spotify_headers, timeout=10) as response: 
                        response.raise_for_status() 
                        response_json = await response.json()
                        images = response_json.get('images', [])
                        if images:
                            artist_image_url = images[0]['url'] # Get first (largest) image URL
                            _LOGGER.debug(f"Retrieved Spotify artist image URL for artist ID '{artist_id}': {artist_image_url}")
                            return artist_image_url
                        else:
                            _LOGGER.info(f"Artist image not found on Spotify for artist ID '{artist_id}'.") 
                            return None
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"Spotify API artist data request failed for artist ID '{artist_id}': {e}") 
                    return None
                except json.JSONDecodeError as e: 
                    _LOGGER.error(f"Spotify JSON decode error for artist data request for artist ID '{artist_id}': {e}") 
                    return None

        except asyncio.TimeoutError:
            _LOGGER.warning(f"Spotify artist data request timed out for artist ID '{artist_id}'.") 
            return None
        except (IndexError, KeyError) as e: 
            _LOGGER.info("Artist image not found in Spotify response.") 
            return None
        except Exception as e: 
            _LOGGER.error(f"Error getting Spotify artist image URL for artist ID '{artist_id}': {e}") 
            return None
        finally:
            await asyncio.sleep(0.5) # Keep delay - might be needed to avoid rate limiting


    """ Spotify Album Art Slide """
    async def get_album_list(self, media_data: "MediaData", returntype: str) -> list[str]: 
        """Retrieves album art URLs, filtering and prioritizing albums."""
        if not self.spotify_data or media_data.playing_tv:
            return []

        try:
            if not isinstance(self.spotify_data, dict):
                _LOGGER.error("Unexpected Spotify data format. Expected a dictionary.") 
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
            # album_data = await self.get_spotify_artist_image_url_by_name(media_data.artist)
            # if album_data:  # Ensure it's not empty or None
            #     album_urls.append(album_data)  # Append only the first value
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
                _LOGGER.debug(f"Returning {len(album_base64)} base64 album art URLs for Spotify slide.") 
                return album_base64
            else:
                _LOGGER.debug(f"Returning {len(album_urls)} album art URLs for Spotify slide.") 
                media_data.pic_url = album_urls
                
                return album_urls

        except (KeyError, IndexError, TypeError, AttributeError) as e: 
            _LOGGER.error(f"Error processing Spotify data to get album list: {e}") 
            return []


    async def get_slide_img(self, picture: str, show_lyrics_is_on: bool, playing_radio_is_on: bool) -> Optional[str]: 
        """Fetches, processes, and returns base64-encoded image data for Spotify slide."""
        try:
            async with aiohttp.ClientSession() as session:
                try: 
                    async with session.get(picture, timeout=10) as response: 
                        response.raise_for_status() 
                        image_raw_data = await response.read()
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"Error fetching image for Spotify slide from URL '{picture}': {e}") 
                    return None


        except Exception as e: 
            _LOGGER.error(f"Error processing image for Spotify slide: {e}") 
            return None

        try: 
            with Image.open(BytesIO(image_raw_data)) as img:
                img = ensure_rgb(img)

                if self.config.crop_borders:
                    img = ImageProcessor(self.config).crop_image_borders(img, False)

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
            _LOGGER.error(f"Error processing image with PIL for Spotify slide: {e}") 
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
        # Use the pixoo_device object directly
        await pixoo_device.send_command(payload)


    async def spotify_albums_slide(self, pixoo_device: "PixooDevice", media_data: "MediaData") -> None: 
        """Fetches and processes images for Spotify album slide animation."""
        media_data.spotify_slide_pass = True
        album_urls_b64 = await self.get_album_list(media_data, returntype="b64") 
        if not album_urls_b64:
            _LOGGER.info("No album art URLs found for Spotify slide animation.") 
            media_data.spotify_frames = 0
            media_data.spotify_slide_pass = False
            return

        frames = len(album_urls_b64)
        media_data.spotify_frames = frames
        if frames < 2:
            _LOGGER.info("Not enough album art URLs (less than 3) for Spotify slide animation.") 
            media_data.spotify_slide_pass = False
            media_data.spotify_frames = 0
            return

        _LOGGER.info(f"Creating Spotify album slide animation with {frames} frames for {media_data.artist}.") 
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
                    _LOGGER.error("Base64 encoded album art URL is None, skipping frame.") 
                    break # Break loop if base64 data is None - avoid further errors

            except Exception as e: 
                _LOGGER.error(f"Error processing image frame for Spotify slide animation: {e}")
                break # Break loop on error to prevent further issues


    async def spotify_album_art_animation(self, pixoo_device: "PixooDevice", media_data: "MediaData", start_time=None) -> None: 
        """Creates and sends a static slide show animation with 3 albums to the Pixoo device."""
        if media_data.playing_tv:
            return # Exit if playing TV

        try:
            album_urls = await self.get_album_list(media_data, returntype="url")
            if not album_urls:
                _LOGGER.info("No album art URLs found for Spotify album art animation.") 
                media_data.spotify_frames = 0
                return

            num_albums = len(album_urls)
            if num_albums < 3:
                _LOGGER.info("Not enough album art URLs (less than 3) for Spotify album art animation.") 
                media_data.spotify_frames = 0
                media_data.spotify_slide_pass = False
                return

            images = []
            for album_url in album_urls:
                try:
                    async with aiohttp.ClientSession() as session:
                        try: 
                            async with session.get(album_url, timeout=10) as response: 
                                response.raise_for_status() 
                                image_data = await response.read()
                                img = Image.open(BytesIO(image_data))
                                img = img.resize((34, 34), Image.Resampling.LANCZOS)
                                images.append(img)
                        except aiohttp.ClientError as e: 
                            _LOGGER.error(f"Error fetching image for Spotify album art animation from URL '{album_url}': {e}") 
                            return 
                except Exception as e: 
                    _LOGGER.error(f"Error decoding or processing image for Spotify album art animation: {e}") 
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
                        except Exception as e: 
                            _LOGGER.error(f"Error pasting image in frame for Spotify album art animation: {e}") 
                            return 

                    base64_image = ImageProcessor(self.config).gbase64(canvas)
                    pixoo_frames.append(base64_image)

                except Exception as e: 
                    _LOGGER.error(f"Error creating frame for Spotify album art animation: {e}") 
                    return # Return if frame creation fails - animation is broken

            pic_offset = 0
            pic_speed = 5000
            _LOGGER.info(f"Sending Spotify album art animation with {total_frames} frames.") 
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
            media_data.spotify_slide_pass = True # Set slide pass to True after successful animation

        except Exception as e: 
            _LOGGER.error(f"Error in Spotify album art animation: {e}") 
            media_data.spotify_frames = 0
            return # Return if animation fails


class Pixoo64_Media_Album_Art(hass.Hass):
    """AppDaemon app to display album art on Divoom Pixoo64 and control related features."""  

    def __init__(self, *args, **kwargs):
        """Initialize Pixoo64_Media_Album_Art app."""
        super().__init__(*args, **kwargs)
        self.clear_timer_task: Optional[asyncio.Task[None]] = None
        self.callback_timeout: int = 20
        self.current_image_task: Optional[asyncio.Task[None]] = None
        


    async def initialize(self):
        _LOGGER.info("Initializing Pixoo64 Album Art Display AppDaemon app…")
        # 1) load your apps.yaml args
        self.config = Config(self.args)
        self.pixoo_device     = PixooDevice(self.config)
        self.image_processor  = ImageProcessor(self.config)
        self.media_data       = MediaData(self.config, self.image_processor)
        self.fallback_service = FallbackService(self.config, self.image_processor)

        self.listen_state(self._mode_changed,      self.config.mode_entity)
        self.listen_state(self._crop_mode_changed, self.config.crop_entity)
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute="media_title")
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute="state")

        self.select_index      = await self.pixoo_device.get_current_channel_index()
        self.media_data_sensor = self.config.pixoo_sensor

        await self._apply_mode_settings()
        await self._apply_crop_settings()

        if self.entity_exists(self.config.lyrics_sync_entity):
            self.config.lyrics_sync = (await self.get_state(self.config.lyrics_sync_entity)) or self.config.lyrics_sync 
            self.listen_state(self._lyrics_sync_changed, self.config.lyrics_sync_entity, attribute="state")

        _LOGGER.info("Initialization complete.")


    async def _lyrics_sync_changed(self, entity, attribute, old, new, kwargs):
        await self._apply_lyrics_sync()

    async def _apply_lyrics_sync(self):
        self.config.lyrics_sync = (await self.get_state(self.config.lyrics_sync_entity))

    async def _crop_mode_changed(self, entity, attribute, old, new, kwargs):
        await self._apply_crop_settings()

    async def _apply_crop_settings(self):
        options = ["Default", "No Crop", "Crop", "Extra Crop"]
        default = options[0]

        # if input_select doesn’t exist yet, create it
        if not self.entity_exists(self.config.crop_entity):
            await self.set_state(self.config.crop_entity, state=options[0], attributes={"options": options})
            await self.call_service(
                "input_select/set_options",
                entity_id=self.config.crop_entity,
                options=options
            )

        else:
            # always keep your options up-to-date
            await self.call_service(
                "input_select/set_options",
                entity_id=self.config.crop_entity,
                options=options
            )
            # read the chosen value (or fall back to default)
            mode = (await self.get_state(self.config.crop_entity)) or default

            m = mode.lower()
            if m == "no crop":
                self.config.crop_borders = False
                self.config.crop_extra   = False
            elif m == "crop":
                self.config.crop_borders = True
                self.config.crop_extra   = False
            elif m == "extra crop":
                self.config.crop_borders = True
                self.config.crop_extra   = True
            elif m =="default":
                self.config.crop_borders = self.config.original_crop_borders
                self.config.crop_extra   = self.config.original_crop_extra

        self.image_processor.image_cache.clear()
        await self.safe_state_change_callback(self.config.media_player, "state", None, "playing", {})


    async def _mode_changed(self, entity, attribute, old, new, kwargs):
        await self._apply_mode_settings()


    async def _apply_mode_settings(self):
        options = [
                "Default",
                "Clean",
                "AI Generation (Flux)",
                "AI Generation (Turbo)",
                "Burned",
                "Burned | Clock",
                "Burned | Clock (Background)",
                "Burned | Temperature",
                "Burned | Temperature (Background)",
                "Burned | Clock & Temperature (Background)",
                "Text",
                "Text (Background)",
                "Clock",
                "Clock (Background)",
                "Clock | Temperature",
                "Clock | Temperature (Background)",
                "Clock | Temperature | Text",
                "Clock | Temperature | Text (Background)",
                "Lyrics",
                "Lyrics (Background)",
                "Temperature",
                "Temperature (Background)",
                "Temperature | Text",
                "Temperature | Text (Background)",
                "Special Mode",
                "Special Mode | Text"
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

            await self.call_service("input_select/set_options", entity_id=self.config.mode_entity, options=options,)

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
                        ai_fallback_engine_turbo = ("turbo" in m) if m else False
                        ai_fallback_engine_flux  = ("flux" in m) if m else False
                        
                        if ai_fallback_engine_turbo:
                            self.config.ai_fallback     = "turbo"
                        elif ai_fallback_engine_flux:
                            self.config.ai_fallback     = "flux"

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
            if not self.entity_exists(self.config.mode_entity):
                _LOGGER.warning(f"You need to create {self.config.mode_entity} as a helper or in configuration.yaml to change settings from HomeAssistant UI")
                return

        if self.config.show_lyrics:
            self.run_every(self.calculate_position, datetime.now(), 1) 


    async def safe_state_change_callback(self, entity: str, attribute: str, old: Any, new: Any, kwargs: Dict[str, Any], timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(total=20)) -> None:
        """Wrapper for state change callback with timeout protection."""
        try:
            async with asyncio.timeout(self.callback_timeout):
            #async with async_timeout.timeout(self.callback_timeout):
                await self.state_change_callback(entity, attribute, old, new, kwargs)
        except asyncio.TimeoutError:
            _LOGGER.warning("Callback timed out after %s seconds - cancelling operation.", self.callback_timeout)
        except Exception as e:
            _LOGGER.error(f"Error in safe_state_change_callback for entity {entity}, attribute {attribute}: {e}")


    async def state_change_callback(self, entity: str, attribute: str, old: Any, new: Any, kwargs: Dict[str, Any]) -> None:
        """Main callback for state change events with early exit conditions."""
        try:
            # Quick checks for early exit
            if new == old or (await self.get_state(self.config.toggle)) != "on":
                return  # Exit early if no change or toggle is off

            media_state_str = await self.get_state(self.config.media_player)
            media_state = media_state_str if media_state_str else "off"
            if media_state in ["off", "idle", "pause", "paused"]:
                await asyncio.sleep(6)  # Delay to not turn off during track changes

                # Quick validation of media state
                media_state_str_validated = await self.get_state(self.config.media_player)
                media_state_validated = media_state_str_validated if media_state_str_validated else "off"
                if media_state_validated not in ["playing", "on"]:
                    pass  # Keep Pixoo off if still not playing
                else:
                    return  # Exit if media player started playing again during delay - avoid turning off Pixoo
                if self.config.full_control:
                    await self.pixoo_device.send_command({
                        "Command": "Draw/CommandList",
                        "CommandList": [
                            {"Command": "Channel/SetIndex", "SelectIndex": self.select_index},
                            {"Command": "Channel/OnOffScreen", "OnOff": 0}
                        ]
                    })
                    _LOGGER.debug("Pixoo device turned OFF due to media player state change to: %s", media_state)
                else:
                    await self.pixoo_device.send_command({
                        "Command": "Draw/CommandList",
                        "CommandList": [
                            {"Command": "Draw/ClearHttpText"},
                            {"Command": "Draw/ResetHttpGifId"},
                            {"Command": "Channel/SetIndex", "SelectIndex": self.select_index}
                        ]
                    })
                    _LOGGER.debug("Pixoo device cleared and reset to channel %s due to media player state change to: %s", self.select_index, media_state)
                await self.set_state(self.media_data_sensor, state="off")
                if self.config.light:
                    await self.control_light('off')
                    _LOGGER.debug("Light control turned OFF due to media player state change to: %s", media_state)
                if self.config.wled:
                    await self.control_wled_light('off')
                    _LOGGER.debug("WLED light control turned OFF due to media player state change to: %s", media_state)
                return  # Exit after handling non-playing state

            # If we get here, proceed with the main logic for "playing" or "on" state
            await self.update_attributes(entity, attribute, old, new, kwargs)

        except Exception as e:
            _LOGGER.error(f"Error in state_change_callback for entity {entity}, attribute {attribute}: {e}")


    async def update_attributes(self, entity: str, attribute: str, old: Any, new: Any, kwargs: Dict[str, Any]) -> None:
        """Update Pixoo display based on media player attributes."""
        try:
            # Quick validation of media state
            media_state_str = await self.get_state(self.config.media_player)
            media_state = media_state_str if media_state_str else "off"
            if media_state not in ["playing", "on"]:
                if self.config.light:
                    await self.control_light('off')
                    _LOGGER.debug("Light control turned OFF in update_attributes due to media player state: %s", media_state)
                if self.config.wled:
                    await self.control_wled_light('off')
                    _LOGGER.debug("WLED light control turned OFF in update_attributes due to media player state: %s", media_state)
                return  # Exit if not playing

            # Get current media data and update
            media_data = await self.media_data.update(self)
            if not media_data:
                _LOGGER.warning("Media data update failed, skipping Pixoo display update.")
                return

            # Proceed with updating Pixoo display
            await self.pixoo_run(media_state, media_data)

        except Exception as e:
            _LOGGER.error(f"Error in update_attributes for entity {entity}, attribute {attribute}: {e}", exc_info=True)


    async def pixoo_run(self, media_state: str, media_data: "MediaData") -> None:
        """Run Pixoo display update with timeout protection."""
        try:
            async with asyncio.timeout(self.callback_timeout):
            #async with async_timeout.timeout(self.callback_timeout):
                # Get current channel index
                self.select_index = await self.pixoo_device.get_current_channel_index()
                #self.select_index = media_data.select_index_original if media_data.select_index_original is not None else self.select_index

                if media_state in ["playing", "on"]:

                    # Cancel any ongoing image processing task
                    if self.current_image_task:
                        self.current_image_task.cancel()
                        self.current_image_task = None  # Reset task after cancellation

                    # Create a new task for image processing
                    self.current_image_task = asyncio.create_task(self._process_and_display_image(media_data))

        except asyncio.TimeoutError:
            _LOGGER.warning("Pixoo run timed out after %s seconds.", self.callback_timeout)
        except Exception as e:
            _LOGGER.error(f"Error in pixoo_run: {e}", exc_info=True)
        finally:
            await asyncio.sleep(0.10)

    async def _process_and_display_image(self, media_data: "MediaData") -> None:
        """Processes image data and sends display commands to Pixoo device."""
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
            _LOGGER.debug("Sent TV ON icon command to Pixoo device.")
            if self.config.light:
                await self.control_light('off')
                _LOGGER.debug("Light control turned OFF for TV mode.")
            if self.config.wled:
                await self.control_wled_light('off')
                _LOGGER.debug("WLED light control turned OFF for TV mode.")
            return  # Exit after handling TV ON icon display

        try:
            start_time = time.perf_counter()
            processed_data = await self.fallback_service.get_final_url(media_data.picture, media_data)

            if not processed_data:
                _LOGGER.warning("Fallback service failed to provide image data, using black screen fallback.")
                processed_data = self.fallback_service._get_fallback_black_image_data()

            media_data.spotify_frames = 0
            base64_image = processed_data.get('base64_image')
            font_color_from_image_processing = processed_data.get('font_color')
            brightness = processed_data.get('brightness')
            # brightness_lower_part = processed_data.get('brightness_lower_part') # Not directly used below
            background_color_str = processed_data.get('background_color')
            background_color_rgb = processed_data.get('background_color_rgb')
            most_common_color_alternative_rgb_str = processed_data.get('most_common_color_alternative_rgb')
            most_common_color_alternative_str = processed_data.get('most_common_color_alternative')


            if self.config.light and not media_data.playing_tv:
                await self.control_light('on', background_color_rgb, media_data.is_night)
                _LOGGER.debug("Light control turned ON, synced with album art colors.")
            if self.config.wled and not media_data.playing_tv:
                color1 = processed_data.get('color1')
                color2 = processed_data.get('color2')
                color3 = processed_data.get('color3')
                await self.control_wled_light('on', color1, color2, color3, media_data.is_night)
                _LOGGER.debug("WLED light control turned ON, synced with album art colors.")
            if media_data.playing_tv:
                if self.config.light:
                    await self.control_light('off')
                    _LOGGER.debug("Light control turned OFF for TV playback mode.")
                if self.config.wled:
                    await self.control_wled_light('off')
                    _LOGGER.debug("WLED light control turned OFF for TV playback mode.")
            
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
            if self.config.spotify_slide and not media_data.radio_logo and not media_data.playing_tv:
                spotify_service = SpotifyService(self.config) 
                spotify_service.spotify_data = await spotify_service.get_spotify_json(media_data.artist, media_data.title)
                if spotify_service.spotify_data:
                    spotify_anim_start_time = time.perf_counter()
                    
                    if self.config.special_mode:
                        if self.config.special_mode_spotify_slider:
                            await spotify_service.spotify_album_art_animation(self.pixoo_device, media_data)
                    else:
                        await spotify_service.spotify_albums_slide(self.pixoo_device, media_data)

                    if media_data.spotify_slide_pass:
                        spotify_animation_took_over_display = True
                        spotify_anim_end_time = time.perf_counter()
                        duration = spotify_anim_end_time - spotify_anim_start_time
                        media_data.process_duration = f"{duration:.2f} seconds (Spotify)"
                        new_attributes["process_duration"] = media_data.process_duration
                        new_attributes["spotify_frames"] = media_data.spotify_frames
                    else:
                        await self.pixoo_device.send_command({"Command": "Channel/SetIndex", "SelectIndex": 4})

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
                    text_overlay_font_color = '#%02x%02x%02x' % color_font_rgb_calc
                except Exception as e:
                    _LOGGER.error(f"Error calculating text_overlay_font_color: {e}")
                    text_overlay_font_color = '#ffff00'
            
            if self.config.special_mode:
                current_text_id += 1
                day_item = {
                    "TextId": current_text_id, "type": 14, "x": 4, "y": 1,
                    "dir": 0, "font": 18, "TextWidth": 33,
                    "Textheight": 6, "speed": 100, "align": 1,
                    "color": text_overlay_font_color}
                text_items_for_display_list.append(day_item)

                current_text_id += 1
                clock_item_special = {
                    "TextId": current_text_id, "type": 5, "x": 0, "y": 1,
                    "dir": 0, "font": 18, "TextWidth": 64,
                    "Textheight": 6, "speed": 100, "align": 2,
                    "color": background_color_str}
                text_items_for_display_list.append(clock_item_special)

                current_text_id += 1
                if media_data.temperature:
                    temp_item_special = {"TextId": current_text_id, "type": 22, "x": 46, "y": 1,
                                    "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6,
                                    "speed": 100, "align": 1, "color": text_overlay_font_color, 
                                    "TextString": media_data.temperature}
                else:
                    temp_item_special = {"TextId": current_text_id, "type": 17, "x": 46, "y": 1,
                                    "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6,
                                    "speed": 100, "align": 3, "color": text_overlay_font_color}
                text_items_for_display_list.append(temp_item_special)

                if (self.config.show_text and not media_data.playing_tv) or \
                    (media_data.spotify_slide_pass and self.config.spotify_slide):
                    dir_rtl_artist = 1 if has_bidi(media_data.artist) else 0
                    text_artist_bidi = get_bidi(media_data.artist) if dir_rtl_artist == 1 else media_data.artist
                    current_text_id += 1
                    artist_item = {
                        "TextId": current_text_id, "type": 22, "x": 0, "y": 42,
                        "dir": dir_rtl_artist, "font": 190, "TextWidth": 64,
                        "Textheight": 16, "speed": 100, "align": 2,
                        "TextString": text_artist_bidi, "color": text_overlay_font_color}
                    text_items_for_display_list.append(artist_item)

                    dir_rtl_title = 1 if has_bidi(media_data.title) else 0
                    text_title_bidi = get_bidi(media_data.title) if dir_rtl_title == 1 else media_data.title
                    current_text_id += 1
                    title_item = {
                        "TextId": current_text_id, "type": 22, "x": 0, "y": 52, "dir": dir_rtl_title,
                        "font": 190, "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 2,
                        "TextString": text_title_bidi, "color": background_color_str}
                    text_items_for_display_list.append(title_item)
            
            elif (self.config.show_text or self.config.show_clock or self.config.temperature) and \
                not (self.config.show_lyrics or self.config.spotify_slide):
                
                text_track = (media_data.artist + " - " + media_data.title)
                if len(text_track) > 14: text_track = text_track + "       "
                text_string_bidi = get_bidi(text_track) if media_data.artist else get_bidi(media_data.title)
                dir_rtl = 1 if has_bidi(text_string_bidi) else 0

                if text_string_bidi and self.config.show_text and not media_data.radio_logo and not media_data.playing_tv:
                    current_text_id += 1
                    text_item = {
                        "TextId": current_text_id, "type": 22, "x": 0, "y": 48,
                        "dir": dir_rtl, "font": 2, "TextWidth": 64, "Textheight": 16,
                        "speed": 100, "align": 2, "TextString": text_string_bidi, "color": text_overlay_font_color
                    }
                    text_items_for_display_list.append(text_item)

                if self.config.show_clock:
                    current_text_id += 1
                    x_clock = 44 if self.config.clock_align == "Right" else 3
                    clock_item_normal = {
                        "TextId": current_text_id, "type": 5, "x": x_clock, "y": 3,
                        "dir": 0, "font": 18, "TextWidth": 32, "Textheight": 16,
                        "speed": 100, "align": 1, "color": text_overlay_font_color
                    }
                    text_items_for_display_list.append(clock_item_normal)

                if self.config.temperature:
                    current_text_id += 1
                    x_temp = 3 if self.config.clock_align == "Right" else 40
                    if media_data.temperature:
                        temp_item_normal = {"TextId": current_text_id, "type": 22, "x": x_temp, "y": 3,
                                            "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6,
                                            "speed": 100, "align": 1, "color": text_overlay_font_color, 
                                            "TextString": media_data.temperature}
                    else:
                        temp_item_normal = {"TextId": current_text_id, "type": 17, "x": x_temp, "y": 3,
                                            "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6,
                                            "speed": 100, "align": 1, "color": text_overlay_font_color}
                    text_items_for_display_list.append(temp_item_normal)

            if not spotify_animation_took_over_display:
                await self.pixoo_device.send_command(image_payload)
                if text_items_for_display_list:
                    txt_payload = ({
                        "Command": "Draw/SendHttpItemList",
                        "ItemList": text_items_for_display_list
                    })
                    await asyncio.sleep(0.10)
                    await self.pixoo_device.send_command(txt_payload)
                
                _LOGGER.debug("Sent album art image payload (possibly with additional info) to Pixoo device.")

            elif spotify_animation_took_over_display and self.config.special_mode and text_items_for_display_list:
                await self.pixoo_device.send_command({
                    "Command": "Draw/SendHttpItemList",
                    "ItemList": text_items_for_display_list
                })
                _LOGGER.debug("Sent special mode info payload after Spotify slide to Pixoo device.")
            
            end_time = time.perf_counter()
            if not spotify_animation_took_over_display:
                duration = end_time - start_time
                media_data.process_duration = f"{duration:.2f} seconds"
            
            new_attributes["process_duration"] = media_data.process_duration
            new_attributes["spotify_frames"] = media_data.spotify_frames
            await self.set_state(self.media_data_sensor, state=sensor_state, attributes=new_attributes)

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
                _LOGGER.info("Ultimate fallback black screen and text displayed on Pixoo device.")
                return

        except asyncio.CancelledError:
            _LOGGER.info("Image processing task cancelled.")
        except Exception as e:
            _LOGGER.error(f"Error in _process_and_display_image: {e}", exc_info=True)
        finally:
            self.current_image_task = None

    def compute_opposite_color(self, color: tuple[int,int,int]) -> tuple[int,int,int]:
    # real complement (WCAG “opposite”)
        return tuple(255 - c for c in color)


    async def control_light(self, action: str, background_color_rgb: Optional[tuple[int, int, int]] = None, is_night: bool = True) -> None:
        """Control Home Assistant light based on album art colors."""
        if not is_night and self.config.only_at_night:
            return  # Exit if not night and only_at_night is configured
        service_data = {'entity_id': self.config.light}
        if action == 'on':
            service_data.update({'rgb_color': background_color_rgb, 'transition': 1, })
            _LOGGER.debug("Turning ON Home Assistant light '%s' with RGB color: %s", self.config.light, background_color_rgb)
        else:  # Action is 'off'
            _LOGGER.debug("Turning OFF Home Assistant light '%s'.", self.config.light)
        try:
            await self.call_service(f'light/turn_{action}', **service_data)  # Call light service
        except Exception as e:
            _LOGGER.error(f"Error controlling Home Assistant light '{self.config.light}': {e}", exc_info=True)


    async def control_wled_light(self, action: str, color1: Optional[str] = None, color2: Optional[str] = None, color3: Optional[str] = None, is_night: bool = True) -> None:
        """Control WLED light based on album art colors."""
        # Ensure we control the light only if time conditions and settings allow
        if not is_night and self.config.only_at_night:
            return  # Exit if not night and only_at_night is configured

        ip_address = self.config.wled

        if not ip_address:
            _LOGGER.warning("IP address for WLED light control is not configured or invalid.")
            return  # Exit if no IP address

        effect_id = self.config.effect
        # Validate the effect ID
        if not (0 <= effect_id <= 186):
            _LOGGER.error(f"Invalid WLED effect ID: {effect_id}. Must be between 0 and 186.")  # Error log if effect ID invalid
            return  # Exit if invalid effect ID

        # Prepare the segment dictionary based on effect requirements
        segment = {"fx": effect_id}
        colors = [c.lstrip('#') for c in [color1, color2, color3] if c]
        if colors:
            if effect_id == 0:  # Solid effect uses only one color
                segment["col"] = [colors[0]]  # Use only the first color
            else:
                segment["col"] = colors


        if self.config.effect_speed:
            segment["sx"] = self.config.effect_speed

        if self.config.effect_intensity:
            segment["ix"] = self.config.effect_intensity

        if self.config.palette:
            segment["pal"] = self.config.palette

        if self.config.sound_effect:
            segment["si"] = self.config.sound_effect

        # Prepare the JSON payload
        payload = {"on": True, "bri": self.config.brightness, "seg": [segment]}

        if action == "off":  # Action is 'off'
            payload = {"on": False}  # Off action simply turns off the light
            _LOGGER.debug("Turning OFF WLED light '%s'.", ip_address)
        else:  # Action is 'on'
            _LOGGER.info("Turning ON WLED light '%s' with effect ID: %s, colors: %s, %s, %s.", ip_address, effect_id, color1, color2, color3)

        url = f"http://{ip_address}/json/state"
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            try:
                async with session.post(url, json=payload, timeout=10) as response:
                    response.raise_for_status()  # Raise an error for bad status codes
            except aiohttp.ClientError as e:
                _LOGGER.error(f"Error sending WLED control command to '{ip_address}': {e}")


    def create_payloads(self, artist: str, title: str, line_length: int) -> dict:
        """Create text payloads for Pixoo device (fallback text display)."""
        artist_lines = split_string(artist, line_length)
        title_lines = split_string(title, line_length)
        all_lines = artist_lines + title_lines
        moreinfo = {
            "Command": "Draw/SendHttpItemList",
            "ItemList": []
        }
        if len(all_lines) > 5:  # Limit to 5 lines as per typical Pixoo display for fallback text
            all_lines = all_lines[:5]

        start_y = (64 - len(all_lines) * 12) // 2
        item_list = []
        for i, line in enumerate(all_lines):
            text_string = get_bidi(line) if has_bidi(line) else line
            y = start_y + (i * 12)
            dir_rtl = 1 if has_bidi(line) else 0
            item_list.append({
                "TextId": i + 1, "type": 22,
                "x": 0, "y": y,
                "dir": dir_rtl, "font": 190,  # Using font 190 as per special mode
                "TextWidth": 64, "Textheight": 16,
                "speed": 100, "align": 2,
                "TextString": text_string,
                "color": "#a0e5ff" if i < len(artist_lines) else "#f9ffa0",  # Using different colors for artist/title
            })

        payloads = {
            "Command": "Draw/SendHttpItemList",
            "ItemList": item_list
        }
        _LOGGER.debug("Created fallback text payload for Pixoo device.")
        return payloads


    async def calculate_position(self, kwargs: Dict[str, Any]) -> None:
        """Wrapper to call LyricsProvider's calculate_position method."""
        await LyricsProvider(self.config, self.image_processor).calculate_position(self.media_data, self)
