pixoo64_media_album_art:
  module: pixoo64_media_album_art
  class: Pixoo64_Media_Album_Art
  SHOW_TEXT: False
  FONT: 2
  FULL_CONTROL: True
  TOGGLE: "input_boolean.pixoo64_album_art" # CREATE IT AS A HELPER ENTITY BEFORE!!
  MEDIA_PLAYER: "media_player.era300" # Name of your speaker
  SENSOR: "sensor.pixoo64_media_data" # Name of the sensor to store the data
  HA_URL: "http://homeassistant.local:8123" # Home Assistant local URL
  URL: "http://192.168.86.21:80/post" # Pixoo64 URL
  CROP_BORDERS: True
  ENHANCER_IMG: False
