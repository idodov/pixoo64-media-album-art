# 🎵 PIXOO64 Media Album Art Display

This AppDaemon script for Home Assistant enhances your music experience by displaying rich visuals on your DIVOOM PIXOO64 screen. It automatically shows album art, lyrics, time, temperature, and more whenever music is playing. If album art isn’t available, it uses online APIs or AI image generation to create one on the fly. It can also sync colors with lights or WLED devices for immersive ambiance.

---

## 🎨 Features

- **📀 Dynamic Album Art** — Displays 64x64 optimized artwork for the current track.
- **🧠 Intelligent Fallback** — Searches Spotify, Discogs, Last.fm, TIDAL, and MusicBrainz. If all fail, uses AI-generated art via pollinations.ai (`turbo` or `flux`).
- **🎤 Synchronized Lyrics** — Shows lyrics with timing when supported by the media player.
- **🕒 Real-Time Overlay** — Displays track info, time, temperature, and more as overlays.
- **🔥 Burned Mode** — Adds high-contrast styling. Can be combined with overlays like clock, temperature, or text.
- **🎞️ Spotify Slider** — Scrolls through Spotify-recommended album covers.
- **🌈 RGB/WLED Lighting** — Syncs nearby lights with the dominant color of the album cover.
- **🛠️ Highly Configurable** — More behavior combinations via YAML or Home Assistant UI.

---


## 🎨 Examples

![PIXOO_album_gallery](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71348538-2422-47e3-ac3d-aa1d7329333c)

---

## 🔧 Prerequisites

Before you begin, make sure you have the following:

1. **DIVOOM PIXOO64**:  
   - Purchase the device from [AliExpress](https://www.aliexpress.com/item/1005003116676867.html).
2. **Home Assistant**:  
   - Ensure you have Home Assistant installed and running with add-on functionality.
3. **AppDaemon**:  
   - Install the AppDaemon add-on in Home Assistant (instructions below).

---

## 🛠️ Installation

Follow these steps to install and set up the PIXOO64 Media Album Art Display script.

### **Step 1: Install AppDaemon**

<details>
<summary>Click to expand installation steps</summary>

1. Open Home Assistant in your web browser.
2. Navigate to **Settings** > **Add-ons**.
3. Click the **Add-on Store** button (lower right corner).
4. Search for "AppDaemon" and install it.
5. After installation, start the AppDaemon add-on.

</details>

### **Step 2: Install Required Python Packages**

<details>
<summary>Click to expand Python package installation</summary>

1. Go to the AppDaemon add-on configuration page (found in the Add-ons page where you started AppDaemon).
2. Locate the **Python packages** section.
3. Add the following packages:

```yaml
python_packages:
  - pillow
  - python-bidi
  - unidecode
```

- `pillow` — Required for image handling.
- `python-bidi` — Supports right-to-left (RTL) text (Arabic, Hebrew, etc).
- `unidecode` — Standardizes non-ASCII text for filenames, caching, and comparison. Used in **Burned Mode**.

</details>

### **Step 3: Create Helpers**

<details>
<summary>Click to expand toggle helper creation</summary>

1. In Home Assistant, go to **Settings** > **Devices & Services**.
2. Click on **Helpers**.
3. Click the **Create Helper** button (lower right corner).
4. Select **Toggle** and give it an appropriate name (e.g., `PIXOO64 Album Art`).
5. Note if the `entity_id` of this helper is not named `input_boolean.pixoo64_album_art`; you will need it later for configuration.
   - **Important:** Ensure this new helper entity is toggled **ON**. If it's off, the script will not run. This toggle allows you to easily disable the script when needed.
6. Add this code to `configuration.yaml` if you want to control the display from Homeassistant UI (or add them as helpers):
![image](https://github.com/user-attachments/assets/a7923467-c901-4981-8017-282c741957de)

```yaml
input_number:
  pixoo64_album_art_lyrics_sync:
    name: Lyrics Sync
    icon: mdi:text-box
    min: -10
    max: 10
    step: 1

input_select:
  pixoo64_album_art_display_mode:
    name: Pixoo64 Display Mode
    icon: mdi:application-cog
    options:
      - "Default"
      - "Clean"
      - "AI Generation (Flux)"
      - "AI Generation (Turbo)"
      - "Burned"
      - "Burned | Clock"
      - "Burned | Clock (Background)"
      - "Burned | Temperature"
      - "Burned | Temperature (Background)"
      - "Burned | Clock & Temperature (Background)"
      - "Text"
      - "Text (Background)"
      - "Clock"
      - "Clock (Background)"
      - "Clock | Temperature"
      - "Clock | Temperature (Background)"
      - "Clock | Temperature | Text"
      - "Clock | Temperature | Text (Background)"
      - "Lyrics"
      - "Lyrics (Background)"
      - "Temperature"
      - "Temperature (Background)"
      - "Temperature | Text"
      - "Temperature | Text (Background)"
      - "Special Mode"
      - "Special Mode | Text"

  pixoo64_album_art_crop_mode:
    name: Pixoo64 Crop Mode
    icon: mdi:application-edit
    options:
      - "Default"
      - "No Crop"
      - "Crop"
      - "Crop Exra"

```
</details>


### **Step 4: Download the Script**

You can install the script using either **HACS** (Home Assistant Community Store, recommended) or by manually downloading the Python file.

<details>
<summary><strong>HACS (Recommended)</strong></summary>

- When installing through HACS, you **MUST** manually move all files from `/addon_configs/a0d7b954_appdaemon/apps/` to `/homeassistant/appdaemon/apps/`.
- HACS places files in the `/homeassistant` directory (which can also be mapped as `/config` directory), while AppDaemon expects them in the `/addon_configs` directory.
- If you're using the SAMBA SHARE add-on, Windows File Explorer will show the directory as `/config`, meaning that files should be moved to `/config/appdaemon/apps/`.

1. Open `/addon_configs/a0d7b954_appdaemon/appdaemon.yaml` and configure it by adding the following line under `appdaemon:`:
   ```yaml
   appdaemon:
      app_dir: /homeassistant/appdaemon/apps/ # DO NOT CHANGE THIS LINE, even if the files are located in the /config directory (when using Samba Share addon)
      latitude: 51.507351 # Update value from https://www.latlong.net
      longitude: -0.127758 # Update value from https://www.latlong.net
   ```

2. Do not remove any existing lines from the file; just add the new line and update the Latitude and Longitude values from https://www.latlong.net

3. If you don’t have HACS installed, follow the instructions on the [HACS GitHub page](https://hacs.xyz/) to install it.

4. After HACS is set up:
   - Go to the HACS page in Home Assistant.
   - If "AppDaemon" repositories are not found, enable AppDaemon apps discovery and tracking in HACS settings:
     - Navigate to **Settings** > **Integrations** > **HACS** > **Configure**.
     - Enable **AppDaemon apps discovery & tracking**.
   - Click on **Custom Repositories** and add `https://github.com/idodov/pixoo64-media-album-art` as an **AppDaemon** repository.
   - Search for and download `PIXOO64 Media Album Art` in HACS.

</details>

<details>
<summary><strong>Manual Download</strong></summary>
   With this method, you will not receive automatic updates.

   
   - Download the Python script directly from the GitHub repository [Download Link](https://github.com/idodov/pixoo64-media-album-art/blob/main/apps/pixoo64_media_album_art/pixoo64_media_album_art.py)
   - Place the file into the directory `/addon_configs/a0d7b954_appdaemon/apps`.

</details>


### **Step 5: Configure AppDaemon**

To activate the script, you’ll need to modify the `apps.yaml` file. This file is typically located in the `/appdaemon/apps` directory that you added in the previous step.
<details>
<summary><strong>Basic Configuration</strong></summary>
For a minimal setup, add the following to your `/appdaemon/apps/apps.yaml` file. Adjust the `ha_url`, `media_player`, and `url` parameters to match your setup.

```yaml
pixoo64_media_album_art:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    home_assistant:
        ha_url: "http://homeassistant.local:8123"   # Your Home Assistant URL.
        media_player: "media_player.living_room"    # The entity ID of your media player.
    pixoo:
        url: "192.168.86.21"                        # The IP address of your Pixoo64 device.
```

If you have more than one PIXOO64 screen, you can add another configuration block and **change the first line's name**. For example:

```yaml
pixoo64_media_album_art_2:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    home_assistant:
        ha_url: "http://homeassistant.local:8123"   # Your Home Assistant URL.
        media_player: "media_player.tv_room"        # The entity ID of your media player.
    pixoo:
        url: "192.168.86.22"                        # The IP address of your Pixoo64 device.
```

</details>

<details>
<summary><strong>Full Configuration</strong></summary>
For all features, use the following configuration. Adjust the values to match your Home Assistant setup and your PIXOO64 device’s IP address.

```yaml
pixoo64_media_album_art:
  module: pixoo64_media_album_art
  class: Pixoo64_Media_Album_Art
  home_assistant:
    ha_url: "http://homeassistant.local:8123"           # Your Home Assistant URL.
    media_player: "media_player.era300"                 # The entity ID of your media player.
    toggle: "input_boolean.pixoo64_album_art"           # Input boolean to enable or disable the script.
    pixoo_sensor: "sensor.pixoo64_media_data"           # Sensor to store extracted media data.
    lyrics_sync_entity: "input_number.pixoo64_album_art_lyrics_sync"  # Lyrics sync offset in seconds.
    mode_select: "input_select.pixoo64_album_art_display_mode"        # Helper for display mode selection.
    crop_select: "input_select.pixoo64_album_art_crop_mode"           # Helper for crop mode selection.
    temperature_sensor: "sensor.temperature"            # Home Assistant temperature sensor (instead of Divoom weather).
    light: "light.living_room"                          # RGB light entity to sync with album art colors.
    ai_fallback: "turbo"                                # AI model to use for image fallback ("flux" or "turbo").
    force_ai: False                                     # If True, always use AI-generated images regardless of availability.
    musicbrainz: True                                   # If True, use MusicBrainz as a fallback if other sources fail.
    spotify_client_id: False                            # Spotify API client ID (required for Spotify features).
    spotify_client_secret: False                        # Spotify API client secret.
    tidal_client_id: False                              # TIDAL API client ID.
    tidal_client_secret: False                          # TIDAL client secret.
    last.fm: False                                      # Last.fm API key.
    discogs: False                                      # Discogs API key.
  pixoo:
    url: "192.168.86.21"                                # The IP address of your Pixoo64 device.
    full_control: True                                  # Controls Pixoo64's power state in sync with media playback.
    contrast: True                                      # Applies a 50% contrast filter to images.
    sharpness: False                                    # Enables a sharpness filter on album art.
    colors: False                                       # Enhances color intensity.
    kernel: False                                       # Applies emboss/edge effect.
    special_mode: False                                 # Show day, time, and temperature in a top bar.
    info: False                                         # Show fallback info when no image is available.
    temperature: True                                   # Show temperature from sensor.
    clock: True                                         # Display a clock in the screen's top corner.
    clock_align: "Right"                                # Clock alignment: "Left" or "Right".
    tv_icon: True                                       # Display TV icon if audio source is a TV.
    lyrics: False                                       # Show synchronized lyrics (disables clock and text).
    lyrics_font: 2                                      # Recommended values: 2, 4, 32, 52, 58, 62, etc.
    limit_colors: False                                 # Limit color palette to 4–256 colors, or use full color if False.
    spotify_slide: False                                # Enable Spotify album slideshow (disables clock and text).
    images_cache: 100                                   # Number of images to cache in memory (each ~17KB).
    show_text:
      enabled: False                                    # Display artist and track title.
      clean_title: True                                 # Remove metadata like "Remastered", file extensions, etc.
      text_background: True                             # Add background behind text for better contrast.
      special_mode_spotify_slider: False                # Enable animated album slider when using special mode.
      force_font_color: False                           # Force text color (e.g., "#FFFFFF" for white).
      burned: False                                     # Enable static (non-animated) burned text above the image.
    crop_borders:
      enabled: True                                     # Enable basic border cropping.
      extra: True                                       # Enable advanced border cropping.
  wled:
    wled_ip: "192.168.86.55"                            # WLED device IP address.
    brightness: 255                                     # Brightness level (0–255).
    effect: 38                                          # Effect ID (0–186).
    effect_speed: 50                                    # Effect speed (0–255).
    effect_intensity: 128                               # Effect intensity (0–255).
    palette: 0                                          # Palette ID (0–70).
    sound_effect: 0                                     # Audio reactive mode (0: BeatSin, 1: WeWillRockYou, etc.).
    only_at_night: False                                # Only enable WLED at night.

```
</details>
With these steps completed, you have installed and set up the script and can now configure it to fit your needs.

Make sure that `input_boolean.pixoo64_album_art` is toggled **ON**. The next time you play a track, the album cover art will be displayed, and all usable picture data will be stored in a new sensor.

![animated-g](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/2a716425-dd65-429c-be0f-13acf862cb10)

Here is the grammar-checked and improved version of your configuration parameter tables. I've corrected typos, fixed phrasing inconsistencies, and made the descriptions clearer and more concise where needed.

---

## 🛠️ Configuration Parameters

Below is a detailed breakdown of all configuration parameters for the PIXOO64 Media Album Art Display script. These allow you to customize the script's behavior to suit your setup.

<details>
<summary><strong>Core Parameters</strong></summary>

| Parameter               | Description                                                                      | Example Values                                  |
| ----------------------- | -------------------------------------------------------------------------------- | ----------------------------------------------- |
| `ha_url`                | The URL of your Home Assistant instance.                                         | `"http://homeassistant.local:8123"`             |
| `media_player`          | The entity ID of your media player.                                              | `"media_player.living_room"`                    |
| `toggle`                | An input boolean to enable or disable the script (optional).                     | `"input_boolean.pixoo64_album_art"`             |
| `pixoo_sensor`          | Sensor used to store extracted media metadata (optional).                        | `"sensor.pixoo64_media_data"`                   |
| `light`                 | RGB light entity to sync with album art colors (optional).                       | `False` or `"light.living_room"`                |
| `ai_fallback`           | AI model to generate fallback album art (`flux` or `turbo`).                     | `"turbo"`                                       |
| `temperature_sensor`    | Temperature sensor entity used instead of the Divoom weather service (optional). | `"sensor.temperature"`                          |
| `mode_select`           | Entity ID of the input select for display mode selection (optional).             | `"input_select.pixoo64_album_art_display_mode"` |
| `crop_select`           | Entity ID of the input select for crop mode selection (optional).                | `"input_select.pixoo64_album_art_crop_mode"`    |
| `musicbrainz`           | Enables fallback album art lookup via MusicBrainz.                               | `True`                                          |
| `spotify_client_id`     | Your Spotify API client ID (required for Spotify features).                      | `False` or `"your_spotify_client_id"`           |
| `spotify_client_secret` | Your Spotify API client secret (required for Spotify features).                  | `False` or `"your_spotify_client_secret"`       |
| `tidal_client_id`       | Your TIDAL API client ID (optional).                                             | `False` or `"your_tidal_client_id"`             |
| `tidal_client_secret`   | Your TIDAL API client secret (optional).                                         | `False` or `"your_tidal_client_secret"`         |
| `last.fm`               | Your Last.fm API key (optional).                                                 | `False` or `"your_lastfm_api_key"`              |
| `discogs`               | Your Discogs personal access token (optional).                                   | `False` or `"your_discogs_token"`               |

</details>

<details>
<summary><strong>PIXOO64-Specific Parameters</strong></summary>

| Parameter       | Description                                                                                               | Example Values                  |
| --------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------- |
| `url`           | IP address of your PIXOO64 device.                                                                        | `"192.168.86.21"`               |
| `full_control`  | Controls the Pixoo64's on/off state based on media playback.                                              | `True`                          |
| `contrast`      | Applies 50% contrast filter to displayed images.                                                          | `True`                          |
| `sharpness`     | Applies a sharpness enhancement to images.                                                                | `True`                          |
| `colors`        | Enhances colors in the image.                                                                             | `True`                          |
| `special_mode`  | Displays time, date, and temperature in a top bar overlay.                                                | `False`                         |
| `temperature`   | Displays temperature data from the configured sensor.                                                     | `True`                          |
| `clock`         | Displays a digital clock in the top corner of the screen.                                                 | `True`                          |
| `clock_align`   | Clock alignment on screen.                                                                                | `"Left"` or `"Right"`           |
| `tv_icon`       | Displays a TV icon when audio comes from a TV source.                                                     | `True`                          |
| `lyrics`        | Displays synchronized lyrics (disables `show_text` and `clock`).                                          | `True`                          |
| `lyrics_font`   | Font ID used to display lyrics. See [DIVOOM Fonts](https://app.divoom-gz.com/Device/GetTimeDialFontList). | `2`, `4`, `32`, `52`, etc.      |
| `limit_colors`  | Reduces color palette size for performance or style; set to `False` to use original colors.               | `4`, `8`, ..., `256` or `False` |
| `spotify_slide` | Enables a slideshow of album covers from Spotify (disables clock and text).                               | `True`                          |
| `images_cache`  | Number of processed images stored in memory (approx. 17KB each).                                          | `1` to `500`                    |

</details>

<details>
<summary><strong>Text Display Options</strong></summary>

| Parameter                     | Description                                                         | Example Values         |
| ----------------------------- | ------------------------------------------------------------------- | ---------------------- |
| `enabled`                     | If `True`, displays artist and track title.                         | `True`                 |
| `clean_title`                 | Removes metadata from titles (e.g., "Remastered", file extensions). | `True`                 |
| `text_background`             | Adds a background color behind text to improve contrast.            | `True`                 |
| `special_mode_spotify_slider` | Animates album art when used with `special_mode` and `show_text`.   | `True`                 |
| `force_text_color`            | Overrides dynamic text color. Use `False` or a hex value.           | `False` or `"#FFFFFF"` |

</details>


<summary><strong>Image Cropping Options</strong></summary>

Many album covers come with borders that can distort the display on the PIXOO64's 64x64 pixel screen. The `crop_borders` feature ensures these borders are removed for a cleaner look.
| Parameter crop_borders  | Description                                                                   | Example Values                          |
|-------------------------|-------------------------------------------------------------------------------|-----------------------------------------|
| `enabled` | Crop borders from album art images.                                                         | `True`                                  |
| `extra`   | Apply enhanced border cropping for better results.                                          | `True`                                  |

| Original | Crop | Extra |
|---|---|---|
| ![cover2](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71fda47e-f4fe-4142-9303-16d95d2c109e) | ![cover2_crop](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/ad32fb20-7b94-4795-a1af-16148dac473f) | ![kb-crop_extra](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/4e6bec64-0fa3-4bb3-a863-9e1ace780b58) |
| ![psb-original](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/beb0d74c-5a27-4ad8-b7a8-f11f6ae8d3ea) | ![psb-crop](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/efc4f44a-4c7d-4aca-b1bf-a158b252b26d) | ![psb-crop_extra](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/b25cc2e7-aa22-4e73-9c7a-b30ea4ec73fb) |
```yaml
pixoo64_media_album_art:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    pixoo:
        crop_borders:
            enabled: True  # If True, attempts to crop any borders from the album art.
            extra: True    # If True, applies an enhanced border cropping algorithm.
```
</details>

<details>
<summary><strong>WLED Configuration</strong></summary>

| Parameter               | Description                                                                                   | Example Values                          |
|-------------------------|-----------------------------------------------------------------------------------------------|-----------------------------------------|
| `wled_ip`               | The IP address of your WLED device.                                                           | `"192.168.86.55"`                       |
| `brightness`            | Brightness level for WLED lights (0–255).                                                     | `255`                                   |
| `effect`                | WLED effect ID (see [WLED Effects](https://kno.wled.ge/features/effects/)).                   | `0` to `186`                            |
| `effect_speed`          | Speed of the WLED effect (0–255).                                                             | `50`                                    |
| `effect_intensity`      | Intensity of the WLED effect (0–255).                                                         | `128`                                   |
| `palette`               | WLED palette ID (see [WLED Palettes](https://kno.wled.ge/features/palettes/)).                | `0` to `70`                             |
| `only_at_night`         | Run WLED automation only during nighttime hours.                                              | `True`                                  |


</details>
<details>
<summary><strong>Additional Notes</strong></summary>

### **Light Feature**
The `light` parameter allows you to sync RGB lights with the dominant color of the album art. If the image is black, white, or gray, a soft random color will be selected. You can configure multiple lights using the following syntax:
 ```yaml
pixoo64_media_album_art:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    home_assistant:
       light:
         - "light.living_room"
         - "light.bed_room"
```

### **WLED Integration**
 The WLED feature is designed specifically for WLED lights. It sends a "turn on" command with RGB values corresponding to the dominant colors in the album art. You can control brightness, effects, and palettes, and optionally restrict automation to nighttime hours.
```yaml
pixoo64_media_album_art:
   module: pixoo64_media_album_art
   class: Pixoo64_Media_Album_Art
   wled:
        wled_ip: "192.168.86.55"                    # Your WLED IP Adress
        brightness: 255                             # 0 to 255
        effect: 38                                  # 0 to 186 (Effect ID - https://kno.wled.ge/features/effects/)
        effect_speed: 50                            # 0 to 255
        effect_intensity: 128                       # 0 to 255
        pallete: 0                                  # 0 to 70 (Pallete ID - https://kno.wled.ge/features/palettes/)
        only_at_night: False                        # Runs only at night hours
 ```

 ### **Display Lyrics**
 When lyrics are displayed above the image, the image will appear 50% darker if both `text_background` and `lyrics` are set to `True`. Note that this feature is not supported for radio stations.
 Recommend `lyrics_font` values: 2, 4, 32, 52, 58, 62, 48, 80, 158, 186, 190, 590. More values can be found at https://app.divoom-gz.com/Device/GetTimeDialFontList (you need ID value)
 ```yaml
pixoo64_media_album_art:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    pixoo:
        lyrics: True
        lyrics_font: 2
        show_text:
            text_background: True
 ```
 ### **Spotify Slider**
 The Spotify slider enhances the PIXOO64 by showing related album art for the current track. To enable this mode, add your Spotify API keys (client ID and client secret) to `apps.yaml` and set `spotify_slide` to `True`.
 ```yaml
pixoo64_media_album_art:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    home_assistant:
        spotify_client_id: # Your Spotify API client ID (needed for Spotify features). Obtain from https://developers.spotify.com.
        spotify_client_secret: # Your Spotify API client secret (needed for Spotify features).
    pixoo:
        spotify_slide: True
 ```
</details>

---

## 🔄 **Fallback Image Handling**

When the script cannot directly obtain the album art for the currently playing track, it activates a **sophisticated fallback system** to ensure your PIXOO64 still displays relevant visual information. Below is a summary of the fallback process:

1. **Original Album Art**  
   - The script first tries to use the album art URL provided by the media player.  
   - This is the primary method and works for most local media and some streaming services.

2. **API Services (Spotify, Discogs, Last.fm, TIDAL)**  
   - If the original album art is unavailable, the script queries these services in the following order:  
     1. Spotify  
     2. Discogs  
     3. Last.fm  
     4. TIDAL  
   - The script uses the first image URL it successfully retrieves.

3. **MusicBrainz**  
   - If API services fail, the script queries the **MusicBrainz database**, an open-source music encyclopedia.  
   - MusicBrainz contains many rare artworks but relies on slower server connections, so retrieval may take time.

4. **AI Image Generation**  
   - If all previous methods fail, the script generates an image using **artificial intelligence** via [pollinations.ai](https://pollinations.ai).  
   - You can choose between two AI models:  
     - `turbo`: Produces vibrant images.  
     - `flux`: Creates artistic and colorful styles.  
   - Note: As this is a free service, it may occasionally be laggy or unavailable.

5. **Black Screen with Text**  
   - As a last resort, the script displays a black screen with the artist and title information of the current track.

This **multi-layered approach** ensures that your PIXOO64 always displays some form of visual content, prioritizing accurate APIs and databases before resorting to AI or text representation.


## 🔑 **API Keys**
To enable advanced features like fetching album art from external services, you’ll need API keys for one or more of the following services. These servers are fast and reliable, making them the most recommended option.
Below are step-by-step guides to help you obtain these keys.

- Use **Spotify**, **Discogs**, **Last.fm**, or **TIDAL** APIs for fast and reliable album art retrieval.  
- If API services fail, the script falls back to **MusicBrainz** or **AI-generated images**.  
- Always store your API keys securely in the `apps.yaml` file.

<details>
<summary><strong> Spotify API Keys</strong></summary>
Obtain your Spotify Client ID and Client Secret from the Spotify Developer Dashboard.

#### **Steps**
1. **Log in to Spotify Developer Dashboard**:  
   Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/login) and log in with your Spotify account.

2. **Create an App**:  
   - Click on the "Create an App" button.  
   - Provide a name and brief description for your app (these fields are mainly for display purposes).

3. **Choose `Web API`**:  
   - From the `Which API/SDKs are you planning to use` section, select `Web API` and press `SAVE`.  
   ![Spotify Web API Selection](https://github.com/user-attachments/assets/d653366f-ac76-4204-a17f-c27b1dc6a051)

4. **Copy Client ID and Client Secret**:  
   - Once your app is created, navigate to the app overview page.  
   - Under the **Basic Information** section, find your Client ID and Client Secret.  
   - Copy these values and store them in the `apps.yaml` file under `spotify_client_id` and `spotify_client_secret`.

</details>
<details>
<summary><strong>Discogs API Keys</strong></summary>

Generate a personal API key from the Discogs website.

#### **Steps**
1. **Log in to Discogs**:  
   Go to the [Discogs website](https://www.discogs.com/) and log in with your account.

2. **Create a Personal Key**:  
   - Navigate to the [Discogs API documentation](https://www.discogs.com/developers/).  
   - Follow the instructions to create a new personal key (no application creation required).

3. **Store the Key**:  
   - Copy the generated key and store it in the `apps.yaml` file under `discogs`.

</details>
<details>
<summary><strong>Last.FM API Key</strong></summary>

Obtain an API key by creating an application on the Last.fm developer site.

#### **Steps**
1. **Log in to Last.fm**:  
   Go to the [Last.fm website](https://www.last.fm/) and log in with your account.

2. **Create an Application**:  
   - Navigate to the [Last.fm API documentation](https://www.last.fm/api).  
   - Follow the instructions to create a new application.  
   - Provide a name and brief description for your application.

3. **Obtain API Key**:  
   - Once your application is created, you’ll receive an API key and secret.  
   - Copy the API key and store it in the `apps.yaml` file under `last.fm`.

</details>
<details>
<summary><strong>Tidal API Keys</strong></summary>

Generate a Client ID and Client Secret from the TIDAL developer dashboard.

#### **Steps**
1. **Create an Application**:  
   Go to the [TIDAL Dashboard](https://developer.tidal.com/dashboard) and log in with your TIDAL account.

2. **Obtain API Key**:  
   - Once your application is created, you’ll be provided with a Client ID and Client Secret.  
   - Copy these values and store them in the `apps.yaml` file under `tidal_client_id` and `tidal_client_secret`.

</details>

---

## 📊 **Sensor Attributes**

The sensor `sensor.pixoo64_media_data` is a virtual entity created in Home Assistant. It stores useful metadata extracted from the album cover art of the currently playing song. This includes details like the artist's name, media title, font color, background color, and more. These attributes enable dynamic visual experiences and automation possibilities based on the music being played.

Below is a detailed breakdown of all the attributes provided by the `sensor.pixoo64_media_data` sensor:

| Attribute                  | Description                                                                                   | Example Value                                                                 |
|----------------------------|-----------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| `artist`                   | The original name of the artist.                                                              | `"Katy Perry"`                                                                |
| `media_title`              | The original title of the media (track or album).                                             | `"OK"`                                                                        |
| `font_color`               | The color of the font displayed on the PIXOO64 screen.                                        | `"#7fff00"`                                                                   |
| `background_color_brightness` | The brightness level of the background color.                                              | `128`                                                                         |
| `background_color`         | The color of the lower part of the background (hexadecimal format).                           | `"#003cb2"`                                                                   |
| `background_color_rgb`     | The RGB values of the background color (lower part).                                          | `[0, 60, 178]`                                                                |
| `color_alternative`        | The most common color in the image (hexadecimal format).                                      | `"#4f7cb7"`                                                                   |
| `color_alternative_rgb`    | The RGB values of the most common color in the image.                                         | `[120, 59, 11]`                                                               |
| `images_in_cache`          | The current number of images stored in memory cache.                                          | `7`                                                                           |
| `image_memory_cache`       | The total memory used by cached images (in KB or MB).                                         | `"114.71 KB"`                                                                 |
| `process_duration`         | The time it takes to process and send the image to the PIXOO64 screen (in seconds).           | `2.49 seconds`                                                                |
| `spotify_frames`           | The number of frames in the Spotify animation (if applicable).                                | `0`                                                                           |
| `pixoo_channel`            | The channel number used by the PIXOO64 device.                                                | `0`                                                                           |
| `image_source`             | The source of the image (e.g., "Original," "Spotify," "AI").                                  | `"Original"`                                                                  |
| `image_url`                | The URL of the image used for the album art (if available).                                   | `"http://homeassistant.local:8123/api/media_player_proxy/..."`                |
| `lyrics`                | Lyrics (if available).                                   | `[]`                |

### **Example Sensor Output**

Here’s an example of the sensor attributes in action:

```yaml
artist: SNIFF'N'THE TEARS
media_title: DRIVER'S SEAT
font_color: "#ff00ff"
background_color_brightness: 64
background_color: "#004f72"
color_alternative_rgb: "#004f72"
background_color_rgb:
  - 0
  - 79
  - 114
color_alternative:
  - 246
  - 167
  - 134
images_in_cache: 15
image_memory_cache: 248.23 KB
process_duration: 3.49 seconds
spotify_frames: 0
pixoo_channel: 0
image_source: Last.FM
image_url: >-
  https://lastfm.freetls.fastly.net/i/u/300x300/1903a3660115ea8295053103419e573c.png
lyrics: []

```

---

## 🛠️ **Troubleshooting**

If you encounter any issues while setting up or using the PIXOO64 Media Album Art Display script, refer to the troubleshooting guide below. These are some of the most common problems and their solutions:

- Always double-check your configuration (`apps.yaml`) for typos or missing parameters.
- Ensure proper power supply (3A charger) and Wi-Fi performance for optimal functionality.
- Use appdaemon logging to diagnose issues with the script or integrations.

<details>
<summary><strong>The PIXOO64 is rebooting</strong></summary>

#### **Possible Causes:**
The PIXOO64 has a known internal issue that after sending approximately 300 +/- commands, it crashes.

#### **Solutions:**
Wait for the PIXOO64 to finish initializing. 
</details>
<details>
<summary><strong>The PIXOO64 Screen is Blank or Not Updating</summary>
   
#### **Possible Causes:**
- The `input_boolean.pixoo64_album_art` toggle is turned off.
- The media player entity ID in the configuration is incorrect.
- The PIXOO64 device is not connected to the same Wi-Fi network as Home Assistant.
- The script is not running

#### **Solutions:**
1. **Check the Toggle Helper:**  
   - Ensure that the `input_boolean.pixoo64_album_art` toggle is turned **ON**. You can check this in Home Assistant under **Developer Tools**.

2. **Verify Media Player Entity ID:**  
   - Double-check the `media_player` entity ID in your `apps.yaml` file. It should match the entity ID of your media player in Home Assistant.

3. **Check Network Connectivity:**  
   - Ensure the PIXOO64 device is connected to the same Wi-Fi network as your Home Assistant instance. 

4. **Check Appdaemon Logs**
   - The log can contains reason why the script is fail.

4. **Restart AppDaemon:**  
   - Restart the AppDaemon add-on in Home Assistant to ensure the script is running correctly.

</details>
<details>
<summary><strong>Album Art is Not Displaying</strong></summary>
   
#### **Possible Causes:**
- The media player does not provide album art metadata.
- The media player does not provide artist / track metadata.
- API keys for services like Spotify, Discogs, or Last.fm are missing or incorrect.
- The fallback system (MusicBrainz, AI) is not configured properly.

#### **Solutions:**
1. **Check Metadata Support:**  
   - Verify that your media player provides album art metadata. Some players (e.g., radio streams) may not include album art.

2. **Verify API Keys:**  
   - Ensure that all required API keys from the servies you choose (Spotify, Discogs, Last.fm, TIDAL) are correctly entered in the `apps.yaml` file. Refer to the [API Keys](#api-keys) section for instructions on obtaining these keys. 

3. **Enable Fallback Options:**  
   - If album art is unavailable, ensure that fallback options like MusicBrainz or AI image generation are enabled in the configuration:
     ```yaml
     musicbrainz: True
     ai_fallback: "turbo"
     ```

4. **Test with Different Tracks:**  
   - Try playing tracks from different sources (e.g., Spotify, local files, Radio statations) to see if the issue persists.

</details>
<details>
<summary><strong>AI-Generated Images Are Not Appearing</strong></summary>
   
#### **Possible Causes:**
- The AI service (`pollinations.ai`) is unavailable or laggy.
- The `ai_fallback` parameter is not set correctly.

#### **Solutions:**
1. **Check AI Service Status:**  
   - Visit [pollinations.ai](https://pollinations.ai) to verify that the service is operational. Note that this is a free service and may occasionally be slow or unavailable.

2. **Verify Configuration:**  
   - Ensure that the `ai_fallback` parameter is set to either `"flux"` or `"turbo"` in your `apps.yaml` file:
     ```yaml
     ai_fallback: "turbo"
     ```

3. **Enable Force AI (Optional):**  
   - If you want to test AI-generated images exclusively, set `force_ai` to `True`:
     ```yaml
     force_ai: True
     ```

</details>
<details>
<summary><strong>RGB Light Sync Is Not Working</summary>
   
#### **Possible Causes:**
- The RGB light entity ID in the configuration is incorrect.

#### **Solutions:**
1. **Verify Light Entity ID:**  
   - Double-check the `light` parameter in your `apps.yaml` file. It should match the entity ID of your RGB light in Home Assistant:
     ```yaml
     light: "light.living_room"
     ```

2. **Test with Different Images:**  
   - Play tracks with colorful album art to ensure the RGB light sync works as expected.


</details>
<details>
<summary><strong>Script Performance Issues</strong></summary>
   
#### **Possible Causes:**
- Insufficient memory due to a large number of cached images.
- Slow Wi-Fi network or power supply issues.

#### **Solutions:**
1. **Reduce Image Cache Size:**  
   - Lower the `images_cache` value in your `apps.yaml` file to reduce memory usage:
     ```yaml
     images_cache: 10
     ```

2. **Optimize Power Supply:**  
   - Use a USB charger with an output of **3A** for optimal performance. Limit screen brightness to no more than **90%** if using a lower-voltage charger.

3. **Reboot Wi-Fi Router:**  
   - If the PIXOO64 responds slowly, reboot your Wi-Fi router to improve network performance.
  

</details>
<details>
<summary><strong>Sensor Data is Missing or Incorrect</strong></summary>
   
#### **Possible Causes:**
- The `sensor.pixoo64_media_data` sensor is not updating correctly.
- There is an issue with the media player or AppDaemon script.

#### **Solutions:**
1. **Check Sensor State:**  
   - Verify that the `sensor.pixoo64_media_data` sensor exists and is updating in Home Assistant. You can view its attributes in the Developer Tools.

2. **Restart AppDaemon:**  
   - Restart the AppDaemon add-on to refresh the script and sensor data.

</details>
<details>
<summary><strong>Lyrics Are Not Displaying</strong></summary>
   Note: Radio stations does not support lyrics.
   
#### **Possible Causes:**
- The track does not have synchronized lyrics that can be found on database.
- Media Player not support needed metadata.
- The `lyrics` parameter is not enabled in the configuration

#### **Solutions:**
1. **Verify Media Player Support:**  
   - Ensure that your media player supports synchronized lyrics (media player contains the attribues: `media_duration`, `media_atrist` and `media_title`).

2. **Enable Lyrics in Configuration:**  
   - Set the `lyrics` parameter to `True` in your `apps.yaml` file:
     ```yaml
     lyrics: True
     ```

3. **Check Font Settings:**  
   - Ensure that the `lyrics_font` parameter is set to a valid font ID.

</details>

---
### **⚠️ Disclaimer**

*This software is **not** an official product from Divoom. As a result, Divoom bears **no responsibility** for any damages or issues arising from the use of this script. Additionally, Divoom does **not** offer end-user support for this script. Please utilize it at your own risk.*
