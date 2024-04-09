
## Installation
> [!TIP]
> Create a **Toggle Helper** in Home Assistant. For example, `input_boolean.pixoo64_album_art` can be used to control when the script runs. Establish it as a helper within the Home Assistant User Interface or YAML code. It’s best to do this prior to installation. Here’s how you can proceed:
> 1. Open `configuration.yaml`.
> 2. Add this lines and restart Home Assistant:
> ```yaml
> #/homeassistant/configuration.yaml
> input_boolean:
>   pixoo64_album_art:
>     name: Pixoo64 Album Art
>     icon: mdi:framed_picture 
> ```
> **Ensure that the helper sensor is created prior to executing the script for the first time.**
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
1. In Home Assistant: Navigate to `HACS` > `Automation`
   * If this option is not available, go to `Settings` > `Integrations` > `HACS` > `Configure` and enable `AppDaemon apps discovery & tracking`. After enabling, return to the main HACS screen and select `Automation`
2. Navigate to the `Custom Repositories` page and add the following repository as `Automation`: `https://github.com/idodov/pixoo64-media-album-art/`
3. Return to the `HACS Automation` screen, press the `+` button, search for `PIXOO64 Media Album Art`, and click on `Download`
> [!IMPORTANT]  
> In AppDaemon, make sure to specify the apps directory in `/addon_configs/a0d7b954_appdaemon/appdaemon.yaml`.
> Also, remember to transfer all files from `/addon_configs/a0d7b954_appdaemon/apps/` to `/homeassistant/appdaemon/apps/`.
> ```yaml
> #/addon_configs/a0d7b954_appdaemon/appdaemon.yaml
> ---
> secrets: /homeassistant/secrets.yaml
> appdaemon:
>   app_dir: /homeassistant/appdaemon/apps/
> ```
_________
## Final Step - Configuration
Open `/appdaemon/apps/apps.yaml` and add this code:
> [!TIP]
>  If you’re using the File Editor add-on, it’s set up by default to only allow file access to the main Home Assistant directory. However, the AppDaemon add-on files are located in the root directory. To access these files, follow these steps:
> 1. Go to `Settings` > `Add-ons` > `File Editor` > `Configuration`
> 2. Toggle off the `Enforce Basepath` option.
> 3. In the File Editor, click on the arrow next to the directory name (which will be ‘homeassistant’). This should give you access to the root directory where the AppDaemon add-on files are located.
> 
>    ![arrow](https://github.com/idodov/RedAlert/assets/19820046/e57ea52d-d677-45b0-90c4-87723c5ddfea)

```yaml
# appdaemon/apps/apps.yaml
-----
pixoo64_media_album_art:
  module: pixoo64_media_album_art
  class: Pixoo64_Media_Album_Art
  home_assistant:
    ha_url: "http://homeassistant.local:8123"  # Home Assistant URL
    media_player: "media_player.era300"        # Media player entity ID
    toggle: "input_boolean.pixoo64_album_art"  # Boolean sensor to control script execution (Optional)
    pixoo_sensor: "sensor.pixoo64_media_data"  # Sensor to store media data (Optional)
    light: False                               # RGB light entity ID (if any) (Optional)
  pixoo:
    url: "http://192.168.86.21:80/post"        # Pixoo device URL
    full_control: True                         # Control display on/off with play/pause
    contrast: True                             # Apply 50% contrast filter
    fail_txt: True                             # Show media info if image fails to load
    show_text:
      enabled: False                           # Show media info with image
      text_background: True                    # Change background of text area
      font: 2                                  # Pixoo internal font type (0-7)
      color: False                             # Use alternative font color
    crop_borders:
      enabled: True                            # Crop image borders if present
      extra: True                              # Apply enhanced border crop
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
| `url` | Pixoo device URL | `"http://192.168.86.21:80/post"` |
| `full_control` | Control display on/off with play/pause | `True` |
| `contrast` | Apply 50% contrast filter | `True` |
| `fail_txt` | Show media info if image fails to load | `True` |
| `show_text - enabled` | Show media info with image | `False` |
| `show_text - text_background` | Change background of text area | `True` |
| `show_text - font` | Pixoo internal font type (0-7) | `2` |
| `show_text - color` | Use alternative font color | `False` |
| `crop_borders - enabled` | Crop image borders if present | `True` |
| `crop_borders - extra` | Apply enhanced border crop | `True` |
