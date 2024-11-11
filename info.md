
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
Open `/appdaemon/apps/apps.yaml` and add this code:
```yaml
# appdaemon/apps/apps.yaml
---
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
        spotify_client_id: False                   # client_id key API KEY from developers.spotify.com
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
        show_text:
            enabled: False                         # Show media artist and title 
            clean_title: True                      # Remove "Remaster" labels, track number and file extentions from the title if any
            text_background: True                  # Change background color or better text display with image
            font: 2                                # Pixoo internal font type (0-7) for fallback text when there is no image
            color: False                           # Use alternative font color
        crop_borders:
            enabled: True                          # Crop image borders if present
            extra: True                            # Apply enhanced border crop
```
> [!WARNING]
> **Only save it once you’ve made the described changes to the settings.**

| Parameter | Description | Example Values |
| --- | --- | --- |
| `ha_url` | Home Assistant URL | `"http://homeassistant.local:8123"` |
| `media_player` | Media player entity ID | `"media_player.era300"` |
| `toggle` | Boolean sensor to control script execution (Optional) | `"input_boolean.pixoo64_album_art"` |
| `pixoo_sensor` | Sensor to store media data (Optional) | `"sensor.pixoo64_media_data"` |
| `light` | RGB light entity ID (if any) (Optional) | `False` or `light.rgb_light` |
| `ai_fallback` | Create alternative album art using AI. Options are `flux` or `turbo` | `turbo` |
| `musicbrainz` | Search for album art in MusicBrainz | `True` |
| `spotify_client_id` | Spotify Client ID. Use `False` or the actual key | `False` or `KEY` |
| `spotify_client_secret` | Spotify Client Secret. Use `False` or the actual key | `False` or `KEY` |
| `last.fm` | Last.fm key. Use `False` or the actual key | `False` or `KEY` |
| `Discogs` | Discogs Personal token. Use `False` or the actual key | `False` or `KEY` |
| `url` | Pixoo device URL | `192.168.86.21` |
| `full_control` | Control display on/off with play/pause | `True` |
| `contrast` | Apply a 50% contrast filter | `True` |
| `clock` | Show a clock in the top corner | `False` |
| `clock_align` | Align the clock to `Left` or `Right` | `Left` |
| `tv_icon` | Show TV art when playing sound from TV | `True` |
| `show_text - enabled` | Show media info with image | `False` |
| `show_text - clean_title` | Remove "Remaster" labels, track numbers, and file extensions from the title if any | `True` |
| `show_text - text_background` | Change background of text area | `True` |
| `show_text - font` | Pixoo internal font type (0-7). Used in fallback screen only | `2` |
| `show_text - color` | Use alternative font color | `False` |
| `crop_borders - enabled` | Crop image borders if present | `True` |
| `crop_borders - extra` | Apply enhanced border cropping | `True` |
