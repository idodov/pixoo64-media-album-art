In the AppDaemon app directory (appdaemon/apps), open **apps.yaml** (using the VSCode or File Editor add-on) and paste the code into it. Make sure to adjust it to your personal needs as explained in the table beyond.
   
| Parameter | Description | Example |
|---|---|---|
| **SHOW_TEXT** | Display the artist name and title. Change to `False` not to display the media info | `SHOW_TEXT = True` |
| **FULL_CONTROL** | This script assumes control of the PIXOO64 display while it’s in use and a track is playing. If `True` then the display will turn off when music paused. If `False` it display the previous channel (clock, visualizer, exc.) | `FULL_CONTROL = False` |
| **TOGGLE** | Primary toggle sensor name that triggering the script. Please create it as a helper in Home Assistant UI interface | `input_boolean.pixoo64_album_art` |
| **MEDIA_PLAYER** | Media Player entity name in Home Assistant | `media_player.era300` |
| **SENSOR** | Sensor name to store data. No need to create it in advance | `sensor.pixoo64_media_data` |
| **HA_URL** | Home Assistant local URL | `http://homeassistant.local:8123` |
| **URL** | PIXOO64 full URL | `http://192.168.86.21:80/post` |
| **CROP_BORDERS** | Remove existing borderlines from the image | `CROP_BORDERS = False` |
| **ENHANCER_IMG** | Increase the color intensity in the image by 50% | `ENHANCER_IMG = True` |


```yaml
#appdaemon/apps/apps.yaml
pixoo64_media_album_art:
  module: pixoo64_media_album_art
  class: Pixoo64_Media_Album_Art
  media_player: "media_player.era300"
  show_text: False
  font: 2
  full_control: True
  toggle: "input_boolean.pixoo64_album_art"
  pixoo_sensor: "sensor.pixoo64_media_data"
  ha_url: "http://homeassistant.local:8123"
  url: "http://192.168.86.21:80/post"
  crop_borders: True
  enhancer_img: False
```
