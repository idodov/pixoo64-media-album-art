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
import logging
import traceback
import math
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from datetime import datetime, timezone

import aiohttp
from PIL import Image, ImageEnhance, ImageFilter

try:
    from unidecode import unidecode
    UNDECODE_AVAILABLE = True
except ImportError:
    logging.warning("The 'unidecode' module is not installed. Special chars might not display correctly.")
    UNDECODE_AVAILABLE = False

try:
    from bidi import get_display
    BIDI_AVAILABLE = True
except ImportError:
    logging.warning("The 'bidi' module is not installed. RTL texts might display reversed.")
    BIDI_AVAILABLE = False

from appdaemon.plugins.hass import hassapi as hass


# --- Constants ---
AI_ENGINE = "https://pollinations.ai/p"
BLK_SCR = b'x\x9c\xc11\x01\x00\x00\x00\xc2\xa0l\xeb_\xca\x18>@\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00o\x03\xda:@\xf1'
TV_ICON_PATH = "/local/pixoo64/tv-icon-1.png"
LOCAL_DIRECTORY = "/homeassistant/www/pixoo64/"

FILES_TO_DOWNLOAD = {
    "tv-icon-1.png": "https://raw.githubusercontent.com/idodov/pixoo64-media-album-art/refs/heads/main/apps/pixoo64_media_album_art/tv-icon-1.png"
}

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler('pixoo64_album_art.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


# --- Helper Functions ---

def luminance(color):
    """Calculates the luminance of a color."""
    r, g, b = color
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast_ratio(color1, color2):
    """Calculates the contrast ratio between two colors."""
    L1 = luminance(color1) + 0.05
    L2 = luminance(color2) + 0.05
    return max(L1, L2) / min(L1, L2)

def is_distinct_color(color, image_palette, threshold=80):
    """Checks if a color is distinct from colors in a palette."""
    return all(math.sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color, img_color))) > threshold for img_color in image_palette)

def get_image_data(img):
    """Encodes image data to base64."""
    try:
        if img.mode == "RGB":
            pixels = [item for p in list(img.getdata()) for item in p]
        else:
            pixels = list(img.getdata())
        b64 = base64.b64encode(bytearray(pixels))
        return b64.decode("utf-8")
    except Exception as e:
        logger.error(f"Error encoding image to base64: {e}")
        return zlib.decompress(BLK_SCR).decode()

def most_vibrant_color(img):
    """Finds the most vibrant color in an image."""
    color_counts = Counter(img.getdata())
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


def split_string(text, length):
    """Splits a string into lines of a given length."""
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


class PixooController:
    def __init__(self, url, headers):
        self.url = url
        self.headers = headers

    async def send_command(self, payload_command):
        """Sends a command to the Pixoo device."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, headers=self.headers, json=payload_command, timeout=10) as response:
                    if response.status != 200:
                        logger.error(f"Failed to send command to Pixoo: {response.status} - {response.reason}")
                    else:
                        await asyncio.sleep(0.25)
        except aiohttp.ClientError as e:
            logger.error(f"Error communicating with Pixoo: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error sending Pixoo command: {e}")

    async def get_current_channel_index(self):
        """Gets the currently selected channel index from the Pixoo."""
        channel_command = {"Command": "Channel/GetIndex"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, headers=self.headers, json=channel_command, timeout=5) as response:
                    response_text = await response.text()
                    response_data = json.loads(response_text)
                    return response_data.get('SelectIndex', 1)
        except Exception as e:
            logger.error(f"Failed to get channel index from Pixoo: {e}")
            return 1

class ImageProcessor:
    def __init__(self, crop_borders, crop_extra, contrast, ha_url):
        self.crop_borders = crop_borders
        self.crop_extra = crop_extra
        self.contrast = contrast
        self.ha_url = ha_url

    async def process_image(self, picture):
        try:
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor() as executor:
                img = await loop.run_in_executor(executor, self._process_image_sync, picture)
                if img is None:
                    return None
                return img
        except asyncio.TimeoutError:
            logger.warning("Image processing timed out!")
            return None
        except Exception as e:
            logger.exception(f"Error processing image: {e}")
            return None

    async def get_image(self, picture):
        """Downloads an image from a URL with a timeout."""
        if not picture:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                url = picture if picture.startswith('http') else f"{self.ha_url}{picture}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        return Image.open(BytesIO(image_data))
                    else:
                        logger.warning(f"Failed to download image: {response.status} from {url}")
                        return None
        except asyncio.TimeoutError:
            logger.warning(f"Timeout downloading image from {url}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"Error downloading image from {url}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Error downloading or opening image:")
            return None

    def _process_image_sync(self, picture):
        img = self.get_image(picture)
        if img is None:
            return None
        img = self.ensure_rgb(img)
        width, height = img.size
        #if width > 128 or height > 128:
        #    img.thumbnail((128, 128), Image.Resampling.LANCZOS)
        if width != height:
            new_size = min(width, height)
            left = (width - new_size) // 2
            top = (height - new_size) // 2
            img = img.crop((left, top, left + new_size, top + new_size))

        if self.crop_borders:
            img = self.crop_image_borders(img)
        if self.contrast:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)
        img = img.resize((64, 64), Image.Resampling.LANCZOS)
        self.lyrics_font_color = self.get_optimal_font_color(img)
        return img

    def ensure_rgb(self, img):
        """Converts image to RGB mode if necessary."""
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img

    def crop_image_borders(self, img):
        """Crops image borders using grayscale conversion for edge detection."""
        temp_img = img
        img = img.convert("L")
        if self.crop_extra:
            img = img.filter(ImageFilter.BoxBlur(20))
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.95)

        try:
            width, height = img.size
            border_pixels = []
            border_pixels.extend([img.getpixel((x, 0)) for x in range(width)])
            border_pixels.extend([img.getpixel((x, height - 1)) for x in range(width)])
            border_pixels.extend([img.getpixel((0, y)) for y in range(height)])
            border_pixels.extend([img.getpixel((width - 1, y)) for y in range(height)])

            border_intensity = max(set(border_pixels), key=border_pixels.count)

            mask = Image.new("L", img.size, 0)
            for x in range(width):
                for y in range(height):
                    if img.getpixel((x, y)) != border_intensity:
                        mask.putpixel((x, y), 255)

            bbox = mask.getbbox()
            if bbox:
                object_width = bbox[2] - bbox[0]
                object_height = bbox[3] - bbox[1]
                center_x = width // 2
                center_y = height // 2
                crop_size = min(object_width, object_height)
                left = center_x - crop_size // 2
                top = center_y - crop_size // 2
                right = center_x + crop_size // 2
                bottom = center_y + crop_size // 2
                left = max(0, left)
                top = max(0, top)
                right = min(width, right)
                bottom = min(height, bottom)
                img = temp_img.crop((left, top, right, bottom))
            else:
                img = temp_img

        except Exception as e:
            logger.error(f"Failed to crop image: {e}")
            img = temp_img
        return img

    def get_image_data(self, img):
        """Encodes image to base64."""
        try:
            if img.mode == "RGB":
                pixels = [item for p in list(img.getdata()) for item in p]
            else:
                pixels = list(img.getdata())
            b64 = base64.b64encode(bytearray(pixels))
            return b64.decode("utf-8")
        except Exception as e:
            logger.error(f"Error encoding image to base64: {e}")
            return zlib.decompress(BLK_SCR).decode()

class MediaDataAndAI:
    def __init__(self, ai_fallback, musicbrainz, spotify_client_id, spotify_client_secret, discogs, lastfm, force_ai):
        self.ai_fallback = ai_fallback
        self.musicbrainz = musicbrainz
        self.spotify_client_id = spotify_client_id
        self.spotify_client_secret = spotify_client_secret
        self.discogs = discogs
        self.lastfm = lastfm
        self.force_ai = force_ai
        self.spotify_token_cache = {
            'token': None,
            'expires': 0
        }
        self.image_cache = OrderedDict() # Use OrderedDict for LRU
        self.MAX_CACHE_SIZE = 10 # Max cache size


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
            logger.error(f"Error getting Spotify access token: {e}")
            return False

    async def get_spotify_album_id(self, artist, title):
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
            "limit": 1
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=spotify_headers, params=payload) as response:
                    response_json = await response.json()
                    tracks = response_json.get('tracks', {}).get('items', [])
                    if tracks:
                        # Find album with earliest year, avoid compilations, match artist
                        best_album = None
                        earliest_year = float('inf')
                        for track in tracks:
                            album = track.get('album')
                            album_name = album.get('name')
                            release_date = album.get('release_date')
                            year = int(release_date[:4]) if release_date else float('inf')
                            is_compilation = album.get('album_type') == 'compilation'
                            artists = album.get('artists', [])
                            album_artist = artists[0]['name'] if artists else "" #Get the artist name from album data

                            #Check for artist match
                            if artist.lower() == album_artist.lower() and year < earliest_year and not is_compilation:
                                earliest_year = year
                                best_album = album

                        if best_album:
                            return best_album['id']
                        else: #No matching artist found, return the first album (if any)
                            if tracks: #Check for availability of albums
                                logger.warning("No matching artist found on Spotify, returning the first album.")
                                return tracks[0]['album']['id']
                            else:
                                logger.warning("No suitable album found on Spotify (no album with matching artist).")
                                return None
                    else:
                        logger.warning("No tracks found on Spotify.")
                        return None

        except (IndexError, KeyError) as e:
            logger.warning(f"Error parsing Spotify track info: {e}")
            return None
        except Exception as e:
            logger.exception(f"Error getting Spotify album ID: {e}")
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
            logger.warning("Album image not found on Spotify.")
            return None
        except Exception as e:
            logger.exception(f"Error getting Spotify album image URL: {e}")
            return None
        finally:
            await asyncio.sleep(0.5)


    async def search_discogs_album_art(self, artist, title):
        base_url = "https://api.discogs.com/database/search"
        headers = {
            "User-Agent": "AlbumArtSearchApp/1.0",
            "Authorization": f"Discogs token={self.discogs}"
        }
        params = {
            "artist": artist,
            "track": title,
            "type": "release",
            "format": "album"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data["results"]:
                            return data["results"][0].get("cover_image")
                        else:
                            logger.warning("No results found on Discogs.")
                            return None
                    else:
                        logger.warning(f"Discogs API error: {response.status}")
                        return None
        except Exception as e:
            logger.exception(f"Error searching Discogs: {e}")
            return None
        finally:
            await asyncio.sleep(1)

    async def search_lastfm_album_art(self, artist, title):
        base_url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "track.getInfo",
            "api_key": self.lastfm,
            "artist": artist,
            "track": title,
            "format": "json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        album_art_url = data.get("track", {}).get("album", {}).get("image", [])
                        if album_art_url:
                            return album_art_url[-1]["#text"]
                    return None
        except Exception as e:
            logger.exception(f"Error searching Last.fm: {e}")
            return None
        finally:
            await asyncio.sleep(1)


    async def get_musicbrainz_album_art_url(self, artist, title):
        search_url = "https://musicbrainz.org/ws/2/release/"
        headers = {
            "Accept": "application/json",
            "User-Agent": "PixooClient/1.0"
        }
        params = {
            "query": f'artist:"{artist}" AND recording:"{title}"',
            "fmt": "json"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, params=params, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("releases"):
                            release_id = data["releases"][0]["id"]
                            cover_art_url = f"https://coverartarchive.org/release/{release_id}"
                            async with session.get(cover_art_url, headers=headers, timeout=20) as art_response:
                                if art_response.status == 200:
                                    art_data = await art_response.json()
                                    for image in art_data.get("images", []):
                                        if image.get("front", False):
                                            return image.get("thumbnails", {}).get("250")
                                    logger.warning("No front cover found in MusicBrainz.")
                                    return None
                        else:
                            logger.warning("No releases found in MusicBrainz.")
                            return None
                    else:
                        logger.warning(f"MusicBrainz API error: {response.status}")
                        return None
        except Exception as e:
            logger.exception(f"Error searching MusicBrainz: {e}")
            return None
        finally:
            await asyncio.sleep(1)

    async def get_final_image_data(self, picture, artist, title):
        """Gets the final image data, using fallbacks."""
        result = await self._get_final_image_data(picture, artist, title)
        return result

    async def _get_final_image_data(self, picture, artist, title):
        if self.force_ai:
            try:
                ai_url = self.format_ai_image_prompt(artist, title)
                return await self.process_ai_image(ai_url)
            except Exception as e:
                logger.exception(f"AI generation failed:")

        else:
            try:
                return await self.process_image(picture)
            except Exception as e:
                logger.exception(f"Original image processing failed:")

        # Fallbacks
        if self.discogs:
            try:
                discogs_image = await self.search_discogs_album_art(artist, title)
                if discogs_image:
                    return await self.process_image(discogs_image)
            except Exception as e:
                logger.exception(f"Discogs fallback failed:")

        if self.spotify_client_id and self.spotify_client_secret:
            try:
                album_id = await self.get_spotify_album_id(artist, title)
                if album_id:
                    spotify_image = await self.get_spotify_album_image_url(album_id)
                    if spotify_image:
                        return await self.process_image(spotify_image)
            except Exception as e:
                logger.exception(f"Spotify fallback failed:")

        if self.lastfm:
            try:
                lastfm_image = await self.search_lastfm_album_art(artist, title)
                if lastfm_image:
                    return await self.process_image(lastfm_image)
            except Exception as e:
                logger.exception(f"Last.fm fallback failed:")

        if self.musicbrainz:
            try:
                mb_url = await self.get_musicbrainz_album_art_url(artist, title)
                if mb_url:
                    return await self.process_image(mb_url)
            except Exception as e:
                logger.exception(f"MusicBrainz fallback failed:")


        try:
            ai_url = self.format_ai_image_prompt(artist, title)
            return await self.process_ai_image(ai_url)
        except Exception as e:
            logger.exception(f"AI generation failed (final fallback):")

        return None, None, None, None

    async def process_ai_image(self, ai_url):
        """Processes an AI-generated image."""
        try:
            return await ImageProcessor(crop_borders=True, crop_extra=True, contrast=False, ha_url="http://homeassistant.local:8123").process_image(ai_url)
        except Exception as e:
            logger.exception(f"Error processing AI image: {e}")
            return None, None, None, None

    async def process_image(self, picture):
        """Processes an image."""
        if not picture:
            return None
        try:
            return await ImageProcessor(crop_borders=True, crop_extra=True, contrast=False, ha_url="http://homeassistant.local:8123").process_image(picture)
        except Exception as e:
            logger.exception(f"Error processing image {e}")
            return None, None, None, None

    def format_ai_image_prompt(self, artist, title):
        """Formats the prompt for AI image generation."""
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
        prompt = random.choice(prompts)
        return f"{AI_ENGINE}/{prompt}?model={self.ai_fallback}"

    def _add_to_cache(self, cache_key, result):
        if len(self.image_cache) >= self.MAX_CACHE_SIZE:
            self.image_cache.popitem(last=False)  # Remove the oldest item
        self.image_cache[cache_key] = result

class Pixoo64AlbumArt(hass.Hass):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.image_lock = asyncio.Lock()
        self.pending_task = None
        self.clear_timer_task = None
        self.is_processing = False
        self.lyrics = []
        self.callback_timeout = 30

    async def initialize(self):
        """Initializes the app."""
        logger.info("Pixoo64 Album Art app initialized.")
        self.media_player = self.args.get('home_assistant', {}).get("media_player", "media_player.era300")
        self.toggle = self.args.get('home_assistant', {}).get("toggle", "input_boolean.pixoo64_album_art")
        self.ha_url = self.args.get('home_assistant', {}).get("ha_url", "http://homeassistant.local:8123")
        self.pixoo_sensor = self.args.get('home_assistant', {}).get("pixoo_sensor", "sensor.pixoo64_media_data")
        self.light = self.args.get('home_assistant', {}).get("light", None)
        self.clean_title_enabled = self.args.get('pixoo', {}).get('show_text', {}).get("clean_title", True)
        self.show_lyrics = self.args.get('pixoo', {}).get("lyrics", False)
        self.show_text = self.args.get('pixoo', {}).get('show_text', {}).get("enabled", False)
        self.show_clock = self.args.get('pixoo', {}).get("clock", True)
        self.clock_align = self.args.get('pixoo', {}).get("clock_align", "Right")
        self.tv_icon_pic = self.args.get('pixoo', {}).get("tv_icon", True)
        self.full_control = self.args.get('pixoo', {}).get("full_control", True)
        self.contrast = self.args.get('pixoo', {}).get("contrast", False)
        self.font = self.args.get('pixoo', {}).get('show_text', {}).get("font", 2)
        self.font_c = self.args.get('pixoo', {}).get('show_text', {}).get("color", True)
        self.text_bg = self.args.get('pixoo', {}).get('show_text', {}).get("text_background", True)
        self.crop_borders = self.args.get('pixoo', {}).get('crop_borders', {}).get("enabled", True)
        self.crop_extra = self.args.get('pixoo', {}).get('crop_borders', {}).get("extra", True)

        pixoo_url = self.args.get('pixoo', {}).get("url", "192.168.86.21")
        pixoo_url = f"http://{pixoo_url}" if not pixoo_url.startswith('http') else pixoo_url
        if not pixoo_url.endswith(":80/post"):
            pixoo_url = f"{pixoo_url}:80/post"

        self.headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Connection": "keep-alive",
            "User-Agent": "PixooClient/1.0"
        }

        self.pixoo = PixooController(pixoo_url, self.headers)
        self.image_processor = ImageProcessor(self.crop_borders, self.crop_extra, self.contrast, self.ha_url)
        self.media_ai = MediaDataAndAI (self.args.get('home_assistant', {}).get("ai_fallback", 'flux'),
                                        self.args.get('home_assistant', {}).get("musicbrainz", True),
                                        self.args.get('home_assistant', {}).get("spotify_client_id", False),
                                        self.args.get('home_assistant', {}).get("spotify_client_secret", False),
                                        self.args.get('home_assistant', {}).get("discogs", False),
                                        self.args.get('home_assistant', {}).get("last.fm", False),
                                        self.args.get('home_assistant', {}).get("force_ai", False))

        self.lyrics_font_color = "#FF00AA"
        self.playing_radio = False
        self.radio_logo = False
        self.fallback = self.fail_txt = False
        self.media_position = self.media_duration = 0
        self.media_position_updated_at = None
        self.album_name = self.get_state(self.media_player, attribute="media_album_name")
        self.ai_artist = self.ai_title = None
        self.track_position = None

        # Download files
        await self.download_files()

        # State listeners
        self.listen_state(self.safe_state_change_callback, self.media_player, attribute='media_title')
        self.listen_state(self.safe_state_change_callback, self.media_player, attribute='state')
        if self.show_lyrics:
            self.run_every(self.calculate_position, datetime.now(), 1)

    async def download_files(self):
        tasks = [self.download_file(file_name, url) for file_name, url in FILES_TO_DOWNLOAD.items()]
        await asyncio.gather(*tasks)

    async def download_file(self, file_name, url):
        local_file_path = os.path.join(LOCAL_DIRECTORY, file_name)
        if not os.path.exists(local_file_path):
            logger.info(f"Downloading {file_name} from {url}...")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            with open(local_file_path, 'wb') as file:
                                file.write(await response.read())
                        else:
                            logger.warning(f"Failed to download {file_name}: {response.status}")
            except aiohttp.ClientError as e:
                logger.error(f"Download error for {file_name}: {e}")

    async def safe_state_change_callback(self, entity, attribute, old, new, kwargs):
        """Handles state changes with timeout protection."""
        if self.is_processing:
            logger.debug(f"Ignoring new callback {new} - {old}")
            return

        try:
            async with asyncio.timeout(self.callback_timeout):
                await self.state_change_callback(entity, attribute, old, new, kwargs)
        except asyncio.TimeoutError:
            logger.warning("Callback timed out - cancelling operation")
        except Exception as e:
            logger.exception(f"Error in callback:")

    async def state_change_callback(self, entity, attribute, old, new, kwargs):
        """Handles state changes."""
        if new == old or (await self.get_state(self.toggle)) != "on":
            return

        media_state = await self.get_state(self.media_player)
        if media_state in ["off", "idle", "pause", "paused"]:
            await self.set_state(self.pixoo_sensor, state="off")
            if self.full_control:
                await asyncio.sleep(5)
                if await self.get_state(self.media_player) not in ["playing", "on"]:
                    await self.pixoo.send_command({
                        "Command": "Draw/CommandList",
                        "CommandList": [
                            {"Command": "Draw/ClearHttpText"},
                            {"Command": "Draw/ResetHttpGifId"},
                            {"Command": "Channel/OnOffScreen", "OnOff": 0}
                        ]
                    })
                    await self.set_state(self.pixoo_sensor, state="off")
                    if self.light:
                        await self.call_service(f'light/turn_off', entity_id=self.light)
            return
        self.is_processing = True
        await self.update_attributes(entity, attribute, old, new, kwargs)
        self.is_processing = False

    async def update_attributes(self, entity, attribute, old, new, kwargs):
        """Updates attributes based on media state."""
        media_state = await self.get_state(self.media_player)
        if media_state not in ["playing", "on"]:
            if self.light:
                await self.call_service(f'light/turn_off', entity_id=self.light)
            return

        title = await self.get_state(self.media_player, attribute="media_title")
        if not title:
            return

        title = clean_title(title, self.clean_title_enabled)

        if self.show_lyrics:
            artist = await self.get_state(self.media_player, attribute="media_artist")
            await self.get_lyrics(artist, title)
        else:
            self.lyrics = []

        await self.pixoo_run(media_state)

    async def pixoo_run(self, media_state):
        try:
            self.select_index = await self.pixoo.get_current_channel_index()
            if media_state in ["playing", "on"]:
                title = await self.get_state(self.media_player, attribute="media_title")
                artist = await self.get_state(self.media_player, attribute="media_artist")
                picture = await self.get_state(self.media_player, attribute="entity_picture")
                media_content_id = await self.get_state(self.media_player, attribute="media_content_id")
                queue_position = await self.get_state(self.media_player, attribute="queue_position")
                media_channel = await self.get_state(self.media_player, attribute="media_channel")

                # Radio handling
                if media_channel and (media_content_id.startswith("x-rincon") or media_content_id.startswith("aac://http") or media_content_id.startswith("rtsp://")):
                    self.playing_radio = True
                    self.radio_logo = False
                    if artist:
                        picture = self.media_ai.format_ai_image_prompt(artist, title)
                    if ('https://tunein' in media_content_id or
                            queue_position == 1 or
                            title == media_channel or
                            title == artist or
                            artist == media_channel or
                            artist == 'Live' or
                            artist is None):
                        self.radio_logo = True
                else:
                    self.playing_radio = self.radio_logo = False

                if UNDECODE_AVAILABLE:
                    normalized_title = unidecode(title)
                    normalized_artist = unidecode(artist) if artist else ""
                else:
                    normalized_title = title
                    normalized_artist = artist if artist else ""

                self.ai_title = normalized_title
                self.ai_artist = normalized_artist

                # Concurrent tasks
                image_task = asyncio.create_task(self.get_final_image_data(picture, normalized_artist, normalized_title))
                other_tasks = asyncio.gather(
                    self.get_state(self.media_player, attribute="media_position", default=0),
                    self.get_state(self.media_player, attribute="media_position_updated_at", default=None),
                    self.get_state(self.media_player, attribute="media_duration", default=0),
                )

                self.media_position, self.media_position_updated_at, self.media_duration = await other_tasks
                gif_base64, font_color, recommended_font_color, brightness, brightness_lower_part, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative = await image_task

                # Check for image loading failure
                if gif_base64 is None:
                    logger.warning("Image loading failed. Skipping display.")
                    return

                new_attributes = {
                    "artist": artist,
                    "normalized_artist": normalized_artist,
                    "media_title": title,
                    "normalized_title": normalized_title,
                    "font_color": font_color,
                    "font_color_alternative": recommended_font_color,
                    "background_color_brightness": brightness,
                    "background_color": background_color,
                    "color_alternative_rgb": most_common_color_alternative,
                    "background_color_rgb": background_color_rgb,
                    "recommended_font_color_rgb": recommended_font_color_rgb,
                    "color_alternative": most_common_color_alternative_rgb,
                }
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
                text_track = (artist + " - " + title) if artist else title
                if len(text_track) > 14:
                    text_track = text_track + "       "
                text_string = convert_text(text_track, BIDI_AVAILABLE)

                dir = 1 if has_bidi(text_string) else 0
                brightness_factor = 50
                try:
                    color_font = tuple(min(255, c + brightness_factor) for c in background_color_rgb)
                except (TypeError, ValueError):
                    logger.error("Error calculating font color. Using default.")
                    background_color_rgb = (200, 200, 200)
                    color_font = (255, 255, 255)

                color_font = '#%02x%02x%02x' % color_font
                color_font = color_font if self.font_c else recommended_font_color

                await self.pixoo.send_command(payload)
                if self.light:
                    await self.call_service(f'light/turn_on', entity_id=self.light, rgb_color=background_color_rgb, transition=2)

                if self.show_text and not self.fallback and not self.radio_logo:
                    textid += 1
                    text_temp = {
                        "TextId": textid,
                        "type": 22,
                        "x": 0,
                        "y": 48,
                        "dir": dir,
                        "font": self.font,
                        "TextWidth": 64,
                        "Textheight": 16,
                        "speed": 100,
                        "align": 2,
                        "TextString": text_string,
                        "color": color_font
                    }
                    moreinfo["ItemList"].append(text_temp)

                if self.show_clock and not self.fallback:
                    textid += 1
                    x = 44 if self.clock_align == "Right" else 3
                    clock_item = {
                        "TextId": textid,
                        "type": 5,
                        "x": x,
                        "y": 3,
                        "dir": 0,
                        "font": 18,
                        "TextWidth": 32,
                        "Textheight": 16,
                        "speed": 100,
                        "align": 1,
                        "color": color_font
                    }
                    moreinfo["ItemList"].append(clock_item)

                if (self.show_text or self.show_clock) and not (self.fallback or self.show_lyrics):
                    await self.pixoo.send_command(moreinfo)

                if self.fallback and self.fail_txt:
                    payloads = self.create_payloads(normalized_artist, normalized_title, 13)
                    payload = {"Command": "Draw/CommandList", "CommandList": payloads}
                    await self.pixoo.send_command(payload)
            else: # Media player is not playing
                if self.tv_icon_pic:
                    picture = TV_ICON_PATH
                    img = await self.image_processor.get_image(picture)
                    if img:
                        img = self.image_processor.ensure_rgb(img)
                        gif_base64 = self.image_processor.get_image_data(img)
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
                        await self.pixoo.send_command(payload)
                        if self.light:
                            await self.call_service(f'light/turn_off', entity_id=self.light)
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
                    await self.pixoo.send_command(payload)
                    if self.light:
                        await self.call_service(f'light/turn_off', entity_id=self.light)
        except Exception as e:
            logger.exception(f"Error in pixoo_run:")

    async def get_final_image_data(self, picture, artist, title):
        return await self.media_ai.get_final_image_data(picture, artist, title)

    def create_payloads(self, normalized_artist, normalized_title, x):
        """Creates payloads for text display."""
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

    def get_optimal_font_color(self, img):
        """Determines optimal font color based on image brightness."""
        small_img = img.resize((16, 16), Image.Resampling.LANCZOS)
        image_palette = set(small_img.getdata())
        avg_brightness = sum(luminance(color) for color in image_palette) / len(image_palette)

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
        max_contrast = 0
        for font_color in candidate_colors:
            if is_distinct_color(font_color, image_palette, threshold=150):
                contrast_with_white = contrast_ratio(font_color, (255, 255, 255))
                contrast_with_black = contrast_ratio(font_color, (0, 0, 0))

                if (avg_brightness < 127 and contrast_with_white > max_contrast) or \
                    (avg_brightness >= 127 and contrast_with_black > max_contrast):
                    max_contrast = max(contrast_with_white, contrast_with_black)
                    best_color = font_color
        return '#%02x%02x%02x' % best_color if best_color else '#000000' if avg_brightness > 127 else '#ffffff'

    async def get_lyrics(self, artist, title):
        """Fetches lyrics for the given artist and title."""
        if self.playing_radio:
            self.lyrics = []
            return

        if not artist or not title:
            logger.warning("Artist or title is missing; skipping lyrics fetch.")
            self.lyrics = []
            return

        lyrics_url = f"http://api.textyl.co/api/lyrics?q={artist} - {title}"
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(lyrics_url) as response:
                    if response.status == 200:
                        lyrics_data = await response.json()
                        self.lyrics = [{'seconds': line['seconds'], 'lyrics': line['lyrics']} for line in lyrics_data]
                        logger.info(f"Retrieved lyrics for {artist} - {title}")
                    else:
                        logger.warning(f"Failed to fetch lyrics: {response.status}")
                        self.lyrics = []
        except Exception as e:
            logger.exception(f"Error fetching lyrics:")
            self.lyrics = []

    async def calculate_position(self, kwargs):
        """Calculates the current position in the song and displays lyrics."""
        media_state = await self.get_state(self.media_player)
        if media_state not in ["playing", "on"]:
            return

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
                    if int(current_position) == lyric_time -1:
                        await self.create_lyrics_payloads(lyric['lyrics'], 11)
                        next_lyric_time = self.lyrics[i + 1]['seconds'] if i + 1 < len(self.lyrics) else None
                        lyrics_diplay = (next_lyric_time - lyric_time) if next_lyric_time else lyric_time + 10
                        if lyrics_diplay > 9:
                            await asyncio.sleep(8)
                            await self.pixoo.send_command({"Command": "Draw/ClearHttpText"})
                        break

    async def create_lyrics_payloads(self, lyrics, max_chars_per_line):
        """Creates payloads for displaying lyrics on the Pixoo, handling line breaks correctly."""
        all_lines = self.split_string(convert_text(lyrics, BIDI_AVAILABLE), max_chars_per_line)
        #Limit to 5 lines, concatenating remaining lines into the last line if necessary.
        display_lines = all_lines #[:5]
        if len(all_lines) > 5:
            display_lines[4] = ' '.join(display_lines[4:]) #Join all remaining lines into the last line.
        
        start_y = (64 - len(display_lines) * 12) // 2  # Adjust vertical spacing based on line count

        payloads = [
            {
                "Command": "Draw/SendHttpText",
                "TextId": i + 1,
                "x": 0,
                "y": start_y + (i * 12),
                "dir": 0,
                "font": self.font,
                "TextWidth": 64,
                "speed": 80,
                "TextString": line,
                "color": self.lyrics_font_color,
                "align": 2
            }
            for i, line in enumerate(display_lines)
        ]
        clear_text_command = {"Command": "Draw/ClearHttpText"}
        full_command_list = [clear_text_command] + payloads
        payload = {"Command": "Draw/CommandList", "CommandList": full_command_list}
        await self.pixoo.send_command(payload)
