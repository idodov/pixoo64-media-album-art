# DIVOOM PIXOO64 Media Album Art Display: Elevate Your Musical Journey
Transform your DIVOOM PIXOO64 into a dynamic visual companion for your music with this script. It automatically fetches and displays the album cover art of the currently playing track, enhancing your musical experience. Additionally, it extracts valuable data such as the artist’s name and the dominant color from the album art, which can be utilized for further automation in your Home Assistant environment.
This script also supports AI image creation using the OpenAI conversation image creation service. It's designed to show alternative AI-generated album cover art when no album art exists, or when using music services (like SoundCloud) where the script can't fetch the image. It also works for radio stations that don't send any picture data.
**Using the OpenAI service incurs a cost. Each AI-generated image costs equating to around 25 images per dollar.**

> [!TIP]
> The following music services have been tested: Apple Music, Spotify, Tidal, YouTube Music, MixCloud, and Sonos Radio.

## Examples
![PIXOO_album_gallery](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71348538-2422-47e3-ac3d-aa1d7329333c)
 
## Features & Functional Advantages
- **Image Cropping:** The script removes any existing borders from the image for a better viewing experience. This is particularly useful for album art with borders or minimalist backgrounds with centralized elements. By trimming the borders, the script ensures that the main subject of the picture is not too small, providing a more detailed view of the album art.
- **Image Enhancer:** Amplifies the color vibrancy of the image for a more striking display.
- **Sensor Data Storage:** All extracted data is stored in a dedicated sensor entity within Home Assistant, making it readily available for further automation possibilities.
- **RTL Support:** Ensures that the artist’s name or song title is displayed correctly in right-to-left languages.
- **Title Normalization:** Normalizes titles and artist names for easier integration with automations and consistent display, regardless of regional characters or symbols. For instance, the artist name “Beyoncé” (with an accent) would be normalized to “Beyonce” (accent removed).
- **Light Dynamic Color Integration:** Uses the dominant color from the album art to set the background color on any RGB light.
## Prerequisites
1. [DIVOOM PIXOO64](https://www.aliexpress.com/item/1005003116676867.html)
2. Home Assistant (with add-on functionality)
3. AppDaemon (Home Assistant add-on)
## Installation
> [!TIP]
> Create a **Toggle Helper** in Home Assistant. For example, `input_boolean.pixoo64_album_art` can be used to control when the script runs. This means that whenever the player starts a track, the album art will appear if the toggle is on. Establish this helper within the Home Assistant User Interface or YAML code. It’s best to do this prior to installation. Here’s how you can proceed:
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
2. On the AppDaemon [Configuration page](http://homeassistant.local:8123/hassio/addon/a0d7b954_appdaemon/config), install the **`requests`**, **`numpy==1.26.4`**, **`pillow`**, **`python-bidi`** and **`unidecode`** Python packages.

> [!IMPORTANT]
> Not installing the packadges may cause the script not work
>```yaml
># http://homeassistant.local:8123/hassio/addon/a0d7b954_appdaemon/config
>system_packages: []
>python_packages:
>  - requests
>  - unidecode
>  - pillow
>  - numpy==1.26.4
>  - python-bidi
>init_commands: []
>```
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
---
pixoo64_media_album_art:
  module: pixoo64_media_album_art
  class: Pixoo64_Media_Album_Art
    home_assistant:
        ha_url: "http://homeassistant.local:8123"  # Home Assistant URL
        media_player: "media_player.era300"        # Media player entity ID
        toggle: "input_boolean.pixoo64_album_art"  # Boolean sensor to control script execution
        pixoo_sensor: "sensor.pixoo64_media_data"  # Sensor to store media data (Optional)
        light: "light.strip_stone"                 # RGB light entity ID (if any) (Optional)
        ai_fallback: False                         # Create alternative album art cover using the power of AI (OPENAI API). fail_txt must also be 'True'.
    pixoo:
        url: "http://192.168.86.21:80/post"        # Pixoo device URL
        full_control: True                         # Control display on/off with play/pause
        contrast: True                             # Apply 50% contrast filter
        fail_txt: True                             # Show media info if image fails to load
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
| `ai_fallback` | Create alternative album art cover using the power of AI (OPENAI API). `fail_txt` must also be `True` | `True` |
| `url` | Pixoo device URL | `"http://192.168.86.21:80/post"` |
| `full_control` | Control display on/off with play/pause | `True` |
| `contrast` | Apply 50% contrast filter | `True` |
| `fail_txt` | Show media info if image fails to load | `True` |
| `clock` | Show a clock top corner | `False` |
| `clock_align` | Align to clock `Left` or `Right` | `Left` |
| `tv_icon` | Shows TV art when playing sound from TV | `True` |
| `show_text - enabled` | Show media info with image | `False` |
| `show_text - clean_title` | Remove "Remaster" labels, track number and file extentions from the title if any | `True` |
| `show_text - text_background` | Change background of text area | `True` |
| `show_text - font` | Pixoo internal font type (0-7). Used in fallback screen only | `2` |
| `show_text - color` | Use alternative font color | `False` |
| `crop_borders - enabled` | Crop image borders if present | `True` |
| `crop_borders - extra` | Apply enhanced border crop | `True` |

> [!NOTE]
> ### `light`
> The light feature is a built-in automation that sends a ‘turn on’ command with RGB values corresponding to the most dominant color in the image. If the image is black, white, or gray, the automation will select a soft random color.
> 
> ### `crop_borders`
> Given the Pixoo screen’s 64x64 pixel size, it is highly recommended to utilize the crop feature. Many album cover arts come with borders, occasionally wide ones, which can distort the display of the cover art on the screen. To rectify this, the script ensures the removal of the picture frame border.
> | Original | Crop | Extra |
> |---|---|---|
> | ![cover2](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71fda47e-f4fe-4142-9303-16d95d2c109e) | ![cover2_crop](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/ad32fb20-7b94-4795-a1af-16148dac473f) | ![kb-crop_extra](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/4e6bec64-0fa3-4bb3-a863-9e1ace780b58) |
> | ![psb-original](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/beb0d74c-5a27-4ad8-b7a8-f11f6ae8d3ea) | ![psb-crop](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/efc4f44a-4c7d-4aca-b1bf-a158b252b26d) | ![psb-crop_extra](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/b25cc2e7-aa22-4e73-9c7a-b30ea4ec73fb) |
____________
## You’re all set!
**Make sure that `input_boolean.pixoo64_album_art` is turned `on`. The next time you play a track, the album cover art will be displayed, and all the usable picture data will be stored in a new sensor.**

![animated-g](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/2a716425-dd65-429c-be0f-13acf862cb10)
_____________
## Sensor Attribues
The sensor  `sensor.pixoo64_media_data` is a virtual entity created in Home Assistant. It’s designed to store useful picture data from the album cover art of the currently playing song. This includes the artist’s name, the title of the media and color information such as the color of the font and the background. This sensor allows for dynamic visual experiences and automation possibilities based on the music being played.

| Attribute | Description |
|---|---|
| `artist` | The original name of the artist |
| `normalized_artist` | The artist's name in Latin letters |
| `media_title` | The original title of the media |
| `normalized_title` | The media title in Latin letters |
| `font_color` | The color of the font |
| `font_color_alternative` | An alternative color for the font |
| `background_color_brightness` | The brightness level of the background color |
| `background_color` | The color of the lower part in background |
| `background_color_rgb` | The RGB values of the background color (lower part) |
| `color_alternative` |  The most common color of the background |
| `color_alternative_rgb` | The RGB values of the most common background color |

Here’s an examples of the sensor attributes:

```yaml
artist: Björk & Trio Gudmundar Ingolfssonar
normalized_artist: Bjork & Trio Gudmundar Ingolfssonar
media_title: Það Sést Ekki Sætari Mey
normalized_title: Thad Sest Ekki Saetari Mey
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
Arabic Title When Normalized (letters changed to English):
```yaml
....
media_title: آمين
normalized_title: amyn
....
```

# Guide to Creating an AI Album cover art
**How it works:** When there’s an issue loading the image, the script triggers another Home Assistant script to call the OpenAI service. This approach is necessary because the OpenAI service doesn’t send a reply outside the Home Assistant script that initiated the call. To transfer data to AppDaemon, we create an input_text helper that stores the image URL. When updated, the AppDaemon script automatically loads the image. Image generation takes around 10 seconds, during which the Pixoo64 displays the artist's name and song title.
To activate the feture make sure the `apps.yaml` define to support `fail_txt` and `ai_fallback`, for example:
```yaml
#apps.yaml
pixoo64_media_album_art:
  module: pixoo64_media_album_art
  class: Pixoo64_Media_Album_Art
  home_assistant:
    ha_url: "http://homeassistant.local:8123"
    media_player: "media_player.era300"
    toggle: "input_boolean.pixoo64_album_art"
    pixoo_sensor: "sensor.pixoo64_media_data"
    light: "light.strip_stone"
    ai_fallback: True                           # TRUE to use AI Image fallback, FALSE just will display text 
  pixoo:
    url: "http://192.168.86.22:80/post"
    full_control: True
    contrast: False
    fail_txt: True                              # True to show fallback text, FALSE not to show text and AI Image fallback
    clock: False
    clock_align: Right
    tv_icon: False
    show_text:
      enabled: False
      clean_title: True
      text_background: False
      font: 2
      color: True
    crop_borders:
      enabled: True
      extra: True
```

## Steps to Get Started

### 1. OPENAI Integration

- Install the [OPENAI Conversation](https://www.home-assistant.io/integrations/openai_conversation/) using your OPENAI API key as described on the integration page.

### 2. Prepare Home Assistant

- If you don't already have a `python_scripts` directory, create one in the `homeassistant/config` directory.

### 3. Download the Python Script

- Grab the Python file from [this repository](https://github.com/pmazz/ps_hassio_entities/tree/master/python_scripts) and place it inside the `python_scripts` directory.

### 4. Update Configuration

- Open `configuration.yaml` and add the following line if it doesn't already exist:

  ```yaml
  python_script:
  ```

### 5. Restart Home Assistant

- Restart Home Assistant to apply the changes.

### 6. Create a Custom Script

Now, let's create a script that will send command to the AI agent and store the data inside a sensor attribute for easy access.

- Go to Settings > Automation > Scripts and create a new script.
- Switch to YAML mode and paste this code:
- **CHANGE PLAYER NAME TO YOUR OWN**  `{{ state_attr('media_player.era300', 'media_artist') }}` (from era300 to your player name)!
- Save this script in name: `ai image`

  ```yaml
  alias: ai image
  sequence:
    - action: openai_conversation.generate_image
      metadata: {}
      data:
        size: 1024x1024
        quality: standard
        style: vivid
        config_entry: 64fb0c3033b52964ff8a74d1e718056e
        prompt: >-
          Create an album cover in 8-bit pixel art style for artist {{
          state_attr('media_player.era300', 'media_artist') }} and song {{
          state_attr('media_player.era300', 'media_title') }}. The artwork should
          feature the artist's likeness, captured as accurately as possible, but
          avoid using any text on the image. Aim for a vibrant, retro aesthetic
          that embodies the spirit of classic video game graphics.
      response_variable: ai_response
    - data:
        action: set_state_attributes
        entity_id: input_text.ai_music
        state: "off"
        attributes:
          - ai_url: "{{ ai_response['url'] }}"
          - ai_update: "{{ '' ~ now().strftime('%H:%M | %d/%m/%Y') }}"
      action: python_script.hass_entities
  description: album cover art
  ```

__________

> [!NOTE]
> While experimenting with the device, you may notice occasional freezes. These could potentially be due to power issues. To address this, it’s suggested to use a USB charger with an output of 3A for optimal performance. If you’re using a charger with a lower voltage (2A, which is the minimum required), it’s advisable to limit the screen brightness to no more than 90%.
>
> Also, at times, an overloaded Wi-Fi network might result in the Pixoo64 responding slowly. Most often, rebooting the Wi-Fi network or the router rectifies this problem. 

**Disclaimer:**
*This software is **not** an official product from Divoom. As a result, Divoom bears **no responsibility** for any damages or issues arising from the use of this script. Additionally, Divoom does **not** offer end-user support for this script. Please utilize it at your own risk.*
