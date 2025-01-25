
## Installation
> [!TIP]
> Create a **Toggle Helper** in Home Assistant. For example, `input_boolean.pixoo64_album_art` can be used to control when the script runs. Establish it as a helper within the Home Assistant User Interface or YAML code. It’s best to do this prior to installation. Here’s how you can proceed:
> 1. Open `configuration.yaml`.
> 2. Add this lines and restart Home Assistant:
```yaml
#/homeassistant/configuration.yaml
input_boolean:
  pixoo64_album_art:
    name: Pixoo64 Album Art
    icon: mdi:framed_picture 
```
> **Ensure that the helper sensor is created prior to executing the script for the first time.**
1. Install **AppDaemon** from the Home Assistant add-on store.
2. On the AppDaemon [Configuration page](http://homeassistant.local:8123/hassio/addon/a0d7b954_appdaemon/config), install the **pyrhon-bidi**, **pillow**, and **unidecode** Python packages.
```yaml
# http://homeassistant.local:8123/hassi/addon/a0d7b954_appdaemon/config
system_packages: []
python_packages:
  - pillow
  - unidecode
  - python-bidi
init_commands: []
```

## Configuration
Open `/appdaemon/apps/apps.yaml` and add this code (replace or change values):
```yaml
# appdaemon/apps/apps.yaml
---
pixoo64_media_album_art:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    home_assistant:
        ha_url: "http://homeassistant.local:8123"   # Your Home Assistant URL.
        media_player: "media_player.era300"         # The entity ID of your media player.
        toggle: "input_boolean.pixoo64_album_art"   # An input boolean to enable or disable the script's execution.
        pixoo_sensor: "sensor.pixoo64_media_data"   # A sensor to store extracted media data.
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
```
