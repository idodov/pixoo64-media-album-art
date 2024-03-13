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
