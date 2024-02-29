## PIXOO64 Media Album Art Display: Enhance Your Music Experience

**This script automatically transforms your PIXOO64 into a vibrant canvas for your currently playing music. It extracts and displays the album cover art, along with extracting valuable data like artist name and dominant color, which can be used for further automation in your Home Assistant environment.**

![PIXOO_album_gallery](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71348538-2422-47e3-ac3d-aa1d7329333c)

This script assumes control of the PIXOO64 display while it’s in use and a track is playing. To exit this ‘mode’, you’ll need to change the PIXOO channel either through the Divoom app or the API. This is why the script relies on an input_boolean entity that you’ll need to create in advance. You can toggle this entity when you want the album art to be displayed automatically. Meaning that when the toggle is activated and the script is running, the PIXOO display will turn on each time you play a music track. If the music is paused, the PIXOO screen will turn off. Upon turning on the display, the most recent album cover art will be shown. To switch to other channels, such as the visualizer, clock, or custom channels, you’ll need to make the change through the Divoom app or API.

**Visual Enhancements:**

- **Eye-catching Cover Art:** Witness the album art of your favorite songs come to life on your PIXOO64, adding a visual dimension to your listening experience.
- **Dynamic Color Integration:** The dominant color from the album art is used to set the font and background colors on the PIXOO64, creating a cohesive and aesthetically pleasing display.

**Functional Advantages:**

- **Sensor Data Storage:** All extracted data is stored in a dedicated sensor entity within Home Assistant, making it readily accessible for further automation possibilities.
- **Clean and Consistent Titles:** Normalize titles and artist names for easier integration with automations and consistent display regardless of regional characters or symbols. This ensures seamless use of extracted data in automations and avoids inconsistencies in visual representations.
  - Original Title: "Beyoncé" (with accent)
  - Normalized Title: "Beyonce" (accent removed)
  
**Prerequisites:**

1. **DIVOOM PIXOO64:** [https://divoom.com/](https://divoom.com/)
2. **Home Assistant:** [https://www.home-assistant.io/blog/2017/07/25/introducing-hassio/](https://www.home-assistant.io/blog/2017/07/25/introducing-hassio/) (with add-on functionality)
3. **AppDaemon:** [https://appdaemon.readthedocs.io/](https://appdaemon.readthedocs.io/) (Home Assistant add-on)

**Installation and Configuration:**

1. Create a Toggle Helper in Home Assistant. For example `input_boolean.pixoo64_album_art` can be used to control when the script runs
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
| **TOGGLE** | Primary toggle sensor triggering the script | `input_boolean.pixoo64_album_art` |
| **MEDIA_PLAYER** | Media Player entity name in Home Assistant | `media_player.era300` |
| **SENSOR** | Sensor to store data | `sensor.pixoo64_media_data` |
| **HA_URL** | Home Assistant local URL | `http://homeassistant.local:8123` |
| **URL** | PIXOO64 full URL | `http://192.168.86.221:80/post` |
```py
import re
import base64
import requests
import time
from collections import Counter
from io import BytesIO
from PIL import Image
from PIL import UnidentifiedImageError
from appdaemon.plugins.hass import hassapi as hass
from unidecode import unidecode

#-- Update to your own values
TOGGLE = "input_boolean.pixoo64_album_art" # CREATE IT AS A HELPER ENTITY BEFORE!!
MEDIA_PLAYER = "media_player.era300" # Name of your speaker
SENSOR = "sensor.pixoo64_era300" # Name of the sensor to store the data
HA_URL = "http://homeassistant.local:8123"
URL = "http://192.168.86.21:80/post" # Pixoo64 URL
# ---------------
IMAGE_SIZE = 64
BLID = 10 # To exlude the blid, chage to 1 (not 0)
LOWER_PART_CROP = (BLID, int((IMAGE_SIZE/3)*2)-BLID, IMAGE_SIZE-BLID, IMAGE_SIZE-BLID)
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
                    gif_base64, font_color, recommended_font_color, brightness, background_color, background_color_rgb = self.process_picture(picture)
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
                        "background_color_rgb": background_color_rgb
                    }
                    self.set_state(SENSOR, state="on", attributes=new_attributes)
            else:
                payload = {"Command":"Draw/CommandList", "CommandList":[
                    {"Command": "Draw/ResetHttpGifId"},
                    {"Command":"Channel/OnOffScreen", "OnOff":0} ]}
                response = requests.post(URL, headers=HEADERS, data=json.dumps(payload))

                if response.status_code != 200:
                    self.log(f"Failed to send REST command with image data: {response.content}")
                    
    def process_picture(self, picture):
        gif_base64 = ""  
        font_color = ""  
        recommended_font_color = "" 
        background_color = ""
        brightness = 0
        if picture is not None:
            try:
                img = self.get_image(picture)
                gif_base64, font_color, recommended_font_color, brightness, background_color, background_color_rgb = self.process_image(img)
            except Exception as e:
                self.log(f"Error processing image: {e}")
        return gif_base64, font_color, recommended_font_color, brightness, background_color, background_color_rgb

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
        lower_part = img.crop(LOWER_PART_CROP)
        lower_part = self.ensure_rgb(lower_part)
        most_common_color = Counter(lower_part.getdata()).most_common(1)[0][0]
        brightness = int(sum(most_common_color) / 3)
        font_color = "#FFFFFF" if brightness < BRIGHTNESS_THRESHOLD else "#000000"
        opposite_color = tuple(255 - i for i in most_common_color)
        recommended_font_color = '#%02x%02x%02x' % opposite_color
        background_color_rgb = most_common_color
        background_color = '#%02x%02x%02x' % most_common_color

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

        return gif_base64, font_color, recommended_font_color, brightness, background_color, background_color_rgb

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
____________
**You’re all set! The next time you play a track, the album cover art will be displayed and all the usable picture data will be stored in a new sensor.**

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
| **background_color** | The color of the background |
| **background_color_rgb** | The RGB values of the background color |
Here’s an example of the sensor values:
```yaml
artist: Ivar Bjørnson & Einar Selvik
normalized_artist: Ivar Bjornson & Einar Selvik
media_title: Rop Fra Røynda / Mælt Fra Minne
normalized_title: Rop Fra Roynda / Maelt Fra Minne
media_picture_gif_base64: >-
  urq0vby2wL+6vLy2v765wcC7wsG9w8O+xMS/vr65vLu2v765vr65srKuv764u7q0u7u1sLCqtLOtvr64xcTAxsXBxMO+vby3srGstbSutravubmyu7q0u7q1t7exvr64vr24vr24vLy3srGsu7u2v765vr24vr24vLy2ubi0sLCruLizwsK9wcC8wcG8xMO/xMTAwsK9ubm0u7u2wsG7urq1u7u2yMjDxsXBxsXBw8O9vb23t7awvLy1uLixuru0s7Ktubizvby2vr23w8K+w8K+wsK+v765v765v7+5vLu2uLe0vLu3uri1ubizurm0wsG8srGttLOuxMS/xcXAwsG9vLu1u7q1vLu1tLOttbSut7awuLexu7y2srKttrWwv766vLu3v765uLeztrawvbu2vr65v765vr24uLeyu7q2w8O+w8O9w8O9x8bByMjDycfDwcC8wsG8v766v7+6v765vby3v8C6wsK+vr24w8K+vLy3uLiyu7q0urmzsbGrtLSvtbWwu7q1vr24wMC7vb25u7q1vb23u7q1trWwsbGrurizwL+6uLayurm0uLeywMC7srGtuLeytbSww8O9xsXAwcC6ubmzt7awurq0urizu7m0u7q1vLu1u7q1s7Kuvby4wL+5v764wL+6u7q2ubizvLu2wsK+wcC8ubi0w8O+w8K9wsK9wL+6xcS/x8fCycnFyMjDxMS/y8rGw8K+ubizu7q2wsG9v7+7u7u2traxtrWvtbWut7axt7awsrKtv7+5u7q1ubizurm1wL+7vb25vLu3uLaxtbSuvr65urm0v7+5v7+6tbSvwL66wL+6w8K/u7m1urm0vby3wsG9v765vb24vb22wcC6wsK8v7+4uLixwMC7wL+6wsG8vLy3urq0wL+6wsG9xMO/wsK9urq1t7axwMC7v766xcXBxsbBwsK8xcTAyMjCwsG8w8K9xsbAxMO/wcC7xMO+zczIwsK9wcC8urq1u7u2u7q1trawtravtbWvt7ewubqzvLy1vr25vLu2xMO+xcTAvry5srCtrKynrq2orKulraump6aitbSvrq2opqWhr66qrq2oq6qlrqyoqqiksbGrsrGtq6qlqqmkpqWfo6Kcq6umq6ulqKiirKunr66psbGsqqmlpaSfr66psrGtsbCsrayoq6qlq6mls7Our66qsrGssa+rra2os7Ksr66ptLSvrKunqqqls7KutbWwsrOtsrGssK+qsLCqsbCrr6+qqqmkqamjtrWwwcG7vb24uru1vLy2wL+5v765wsG8xsXAtbSvtbSws7Ktu7y2trWvtrWvtLSutLOuvLy3u7q1vLu2trSwurm1vLu2uLiyubiyvr24urm1travt7ewtravt7ewsLCrtrWwt7WxuLi0t7ayr62osK6pubizurm1t7eytbSusbCrvr25vby4v7+6tbSvtbSwurm0uLexubm0urm0urq1treyvb24vb24u7q2uLi0tbWws7SuvLq2vb24sbGsrKymq6qkvLu0wsG8w8O/vb+5ubiyu7q0u7q0v765s7Ktv766urm0v7+5vr24v765v765u7u1u7q1trWwwL+6vr25vby4wsG7wsK8wsG8w8K9wL+6urmzvLu1wMC5vr24urm1v765vr24v7+6t7azvr64v765tbWwvby3wcG7vLu2uLeyvby3xsS/xcO/u7q2wcG8wL+6wcG7wsG8v764vLu2uLezv7+6vr66u7u3xMO/x8XBwcG7w8K+v7+5tbWvtLStqqqkv765v766wcG8uLizurmztbSvuLexv764r66pubezvLu2sK+psrGstLOts7OssrCrtbSvrq2mrKqlsbCrrq2ps7KttrWwuLeyuLeytLSutrWwrKqks7KstbOvr6+os7Otrq6os7KrsK6qtbWvtbSur6+ptbWvtrWxtLOusK+psK+qtrWvtLOut7axtLOtt7WwuLizuLeysrKsrq6orq2nrK2ms7Outraxurmzt7ayubeyurm1trWwurm0rKulp6ehwMC6urq1t7extbWvv765urizs7KswL+6rq2ps7KtuLizq6qlyMW/z87IzMrDy8nBy8rCzMrCzMrCzczEz87IzczHzc3Gz8/Hzs3G0M/Jy8rDzcvDzMvEy8nCy8rCzc3EzszEy8rD0dHJ0tLKzs3F0NDI0tHL0M/Kz87Hzc3F1NPN0dDL0dHKz8/I0c/Lz87I0c/Kzs3Iy8rDy8vDyMfAx8e/y8rDz87I0tHLz87KysnDyMfBsLCrvr25q6qlp6ehvr63tLSuu7u1t7exvr24vbu2s7Gru7q0r66ptbSuurm0rq6pzszF1NLN0c/J0dDJ0M7H0c/Izs7Hzs3Gz8/J0c/L0M/Kz8/J1NTPyMfBx8e/ubewxsW9xsO8ycjBycjCw8O8y8rDysnDurq0yMfAx8e/yMfBw8K9w8K8yMi/urm0y8rFysrDysrDzczHz87Jz8/Kzs7IzMzGysnDyMjAy8vE0NDI1dTP2NfR2NfS1tXQ0M/KsrGtvLy3s7OtqKehuLeyurm0v7+5u7y2u7u0vby3uLextbStr66purm0tLOurayny8jC0c/J0c/K0M3HzMnC0M3GyMbAw8K7xsXAxcO+xMK+x8bAz87Ivry2xsS9u7ixu7ixu7mzwcC5x8bAvLu1xsW+x8W/tLSuwcC7travwL+4vr64wL65yMjBsK+pxMO+xMO+wcC6wsG7y8rFwsK9xMS+xcS/vr63vr22x8fAzc3G19bR19bR1dTP2tnU09LNt7ayu7u1uLeyqaiit7awvLu2vLy3vb64uLexurm0u7q0urizqKejt7axtLOtr66oy8jB1dLL0c7J0c/J0c7I0c7I0M3F08/J0s/I0tDL0tHL1NLL0s/J0c3Hz8zFz8zF0M3G0c3H0s/I09LM09PN0tLM1dTN2dnS29nU2NfP1tXQ1NTM2NfR1dTP1dXO1tXQ1dXP0M/I0c/I0M7J09PN09LN1dXP0dHKz87J0dDKzc3G0dDL1dTP0tHM1dTPz87ItbWvubiysrGsoqKcubiyubmzvby3vLu2trSvt7axvLu2vr23qqmks7Kuurm0rq2nyMW+1NHM0tDL0c/I0s/J0c/Iz8zFzsvDzszEzszF0M/I0M7H0c7IzsvDz8zFz8zFz8zF0M3G0c7I0tHM0M/K09HMycjCrKylm5qUsrKrzs3I0NDJ0tLL09LM0tHL09LN0M/JzszF0M/Jzc3F0M/K0tHM0dHKy8vEzs3I0tLM0NDI0dHK0tHL0tLL0tHLzczHsbGsvby4sbGrpqahurq0u7u1vLu2ubq0sa+psrGrs7Gsurmzp6ahs7KtwMC6tLOtysfA0s/I0c/KzcnDz8zFzsvEz8zFy8jAzcvE0M7I0c/I0s7H0s/K0M3Hz8zF0c7H0M3G0c/I0tHK0M/K0M/K1NLNp6ahTUpHPTo3eHZz0M/Jz8/Hzs7G0NHJ09LN1NPO09PM0NDJ0tHMz87Jzs7H0tHMz8/IzMzEzs7G0NDI0NDH0NDJ0dHL0tHM0tHLzs3Iurm0y8rFubm0qKejuLeyu7q1t7eyvLy3vbu1t7WvubiyubexpaSetraxubmzrq2pzMrD0M7Jz83Hy8nBy8jAzszGz83GzszG09LM0NDIzsvE09HL09HM0c/K0M7I0M3G0c7Iz8zF0s/I0dDK1NPOy8rEhoSBQT08PTk4bWxowsG709PL0NDJ0tHK1NLN1NPO09HMz83G09LN0c/K0dDK0tHMzs3HzMvDz8/I0tLL0dDJ09LN1tXQ0M/J09LN0dDLsbCrwsG8vLu3qaijvby3vLq1vr24w8K+v765vry3vr24wsG8rKulr66pubiyraynysjB09LOzcvFzc3F0M/Iz87Jz8/I0dHK1NTOz87Hz87G1NPO1dTP09LN0M/I0M3G0M7Jzs3Gz83G0dDJ0dDL19bRvr25l5aRjoyItbSw09LM0dDK0tHL1tTP2NfS0tLMzs7I0dDJ1NPO0dDK09LN0NDKzMvDz87H1NPP09LN09PM2NfS09PM0tLL19bR0tHMsLCrt7axsLCrr6+qvr24vLu2v765v766vbu3v766wL+7wcC7raymsbCrv7+6s7KszcvF1NPOzszGzczE09LM0dDL0tHMz87J0dHK0tDK1NLL09LN19bR1dTP09PM09DI0dDI09PM0dHJ1NPO09LM1dTN1tXO1tbO2NfR09LN0tHM09LM1tXP19bQ2tnU1dTP0dDL0M/K0tHM09LM09HNzs7Izs/F0dDK09LM1tXP09LM1dTO0tHL09LM19bRz87Js7Ktvr24sK+praynw8K9vr64wMC7vr65u7q0wcC7v766v765sK+puLeywL+6s7OtzcrE0tHKzcvDzcrEzs3G0tHKu7q1rKumtLSuvby2srGrycjDqKijsrGrsbCrqKehsbGptbSvtLOus7Kst7awraymw8O8uLexwMC5vLu2ubmzsrGsuLeyvr23u7u1trWxv765tLOus7Kturm1urmzs7Ktr6+osrGrr66pvby30tHM0tHM09LN1dTP1NPOzs3Is7Osvry3tbSusbCrw8K+wcC6wsK8v765u7q0wb+7vr23xcW/sK+quLayw8K9rq2ozcvG1NPOzs3GzMvEz83J1NLNt7axsK+qraylqqmjmpmUxMO9nZyZoJ+aq6qlmZiToKCasK+oqaihnp2YsbCrqKeiubmzq6qltLOuu7q1sK+pqqmksK+pr6+pq6umo6KetLOuqKairKumsbCrtrWwuLeyqqmkp6aiurm1sK+q0dDL0dDK0dHKzMvF09LNzs3IrKunvr24tLSuraymwL+5u7u1vr64v765u7q1uLeyvbu3xsXAsK+qrKyou7q1s7KszcvF1tXR1NPN2djR2djT0M/L09LM3NvW09LK0tPL1dXN09LN0dDL19bQ0tLK0tPM2NfR09HKz8zG0c/J1dTO3NvV2trS0NDI0NDJ0tLL1dTQ397Z2tnT0tHL1dTP2NfS29vW3d3X0dDLz87J1NPO0tHM09LN2djT0dDL1NPO3dzX4ODarKulv7642tnT0M/LtLOut7ayrKynraynw8K8uLextbWuv7+6vby3uLiztbWwvLy3srGstLSwv766r6+pzs3H19fRuLexiYeDl5aR09LL0NDJjIqGt7exrKuklpSQ3dzX09LMiYeDurq0vLy1kI6J0dDKz87H19jRxcO+i4mFoJ+Z19fQ0NDJ2dnSxsS/jYqGo6Gc2tnU2tnUy8rFmJaSioeDy8nB0tHK09LN1tXQpqahlpSQ1NPN0tLLl5aRj42KkI+JmpmU1dTP0M/Kr66pv725trWwsLCqurm0u7q0vby2v765vr24vr24uLexuLixrKqmvby3u7u2sLCpy8rEz87JVlNQjIqFfnx3xsa+09PLaGZip6ahhIJ+lpWR3NzW1tbPb21ptbSvs7KsaGVi0tLK0tLKq6qjgn97lZOOj42I0dHK1tbPraumhIJ9kY+KlZOO29rV3t3Yc29sfXp2fXx4uLeuz83Gzs3J2NjSkpGMdnRx3t7VqaihYV5bhoaBUE9Lfnt33dzXy8rEs7OsvLu3u7q1paWgt7Wwu7q0u7u0vLu1ubiyuLexurm0u7u0qqmkvLu2v766r6+qy8rE1tXQioiDU09Ns7CpzszEzMzEc3FtVVNQa2pl1tbP1NPO1tXQcm9ssrGtr66pZmRf0tHKzMvEZ2VhxcO+t7awjYuGzc3Fzs7IaWdjzMvGtLOtj42I0tHM397ar66pUk5Lm5qU09PL0dDK19bR397Yi4mEe3l02trSu7u0rKukjYuGnZyXcnBt0tHLzcvGsK+rwcC8urm1qaijwL+6vr25vr23wcC7t7avvLu2u7q0wL+5r66qs7Ksw8K9r66qzczHzc3I2djPjYqGWVZTyce/1NTMbmtnlJOPcG5qnJuW3t7XycjDUk9NxsXBubeyX11Z1NTOubiyXFlW3dzWoJ+ZZWJf2dnRsa+qX1xZ4uLcm5qVaWZj2NfSz87J5eXgtLGtT0xItbWv4uHcsK+rrquloqCaeXdz19bP19fPvb22XVpXgH56TElGy8rEzs3IrKynw8K+u7q1srGsxcW/v765vby3vb24urm0vr24vr24w8K9sbGsvLu2wcC8rq2o19bRk5GNmZeS0tHLU1BOs7Ks3NzUdHJtrKymq6mkYmBc1NPO0dDLWVZTlpSQeHZzYF1a1NPNzc3GT05KnZuWqqihbWpn2dnRzczEVVJOp6agqKehdHJu6OfitbSvioiF4uHba2hjkY+K6urke3l1cG1ptLOtaWdk0M/J2trTkI6JiYiCw8K7VlNPuLay0c/JrqynxMO/wL+6r6+qxMS/wcC7u7q0ubmzu7q1ubiztLOuurm1rKyoubi0vr24rq2o09LNoqGdVlJQeXdzlJKP0tHK0NDIf315qKiizs3IeHZywsG94N/asK+qb2xoioeEb2xoxsbA19bPraylbGpngoB7e3l1wL+4rq+pcnJvXV9chYaDZmZjmpqWpqagV1RRf3x4iYeDz83J2NfSzczHfnx4bm1otrWv1NTO0NDKgX96nZ2W29vTeXdzpqWg0dHJraynxcTAvby3q6qlurq1u7q0uLizv765t7axtbSvrq2ourm0rq2otLOvw8K+tbSwy8rFzs7JxcS/xMO+09PM09LMzc3Gz87H0M/Izs3I1tXQ1dTQ1NPN19fS2tnU2djT0M/K0dDLy8nC1NHL2tnUs7Otj5COcnV1dnl6cnV3e35/f4GCcnR1ZWdoaWtrd3d1qKik397Z19fR0dDL1dTP19bRz87I1dTNz8/I0dDJ0NDIz8/Hz87H1NPN0tLLysrCtrawyMfEubm1srKtwL+6tLOusbCrtrWxubizubi0vr23wcG8tLOvs7OuwL+7uLezz87J0tHM0dDL1NPNz8/H09LMzc3G0tHL0dDK1dTP1dTP1tXQ1NTN09PN09LN1tXQ2djT0tLLzczF0c7HnZyYaGlrfH6BYmRmYWNkW15dSUtJT1FRTE5OW1tca2xtWlpaYWJjhYaD1dTO1dTP0tHM09LL0dHK0dHK09LM0M/Kz87H0dDK0c/J0tHM0dHKysrBtrWww8K9ubm1srGtw8K9vb23tLOuu7q0t7exu7q1vLu2wL+7sbCst7aywsG9trWw0dDL1tXQ1dTP09LN0c/K0c/J0M/I1dXO1dTQ2NfS2NfS19bQ1NPN1NPO1dTP1tXQ1tXQ0M/J1dTNoqKdZ2hqdHZ4Wltcenx5qaulw8O9xMS/r7Cqi4yHUFFOTE1NWVhYcXJybW5senp41NPO0dDLz8/Jz8/H0tLL0tHMz87JzczF0dDJ09LN0M/K0dDKy8vEs7OtxMS+vLy3sbCtwMC7wL+6v765urq1vr24uLizubizvb24rKuou7q2wMC7uLey0tHM19bR1NPO0tLMz8/I0NDIz87H0tHL1NPN1dTN1tXQ1tXQ1NPO1tXQ19bR1tXQ1dTP1NPNx8a+a21rfX6BXF1cpaai2trS29vT3t3X397Z4N/a3dvWyMjBamtnX19fYGFfuru2cnNwjo+M29nUz87J0tHM0M/K0M/Kzs7Hzs7G0tHLzczFz87H09LNzczGsbCqwcC8t7eyqaikvb24tbSvurm1ubmzt7aywcC8uri1uLi0q6qnt7ayv766tbSw0M/K2NfS09LN0dDM0NDKz8/JzczFz87I0dHL09PM19bQ1dTP1NPO1dTP1tXQ09LN0M/K2NbQnZ6YZ2lqXV1dnp+c4eDb1dTNy8vDr7Crp6mkuru109LM29rUycjDcXFvXl5doKGexcbAX2FfvLu31dPOz87J0tHM1dTP0M/Kzc3Gzs3IzczG0dDK09LNzczGsrGswsG9uLizqaijt7eytLSuubmzra2nvLu2t7azubi0vbu3sLCstLSvurm1srKt0M/K1tXQ09LN1NPO0tHMz87Iz83F0tDL0dDK09PN1tXQ0dDL0M/K0M/K1NPN0dDL09LN0tHLdnh1Y2JkdXV02NjS19XQrKyoh4qInZ+bqKmlmpqWl5iTy8vF3NzUmJiUUFBQkZKQ4eDafX59kpOR19bQzs3I1NPO1dTP09LNzs3Iz87J0tHM1tXQ1dTQ0M/KsbCruLiys7KtsK+rwcC9uLeysK+qt7exubizsLCrtrWxwMC7srKtubi0wMC8s7Ku09LN1tXQ1dTP1dTP09LN0tDK0c7I0tDL0M/J09LN1dTP0tLM0tHL0M/Iy8vDzs7H29rUhIeBd3p6a2xrqaqm4uDbtrWvbXBtxsfD3t3X1NTO3dzWsbGsoaGb3t3YrKuoUVFRk5SR4+Lcl5eUbnBx0NDK1NPO09LN09LN0dDLzs3IzczHz87J09LN0tHMzszIqqmlu7q1u7q1srKuvr24t7ayrq2ou7q1tbSvurm1tbSwube0qqiku7q2x8bCuLezzs3I1tXQ1NPO1NPO1NHN1NHM1NHL0c7I0tHL0dDL0tHM09LO0M/Jzc3GxsO81tTNmJmUVVZXlJaXeXp5wsK8397Yjo6KpKWi5eTcsLGsoaOfqqum0tHKo6Kf19XRtbWxU1RTqqqn4eDaq6unXV5fzczJ2djT0dDL0tHM0M/K0M/K0tHM09LN1NPO09LNx8bBsbCrt7exsrGsqaikt7Wxt7ayu7q1srOtvr25urm1ubi0wL65qqmlu7q2w8K/trWxzszH09LN0tHM09HM1NLN09HL09DK09DJ0s7J0M7J0tHM0tHMzMvFy8nC0c/Ip6iiaWtsfHyAeHp7hYaE0tLL0dDKhISAw8TAz8/HoKGcurq1pqehz87JoKCc2dnTn5+aVVZVzMvH3dzXuLeyWlxdzMzH2tnU1tXQ1NPO1NPO1NPO1tXQ0tHM1dTP1tXQz87Jr66qt7ext7axqailvb23ubmzvby3u7q1vLu2wL+7v765wcC7r66pt7axxMO/tLKtzMnE0c/K0dDK0s/K0M7J0M3G0tDK1NLM0M7J0M7J0c/K0M/KzcvFy8jB1dPMhISBX2FjgYOEZ2lqiouJ2djT1tXQgIB9tLWw29nUnZ6YtLaxx8jCq6umrq6o3d3WZ2lnj5GO3NvW3NvWsLCsaWtqzs3I2tjU1dTP1tXQ1tXQ1dTP1dTP1NPO09LN1tXQ0M/KsK+qv7+6uLayrq2ovr64v7+5wb+7vLu2urq0u7q1v765wMC7sa+qtrWww8K+tbSwzMvG0M7J0dDL0dDL0tDL0c7H0tHM09DLz87Hz83H0M/K0tHMzs3GzcnC0c/Iy8vEbW9rdnh5d3h6hoiG09PN2trUmJeTgYJ/4+Pdz83IpKahoKKdr7Cr4uHblJWRcnVz1tXQ1dTP3t3YlZWThYWE29rV1NPO1tXQ19bR1NPO1NPO1dTP1dTP1NPO2NfS0dDLs7Otvb24tbSwsbGrwcC7v765wL+7wcC8srGssrKss7KtvLu2rKumurm1uri1rKqmzczG0tDKz8/J0M7J0s/Kz83G0dDK0c7I0MzH0c7I0dHM0dDLz87I0c/J0M/I397YnZ2XU1RWaWptbG1rz8/J0tHK09LLent3lZiT1NTM3dzV1tbO09LLkpSQcHJxxsbA1NPN0tHLysnDXV9eq6yo29rV0dHL1dTP1NPO0NDKzs3Iz87J0dDL1NPO1tXQ0dHMr6+quLizt7eysK+qwsG8ubizvby3v7+6uLews7KtsbGssrKsoqGbubmzvby4rq2ozczG09HKz87Hz83I0s/J0c7H0tDK09DL0s/K0c/J0tHL0dDK0tDM0c/J0tDL1dTOg4SAY2RmhoeJW1xcnZ+b3NzVz8/Hzs3FhIWAcXNvioyIgYJ+a21qjY+LzczG1dTOysnC2tnRgIF8Z2pn1dTP0tHLz87Hz87Izc3GzMzEzczGzs3H0dDK0tHM0tHMz87KtbSwwcC8ubizqaijubizurm0wL+7x8fCvby4uLaxvLu2vby2qKeivr24v765sK+q0M/J1tTO0tHK09PO1NPN09HM1dTO1dTP0dDK09LM09LN0dDK0s/J0M3G1NTOx8fAbW5ui42PiYuNYGFhR0pHubq03NzVzs7H1NPMvb24o6SdpaWgwL+61tXN0tHL0M/K29rUlJSNS0xKvL231dTP0M/Ky8vDycnBzs3Hz87Jz8/I1tXP0tLMzs7I1NPNz87KsbCswL+6uLeyq6mlwL+6wL+5wMC7xMPAv765wL+6wcC7xsXAsK+qsrGsx8jCtbWwzs7I1dTO0tLM1NPN09LO1NPO0tHM0tHM0M/J0tLMz87I0NDKzczFzMrC2tjRqKehbHBxoKKklZaYfX6BSEdHTU1LsrOv2NfQ1NPN1NPO2NfP2NfQ09LM09LM2tnU19bRkJGMOjs4o6Of2tjS0dDL0dDKzc7Fz8/J0tHN09LN09PM1tXQ0dDK0M/J1NPOzczItLOvvb24r6+qr66pwsG8vr24vr24wsK9u7q1wL66wL+7xMO+q6ulu7q1zMvFurm1z87J2NfS1NPO1dTP09LN1NTO0tHM0dDL0tDL0M/Jzs7H09LN0NDJzczG2tfQkpKMcnV2j5GTnqCglpiZampqSklIRkdHenx4uLi019bQ1NTM2dnR2dnR09PLsrKtdXZyNzg1aWpn2dnT0tHL09LN0NDK0NDI0tHL0dDK1NPO0tHLz8/J0dDLz87J09LNz87JtrWwxMO9ubizqaijw8O9wcC7wcC7v7+5urm0vr24vLu2urm0rKumwcC7zMvHubiz0M/K2tnU19bR1dTP2NfS0tLM0dHL09LN0tLM0tHL0dDK09LM0M7HzczG29rTn5+ZZmlpbnJygIKEmJqcj5CSc3V3X2BhRkZFTlBQd3h0amtpgIF9goJ+Xl5bQEE/SUhJYGJhiouJ2NfS0M/J0dDLz87I0c/J09PL0NDJ1NTO0dDK0c/I0tHL09LN09LNzs3ItLSvxMO/u7q0pqWgu7q0wcC7xcTAwMC6vby3urm0ubezwL+7t7ezxcXAzs3Kvr650dDL2djT2djT19bS2djT1dTO0tHL0tHL0dHK0tHLz8/IzMvDy8nCzs3F09LLyMfBZGViQUJBUFFQYWNjen1+dnd6bnBwUlFQU1NRUlJPQ0NDOzo5REREVFRUXV9gi4uNiImKmpqX2djTz87J1dTP1NPO0tHL1NPP1NPO09LN0tHM09LM0tHKz8/I0NDKzczHtraxwcG7u7q1rauntbSutbSut7exvr65vr23ubizv766yMjEt7ayx8bD0tHOvL240dDL1tbQ1tXQ29rW2NfT09PN1NPO1tTQ0tHLz8/J0dHKzczFz8/H0dHK0tHL1NTNwL+5m5uVpKWggoR/XGBfjY+Renx8WltZUE9MW1pab3ByX19feHh6kJGSamxqZ2hna21tn5+b29rT0dHK2tnU1NPN1dTO1NPO1dTP1NPO1NPO0tLMz8/H0NDI1NPO0M/KtrSvw8K8urmzra2nwsG8t7axtbSuvr25vr64w8K9wMC7yMjDsbGtw8K+zs3JuLizysrC0tLK1dTP29rV29rW1tXQ1NTN1dTP09LN0tLM0M/Jzc3G0dHJ0tLL09LN0dDK1NLO19bO3dvW2djSVVdTenx+cHJze31+RkZEVFRWdXZ5ZGZmeXp7h4iJe3t3ra2plZaSwsK8zszE0M/J19bR0dHLzs3Hz8/I0M/I0M/J0tHM0tHLz87H0tHL1tXQzs3ItLOux8XBubizraynwsG8vLq1vby2ubizu7q1xMK+w8O+y8rGt7eyxMO/yMfDsK+ry8vE1dXO1tXQ2tnU2NfS2dfT19bRzs7G0NDJ09HL0M7IzczGzc3Fz8/H0M/J0M/Kz83JysjC3d3WpqagPD06bG9wbW9ueHp7XFxbSUpKYGFjZmhpdHV2Z2hph4aC4uHc3dzX1dXPysjBzMrD1dTP0tHMz87HzczEzMvEz87H0M/J0NDJz83Gz83G09LNzc3GsrGsxcTAwcC7sK+qv765vLu2uLiyuLizvr23v765xsXBzczJubm1ysnExMO/ubq11dTQ1tXP1dTP2NfS2tnV3NrW1NTO0tHK1NPO1NPO0tHM0dDK1NTNz87IzczG0dDK1tXP2NXPqKegRUdEQUJBdXd4Z2dnUVNTZ2dpRkREWFlaVVZWT1BPbm9tsbGt2NfS0dDM0NDJ0c/I1NTO1tXQ0dDKzc7Gzs3Fzs3Gz8/Izs3F0tHK0dDJzcrC0tDLzs3IsrKtxsXAxcW/raymv724vLy3vby2vr24v766v766xcO/zMvIvr66xcW/xsXAt7ay09LO1tXQ0tLL19bR2NjS19bR2NjS2NfS0tHMz8/Iz87H0tLL0tHM09LN3dzX1NTOtraxgH98T1FOS0xNUVFSYGFiU1NUQkFBWVpaWVhYOjs6UFBQs7Ou09LM2NfS2djT1tXQ1dTO09PL1tXQ1dTPzs7I0tLM1NPNz8/H0NDJ0NDI0tLL0dHJz87G09LM0M/KsrGsx8fCwsK8tLOvw8G8vr24v765vLu2wcC7wL66wsG9xcPAt7e0x8bBwcG8trWx1dTP1tXP09PM3NvV2NfS1dTP1dTP1NPO0M/Izc3E0dHJ0dDK1tXP0dHKmZmVZmZiR0hGX2JkdXl5X2FiZWlpVFZVRkZHPz8+OTk3UFBPampouru32trS0M7H09LN19bS1NPP0tHL1tXP1dTO0tHM1NPO1dTP1tXQ0tHK0tHK0dHJ0dDI0NHJz8/H1NPN0NDJs7KuxsXBw8K+rKynwsG9wcC8wL+7v7+5ubmzuLiyvb24wMC7s7KvwMC8xcXAu7q21NPP2NfR1dTP1dTP09PN1NPN1NPO0dDK1NPN0tLL09LM0dDIvL21aWpmWltbcXN0X2BgWFpaeHx9hoiKbXBwU1VVSklKNDQympuWy8vE29vV3dzWzc3G0tDL0M/K0tHM2djT1dTP1tXP1tXR09LN0tHN0NDK0dHL0tHL09PN0NDIz87H0NDI0dDK1NLOy8rEs7Ktw8PAu7q2rayov7+7urm0tLOuurm0v7+5vr24wcG8xsXBt7e0u7u3wsK+uLey0tHM2NfS1NPO1tXQ09PM0tLM0dDK1NPN09LM0dHK0NDL1dXMf4F8XmBhd3l6k5WYiYqMbm9wbXBxfH6BaWtsZmdpS0tLampo2tvT1dXP2NfS1tXQzs3Hzs7I0M/K1tTQ2NfT1tXQ1NPO1dTP09LN0dDK1NPN0tLL0tLL0dHLz87Gz87G0M/H0NDK0tDKx8e/sbCqwsG+t7azsrCsw8K9vLu2uLawvb23wL+7wsG8wcC8xMO+tLSwv7+7w8K+vby41NPO2tnU1NPO1dTP1tXQ2tnU1tbQ1NPO0dDJz8/I2djTysjBVlZTXl9geHp8iIuOiouNg4aHlZaXd3p8ZGRmaGpqWltcgYJ/2djSzs3I0dDL0dDLysnEzs3I0M/K19bR1NPO0NDK09LN09LN0tHM1NPO1NLN0tHM1NLN0tHL0M/J0tDJ0tDK0dDLz8/JyMe/tbSuwsK9vby4rKuowsG8vr24uLexvby3wcG8wMC6wsG9vby4t7izxcXAvb24u7q22NfS2tnU1dTP19bR1tXQ2NfS1tXQ1dTO0tHM2tnTs7OuaGloPj49SklJaGlqeHp7gIGDbm5wb3Fyi46OZmdoZWZoZmlqent62dnT1tXP0tHM0tHMz87J0M/K0M/K1NPO1NPOz8/J1NPO1NPO09LN1NPO1dTQz8/I0NHJ0tHK0M/H0M3I0tHL0tLN0dDLzMvFsbCru7u1wcG8srGtvLu2urm0vLu2vr24ycjEwsG9ubm0vr24tbWxvr26x8bDu7q22djT2djT2djT2djT1tXQ1tXP1dTP2djT2tnTpKWibG9vc3V2YWNiWVxcfYCBent8enx8b3BxaWxsdnh5bG1ufH6BeXx9WVpYxMXA2tnT1NPO1tXR0tHM1tXQ09LO1dTP1tXQ09LN19bR1tXQ09LNz87J0tHN1NPO0NDI0NDI0tLL09PMz87H09LN1dTPzs/Hr66pvr25tbSvsK6qubiztbWvvLy1vr24wsK+v7+6uLezxcW/t7ezvLy5xsXCtbSx0dDM1NPO09LN0tLM0tHM0M7K0dHKy8vEfn58fH1/l5magIGCamxucHJ1cHJ0a21vcXJ0UVBQVFNVU1NTb3Bxh4mMfYCDUFJTfH162NbR0M/K0M/KzMvG0M/Jz87K09LOz87J0dDL0dDL0M/Kzs3IycjDzMvG0M/Kz87IzMvFzczFz87JzMvFz87I0dDLyMfBrKyovLu2tLOtrq2ow8K9tbWwvb24vby4vb24vLu3vr24yMjDuLe0wcG9w8O/vLu3v7+7vby5u7q2urq1vLy3traxtrWwqqmlh4iFqKimra2ql5iVlJORoaGfnJyZlJSSlpaTiIeFgIB9iIaDmpqXqKmlk5OSjo2LkZCNsbCrt7aytLSwt7axs7KttLSvu7q3srKts7Outraxubm0ubi1uLeyuLiztbawt7axsK+qtrWwt7extraxuLizuLizuLeys7Ouu7u1urm1s7KtxcTAvLu3uLizvLy3vby3xcTAxMS/y8rGvb26xsfDxcTBycjEzMvHzs7KyMfDyMfCxcXAwcG8xcS/xMK9y8rFyMjCyMfCysrEx8bBxMO+vLu2x8bByMbCxMO+wcC6xsbAyMjByMfDxMK/x8bAx8bBubm1vr65xMPAv765u7q2xMO/zMvHx8bCvby5wsG9x8fDysrGxMO+xsXAxcTAwL+7wMC7v726vr25wsK9x8fBx8fCxMO+wsG8t7awurm1s7GtwcC7v765v765ubmzx8bCycjEyMjEy8vHu7y4vby4vr66wcG9w8K+xMTAvb25uLizvr65wsG9wcG8ubizu7y3vby3vLu2ubmzt7axsbCrs7KttrWxuLiztrWxr66qsrKssrGsubi1urm0sa+rsrGturm1vLy4u7m2ubi0trWxwcG8w8O/w8K+wcC8trWxu7q1vr65v765urm0ubm0uLezvby3ubi0uLizubizurm1vLu3u7q1u7q0q6ukq6ylsbCrv765wL+6wL+6u7q0yMfDxsbAzczIysrFv766t7eztrWxtbSwuLezuLezsLCsu7q2tLSwsa+rt7izsbCssK+qsbCsrqypsrGtrKunp6ahqqmkrayopKSgqqmkrKumqKeirq2osrKtsrGtrKunqKaisbCssbCssrKusK+rsbCsra2osrKura6qtLOusK+rr66qt7axsbGttrWxs7KurKuotLOwtrWxs7Ourq6qsK+rtLOusbCrq6qlqKeirq2ovby3vb24u7m1u7q1vby2xsXBw8K+wsK9wsG9wsG9wcC8wsK/xcbCw8K+ycjEycnGzMvHx8bDwMC8x8fDx8fDx8bDvr26vr25wL66vr25ubizvb24x8XCx8bCv765wcC7v725wcC7xcXAxMTAu7u2vLy3w8K9wsG9xsXByMjDwcC8t7ayvr24vr67xMTAycjDysnFx8fDzMvGxcTAx8bCy8vGx8bBw8K+xcO+y8rFxsXByMfCurm2tLOvuLaxvr24v766sbCrtLOtv765v7+6u7q1u7u2wL67xsbBxsbCx8bDxcXCyMjFw8PAxMTBxcTCyMfDy8zIv768wsG+wMC7xcTAtrWxvr25u7q3wsG8v766w8K9wsG9vr25w8K+vLy3vby3vr+6wcK9v8C6t7eyv7+6xMO+xcXBwsK9vLy4ubizwL+7xcTBw8K+wMC8ysnFyMnEyMjEyMfExsbCyMjEyMfDysrFx8fCxsXBwMC7vb24v766wsG8ubmzuLizu7u3vb24vLu2t7eyuLeyt7axvLq2wL+6wcC7w8O+xcS/y8rGyMjEyMfDxsbCzczJycnExMXBx8bDvr26xMO/wb+7xsXBtbWxurm2x8fCxMO+v765wsG9xsXBx8bCvLy4ubmzvr64wcG8wMC7traxtrWxwcC7v7+5wMG7urmzt7axvb24wsG8v765vby4ubezu7u3x8fDyMjFyMfDx8bCx8bCw8K9x8bCxMO+vr26wsO/xMTAxMS/wcG7wL+5xMK+xcTAwsG8v7+6vr65vby4uLiyvby3wcG7v7+5vr64xcTAw8K9w8O+ysrGzs3JysrHycjEysrFy8rHubi1xMO/w8G+xcO/uLi0wsK+xMS/xMO/xMO+xMO+wsG9u7q2t7eytbSvurq0vb23urmzsrOuuLizvr65vr64ubmzs7KtvLq1vby3v765vLu2traws7Our6+rurq1xsbCxsXAwcG9wsG9w8K+xcXAvr65wcC8xsXBxMO/xsXAycfDw8K9xMO+wsG8wsG9wcC6wMC7vr24vLy2
font_color: "#000000"
font_color_alternative: "#2b2c31"
background_color_brightness: 209
background_color: "#d4d3ce"
background_color_rgb:
  - 212
  - 211
  - 206
```
