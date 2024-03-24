## Prerequisites
1. [DIVOOM PIXOO64](https://www.aliexpress.com/item/1005003116676867.html)
2. Home Assistant (with add-on functionality)
3. AppDaemon (Home Assistant add-on)
## Installation
> [!TIP]
> Create a **Toggle Helper** in Home Assistant. For example, `input_boolean.pixoo64_album_art` can be used to control when the script runs. Establish it as a helper within the Home Assistant User Interface, as Home Assistant will not retain the sensor’s last state after a restart. Ensure that the helper sensor is created prior to executing the script for the first time.
1. Install **AppDaemon** from the Home Assistant add-on store.
2. On the AppDaemon [Configuration page](http://homeassistant.local:8123/hassio/addon/a0d7b954_appdaemon/config), install the **requests**, **numpy pillow**, and **unidecode** Python packages.
```yaml
# http://homeassistant.local:8123/hassio/addon/a0d7b954_appdaemon/config
system_packages: []
python_packages:
  - requests
  - numpy pillow
  - unidecode
init_commands: []
```
### Manual Download
1. Download the Python file from [This Link](https://github.com/idodov/pixoo64-media-album-art/blob/main/apps/pixoo64_media_album_art/pixoo64_media_album_art.py).
2. Place the downloaded file inside the `appdaemon/apps` directory and proceed to the final step
### HACS Download
1. In Home Assistant: Navigate to `HACS > Automation`
   * If this option is not available, go to `Settings > Integrations > HACS > Configure` and enable `AppDaemon apps discovery & tracking`. After enabling, return to the main HACS screen and select `Automation`
2. Navigate to the `Custom Repositories` page and add the following repository as `Automation`: `https://github.com/idodov/pixoo64-media-album-art/`
3. Return to the `HACS Automation` screen, press the `+` button, search for `PIXOO64 Media Album Art`, and click on `Download`
> [!IMPORTANT]  
> In AppDaemon, make sure to specify the apps directory in `/addon_configs/a0d7b954_appdaemon/appdaemon.yaml`.
> Also, remember to transfer all files from `/addon_configs/a0d7b954_appdaemon/apps/` to `/homeassistant/appdaemon/apps/`.
```yaml
#/addon_configs/a0d7b954_appdaemon/appdaemon.yaml
---
secrets: /homeassistant/secrets.yaml
appdaemon:
  app_dir: /homeassistant/appdaemon/apps/
```
_________
## Final Step - Configuration
Open `/appdaemon/apps/apps.yaml` and add this code:
```yaml
#apps.yaml
pixoo64_media_album_art:
  module: pixoo64_media_album_art
  class: Pixoo64_Media_Album_Art
  media_player: "media_player.era300" # Change to your speaker name in HA
  toggle: "input_boolean.pixoo64_album_art"
  pixoo_sensor: "sensor.pixoo64_media_data"
  ha_url: "http://homeassistant.local:8123"
  url: "http://192.168.86.21:80/post" # Pixoo64 full post URL
  show_text: True
  text_background: True
  font: 2
  full_control: True
  crop_borders: True
  tolerance: 100
  enhancer_img: False
  enhancer: 1.5
```
> [!WARNING]
> **Only save it once you’ve made the described changes to the settings.**

| Parameter | Description | Example |
|---|---|---|
| `media_player` | Media Player entity name in Home Assistant | `media_player.era300` |
| `toggle` | Primary toggle sensor name that triggering the script. | `input_boolean.pixoo64_album_art` |
| `pixoo_sensor` | Sensor name to store data. No need to create it in advance | `sensor.pixoo64_media_data` |
| `ha_url` | Home Assistant local URL | `http://homeassistant.local:8123` |
| `url` | PIXOO64 full URL | `http://192.168.86.21:80/post` |
| `show_text` | Display the artist name and title | `True` or `False` |
| `text_background` | Adjust the brightness of the lower section of the image to enhance the visibility of the text | `True` or `False` |
| `font` | The device is compatible with 8 different fonts, which are numbered from 0 to 7 | `0` to `7` |
| `full_control` | This script assumes control of the PIXOO64 display while it’s in use and a track is playing. If `True` then the display will turn off when music paused. If `False` it display the previous channel (clock, visualizer, exc.) | `True` or `False` |
| `crop_borders` | This feature is designed to eliminate existing borders from an image, especially for album arts that have single-color edges. When the primary image within the border appears small or potentially skewed on the screen | `True` or `False` |
| `tolerance` | Parameter that you can adjust to fine-tune the border detection  | `100` |
| `enhancer_img` | Change the color intensity in the image | `True` or `False` |
| `enhancer` | Adjust the contrast enhancer value within a range of 0.0 to 2.0, where a value of 1.0 implies no modification to the image | `0.0` to `2.0`|
____________
## You’re all set!
**The next time you play a track, the album cover art will be displayed and all the usable picture data will be stored in a new sensor.**
