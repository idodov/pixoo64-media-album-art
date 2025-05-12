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
        mode_select: "input_select.pixoo64_album_art_display_mode" # A sensor to store display modes

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
import async_timeout
import base64
import json
import logging
import math
import random
import re
import sys
import time
import traceback
from appdaemon.plugins.hass import hassapi as hass
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

# Third-party library imports
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw

try:
    from bidi import get_display
    bidi_support = True
except ImportError:
    bidi_support = False
    print("The 'bidi.algorithm' module is not installed or not available. RTL texts will display reversed.")

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
_LOGGER = logging.getLogger(__name__)

# Constants
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
        _LOGGER.error("To display RTL text you need to add bidi-algorithm package.")
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
    except (PIL.UnidentifiedImageError, OSError) as e: 
        _LOGGER.error(f"Error converting image to RGB: {e}", exc_info=True) 
        return None


class Config:
    def __init__(self, app_args: Dict[str, Any]): 
        """Initialize Config object with arguments from AppDaemon."""
        ha_config = app_args.get('home_assistant', {})
        wled_light = app_args.get('wled', {})
        pixoo_config = app_args.get('pixoo', {})
        show_text_config = pixoo_config.get('show_text', {})
        crop_borders_config = pixoo_config.get('crop_borders', {})

        # Home Assistant settings
        self.media_player: str = ha_config.get("media_player", "media_player.living_room")
        self.toggle: str = ha_config.get("toggle", "input_boolean.pixoo64_album_art")
        self.ha_url: str = ha_config.get("ha_url", "http://homeassistant.local:8123")
        self.pixoo_sensor: str = ha_config.get("pixoo_sensor", "sensor.pixoo64_media_data")
        self.mode_entity: str = ha_config.get("mode_select", "input_select.pixoo64_album_art_display_mode")

        self.ha_temperature: Optional[str] = ha_config.get("temperature_sensor") 
        self.light: Optional[str] = ha_config.get("light") 
        self.force_ai: bool = ha_config.get("force_ai", False)

        # AI and Fallback services settings
        self.ai_fallback: str = ha_config.get("ai_fallback", 'turbo')
        self.musicbrainz: bool = ha_config.get("musicbrainz", True)
        self.spotify_client_id: Optional[str] = ha_config.get("spotify_client_id") 
        self.spotify_client_secret: Optional[str] = ha_config.get("spotify_client_secret") 
        self.tidal_client_id: Optional[str] = ha_config.get("tidal_client_id") 
        self.tidal_client_secret: Optional[str] = ha_config.get("tidal_client_secret") 
        self.discogs: Optional[str] = ha_config.get("discogs") 
        self.lastfm: Optional[str] = ha_config.get("last.fm") 

        # Pixoo device settings
        pixoo_url_raw: str = pixoo_config.get("url", "192.168.86.21") 
        self.full_control: bool = pixoo_config.get("full_control", True)
        self.contrast: bool = pixoo_config.get("contrast", False)
        self.sharpness: bool = pixoo_config.get("sharpness", False)
        self.colors: bool = pixoo_config.get("colors", False)
        self.kernel: bool = pixoo_config.get("kernel", False)

        self.special_mode: bool = pixoo_config.get("special_mode", False)
        self.info: bool = pixoo_config.get("info", False)
        self.show_clock: bool = pixoo_config.get("clock", False)
        self.clock_align: str = pixoo_config.get("clock_align", "Right")
        self.temperature: bool = pixoo_config.get("temperature", False)
        self.tv_icon_pic: bool = pixoo_config.get("tv_icon", True)
        self.spotify_slide: bool = pixoo_config.get("spotify_slide", False)
        self.images_cache: int = max(1, min(int(pixoo_config.get("images_cache", 10)), 100))

        # Text display settings
        self.limit_color: Optional[int] = pixoo_config.get("limit_colors") 
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
        self.wled: Optional[str] = wled_light.get("wled_ip") 
        self.wled_brightness: int = wled_light.get("brightness", 255)
        self.wled_effect: int = wled_light.get("effect", 38)
        self.wled_effect_speed:  int = wled_light.get("effect_speed", 60)
        self.wled_effect_intensity: int = wled_light.get("effect_intensity", 128)
        self.wled_only_at_night: bool = wled_light.get("only_at_night", False)
        self.wled_pallete: int = wled_light.get("pallete", 0)
        self.wled_sound_effect: int = max(0, min(int(wled_light.get("sound_effect", 0)), 3))

        # Fixing args if needed
        self._fix_config_args(pixoo_url_raw)
        self._validate_config()


        # Saving original configuration
        self.original_show_lyrics     = self.show_lyrics
        self.original_spotify_slide   = self.spotify_slide
        self.original_special_mode    = self.special_mode
        self.original_special_mode_spotify_slider = self.special_mode_spotify_slider
        self.original_show_clock      =  self.show_clock
        self.original_temperature     = self.temperature
        self.original_show_text       = self.show_text
        self.original_text_bg         = self.text_bg
        self.original_force_ai        = self.force_ai



    def _fix_config_args(self, pixoo_url_raw: str): 
        """Fixes and formats configuration arguments."""
        pixoo_url = f"http://{pixoo_url_raw}" if not pixoo_url_raw.startswith('http') else pixoo_url_raw 
        self.pixoo_url: str = f"{pixoo_url}:80/post" if not pixoo_url.endswith(':80/post') else pixoo_url

        if self.ai_fallback not in ["flux", "turbo"]:
            self.ai_fallback = "turbo"


    def _validate_config(self):
        """Validates configuration parameters and logs warnings/errors if needed."""
        if not self.ha_url:
            _LOGGER.warning("Home Assistant URL (`ha_url`) is not configured. Defaulting to 'http://homeassistant.local:8123'.")
        if not self.media_player:
            _LOGGER.warning("Media player entity (`media_player`) is not configured. Defaulting to 'media_player.living_room'.")
        if not self.pixoo_url:
            _LOGGER.error("Pixoo URL (`pixoo_url`) is not configured. This is required for the script to function.")
        if self.images_cache <= 0:
            _LOGGER.warning(f"Invalid `images_cache` value: {self.images_cache}. Defaulting to 1.")
            self.images_cache = 1
        if not (0 <= self.wled_brightness <= 255):
            _LOGGER.warning(f"Invalid WLED brightness value: {self.wled_brightness}. Value should be between 0 and 255. Defaulting to 255.")
            self.wled_brightness = 255
        if not (0 <= self.wled_effect <= 186): 
            _LOGGER.warning(f"Invalid WLED effect value: {self.wled_effect}. Value should be between 0 and 186. Defaulting to 38.")
            self.wled_effect = 38
        if not (0 <= self.wled_effect_speed <= 255):
            _LOGGER.warning(f"Invalid WLED effect speed value: {self.wled_effect_speed}. Value should be between 0 and 255. Defaulting to 60.")
            self.wled_effect_speed = 60
        if not (0 <= self.wled_effect_intensity <= 255):
            _LOGGER.warning(f"Invalid WLED effect intensity value: {self.wled_effect_intensity}. Value should be between 0 and 255. Defaulting to 128.")
            self.wled_effect_intensity = 128
        if not (0 <= self.wled_pallete <= 70): 
            _LOGGER.warning(f"Invalid WLED pallete value: {self.wled_pallete}. Value should be between 0 and 70. Defaulting to 0.")
            self.wled_pallete = 0
        if not (0 <= self.wled_sound_effect <= 3):
            _LOGGER.warning(f"Invalid WLED sound effect value: {self.wled_sound_effect}. Value should be between 0 and 3. Defaulting to 0.")
            self.wled_sound_effect = 0
        if self.clock_align not in ["Left", "Right"]:
            _LOGGER.warning(f"Invalid clock alignment value: {self.clock_align}. Defaulting to 'Right'.")
            self.clock_align = "Right"
        if self.ai_fallback not in ["flux", "turbo"]:
            _LOGGER.warning(f"Invalid AI fallback model: {self.ai_fallback}. Defaulting to 'turbo'.")
            self.ai_fallback = "turbo"
        if self.lyrics_font not in [2, 4, 32, 52, 58, 62, 48, 80, 158, 186, 190, 590]: 
            _LOGGER.warning(f"Lyrics font ID: {self.lyrics_font} might not be optimal. Recommend values: 2, 4, 32, 52, 58, 62, 48, 80, 158, 186, 190, 590. Check Divoom documentation for more.")


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
                        await asyncio.sleep(0.15) # Consider making this sleep configurable
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
                    size += sys.getsizeof(value)  # Account for tuples
                elif isinstance(value, list):
                    for list_item in value:
                        size += sys.getsizeof(list_item) # Account for lists
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
        use_cache = cache_key is not None # Explicitly check for None
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
        if use_cache and cache_key in self.image_cache and not spotify_slide and not media_data.playing_tv:
            _LOGGER.debug(f"Image found in cache for album: {cache_key}") 
            cached_item = self.image_cache.pop(cache_key)
            self.image_cache[cache_key] = cached_item
            return cached_item

        try:
            async with aiohttp.ClientSession() as session:
                url = picture if picture.startswith('http') else f"{self.config.ha_url}{picture}"
                try: 
                    async with session.get(url, timeout=10) as response: 
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


    def crop_image_borders(self, img: Image.Image, radio_logo: bool) -> Image.Image: 
        """Crop borders from the image, or return original if radio logo."""
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

    def get_dominant_border_color(self, img: Image.Image) -> tuple[int, int, int]: 
        """Get the dominant color from the image borders."""
        width, height = img.size
        top_row = img.crop((0, 0, width, 1))
        bottom_row = img.crop((0, height - 1, width, height))
        left_col = img.crop((0, 0, 1, height))
        right_col = img.crop((width - 1, 0, width, height))

        all_border_pixels = []
        all_border_pixels.extend(list(top_row.getdata())) 
        all_border_pixels.extend(list(bottom_row.getdata())) 
        all_border_pixels.extend(list(left_col.getdata())) 
        all_border_pixels.extend(list(right_col.getdata())) 

        return max(set(all_border_pixels), key=all_border_pixels.count) if all_border_pixels else (0, 0, 0)


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

        if self.config.show_clock and not self.config.show_lyrics:
            lpc = (43, 2, 62, 9) if self.config.clock_align == "Right" else (2, 2, 21, 9)
            lower_part_img = img.crop(lpc)
            enhancer_lp = ImageEnhance.Brightness(lower_part_img)
            lower_part_img = enhancer_lp.enhance(0.3)
            img.paste(lower_part_img, lpc)

        #if (self.config.temperature or media_data.temperature) and not self.config.show_lyrics:
        if self.config.temperature and not self.config.show_lyrics:
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
        """Convert RGB tuple to hex color string."""
        return '{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])

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

            title = self.clean_title(title) if self.config.clean_title_enabled else title

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

            if self.config.ha_temperature:
                temperature = await hass.get_state(self.config.ha_temperature)
                temperature_unit = await hass.get_state(self.config.ha_temperature, attribute="unit_of_measurement") # Get unit separately
                try:
                    temperature_val = float(temperature) if temperature else None # Handle None temperature value
                    if temperature_val is not None and temperature_unit: # Check for both value and unit
                        self.temperature = f"{int(temperature_val)}{temperature_unit.lower()}"
                    else:
                        self.temperature = None # Reset to None if no valid temp or unit
                except (ValueError, TypeError): # Catch potential conversion errors
                    self.temperature = None
                    _LOGGER.warning(f"Could not parse temperature value '{temperature}' from {self.config.ha_temperature}.") # Log warning if parsing fails

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
        return prompt


    def clean_title(self, title: str) -> str: 
        """Clean up the title by removing common patterns."""
        if not title:
            return title

        # Patterns to remove
        patterns = [
            r'\([^)]*remaster(ed)?\s*[^)]*\)',
            r'\([^)]*remix(ed)?\s*[^)]*\)',
            r'\([^)]*version\s*[^)]*\)',
            r'\([^)]*edit\s*[^)]*\)',
            r'\([^)]*live\s*[^)]*\)',
            r'\([^)]*bonus\s*[^)]*\)',
            r'\([^)]*deluxe\s*[^)]*\)',
            r'\([^)]*\d{4}\)', 
            r'^\d+\s*[\.-]\s*',
            r'\.(mp3|m4a|wav|flac)$',
        ]

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


    async def get_lyrics(self, artist: Optional[str], title: str) -> list[dict]: 
        """Fetch lyrics for the given artist and title from Textyl API."""
        lyrics_url = f"http://api.textyl.co/api/lyrics?q={artist} - {title}"
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                try: 
                    async with session.get(lyrics_url, timeout=10) as response: 
                        response.raise_for_status() 
                        lyrics_data = await response.json()
                        # Store the lyrics and seconds in a list of dictionaries
                        processed_lyrics = [{'seconds': line['seconds'], 'lyrics': line['lyrics']} for line in lyrics_data] 
                        self.lyrics = processed_lyrics
                        _LOGGER.info(f"Successfully retrieved lyrics for '{artist} - {title}' from Textyl API.") 
                        return processed_lyrics
                except aiohttp.ClientError as e: 
                    _LOGGER.error(f"Textyl API request failed for '{artist} - {title}': {e}") 
                    self.lyrics = [] # Reset lyrics on failure
                    return []  # Reset lyrics if fetching fails
                except json.JSONDecodeError as e: 
                    _LOGGER.error(f"Textyl API JSON decode error for '{artist} - {title}': {e}") 
                    self.lyrics = [] # Reset lyrics on failure
                    return []
        except asyncio.TimeoutError:
            _LOGGER.warning(f"Textyl API request timed out for '{artist} - {title}'.") 
            self.lyrics = [] # Reset lyrics on timeout
            return []
        except Exception as e: 
            _LOGGER.error(f"Error fetching lyrics for '{artist} - {title}' from Textyl API: {e}") 
            self.lyrics = [] # Reset lyrics on error
            return [] # Reset lyrics on error


    async def calculate_position(self, media_data: "MediaData", hass: "hass.Hass") -> None: 
        """Calculate and display lyrics based on media position."""
        if not media_data.lyrics:
            return

        if media_data.media_position_updated_at:
            media_position_updated_at = media_data.media_position_updated_at
            current_time = datetime.now(timezone.utc)
            time_diff = (current_time - media_position_updated_at).total_seconds()
            current_position = media_data.media_position + time_diff
            current_position = min(current_position, media_data.media_duration)
            current_position_int = int(current_position) 
            if current_position_int is not None and media_data.lyrics and self.config.show_lyrics:
                for i, lyric_item in enumerate(media_data.lyrics): 
                    lyric_time = lyric_item['seconds']

                    if current_position_int == lyric_time - 1: # Compare integer positions
                        await self.create_lyrics_payloads(lyric_item['lyrics'], 10, media_data.lyrics_font_color) # Pass lyrics_font_color

                        next_lyric_time = media_data.lyrics[i + 1]['seconds'] if i + 1 < len(media_data.lyrics) else None
                        lyrics_display_duration = (next_lyric_time - lyric_time) if next_lyric_time else 10
                        if lyrics_display_duration > 9: 
                            x = int(self.len_lines * 1.6)
                            await asyncio.sleep(x) 
                            await PixooDevice(self.config).send_command({"Command": "Draw/ClearHttpText"}) 

                        break # Exit loop after displaying lyrics



    async def create_lyrics_payloads(self, lyrics: str, line_length: int, lyrics_font_color: str) -> None: 
        """Create and send lyrics payloads to Pixoo device."""
        if not lyrics:
            return # Early exit if no lyrics

        all_lines = split_string(get_bidi(lyrics) if has_bidi(lyrics) else lyrics, line_length) # Use line_length parameter

        if len(all_lines) > 6: # Limit to 6 lines as per typical Pixoo display
            all_lines = all_lines[:6] # Keep only first 6 lines
        self.len_lines = len(all_lines)
        font_height = 10 if len(all_lines) == 6 else 12
        item_list = []
        start_y = (64 - len(all_lines) * font_height) // 2

        for i, line in enumerate(all_lines):
            y = start_y + (i * font_height)
            dir_rtl = 1 if has_bidi(line) else 0 
            item_list.append({
                "TextId": i + 1, "type": 22,
                "x": 0, "y": y,
                "dir": dir_rtl, "font": self.config.lyrics_font,
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
            album_base64 = []
            show_lyrics_is_on = True if media_data.lyrics else False
            playing_radio_is_on = True if media_data.playing_radio else False

            for album in sorted_albums:
                images = album.get("images", [])
                if images:
                    album_urls.append(images[0]["url"])
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
            _LOGGER.info("Not enough album art URLs (less than 2) for Spotify slide animation.") 
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
                    pic_id=1,
                    pic_speed=pic_speed,
                    pic_data=frame
                )

                pic_offset += 1
            media_data.spotify_slide_pass = True # Set slide pass to True after successful animation

        except Exception as e: 
            _LOGGER.error(f"Error in Spotify album art animation: {e}") 
            media_data.spotify_frames = 0
            return # Return if animation fails


    async def create_album_slider(self, media_data: "MediaData") -> Optional[Image.Image]: 
        """Creates a horizontal album slider PIL Image."""
        album_urls = await self.get_album_list(media_data, returntype="url")
        if not album_urls or len(album_urls) < 3:
            _LOGGER.info("Not enough albums (less than 3) to create Spotify album slider.") 
            return None

        album_urls = album_urls[:10]  # Limit to 10 albums for slider
        canvas_width = 34 * (len(album_urls))
        canvas = Image.new("RGB", (canvas_width, 64), (0, 0, 0))

        for i, album_url in enumerate(album_urls):
            try:
                async with aiohttp.ClientSession() as session:
                    try: 
                        async with session.get(album_url, timeout=10) as response: 
                            response.raise_for_status() 
                            image_data = await response.read()
                            img = Image.open(BytesIO(image_data))
                            img = img.resize((34, 34), Image.Resampling.LANCZOS)
                            canvas.paste(img, (34 * i, 8))
                    except aiohttp.ClientError as e: 
                        _LOGGER.error(f"Error fetching image for Spotify album slider from URL '{album_url}': {e}") 
                        return None # Return None if image fetch fails - slider cannot be created
            except Exception as e: 
                _LOGGER.error(f"Error processing image for Spotify album slider: {e}") 
                return None # Return None if image processing fails - slider cannot be created

        _LOGGER.debug("Successfully created Spotify album slider image.") 
        return canvas


    async def create_slider_animation(self, media_data: "MediaData") -> Optional[list[str]]: 
        """Creates frames for horizontal album slider animation."""
        canvas = await self.create_album_slider(media_data)
        if not canvas:
            return None # Return None if canvas creation failed

        frames = []
        total_frames = (canvas.width) // 3  # Move 3 pixels per frame - Adjust as needed
        for i in range(total_frames):
            frame = canvas.crop((i * 3, 0, i * 3 + 64, 64))
            frame = frame.resize((64, 64), Image.Resampling.LANCZOS)
            base64_image = ImageProcessor(self.config).gbase64(frame)
            frames.append(base64_image)

        _LOGGER.debug(f"Created {len(frames)} frames for Spotify album slider animation.") 
        return frames


    async def send_slider_animation(self, pixoo_device: "PixooDevice", media_data: "MediaData") -> None: 
        """Sends slider animation frames to Pixoo device."""
        media_data.spotify_slide_pass = False # Reset slide pass status
        frames = await self.create_slider_animation(media_data)
        if not frames:
            _LOGGER.warning("No frames generated for Spotify slider animation, cannot send animation.") 
            return # Exit if no frames

        await pixoo_device.send_command({"Command": "Draw/CommandList", "CommandList":
            [{"Command": "Channel/OnOffScreen", "OnOff": 1}, {"Command": "Draw/ResetHttpGifId"}]})

        pic_offset = 0
        _LOGGER.info(f"Sending Spotify slider animation with {len(frames)} frames.") 
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
        media_data.spotify_slide_pass = True # Set slide pass to True after successful animation

class Pixoo64_Media_Album_Art(hass.Hass):
    """AppDaemon app to display album art on Divoom Pixoo64 and control related features."""  # Class docstring is excellent

    def __init__(self, *args, **kwargs):
        """Initialize Pixoo64_Media_Album_Art app."""
        super().__init__(*args, **kwargs)
        self.clear_timer_task: Optional[asyncio.Task[None]] = None
        self.callback_timeout: int = 20
        self.current_image_task: Optional[asyncio.Task[None]] = None

    async def initialize(self) -> None:
        """Initialize the app, load configuration, and set up state listeners."""
        _LOGGER.info("Initializing Pixoo64 Album Art Display AppDaemon app...")
        # Load configuration
        self.config = Config(self.args)
        self.pixoo_device = PixooDevice(self.config)
        self.image_processor = ImageProcessor(self.config)
        self.media_data = MediaData(self.config, self.image_processor)
        self.fallback_service = FallbackService(self.config, self.image_processor)

        # Set up state listeners
        self.listen_state(self._mode_changed, self.config.mode_entity)
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute='media_title')
        self.listen_state(self.safe_state_change_callback, self.config.media_player, attribute='state')
        if self.config.show_lyrics:
            self.run_every(self.calculate_position, datetime.now(), 1)  # Consider making run_every interval configurable

        self.select_index = await self.pixoo_device.get_current_channel_index()
        self.media_data_sensor: str = self.config.pixoo_sensor  # State sensor
        await self._apply_mode_settings()


        _LOGGER.info("Pixoo64 Album Art Display AppDaemon app initialization complete.")

    async def _mode_changed(self, entity, attribute, old, new, kwargs):
        await self._apply_mode_settings()


    async def _apply_mode_settings(self):
        mode = await self.get_state(self.config.mode_entity)
        options = [
                "Default",
                "AI Generation",
                "Text only",
                "Text with Background",
                "Clock only",
                "Clock and Temperature",
                "Clock Temperature and Text",
                "Clock Temperature and Text with Background",
                "Lyrics",
                "Lyrics with Background",
                "Temperature only",
                "Temperature and Text",
                "Temperature and Text with Background",
                "Special Mode",
                "Special Mode with Text",
                "Spotify Slider"
                ]
        if mode:
            m = mode.lower()
            if not m == "default":
                # map the input_select to your Config flags:
                self.config.show_lyrics     = ("lyrics" in m) if m else False
                self.config.spotify_slide   = ("slider" in m) if m else False
                self.config.special_mode    = ("special" in m) if m else False
                self.config.show_clock      = ("clock" in m) if m else False
                self.config.temperature     = ("temperature" in m) if m else False
                self.config.show_text       = ("text" in m) if m else False
                self.config.text_bg         = ("background" in m) if m else False
                self.config.force_ai        = ("ai" in m) if m else False
                self.config.special_mode_spotify_slider = (self.config.spotify_slide and self.config.special_mode and self.config.show_text)
            else:
                self.config.show_lyrics = self.config.original_show_lyrics
                self.config.spotify_slide = self.config.original_spotify_slide
                self.config.special_mode = self.config.original_special_mode
                self.config.show_clock = self.config.original_show_clock
                self.config.temperature = self.config.original_temperature
                self.config.show_text = self.config.original_show_text
                self.config.text_bg = self.config.original_text_bg
                self.config.force_ai = self.config.original_force_ai
                self.config.special_mode_spotify_slider = self.config.original_special_mode_spotify_slider
                self.set_state(self.config.mode_entity, state=options[0], attributes={"options": options})
        else:
            self.set_state(self.config.mode_entity, state=options[0], attributes={"options": options})
        
        if self.config.show_lyrics:
            self.run_every(self.calculate_position, datetime.now(), 1)  # Consider making run_every interval configurable


    async def safe_state_change_callback(self, entity: str, attribute: str, old: Any, new: Any, kwargs: Dict[str, Any], timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(total=20)) -> None:
        """Wrapper for state change callback with timeout protection."""
        try:
            #async with asyncio.timeout(self.callback_timeout):
            async with async_timeout.timeout(self.callback_timeout):
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
            #async with asyncio.timeout(self.callback_timeout):
            async with async_timeout.timeout(self.callback_timeout):
                # Get current channel index
                self.select_index = await self.pixoo_device.get_current_channel_index()
                self.select_index = media_data.select_index_original if media_data.select_index_original is not None else self.select_index

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
            font_color = processed_data.get('font_color')
            brightness = processed_data.get('brightness')
            brightness_lower_part = processed_data.get('brightness_lower_part')
            background_color = processed_data.get('background_color')
            background_color_rgb = processed_data.get('background_color_rgb')
            most_common_color_alternative_rgb = processed_data.get('most_common_color_alternative_rgb')
            most_common_color_alternative = processed_data.get('most_common_color_alternative')

            if self.config.light and not media_data.playing_tv:
                await self.control_light('on', background_color_rgb, media_data.is_night)
                _LOGGER.debug("Light control turned ON, synced with album art colors.")
            if self.config.wled and not media_data.playing_tv:
                # Retrieve cached color values - already retrieved from processed_data
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
                "pixoo_channel": self.select_index,
                "image_source": media_data.pic_source,
                "image_url": media_data.pic_url
            }

            payload = {
                "Command": "Draw/CommandList",
                "CommandList": [
                    {"Command": "Channel/OnOffScreen", "OnOff": 1},
                    {"Command": "Draw/ClearHttpText"},
                    {"Command": "Draw/ResetHttpGifId"},
                    {"Command": "Draw/SendHttpGif",
                        "PicNum": 1, "PicWidth": 64, "PicOffset": 0,
                        "PicID": 0, "PicSpeed": 10000, "PicData": base64_image}]}

            if self.config.spotify_slide and not media_data.radio_logo and not media_data.playing_tv:
                spotify_service = SpotifyService(self.config)
                spotify_service.spotify_data = await spotify_service.get_spotify_json(media_data.artist, media_data.title)
                if spotify_service.spotify_data:
                    start_time = time.perf_counter()
                    media_data.spotify_frames = 0

                    if self.config.special_mode:
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
                        await self.pixoo_device.send_command({"Command": "Channel/SetIndex", "SelectIndex": 4})  # Avoid Animation Glitch

            if not media_data.spotify_slide_pass:
                await self.pixoo_device.send_command(payload)
                _LOGGER.debug("Sent album art image payload to Pixoo device.")

            end_time = time.perf_counter()
            duration = end_time - start_time
            media_data.process_duration = f"{duration:.2f} seconds"
            new_attributes["process_duration"] = media_data.process_duration
            await self.set_state(self.media_data_sensor, state="on", attributes=new_attributes)

            if self.fallback_service.fail_txt and self.fallback_service.fallback:
                black_img = self.fallback_service.create_black_screen()
                black_pic = self.image_processor.gbase64(black_img)
                payload_fail = {
                    "Command": "Draw/CommandList",
                    "CommandList": [
                        {"Command": "Channel/OnOffScreen", "OnOff": 1},
                        {"Command": "Draw/ResetHttpGifId"},
                    ]
                }
                await self.pixoo_device.send_command(payload_fail)
                await self.pixoo_device.send_command({
                    "Command": "Draw/SendHttpGif",
                    "PicNum": 1, "PicWidth": 64,
                    "PicOffset": 0, "PicID": 0,
                    "PicSpeed": 1000, "PicData": black_pic
                })
                payloads = self.create_payloads(media_data.artist, media_data.title, 11)
                await self.pixoo_device.send_command(payloads)
                _LOGGER.info("Ultimate fallback black screen and text displayed on Pixoo device.")
                return  # Exit after ultimate fallback display

            textid = 0
            text_string = None
            text_track = (media_data.artist + " - " + media_data.title)

            if len(text_track) > 14:
                text_track = text_track + "       "
            text_string = get_bidi(text_track) if media_data.artist else get_bidi(media_data.title)
            dir_rtl = 1 if has_bidi(text_string) else 0
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
                textid += 1
                text_item = {
                    "TextId": textid, "type": 22, "x": 0, "y": 48,
                    "dir": dir_rtl, "font": 2, "TextWidth": 64, "Textheight": 16,
                    "speed": 100, "align": 2, "TextString": text_string, "color": color_font
                }
                moreinfo["ItemList"].append(text_item)

            if (self.config.show_clock and not self.config.special_mode):
                textid += 1
                x_clock = 44 if self.config.clock_align == "Right" else 3
                clock_item = {
                    "TextId": textid, "type": 5, "x": x_clock, "y": 3,
                    "dir": 0, "font": 18, "TextWidth": 32, "Textheight": 16,
                    "speed": 100, "align": 1, "color": color_font
                }
                moreinfo["ItemList"].append(clock_item)

            #if (self.config.temperature or self.config.ha_temperature) and not self.config.special_mode:
            if self.config.temperature and not self.config.special_mode:

                textid += 1
                x_temp = 3 if self.config.clock_align == "Right" else 48
                if self.config.temperature and not media_data.temperature:
                    temperature_item = {"TextId": textid, "type": 17, "x": x_temp, "y": 3,
                                        "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6,
                                        "speed": 100, "align": 1, "color": color_font}
                    moreinfo["ItemList"].append(temperature_item)
                elif media_data.temperature and self.config.temperature:
                    temperature_item = {"TextId": textid, "type": 22, "x": x_temp, "y": 3,
                                        "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6,
                                        "speed": 100, "align": 1, "color": color_font, "TextString": media_data.temperature}
                    moreinfo["ItemList"].append(temperature_item)

            if (self.config.show_text or self.config.show_clock or self.config.temperature) and not (self.config.show_lyrics or self.config.spotify_slide or self.config.special_mode):
                await self.pixoo_device.send_command(moreinfo)
                _LOGGER.debug("Sent text/clock/temperature info payload to Pixoo device.")

            if self.config.special_mode:
                day = {
                    "TextId": 1, "type": 14, "x": 4, "y": 1,
                    "dir": 0, "font": 18, "TextWidth": 33,
                    "Textheight": 6, "speed": 100, "align": 1,
                    "color": color_font}

                clock = {
                    "TextId": 2, "type": 5, "x": 0, "y": 1,
                    "dir": 0, "font": 18, "TextWidth": 64,
                    "Textheight": 6, "speed": 100, "align": 2,
                    "color": background_color}

                if media_data.temperature:
                    temperature = {"TextId": 3, "type": 22, "x": 46, "y": 1,
                                "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6,
                                "speed": 100, "align": 1, "color": color_font, "TextString": media_data.temperature}
                else:
                    temperature = {"TextId": 4, "type": 17, "x": 46, "y": 1,
                                "dir": 0, "font": 18, "TextWidth": 20, "Textheight": 6,
                                "speed": 100, "align": 3, "color": color_font}

                dir_rtl_artist = 1 if has_bidi(media_data.artist) else 0
                text_artist = get_bidi(media_data.artist) if dir_rtl_artist == 1 else media_data.artist
                artist = {
                    "TextId": 4, "type": 22, "x": 0, "y": 42,
                    "dir": dir_rtl_artist, "font": 190, "TextWidth": 64,
                    "Textheight": 16, "speed": 100, "align": 2,
                    "TextString": text_artist, "color": color_font}

                dir_rtl_title = 1 if has_bidi(media_data.title) else 0
                text_title = get_bidi(media_data.title) if dir_rtl_title == 1 else media_data.title
                title = {
                    "TextId": 5, "type": 22, "x": 0, "y": 52, "dir": dir_rtl_title,
                    "font": 190,  # 2, 4, 32, 52, 58, 62, 158, 186, 190, 590
                    "TextWidth": 64, "Textheight": 16, "speed": 100, "align": 2,
                    "TextString": text_title, "color": background_color}

                moreinfo["ItemList"].append(day)
                moreinfo["ItemList"].append(clock)
                moreinfo["ItemList"].append(temperature)
                if (self.config.show_text and not media_data.playing_tv) or (media_data.spotify_slide_pass and self.config.spotify_slide):
                    moreinfo["ItemList"].append(artist)
                    moreinfo["ItemList"].append(title)
                await self.pixoo_device.send_command(moreinfo)
                _LOGGER.debug("Sent special mode info payload to Pixoo device.")

        except asyncio.CancelledError:
            _LOGGER.info("Image processing task cancelled.")
        except Exception as e:
            _LOGGER.error(f"Error in _process_and_display_image: {e}", exc_info=True)
        finally:
            self.current_image_task = None  # Reset the task variable


    async def control_light(self, action: str, background_color_rgb: Optional[tuple[int, int, int]] = None, is_night: bool = True) -> None:
        """Control Home Assistant light based on album art colors."""
        if not is_night and self.config.wled_only_at_night:
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
        if not is_night and self.config.wled_only_at_night:
            return  # Exit if not night and only_at_night is configured

        ip_address = self.config.wled

        if not ip_address:
            _LOGGER.warning("IP address for WLED light control is not configured or invalid.")
            return  # Exit if no IP address

        effect_id = self.config.wled_effect
        # Validate the effect ID
        if not (0 <= effect_id <= 186):
            _LOGGER.error(f"Invalid WLED effect ID: {effect_id}. Must be between 0 and 186.")  # Error log if effect ID invalid
            return  # Exit if invalid effect ID

        # Prepare the segment dictionary based on effect requirements
        segment = {"fx": effect_id}

        if effect_id:  # Simplified condition
            if effect_id == 0:  # Solid effect uses only one color
                segment["col"] = [color1]
            else:
                segment["col"] = [color1, color2, color3]

        if self.config.wled_effect_speed:
            segment["sx"] = self.config.wled_effect_speed

        if self.config.wled_effect_intensity:
            segment["ix"] = self.config.wled_effect_intensity

        if self.config.wled_pallete:
            segment["pal"] = self.config.wled_pallete

        if self.config.wled_sound_effect:
            segment["si"] = self.config.wled_sound_effect

        # Prepare the JSON payload
        payload = {"on": True, "bri": self.config.wled_brightness, "seg": [segment]}

        if action == "off":  # Action is 'off'
            payload = {"on": False}  # Off action simply turns off the light
            _LOGGER.debug("Turning OFF WLED light '%s'.", ip_address)
        else:  # Action is 'on'
            _LOGGER.debug("Turning ON WLED light '%s' with effect ID: %s, colors: %s, %s, %s.", ip_address, effect_id, color1, color2, color3)

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
