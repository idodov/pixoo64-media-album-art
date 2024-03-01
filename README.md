## PIXOO64 Media Album Art Display: Enhance Your Music Experience
**This script automatically transforms your PIXOO64 into a vibrant canvas for your currently playing music. It extracts and displays the album cover art, along with extracting valuable data like artist name and dominant color, which can be used for further automation in your Home Assistant environment.**

![PIXOO_album_gallery](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71348538-2422-47e3-ac3d-aa1d7329333c)

**Visual Enhancements:**

- **Eye-catching Cover Art:** Witness the album art of your favorite songs come to life on your PIXOO64, adding a visual dimension to your listening experience.
- **Dynamic Color Integration:** The dominant color from the album art is used to set the font and background colors on the PIXOO64, creating a cohesive and aesthetically pleasing display.

**Functional Advantages:**

- **Sensor Data Storage:** All extracted data is stored in a dedicated sensor entity within Home Assistant, making it readily accessible for further automation possibilities.
- **Clean and Consistent Titles:** Normalize titles and artist names for easier integration with automations and consistent display regardless of regional characters or symbols. This ensures seamless use of extracted data in automations and avoids inconsistencies in visual representations.
  - Original Title: "Beyoncé" (with accent)
  - Normalized Title: "Beyonce" (accent removed)
  
**Prerequisites:**

1. **DIVOOM PIXOO64:** [https://divoom.com](https://divoom.com)
2. **Home Assistant:** [https://www.home-assistant.io/blog/2017/07/25/introducing-hassio/](https://www.home-assistant.io/blog/2017/07/25/introducing-hassio/) (with add-on functionality)
3. **AppDaemon:** [https://appdaemon.readthedocs.io/](https://appdaemon.readthedocs.io/) (Home Assistant add-on)

**Installation and Configuration:**

1. Create a Toggle Helper in Home Assistant. For example `input_boolean.pixoo64_album_art` can be used to control when the script runs.
2. Install **AppDaemon** from the Home Assistant add-on store.
3. On Configuration page, install the **requests**, **numpy pillow**, and **unidecode** Python packages.
```yaml
# appdaemon.yaml
system_packages: []
python_packages:
  - requests
  - numpy pillow
  - unidecode
init_commands: []
```
4. In the AppDaemon app directory (addons_config/appdaemon/apps), create a file named **pixoo.py** (using the VSCode or File Editor add-on) and paste the code into it. 
Before saving the code, make sure to adjust it to your personal needs.

| Parameter | Description | Example |
|---|---|---|
| **SHOW_TEXT** | Display the artist name and title. Change to `False` not to display the media info | `SHOW_TEXT = True` |
| **FULL_CONTROL** | This script assumes control of the PIXOO64 display while it’s in use and a track is playing. If `True` then the display will turn off when music paused. If `False` it display the previous channel (clock, visualizer, exc.) | `FULL_CONTROL = False` |
| **TOGGLE** | Primary toggle sensor name that triggering the script. Please create it as a helper in Home Assistant UI interface | `input_boolean.pixoo64_album_art` |
| **MEDIA_PLAYER** | Media Player entity name in Home Assistant | `media_player.era300` |
| **SENSOR** | Sensor name to store data. No need to create it in advance | `sensor.pixoo64_media_data` |
| **HA_URL** | Home Assistant local URL | `http://homeassistant.local:8123` |
| **URL** | PIXOO64 full URL | `http://192.168.86.21:80/post` |
```py
import re
import base64
import requests
import json
import time
from collections import Counter
from io import BytesIO
from PIL import Image
from PIL import UnidentifiedImageError
from appdaemon.plugins.hass import hassapi as hass
from unidecode import unidecode

#-- Update to your own values
SHOW_TEXT = True 
FULL_CONTROL = True 

TOGGLE = "input_boolean.pixoo64_album_art" # CREATE IT AS A HELPER ENTITY BEFORE!!
MEDIA_PLAYER = "media_player.era300" # Name of your speaker
SENSOR = "sensor.pixoo64_media_data" # Name of the sensor to store the data

HA_URL = "http://homeassistant.local:8123"
URL = "http://192.168.86.21:80/post" # Pixoo64 URL
# ---------------
IMAGE_SIZE = 64 
LOWER_PART_CROP = (5, int((IMAGE_SIZE/4)*3), IMAGE_SIZE-5, IMAGE_SIZE-5)
FULL_IMG = (1, IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE)
BRIGHTNESS_THRESHOLD = 128
HEADERS = {"Content-Type": "application/json; charset=utf-8"}

class Pixoo(hass.Hass):
    def initialize(self):
        self.listen_state(self.update_attributes, MEDIA_PLAYER, attribute='media_title')
        self.listen_state(self.update_attributes, MEDIA_PLAYER)
        
    def update_attributes(self, entity, attribute, old, new, kwargs):
        try:
            input_boolean = self.get_state(TOGGLE)
        except Exception as e:
            self.log(f"Error getting state for {TOGGLE}: {e}. Will create a new entity")
            self.set_state(TOGGLE, state="on", attributes={"friendly_name": "Pixoo64 Album Art"})
            input_boolean = "on"
    
        media_state = self.get_state(MEDIA_PLAYER)
        
        if media_state in ["off", "idle", "pause"]:
            self.set_state(SENSOR, state="off")

        if input_boolean == "on":
            payload = '{ "Command" : "Channel/GetIndex" }'
            response = requests.request("POST", url, headers=HEADERS, data=payload)
            response_data = json.loads(response.text)
            select_index = response_data.get('SelectIndex', None)
            
            if media_state in ["playing", "on"]:  # Check for playing state
                new = self.get_state(MEDIA_PLAYER, attribute="media_title")
                if new:  # Check if new is not None
                    title = new
                    normalized_title = unidecode(new)
                    artist = self.get_state(MEDIA_PLAYER, attribute="media_artist")
                    if artist:  # Check if artist is not None
                        normalized_artist = unidecode(artist)
                    else:
                        artist = ""
                        normalized_artist = ""
                    picture = self.get_state(MEDIA_PLAYER, attribute="entity_picture")
                    gif_base64, font_color, recommended_font_color, brightness, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative = self.process_picture(picture)
                    new_attributes = {
                        "artist": artist,
                        "normalized_artist": normalized_artist, 
                        "media_title": title,
                        "normalized_title": normalized_title, 
                        "media_picture_gif_base64": gif_base64, 
                        "font_color": font_color,
                        "font_color_alternative": recommended_font_color,
                        "background_color_brightness": brightness,
                        "background_color": background_color,
                        "color_alternative_rgb": most_common_color_alternative,
                        "background_color_rgb": background_color_rgb,
                        "recommended_font_color_rgb": recommended_font_color_rgb,
                        "color_alternative": most_common_color_alternative_rgb,
                        
                    }
                    self.set_state(SENSOR, state="on", attributes=new_attributes)
                    if SHOW_TEXT:
                        payload = {"Command":"Draw/SendHttpText",
                            "TextId":3,
                            "x":0,
                            "y":48,
                            "dir":0,
                            "font":2,
                            "TextWidth":64,
                            "speed":80,
                            "TextString": normalized_artist + " - " + normalized_title + "             ",
                            "color":recommended_font_color,
                            "align":1}

                        response = requests.post(URL, headers=HEADERS, data=json.dumps(payload))

                        if response.status_code != 200:
                            self.log(f"Failed to send REST command with image data: {response.content}")
            else:
                if FULL_CONTROL:
                    payload = {"Command":"Draw/CommandList", "CommandList":[
                    {"Command":"Draw/ClearHttpText"},
                    {"Command": "Draw/ResetHttpGifId"},
                    {"Command":"Channel/OnOffScreen", "OnOff":0} 
                   ]}
                else:
                    payload = {"Command":"Draw/CommandList", "CommandList":[
                    {"Command":"Draw/ClearHttpText"},
                    {"Command": "Draw/ResetHttpGifId"},
                    {"Command":"Channel/SetIndex", "SelectIndex": 4 },
                    {"Command":"Channel/SetIndex", "SelectIndex": select_index }
                   ]}
                response = requests.post(URL, headers=HEADERS, data=json.dumps(payload))

                if response.status_code != 200:
                    self.log(f"Failed to send REST command with image data: {response.content}")
                    
    def process_picture(self, picture):
        gif_base64 = ""  
        font_color = ""  
        recommended_font_color = "" 
        background_color = ""
        background_color_rgb = ""
        recommended_font_color_rgb = ""
        most_common_color_alternative_rgb = ''
        most_common_color_alternative = ""
        brightness = 0
        if picture is not None:
            try:
                img = self.get_image(picture)
                gif_base64, font_color, recommended_font_color, brightness, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative  = self.process_image(img)
            except Exception as e:
                self.log(f"Error processing image: {e}")
        return gif_base64, font_color, recommended_font_color, brightness, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative_rgb, most_common_color_alternative

    def get_image(self, picture):
        try:
            response = requests.get(f"{HA_URL}{picture}")
            img = Image.open(BytesIO(response.content))
            img = img.convert("RGB")
            img.thumbnail((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.LANCZOS)
            return img
        except UnidentifiedImageError:
            self.log("Unable to identify image file.")
            return None

    def process_image(self, img):
        img = self.ensure_rgb(img)
        pixels = self.get_pixels(img)
        b64 = base64.b64encode(bytearray(pixels))
        gif_base64 = b64.decode("utf-8")
        full_img = img
        lower_part = img.crop(LOWER_PART_CROP)
        lower_part = self.ensure_rgb(lower_part)
        most_common_color = Counter(lower_part.getdata()).most_common(1)[0][0]
        most_common_color_alternative_rgb = Counter(full_img.getdata()).most_common(1)[0][0]
        most_common_color_alternative = '#%02x%02x%02x' % most_common_color_alternative_rgb
        brightness = int(sum(most_common_color) / 3)
        font_color = "#FFFFFF" if brightness < BRIGHTNESS_THRESHOLD else "#000000"
        opposite_color = tuple(255 - i for i in most_common_color)
        recommended_font_color = '#%02x%02x%02x' % opposite_color
        background_color_rgb = most_common_color
        background_color = '#%02x%02x%02x' % most_common_color
        recommended_font_color_rgb = opposite_color
        
        # Calculate contrast ratio
        l1 = self.luminance(*most_common_color)
        l2 = self.luminance(*opposite_color)
        ratio = self.contrast_ratio(l1, l2)

        # Adjust recommended_font_color if contrast ratio is less than 4.5
        if ratio < 4.5:
            # If brightness is high, use black; otherwise, use white
            recommended_font_color = "#000000" if brightness > 128 else "#FFFFFF"
        
        payload = {"Command":"Draw/CommandList", "CommandList":[
            {"Command":"Channel/OnOffScreen", "OnOff":1},
            {"Command": "Draw/ResetHttpGifId"},
            {"Command": "Draw/SendHttpGif",
                "PicNum": 1,
                "PicWidth": 64,
                "PicOffset": 0,
                "PicID": 0,
                "PicSpeed": 1000,
                "PicData": gif_base64 }]}
            
        response = requests.post(URL, headers=HEADERS, data=json.dumps(payload))

        if response.status_code != 200:
            self.log(f"Failed to send REST command with image data: {response.content}")

        return gif_base64, font_color, recommended_font_color, brightness, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative, most_common_color_alternative_rgb

    def ensure_rgb(self, img):
        if img.mode != "RGB":
            img = img.convert("RGB")
        return img

    def get_pixels(self, img):
        if img.mode == "RGB":
            pixels = [item for p in list(img.getdata()) for item in p]  # This flattens the tuples to a list
        else:
            pixels = list(img.getdata())
        return pixels

    def luminance(self, r, g, b):
        a = [i / 255.0 for i in [r, g, b]]
        for i in range(3):
            if a[i] <= 0.03928:
                a[i] = a[i] / 12.92
            else:
                a[i] = ((a[i] + 0.055) / 1.055) ** 2.4
        return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2]

    def contrast_ratio(self, l1, l2):
        return (l1 + 0.05) / (l2 + 0.05) if l1 > l2 else (l2 + 0.05) / (l1 + 0.05)
```
4. Open **app.yaml** file from the AppDaemon directory and add this code:
```yaml
pixoo:
  module: pixoo
  class: Pixoo
```
5. Restart AppDaemon
____________
**You’re all set! The next time you play a track, the album cover art will be displayed and all the usable picture data will be stored in a new sensor.**

![צילום מסך 2024-02-29 230356](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/54546384-70c1-4c18-ba1e-aaeb91ac11ec)

![animated-g](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/2a716425-dd65-429c-be0f-13acf862cb10)
_____________
## Sensor Attribues
The sensor  `sensor.pixoo64_media_data` is a virtual entity created in Home Assistant. It’s designed to store useful picture data from the album cover art of the currently playing song. This includes the artist’s name, the title of the media, the base64 encoded GIF of the media picture, and color information such as the color of the font and the background. This sensor allows for dynamic visual experiences and automation possibilities based on the music being played.

| Attribute | Description |
|---|---|
| **artist** | The original name of the artist |
| **normalized_artist** | The artist's name in Latin letters |
| **media_title** | The original title of the media |
| **normalized_title** | The media title in Latin letters |
| **media_picture_gif_base64** | The base64 encoded GIF of the media picture |
| **font_color** | The color of the font |
| **font_color_alternative** | An alternative color for the font |
| **background_color_brightness** | The brightness level of the background color |
| **background_color** | The color of the lower part in background |
| **background_color_rgb** | The RGB values of the background color (lower part) |
| **color_alternative** |  The most common color of the background |
| **color_alternative_rgb** | The RGB values of the most common background color |

Here’s an example of the sensor values:
```yaml
artist: Yona
normalized_artist: Yona
media_title: Nättii, eipä
normalized_title: Nattii, eipa
media_picture_gif_base64: >-
  EhMXEhMXEhMXEhMXEhMXEhIUEhISEhISEhISEhISEhISEhISExMTEhISEhISEhISExMTExMTEhISFBQUEhISExMTExMTEhISExMTExMTFRYXFBUVFBMUFBQUFBQUFBQUExMTExMTFRUVFBQUFBQUFBQUFBQUFBMUFBQUExMTExMTExMTExMTExMTExMTExMTEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhMXEhMXEhMXEhMXEhMXEhIUEhISEhISEhISEhISEhISEhISEhISEhISEhISExMTEhISEhISEhISExMTExMTExMTExMTExMTExMTExITGR0dGBsbFRQTFhYVFxcWFRUVFRUVFBQTFhUUFRUTFBQUFBQUFRYVFRUVFRUVFRUVFBQUEhISFBQUEhISExMTExMTExMTExMTEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhMXEhMXEhMXEhMXEhMXEhIUEhISEhISEhISEhISEhISFBQUFRUVEhISExMTExMTExMTExMTEhISEhISFBQUFBQUExMTFRUUFRUUExMTFRUVFBQTFxcVFxYUFxcWFhYWFhYWFxcWFxcVFRUTFhYVFxcVFRUUFhUUFhUUFBQUExMTExMTEhISExMTEhISExMTExMTFBQUFBQUEhISExMTEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhMXEhMXEhMXEhMXEhMXEhMVEhISExMTEhISEhISEhISFBQUEhISExMTExMTExMTExMTExMTExMTFBQUFRUVFBQUFBQUFRUWFxcWFRUTFhYVFxcVGRkVGhsWGxwYGBgVFxgWGRkYGRkXFhYUGRkWGBgWFhUTFRQTFRQTExMTExMTFRUUFxcXExMTExMTExMUFBQUFBQUFBQUExMTEhISExMTEhISEhISEhISEhISEhISEhISEhISEREREhISEhISEhMXEhMXEhMXEhMXEhMXEhMVEhISEhISEhISEhISEhISEhISFBQUFBQUFBQUExMTExMTFBQUGBgYFBMUFRUVFhUUFxYVFhUVGBgXFxcVFRUUGRkXHR4YGxwWGxsXFxcVFhYUGRkVGRkWGhoXGRoVGBgWGRgXGRcVGRgWFhYUFRUTFRQTGBkYExMUFBQTFRUTFBQUFBQVFBQUExMTEhISExMTExMTEhISEhISExMTEhISEhISEhISEhISEhISEhISEhMWEhMWEhMWEhMWEhMXExMUExMSEhISEhISEhISEhISExMTFBQUExMTFBMTFBQUExMTFRUVFRUVFBQTFRQTFxUUFhUTFhYUGRkXGhcXGRgVGxwYHR0ZHh4YGxoWHB0ZHR0ZHR4ZISIdHRwYHB0XHBwYGxoYGxoVGRgVGRkXFhUTFRQUExMTFBQTFhYVFxcVFxcXFRUVFRUUFBQUExMTExMTExMTExMTExMSExMTEhISEhISExMTEhISEhISEhISEhISEhISFBQUEhISEhITExMUExMTExMTExMTEhISFBQUFBQUExMTExMTGRgWFRUTFBQTFRUTFhUTGBkVGBgVGhgXGRgWGhoWGRoWHR0ZHB4YGRoWHx4ZICEaICIaISIZHR8YHyAaHyAaHyEZHyAZHh0YHRwYGxsWGhoWGhoXGhkYGBcVFRUTGhoYFhYUFxcVGBgWFxcVFhYUFBQTFRUUEhISExMTEhITEhISExMTExMTERESExMTEhISExMTExMTEhISEhISEhISEhISExMTExMTExMSFBQUExMTExMTFRUVFRUVFBMUFBMSGRgWFhYUFxcUFRUTFxcVFxcVGxkXGRgVGxoWGhsXHiAZHR4XISMbJCgeJCYcJigdIyYdIiQaJCYdJCYcIyUbJCceIiUcICMbHyAZIyYcHyAZGhoWGxkXGxoWHBoXFxUUFhUTGRkWGRkWGBgXFxcVGBgVFxcVFhYVExMTExMSExMTFBQUExMTEhISFBQUExMTExMTEhISExMTExMTExMTExMTExMTExMTEhISExMTFBQUFBMTFBQTFRUUFRMTGRcWGBgVFRUTFhYVFxYVFhUTGxoYGhoXGRgVHRsYHh4ZICIaHyIZJSodKjAhKi0fJigcJCYcJigcJCcbJikdJCUbJikfIygdICIZISIaIigbISMbHR4YHR0YHRwYHh4ZGxoWHBsYHR0XHBwXGhsXFhYUFxcVFxcWFxcVFRUVFRUUFBQUFBQUFBQTFBQTFBQUFBQUFBQUExMTExMTExMTExMTExMTFBQUExMTExMTFRUUFRUTFRUTFRUTFhYTFhUUGBcWGBcVGBgVGxoXGRsXGRkXGBgVGxwXHiAbHyAZJCUdJSkdJiodLDckJiocJCQZJiccJCkcKi4gJysdJyweJy8fKC4eJigcJCQbIiMcIyUbJSgdICIZISIaICAZICEZIiMcHB0XHh4ZGxwXGhsWGRkWGRkWGhsXGBgVFhcVFhcVFRYVFhYWFBQUFRUUExMUFBQUFBUUFBQTFBQUFhYWExMTFBQUExMTFBQTFBQTFhYUGBcVFxcVGBcVFhUUFxYVFxUUGRkXGBgWGxoWHCAZHR4aHBsWHyEZISQaIy0eJSkdIiQaJiocJjAfKjAhKi0fKCodKi4eKS8eKzMfKjYiLDojLDQiKC0eJi8eIyMcJygeIiQZJCUbJyodISEZIiIbIiIaICAaIiUcGxwWICEbHB0WGxsWGhoVGhsWGRsWGBgWFhYUFhUTFhYUFhYVFRUUFBQTFRQTFhUVFBQUFBQUFBQUFBQUExMTFBQUFBQTFRUTGRgWGRoXGhsZGBgWGBcVGBYUHh0ZGhkWHR0ZHBwXIiIbICEaIyUbKCsdIy4eJzAhJykdIiUaJCwdJy4fKzIhKi8dMDomMUQoLTwkKDQfKTAgLTchKDcgKDEgKy0gKC4fKzMiKjYhJi4eIygdJy0fJisdIiIaIiUcHyEZIyUdHR4YGhkWGRgUGhsWHB0YGxsWGBcVFhUTGBcVFxcVFhYUFhUTFhUUFRMVExMTFBQUFBQUFRUVFhYWFRUVFhYVFxcUGBgUHBwZGBkVGRkWHBwYGxoVHyAaICEbHx0XIyEcHhwXICAZJCgcLDEgKDIgJzIgKC8fKjIfLjckKzAgKzYhKTUhLDojKzIiKS4eLjgjLTchKzQgLjkiLDUiLDEhKCweKyweLDUgKS4fKDAgJy8fKCoeKCweJCYbJiofISIaISIbHR0YHyIaHyAYHR4YHR8ZGhoXGhoXGhkXGBgVFxcVGRgWFxYUFRQTFBQUFRUVFxcWFhYVFRUUFhYUGBgWFhYUGBgWIB8cGhkVGBkVHR0YHx0ZIiQcHR8YIyccJCMaIR8ZLCwhJSodKTAfKzEfJy0eKjAeMDokLj0lLUEmLjwmL0EmKDEeHBwVHxsYIh8ZKSkcKysdLDIfLzsjLTIhLTYgLzEgMDYiKCocLDEgKTMgKC8fKi0hKS0fKC8gJSUbICAZISMZJCcbIyUbHRwXHBsXHyAZHyAaGxsXGBcVGBcWGhkWGBcVFhcVFRUTFhYVFRUTFhYU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NzMlLzQgMjsiOkcnND0jGxwoGx4wGh0rGRwnGR8yGR4vGRwpGR41GR0uFhYaExMTIyUbKSkdJiUbJigcJyccIiEZHBwWICAaIB8ZHh0XGBgVFBQSExMTFBQUFBQTFRUUFhYTFxYUGBcVGhkWGhkXHBoWHyAaICAYJCodKTAgIycaJywdJiocIyUaIyQbIyQaJCgbKCsdKzMhKikdNDYjNj8mOkIpNDUkMC4gNDQiLDMfMDwkKzYgMj0jMj4kNj4mNzsnLzAiMTciMzchNjoiIiQdExIZGhkgGRwoGBoiGBoiFhYbFhcdFxcdERERGxwYISIZISIbIiIZJSccIyQcJSUbHx8ZHiAaHx8ZHBwXGRoVFxcVFBQUFBQUFBQTFhYUFRQSGBcVGRgWGhkXGxsYGRkWGxsVHBsXHR0YJCUbJCccJCgcJikcIiYaJikbLC4jLS4kODopKTAdMD0lO0cqPkYpMjIhMCweMDIfMTQhNDwmMDckMDQkMj0kLzAhMzojNj8lLTIgLC4eKS4dMDIgMTEfHR8VExIWFRQYFBMUFRUWFBMVExMUEhETFRQUHyEaHh8YIyQcIyQbHx8YISIZICAZHRsXHh4aHx8aGRoVFhcUFhYUFRUVFBQUFBQUExMSFRUVFBQTFxcVFxcVFxcVGRkYGRkWGhsWHR0ZHx8YIiUaICEZKi4gIyQbKCkhMS4sJyIkSEA4Uk84IicaLzgiLzgiMjMjOS8iLjQiKi8fLjUhMzklMC8iNT4lLC4fKScdNjIkLi0eNDMhMjQiKy8fMjYjNTklGxsVDxAQEhESExMTFhYZFhUbExMTIR8YJyYaHh8ZHiAZHh8ZICAbHx8ZGxsWGRcUGxoXFxgUFxcVFxYWFhYUExMTExMTExMTExMTFBQUFBQUFRUTFRUTGBgWGRkXGBgWFhcUGRoWHR0ZGhoWIiIdIiEbGhkXJiIjLCgoHxwaKiQlZGFVKScbLTEgKyweKiceKSkdMzokLjAhJSYcLDAeLjEfLTMhMzknMC0kLicfOTckOC8kKyUaKy8eKi0dKCkbKCkbGhsVEREREhITExMVERERHSAZJSQaJCIaHR4ZHiAZGhsWHBwXGRkWGBkVGBYUFxcUFhcVFxYWFBQUExMSEhISEhISExMTExMTExMTExMTFRUUFxcVGBgWHBwaFxcVGBgWGBcVHRwYHRwYHh0bGRgYHBobIB4fHx0cGRYXLy0sSko/ISEWKCkdIyQbKCoeJykdLzIiLS0gMDIjLCoeKyofKiodKzEgJycdKiceMDEgLishLCcfLy8fIyIYJSMaJiQaKysdHh4YEhISFBQTHB4YIyUcHyAYHh8ZHR8YGRoWHSAZICIcFxcVFhYVFRUUFRQUFhcVFBQTExMTFRUVEhISEhISExMTFBQUExMTEhISFBQUFBQTFBQTFxcWFRUUFhUUGRgWGhgXGRgWGBYXGxkaGRcYGRgZHhsdHRocQUI6KSwgIiMZJigdJyoeKCofJykbLC0eLjEkLCwgJSQaJScbLjIhKCkcJygdJiUaJCQaJiccKCsfJigcJSQaICAYJiMaLCcbKCQbHyAaGxwXHyAZISEZJCMcHh8ZHBwXGxwXHR8ZGx0ZGBgWFxcVFhYVFRUVFRUVEhISExMTExMTEhISEhISEhISExMTExMTExMTFBQTExMSFRUVFBQUFRUVFhYVFxUUFhQVGBUXGBcXGBYXFhQVGBYXGBYXMC4qLS8lHh8YJCMdJiQfIB4ZKCgcKCccJSMcKCodJyccJCUbKiceLikdKCkdJSUaJykeISQcIyMbJykcJicdJiQaISMZISAaJiIZJiUaICAaHh4ZHh4XHx8YHyAaHR4YGxsXGBgWGBcVFxYVFhYVFxkXFBUUFBQUFRUVFRUVEhISExMTEhISEhISExMTEhISExMTEhISExMTExMTFBQUFBQUFBQUFRUUFxYUFxUWGBYWFxUWFRQUGhcXHBsaJCQhIyQeHR4XIB8bISAbISAaJCMbIyQZIyUbHh0ZIyMaIiIYJSQaJiMbHRwYJSYcIyQaKiwiKi0gJygbJSUcIyQbJCMbHh4ZHR4ZIB8YIyMdHh8ZHB0XHyAZGxsWHR0XGhsWGhsXGhoXGRkVFRQUFhYVFxcVExMTFBQUExMTFBQUExMTEhISEhISEhISExMTEhISEhISEhISEhISExMTEhISExMTFBQVFRUUGBcWGBYXFRMUFhQVGhgXHh0bGhkWHRwYGxwXHx8ZIB8aHBwXHR0ZIiMdIiMcHR4XHiAZJicbJiUbIh8ZJSQdIiMdISIaIyUbJCUaIyQaJCQbIiIaISEaGxoVGRkWHB0XHh8ZHB0YGxwXGhsWGxsWGRkVFxYUGRgVFxcUGBgVFxcVFhcVFRUUFhYUFRUUFBQUEhISEhISExMTEhISEhISEhISEhISEhISEhISExMTEhISEhISExMTFBQUFBQVFRUVFhUVFRQVFhQVFxYVGRkXFhYVGBcWGhkWGxoXGxsXHR0YHh4ZHh0ZGxsXHR0ZHB0YHh8ZHyAZIB8ZHx8aIyQdJyggICEaISIbIyQaICIZHyAaIyIbHBwVGxsWGRgUHh0XHyEbGxwYGBgWHB0YGRkWFxgWFxcVFhYVFhUUFBQUFRQVFBQTFBQTFBQTFBQUFBQUExMTExMTEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISExMTExMTExMTExMUFBQTFBQUGBgXFhYUFhYUGBgWGBgVGBgWGBgWGxwXHx4ZHh4YHh0YHB0YICEbHx4ZIB8bHh4YHR4YHR0XHx8aHBwYHB0XHx8aGxsXGhsXHBsWHB0YHB4aGhoWGhoWGhwXHR0XGhoXFRYTFhUTGBgWGBYVFxUVFRUTFBQTExMTFBQUFBQUExMTExMTExMTEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISEhISExMTExMTExMTFBQUFBQUEhISExMTFRUUFRUTFhYUFhYVFxcWFhYWFxcWGRkVGBgVGRoYGRkWHBwXGxsWICAaHx4aGxoWGhsXGxsYHRwYGBgVGRkWGRkXGBgVGhsWGBgWFxcVFhYWFxcUGRkVFRUVGRkVGRkVEhITExMSFBQSFhYUFhUUEhITFRQUEhISEhISEhISExMTExMTEhISEhISEhISEhISEhIS
font_color: "#FFFFFF"
font_color_alternative: "#e8e8ea"
background_color_brightness: 22
background_color: "#171715"
background_color_rgb:
  - 23
  - 23
  - 21
recommended_font_color_rgb:
  - 232
  - 232
  - 234
color_alternative: "#121212"
color_alternative_rgb:
  - 18
  - 18
  - 18

```
