In the AppDaemon app directory (appdaemon/apps), open `apps.yaml` (using the VSCode or File Editor add-on) and paste the code into it. 
```yaml
#apps.yaml
pixoo64_media_album_art:
  module: pixoo64_media_album_art
  class: Pixoo64_Media_Album_Art
  media_player: "media_player.era300"
  toggle: "input_boolean.pixoo64_album_art"
  pixoo_sensor: "sensor.pixoo64_media_data"
  ha_url: "http://homeassistant.local:8123"
  url: "http://192.168.86.21:80/post"
  show_text: True
  text_background: True
  font: 2
  full_control: True
  crop_borders: True
  enhancer_img: False
  enhancer: 1.5
```
> [!WARNING]
> Make sure to adjust it to your personal needs as explained in the table beyond.
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
| `enhancer_img` | Change the color intensity in the image | `True` or `False` |
| `enhancer` | Adjust the contrast enhancer value within a range of 0.0 to 2.0, where a value of 1.0 implies no modification to the image | `0.0` to `2.0`|
