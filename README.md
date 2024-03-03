## DIVOOM PIXOO64 Media Album Art Display: Enhance Your Music Experience
**This script automatically transforms DIVOOM PIXOO64 into a vibrant canvas for your currently playing music. It extracts and displays the album cover art, along with extracting valuable data like artist name and dominant color, which can be used for further automation in your Home Assistant environment.**

**Demo video:**

https://github.com/idodov/pixoo64-media-album-art/assets/19820046/05731164-851a-4a35-9e6a-79198c37b909

**Examples:**

![PIXOO_album_gallery](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71348538-2422-47e3-ac3d-aa1d7329333c)

**Visual Enhancements:**

- **Eye-catching Cover Art:** Witness the album art of your favorite songs come to life on your PIXOO64, adding a visual dimension to your listening experience.
- **Dynamic Color Integration:** The dominant color from the album art is used to set the font and background colors on the PIXOO64, creating a cohesive and aesthetically pleasing display.

**Functional Advantages:**

- **Sensor Data Storage:** All extracted data is stored in a dedicated sensor entity within Home Assistant, making it readily accessible for further automation possibilities.
- **Clean and Consistent Titles:** Normalize titles and artist names for easier integration with automations and consistent display regardless of regional characters or symbols. This ensures seamless use of extracted data in automations and avoids inconsistencies in visual representations. Example:
  - Original Artist: "Beyoncé" *(with accent)*
  - Normalized Artist: "Beyonce" *(accent removed)*
  
**Prerequisites:**

1. **DIVOOM PIXOO64:** [https://divoom.com](https://divoom.com)
2. **Home Assistant:** [https://www.home-assistant.io/blog/2017/07/25/introducing-hassio/](https://www.home-assistant.io/blog/2017/07/25/introducing-hassio/) (with add-on functionality)
3. **AppDaemon:** [https://appdaemon.readthedocs.io/](https://appdaemon.readthedocs.io/) (Home Assistant add-on)

**Installation and Configuration:**

1. Create a Toggle Helper in Home Assistant. For example `input_boolean.pixoo64_album_art` can be used to control when the script runs.
2. Make sure that home assistant configuration.yaml allowed external urls.
```yaml
#configuration.yaml
homeassistant:
  allowlist_external_urls:
    - http://192.168.86.202:8123 # your home assistant ip
    - http://homeassistant.local:8123
```  
3. Install **AppDaemon** from the Home Assistant add-on store.
4. On Appdeamon Configuration page, install the **requests**, **numpy pillow**, and **unidecode** Python packages.
```yaml
# appdaemon.yaml
system_packages: []
python_packages:
  - requests
  - numpy pillow
  - unidecode
init_commands: []
```
5. In the AppDaemon app directory (addons_config/appdaemon/apps), create a file named **pixoo.py** (using the VSCode or File Editor add-on) and paste the code into it. 
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
#pixoo.py
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
FULL_CONTROL = False 

TOGGLE = "input_boolean.pixoo64_album_art" # CREATE IT AS A HELPER ENTITY BEFORE!!
MEDIA_PLAYER = "media_player.era300" # Name of your speaker
SENSOR = "sensor.pixoo64_media_data" # Name of the sensor to store the data

HA_URL = "http://homeassistant.local:8123"
URL = "http://192.168.86.21:80/post" # Pixoo64 URL
# ---------------
FONT = 2
IMAGE_SIZE = 64 
LOWER_PART_CROP = (3, int((IMAGE_SIZE/4)*3), IMAGE_SIZE-3, IMAGE_SIZE-3)
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
            response = requests.request("POST", URL, headers=HEADERS, data=payload)
            response_data = json.loads(response.text)
            select_index = response_data.get('SelectIndex', None)
            if media_state in ["playing", "on"]:  # Check for playing state
                new = self.get_state(MEDIA_PLAYER, attribute="media_title")
                if new != "TV" and new is not None:
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
                    self.send_pixoo(payload)
                    self.set_state(SENSOR, state="on", attributes=new_attributes)
                    if SHOW_TEXT:
                        payload = {"Command":"Draw/SendHttpText",
                            "TextId":3,
                            "x":0,
                            "y":48,
                            "dir":0,
                            "font":FONT,
                            "TextWidth":64,
                            "speed":80,
                            "TextString": normalized_artist + " - " + normalized_title + "             ",
                            "color": recommended_font_color,
                            "align":1}
                        self.send_pixoo(payload)
                else:
                    payload = {"Command":"Draw/CommandList", "CommandList":[
                        {"Command":"Draw/ClearHttpText"},
                        {"Command": "Draw/ResetHttpGifId"},
                        {"Command":"Channel/SetIndex", "SelectIndex": 4 },
                        {"Command":"Channel/SetIndex", "SelectIndex": 2 }
                        ]}
                    self.send_pixoo(payload)
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
                self.send_pixoo(payload)

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
        most_common_colors = [item[0] for item in Counter(lower_part.getdata()).most_common(10)]
        candidate_colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255)]
        for color in candidate_colors:
            if color not in most_common_colors:
                font_color = '#%02x%02x%02x' % color
                break
        #font_color = "#FFFFFF" if brightness < BRIGHTNESS_THRESHOLD else "#000000"
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
        if ratio < 2.5:
            # If brightness is high, use black; otherwise, use white
            recommended_font_color = "#000000" if brightness > 128 else "#FFFFFF"
        return gif_base64, font_color, recommended_font_color, brightness, background_color, background_color_rgb, recommended_font_color_rgb, most_common_color_alternative, most_common_color_alternative_rgb

    def send_pixoo(self, payload_command):
        response = requests.post(URL, headers=HEADERS, data=json.dumps(payload_command))
        if response.status_code != 200:
            self.log(f"Failed to send REST: {response.content}")
    
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
6. Open **apps.yaml** file from the AppDaemon directory and add this code:
```yaml
#apps.yaml
pixoo:
  module: pixoo
  class: Pixoo
```
7. Restart AppDaemon
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

Here’s an examples of the sensor values:

```yaml
artist: Björk & Trio Gudmundar Ingolfssonar
normalized_artist: Bjork & Trio Gudmundar Ingolfssonar
media_title: Það Sést Ekki Sætari Mey
normalized_title: Thad Sest Ekki Saetari Mey
media_picture_gif_base64: >-
  zMGWyr6MxbNvxbRxyLyLybyJzL6LzMGRzcCUzL+Sy8CRyr6Kx7qEyb2OzMGRyr+Sy8CTzMGSy8GTy8KSzMGTy7+Ry7+Py76Vyr6Uyr+Tyr+Vy8CSyr+Tyb2Qyb6QysCSzL+TybqFyLmByr2Mx7uLyr2RzcCNzL+Oyb2QyryIyb2KzsSWy8GSyL2RzcCV0MSWyr+Tyr6Syb+Qyr6Syr+Tyb2QyLqIybuGyr2Oyb2WybyNyLqIyb6Qyr6UysCVy76Uyr6QyLyGxLFqxLJuyLuIybuFyryJzMGSy7+Tyr2Ryb6RybyIxbiAyLyNy7+Ryr6Qyb2Oyb6Kyb2Kyb2IyLyIyLyEyLyFyLuKyLuMyb2Pyb6Pyr+Qyr+RyL2Nyb6Oyr6RyL2KxbVyw69jxbZ9zsCNy76St6p+vrGDzcGPvrGAvrKEsKaBua2CzcGTvbOLr6Z/y76Syb2RyL6QyL2PyL2Qx7uMx7mFxrmDyLqMybyPxbmGw7eCyb6Qyb6Syb6Ryb2Ry7+RyLuGxLFpxLFuyLuJybuGyr2Ly8CPy7+Ryr6Ryr6RyLyJx7uByLuHybuJx7qGyLuHyLuCyLuFx7uDx7uEx7qCyLqDx7mHxrmGxrmGxrmEyb2Jyb6OyLyKyLyNybyOyLuHxrVzv6xdybh1p5xzTUQ4KiIiNzAqWVBBgnZZamBJHhYWjoJj1sqbX1lGLSUfw7aLyr6RxryNxruNx7uOx7qMxriEybuCz8OQzcCR0sWPzsKKyL2Oyb2Qyb6Ryr2Py76OyLuFw7FnxLJuybqJyLqGybuKyr+Oyr6Oyb6Syr+SyLmDxLNtxLV1x7qDxrqEx7qFyLyEx7yFx7uHx7qExrqDx7qEyLmGx7qFxriExrmDxrqBx7qEx7uHybyMyLuLx7qHw7NyxbFfr59kNi8oSj41cmhSaV9JLSYifG9Sua6CTUU5m45s286cnZRyf3Ray7+Pyr6PybyPzcGSysCQyLuLyrqEsqZ1Vk49TUM4X1dDgHVWx7qLyb2PyL2Pyb2Jy76OyLqHw7FnxLJuyLuGyLqEyb2IysCNyb6OybyRyb2KxLRtv6tXxbNwyLuGx7qEyLqGx7d5x7h+x7qHxrmDyLqEyLqDyLmEx7mGxriFxrmFyLqCyLmAx7mBybyJx7uJxrmGw7NxyLVhZVk5dWpRz8OS0cSP3tCWrKF4m45h2s2ZZ19LqZ13kohoUEg4m5BuoZh0Rz0xlIlrXVVFV08/vK6Bzb6IeG5Qc2dRiYBjS0M1gHJVzcCOyLyMyb6Px7yFy7+PyLqHw7BnxLJsx7uGyLmEybuJyr+Qyr2Nx7mHxrqDw7NswaxZxLRzxrqFxriBx7qGw7Jrw7NvxrmGxriDxrmBxrmBxrmCxbiDx7iExrmEyLmBxrmAxLd+xrmByLqGxbiHxrZzuKdaZFk9w7WEyb2MoJRuiX5fj4Zkn5Joy76NYVhFrqJ5pZl3ODEqfXJYua+EU0o7OzMramFMOjIqjoNe1siMem5Qk4douK2DcGRMva57zL+PyLyNyL6Px7uEyr2NyLmFxLBnxLFux7uGyLqDybyNyb2Ox7qDxbiDxLqDwbJqwK1cxLNyxbmDxLmAxbmFwrFrwbBrxrmFxLiDxrmCx7qExbiCyLuGxraFxreDyLl/yLl/xbd9x7h/xrV3xriHx7d1uKZbXVQ5vbCA1MmUpJhwhnpcSkM2a19G1ceSa2FNua2C4dSijYRkj4Rk5NeklIlojH9j59mhfnVWn5Fpzb6FdmxOVEo9ZFtFoJJoyr6FxrmLyL2Qyb6Qx7uFyLyJyLuExLFoxbJtyLqFyLqEybuLyLqGyLmCxrmDxbmEw7Jov6taxLJyxrmExrqBxreAwK5jwLBqxrmFxrqFxreAr6JxtKd0rqBzz7+MyLmFx7iCx7iBxrd/xrd7wa9nxreExLN2x7NjWE00PzUudW1VenJZXVZCKCEglIZfppxxQDgwm49ws6iBSUE1bmRNuq+FU0s6YVZGxLiJcWxTYVdDi4BdNC8nd21WfnJcg3dWuq18yr6Pyb2QyLyNx7mCyLuHx7mCxLBpxLJuxriExbiDxrmFxrqEx7iCyLiExrmEwbBnvqtXxLNvxrmEx7qCxLRzv61dwrBqx7iEybuEv7J+em9RnI9mm45jjYBcqJpwzL+JxbeBxriDxLR1wKxdxbZ+w7N2xbFgqZlcST80KCEeKyIfPjUsem9Tx7mDgnlWPzcwhnphn5VxRTswXlI7p5txW1E/WlA8t6p+hnxgWk8/npBoSkM2U0s9WlFAPTUreW1S0seSxryNx7qJxrmCybuJxriExLBnwrBvxbiFxriExbeGxbiIxrmDx7mFx7mDwK9ov6paxLRyxbqHx7h/w69jwK1ewbBnxriBxrmEybyDmYxkkIJdgXZWUkY3qJlwxriGxraCx7eFwrBswatbw7V2xLN3v6tZx7JnxraFtKd9tKd4wrWCz8KOxrqDxbmEyryNyLiJxbeDx7qJx7qBxLeDy7yJzcCKxrqGxbmLzcCLuqt7T0c3joZnoZVybGBHl4tkzsKRx7qMx7iHx7mHx7qLx7iFw7BlwrFwxbiGxrmBxrmFx7iGybuFx7qGx7mBwa5mwKxdw7NwxbqFwrN0wa1gwbBpwLBoxLiAxbiCy7uDopVsaV5Gq55ye3FTa15InY9lzL2IxLR8v6xhwKtaxLVzxbR4wKxdwK1jx7eFzb+Oy76LxrqIxLeJxLeBx7qFxLiFw7WCxLeEw7WFw7R/xLeCw7aCxLeCxbeCxLaHw7aEyLqDgndXVEo8eW5Wrp9uzb6ExrqMyLqKx7eGyLuKyLuKxbeEw69kxLFwxriHxrmAxrqDx7iHxrV1xrV1x7mDwq9lwKtdwrJvxbmCv65nwK5kw7Jwv61kxbeAxbiCzb+EiXxbXVA9k4djRj4xSD0yqptwybqIwa5uv6pbwKxaxbZ6xbV3v6xav61jxraCx7uMxrmIxrmHx7qLxrmBxLeDxbeFzr+JyLmDyruKzb2HxbeBxLiCwbN+wLF/xLaGz8KMuax6qZxzzsKQz8OPyr2BxriByLuLx7mCxriHybyOyLuLxbeEwq5iwrBwxLeIxrl+xbiCxLR8v6pfwa9ixrh/wK9lvqldwbJuxLd7vapfwrJtxLVzv6xhw7V8xLeAyr2GlohkeGtNfnJTd2tQdWpNw7WGxLR7watfwKtcwa1hx7iDw7V1wa1cwq1kxbaCyLuLx7qGx7qHyLqKxbeAyLqIwrSCgHRYT0c4XVRDhXpZin5Wc2dMNCsnlYlf0cWPlYtmNy8mVUo8xruLxbiKxLZ+xrmCyLuHxrh/x7uJybyPybyMxbiEwq9lw7NyxLeHxriAx7qCw7JtwKxfwa9jxrd9wrBkv6tYw7Jxxrd7vqtgxLZ4xbZ1wa9fw7d8xriDxriDwLN+wrWCd2pQe25Qf3VUopJnyrVuv6hZwaxdw7Ftx7iJxLVzv6xcwK1hxbd+x7qMxriFxLaDxbmLx7d/wrF4Ukk4JRwdOjAlOjAjHxgbal06nYtQOzEll4dZ18mOk4Zcf3JUw7WIyr6PxrmLxbiAyLqEyLqCx7l/yLyKyb2Nyr2MxbiCwq5ixbNzx7mFx7iCyLmAwrBkw65ewa5ix7d8w7BmwKxZxLRyxLZ4wa5lx7mBxbZzwK5gxbZ9yLqCx7mByLmCx7iCxbeFqZxtbWJITUIyrJhaw65dvapdx7V6x7iFxbRywaxfwKxfxbZ4zL+Qz8OMzsGGzb+Ozrt4eGpBRTorqJZavqpexrBkh3VKgHBC18FraFs6pJdqs6ZzVEs2Rj0zWk9BsaZ+yr6LxLZ+ybmCybmAyLqEyL6Lyb2Nyr6Px7mCwq5exLNyx7iFx7mGxLV4wa5cwa1ewa5fxrd4wrBmwKtbxLJxw7Rzwa9qx7qHxrdwwa5fx7aBx7mDxbmAxriBxrd/yrqCva97Rz8yHxodZFc3yrNiybZvx7aBxLaBxLRywatev6tgyLl8p5x2jIJijoNYnY5kxrmBYFU7qpdZyLRirpxUpZJNpZFWqJRZwa5pZFhCsqZ3cGdHY1Y2bmE9Ny0lY1hDzsKOwrV9yLmCyLmCx7mFyL2LyL2Ny8CNybyFw69gxrR2x7mHyLmBw7Frwa5cwa5ewa1exbZ2xLFpwq5bw7JyxbV5xLJtyLqFxrZzwa5hx7iAx7qDx7mBx7eBxrd+yLqEuat5PDQrJyMjKCMiU0gxnpBnybyIzb+LxLN0wKxcv6tbzr9/d21TNy0jPTQnYFQ+uat7aV5Fx7d/z716l4laa19CUEc2Z1o/yLqBbmNIsqV3amBEzLhi2MNktadyYVhGyr2LxrWAx7mFyLqGyLmHyr2Pyb2Oy8CNy76Mw69mxbR0ybqHyLZ4wq1dwa1cwK5fwa1dxbZ1xLFqwa1bw7NvxriAx7h7yLuGxbd3wK5fxrh9x7qDyLmAyLiCxrd+xriDwrBxRj4vKiUiPzYsPjYwJR8cT0c3n5RuxbR2wKtdwatgxbV6wbSDv61tvapgxbZ9yryHU0o2a2FIqZt1p5pxkoZkOzUsd2pPtah4WU86saN2TkU3YVQzjn9LXFE8c2lP0cORw7V/x7mEyb2Myr2Oyr2OyryQzMCOyr6Px7d5xrV2yLuExLJswqxcwa5ewa5cwq1bxrZ2xLFowa1aw7FvxbmExrl/yLuFxrd6wq5dxrd8x7qEx7qCxrmEx7mCxrV4valdfW1AYFM3aF9CkYNhoJRuNTApIx0gkoFRyLJfwKtixLR4x7yHxrVxwa1ew7V5zMCHlotiKB4eIhsbIx0dHxgYQTYrsaN1dWtSIhkYi3xbopduPzUpMiglUEQztqh0yr6LxreAybuIyb6Pyb2MyLuIyLqIy7+Nyb2MyLqDyruFx7dzw61dw61fwq5dwq1Zwq5dxbV4w7Bmwa5axbRvxrmEx7h+ybuDyLh8wq5dxrd7ybuFxrp/xrqDybiAw69iv6pT0b5xiHtXWlI6X1Y+1MiUj4hoGBMZfWxByrVfvaldxLV6x7qIxbNvwatexbd6xbiDzLyHrJ9zg3dXgnVYnZFoxLWCzb6It6x5rqFwt6p6yLmDv6xgsJ1Wxbd7yryAx7uIx7iAyLmFyLuIyLmEx7qGx7qHyr+Oyb2LxrqDyr2Ix7d0wq9hwq1exK9hxK5dwK1dxbR4w7Bmwq1ZxbNwxriFx7mBx7uDx7h6wq5cxrd3yLqDx7l+x7qFxbRzwq1iwrJwzr6BlYtiWU45WlE8o5dxsKd6IBsddWY+y7ZhvqlbxLR5yLyJva1ruqZcx7Z7x7mDxraDy72Cz8GFzb+Ezb6Fx7qEw7R/wLJ7y72CnpJou614w69iw69gxbd6xLh/yLuHx7qCx7mBybl+ybmCx7h7ybmGyr+Nyb2LybmDybp/ybuByLl+xLJwxrRyw69dwKxYxrV2xLNmwq1ZxbRwyLqFyLqAyLyBx7p7xK9dxrZ0x7uEyLp+ybqDxrV4xrd+xriAyrx/saRyjH5Xe3FRWVJBTkc4IB0ecGNAy7Vkv6xbxLR4yLuFwrJuv6tfxrV5x7iDx7aDxbeAxbZ9w7R7xLaAv7N9va13xbV9uKx2nI9myruBwaxhwKxhxrZ6xrqDybyKybqDybqAyLqBx7Z6wq9cxrV2y7+Oyr6MxrZ2xbZ1yLuEx7iAx7qIyLyKxbNxxK9lxrV2w7FowKtXw7JryLmDx7mCx7yAyLp+wrFlxbd3yLuHyLyIybyHx7qExbmBxrd/xbd/wbN/rZ9tjIRgKyYmIx4eJyMjPzUntaFawa1cxLRzx7mFxLRtwKxdw7R3xriCxbaCxbiCxrh+ybmAzb+ErJ5vuqp3y72El4tgrKBuy71+wq1iwKxgxrZ5yLuIyL2KybuHx7h8ybuAxbRuwq1YxbJqy7+Pyr6LwrBkxbZ3yLuHx7mByLyJyL2NyLqGx7mBx7qGx7h9xbRxxbd4x7uGyLuIyL2HyL2Gx7qBybyIyb6Myb2Nx7uExriCxbmAxLiBw7R6zb+G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X1I8vK54ybh3w7Jxxrp/x7l5x7mDybyJyLyKx7qBx7qCx7qDx7qJxbRwvKhYRjwrbmNKm4xlj4NgppltppdhTUU2Qjovu616wLR9gXdZoJVu0caSx7uIyb2MxbmExbqDz8KIzsCDn5FobF9GhnlbjoNkV08/PTYtNzAqJSAfST42kIRniH1eUUg5NjAqZVpDem9RlYlqvbGCjIFfJBwbYFdFv7SK1cqWzcKP0siUpJdxr6F5x7uNcWZPbmNQY1dEvrCAybyCw7Fmw7JxxrqBx7l9ybyKybyLyb2LyLqCx7qDx7qCyLmHx7d/wbFnrJxsu6x8u657lIlic2dOPDMnXlNAWlFAYlhCtql5aF9It6yCzMCMyLyIyb2Lx7qFx7qFxriCxrZ9zr+ExbiFsaV9WVFBHRgaJSAgJiEgKSYlKSQiZ15Jf3JUmoxmWlA9Y1lCiHtch31jdGhOua58UEY4u6+E0caXpZp2p5x3yb6NtKp/bGBIva+GtKqDVEg5pJZ0zcGNxLd8wq9fxLJyxrmDyLyFyryMyLyKybyKx7mEx7qDx7qEyrqFx7iFxrmDy72GxrmEx7uCva96tKZ4g3dSTkUyl4xpKyQhkYRe2MyXx72LyL2Iyb6Jyb2Lx7uFx7uGx7qCxrh+xbaAxLSE18mbkohpSUI3PjgzMSwoKSUlIBwajoJlgndbmYxkdmpPS0EyWE48a2FMeG5Stqp2fnNWtKmBaWFNLCUjQzkwwLSFvLGEgHVZkYRndGpOoZZvzsKTxbmHxrl8wq5exLNwx7uGyr2Kyb2LyLyKyb2JxrmGxrmEyLqFyLqHx7qFx7mCx7iCxLeCxLeBx7qCsaRxqptsjYNdiH1caV9IMScit6uByL6Ox72Lyb6KyL6Kx7yGx7uFxrmFxbmAw7eAzcCKtamBdGpQnpRwOzUtIRseJSAhRz40v7OKkIRmh3labmNMX1RDUEY1bmRPfnJZq5xvcGdLXlZDJB0eJiIiTkM5yLuNu6+EoJNu1cmaxbqLy76Ox7qJx7uLxrh+wq1dxbRuyL2Gyb2Myb2KybyKyLyJx7qFxrmFybqFx7mHxrmEx7iDxriCxbiExbiDxbl/yLyEy76IvrF9d2xPqpxyRj4vgHdb0siWxryKyb2NyL6KxrqExrqGxbeEwrZ/yb2EraJ2e3BZurCFY1tHaF9KXVVFRj0ywLSIxLqO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yb2Lyr6Oyb2LyLyMyr2Ox7uExrp/yLqIy76Nyb6NyL6OyL2NxrmHxLiHw7eFyr6Kx7h5vqtgvq5rgXZNWE08qJ52pJt2cGVPm5BxeG9XPTYrOTYuenFZKyUiLCcmLykmJCAfYVhI1cmZhn9hJB4fLScnJiAeoZZ01MeXrKB5Ix0eRjswwrSD2MuZn5Vvi31azL6IxLl+xrmBxriExrqFxbJtwaxawq1dwa1awK1hwa5ewqxfxbZ3wq9kwaxXxLR3yb2Lyr6Nyr6LybyNyb2OxruCxrt9x7uGy8CNyb6Pyb6RyLqHwbFwsaJrybuFxLaDxLV2wa1bwrFnwKxlY1g4KiMidmtUwLOKbGRMkolqWFJBLCUjPzcxLScmLicmKSQiGxcZQjkwz8GUhX5iJB4fKCMjPTYuu66Hy7+Tw7eGaF5IQDYpuKt9zL+SvbGEg3ZUxrmDyLuCyLmFx7qJx7R6watcwq1Zw6xdwK1bxbNywq5hwatgxbZ6wrBlwKtXxrV6yr6Pyr6Pyb2NyLyNyb2Nx7yDxrp/x7qDy7+Nyr+OyL2MxLNxwKtZw7N1xriGuax9xLR3wKxer55eqplZYlY4QTowY1hFVEw8UUs7ioJgRj8zJR8gLCclLSgmJyIhRj00hnthmI1sz8OWd29XJB4gKyclOjQsuKuFy7+VyLqIy7yJvbF+xrqEybyPy76OqZ5twbWAybyEx7mGxrmEwa5lwaxgwq5bwqxcxbJyx7h9wq1gwqxixrZ6xLFlwKtYxrZ7yr+Pyb6Nyr6NyL2Myb2NyLuFxrmCxrmFyr+Lx7uIyLl+wq9iwa1bxbR2yLuIz8KOzb19nItOemtGWE0zbWE9tKV00sONpZtuf3RWsqd+j4dlRDwwLSglOjMuKiMhhXhf3tOjzsKSzMCRsKZ/NjAqWVFCMSomamFNz8OXw7eExbiFybqHx7qEyryPyryNy76FybuGx7uEyLqDwrFtwK1fwqxfwK1ZxLJtybmHyLd9wq5ewaxhxrZ7w7FlvqpXxLZ4yr+Pyr+Oyr2Oyb2Myb6NyLuHxriExriIyL2Ex7qFxbJtwa1ewK1axLR1yb2Iv7N9em5OVkgwf3BJt6NZzLdkpJZkuKx70MOGxbmFzcGRzcOMyr6IfHRZPjcwOzMsm5Fwv7OJwraKx7yOz8OTZFtHUEc6dm9YMCkkv7OKxLmFvbB9xrmIyLqFyb2Pyr+QxrqDybqEyLuGybh4wq1fwKxjwKtbw7BoyLmBx7iDyLh7wa1ewaxjx7Z/wa9iwK1iyLuAyb+Oyb6Oyr6Oyb2Myb6Nx7uIx7iDxbiIyb2HxbR0wa5ewq5hwaxcx7d2wbWDhXpYd2lJlINKx7Vsx7RkvKlataZxzMCLrJ9yeGtOzcGMwbR5s6RfzMCFUUo5JBwbuKuDu7CHnpJvzcGSw7iIpZp1OjApsqiBVk8+mo5v0cWRwrWBx7mHyLqIyb2Myr+RybuKyLqDyruFxbNowa1dwKxewrBox7mExriEx7qEx7d+wq1iwaxlxrZ+xLNvx7V9yb2Jyb+Oyb+Pyb6Pyb2Nyb6NybyHyLiDxriIx7d2wa1jwa1cwq5jwq1ixbRxxbeEoZZruahvybVgw7BlwrBjw7Bbx7h70cOKhnlNo5Rh08aIr6RspZRYzsGFsqZ7emxRwLSD0MWWqp55p5p0y8CRyL6NW1NCqZ54t66GZlpHybuNx7yFx7mIx7qHyb2Kyr+Pyr+RyLyKx7h5w69ew61cwq5kx7h/xrmIx7mEyLqFxrd+wa1hwq5pxriFybqGxriGyLyJy7+Qyr6Nyr6Oyr6Nyr6PyLyHybqEyLqHxLFhw61hwa5dxbJuxK9kxLNsyryHzcKHyrp9w69dxLJkw7Bkwa1cx7d3vK5ntqRZxrp7zsKGnpJirZxay76DybyFzsGIxruDyLuLzsOZppp2sKR91MmXkIdpiH1g3NCdX1dEbmFLzsKKxrmHxrmHyb2Jy8CQy7+Tyr+Sx7h+xLFowq5gxrN1x7qDx7mEx7iEyLqFyLqFxbZ2yLiCyLuMx7mGxrmEyLyLy8CQyr+Myr2PybyMyLyLx7d8xLFqw7Buwq9ewq1hw7Boxrh+wq9jxLJsyb2IyLyGyLh8w7BgxbNnxLJnw7BjvqxjnYtKxbVvx7uIyLyGl4hYvqxnyLuFxrmExbiExrqEyLyJzL+UzcCSqJ11xbmIwLWMWVBByLuNfXZXHhcXi35bzsGLxbmEyb2Ly8CQy7+UysCUyb2KyLqHxreAybuJyLyKyL2LyLuNyb6Pyr6Ox7uEx7mEybyLx7uFxbmFyLyLy7+Ryb6KybqIx7mCx7qBx7Vzwaxbwq1hw65ewq5jxrZ7yLuGxLFnxbRwyLyJyryIybl9xK9gw7Jnw7FoyLVhpJFPqJdZyr6Dx7qHx7uIrp9oxLFpx7mDx7uEx7qGxrqFy76MvrGFyr6Ryb6PwraJgXZcIx4deG1Vg3peGBMWZlxIzsGMxbmEyb2Ny8GTzMCTyr6QyLuGyLuIyLuMyb6QyL2Syb6Nyb2Qyr+Syb+NyLqCx7qDyL6Lx7yGxrmEyL2MyL2LyLyDybmEyLiCyLqFxbZ3w65iwq9kwq5cxLBsybqJyLqExbFoxbRzybuKyryKybmBxLBkxLNrxbNrxK9eq5hdxbeAx7yGyb2Iv7GCuq1yyLZqyLqFx7qFx7qHx7uGyr2OsaV/rKJ91cedp5x5HhsZHxkbb2RPppx6IhwabmJM1MWRxbiFyr6PysGSzMCUy8CRybyHybuJyryOyr+Syr6Syr2Oyr2PzL+Tyb6PyLuEyLuEyb+OyLyHx7qFyLyJyLqGybmGyrqGybqDyLuGxrd4wq5ixLFkwa5fxrR9yLyLyLuDw7FlxrR1yryNy72PyLqDxK9pxbNxxrZzxbRwyryGybyIx7yGyb2Iv7KDw7R3u6hoxLeEyr2Ix7qGyLyNy76Uppt4mY5swLOLs6eGSUA1h3tiyr6V0sabm49to5Zsz8GOyLqIyr6Qy8GTysKUy8CUyr2JybuJy76Ry7+Tyr6Ty76Sy7+Qy7+TysCPybuGyLuFyb6QyLyJx7qFx7uFyryDybuGyLyFyLyFyruIyLh4wq5jxLFiw7Fnx7qHyLqKyryGxbJmxrZ0yr2Ny7yRybuAwrBmxLR1y76Oyb6IyLuGybuHyLuIx7uFyb2Jx7l/n45YxriFyr2Kx7yJyL6RzcKXwLWPxLmMw7ePxrqTx7uS0saZzMCWy8CW0cSU0MKOyLyKybyKzMGSysCTy8GSzMCUyryKybuIyb6UzMCVy76Vyr+TysCSzMKVyb6PyLqFybqFzL+Syr2LyLyGyLyEyLuCx7uFx7uGyLuGyLuIyLd5wq9jxbJhxLZ2xLmIyLuJw7WDxLFkyrp3zMCOzb+Qyr2Gyrp+zMCKyL+SzsOUzsKPzL+KzL6NzcCMysCKx7mBvaxpzL6Ix7uLzMGUz8WaysCVz8ab0siasqWBvbCK0caXzMKWyL6Ux76Tyr6Qv7KFx7uLzsGPxLmN0cab08ab0seb0MOSzsKOzcOXyr+W0caY0MSYy8GTxbmOz8SVzcGLzL+KybyPxbmLyLyIzsGL0MGMzsGM0MOMzsCJzsGNzb5+xrRjxrJgwLSIk4ZkqZt0npFprJtgrZ1ptqt/y8CUpJlyqptxv7SCn5Rws6iBua6Hv7KEva+DvK+Ctap8r6J0u6tzraB4q598raN8tKiBrKJ7rqF9wLWOh3xgr6OAsaWArKF6pZx4mY9sv7OImItnmoxnsaN5k4Vhppp4ppl2sKWArKB3q51zqJt3npJwq6B5qJx0x7yQnZFupJdxsaR3qZxumY1moZZxk4ddqZxxpphup5pwoJNoq55upJdsn5JgsJxTybRevbKLiX5gqJ17oJRxnpFrnZBtpJd0wreQmIpsmYtmnZFroZRynZBwlYhooZVxm41um5BumI5tn5Nvmo1pmY1toJNzoZRypZl2pp14qJp4wrWPnZFzsqWDsaSAp5t2sKaApJt4wbWKopRupZdwp5lyr6J7qp57qZ17qJx7p5x4rZ98qp18ppl3oZNxr6J8y8CUs6iAs6Z/l4lklodgrJ94saV/saV1q51vqZxwqp1xqJtwr6FypphvqJlpvKhexrNcyr6TysGZwriPyb6Tyb2Ly8CSzMKVzsOYyb6Py7+Lyr6My8KWz8OWz8SZzMGWy8GZzMKay8GVysCOyb2LysGVy8GXzcKYzMKZy8OYzMKVy8KYzcObzsOazcKXzcOVzMGXzMOczMGRyr2MzsGRzMCMzcGUzcSbzsOWzsSZzcSYzsKZz8WZzsKYzcOWzcOWzMGUzcKW0MSXxrmIw7aFzcGUzsKVzsOSzsKOzsKOzcCNzcGJzL6JzsGNzb6CxbFkxbBf
font_color: "#00ff00"
font_color_alternative: "#37457a"
background_color_brightness: 173
background_color: "#c8ba85"
color_alternative_rgb:
  - 198
  - 185
  - 132
background_color_rgb:
  - 200
  - 186
  - 133
recommended_font_color_rgb:
  - 55
  - 69
  - 122
color_alternative: "#c6b984"
```
Arabic Title:
```yaml
artist: Tamer Nafar & Yacoub Alatrash
normalized_artist: Tamer Nafar & Yacoub Alatrash
media_title: آمين
normalized_title: amyn
....
```
_______
## Test & working on
Sonos Speaker with the following music services:
* Apple Music
* MixCloud
* Spotify
* Tidal
* YouTube Music
* Local Media (if the music file also contains the album cover art)

*Not compatible with SoundCloud*
