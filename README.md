# PIXOO64 Media Album Art Display

This AppDaemon script for Home Assistant enhances your music experience by displaying relevant information on your DIVOOM PIXOO64 screen. When music plays, the script automatically fetches and displays the album art of the current track. If album art isn't available, it can generate an image using AI, ensuring a visually engaging experience. The script also supports synchronized lyrics, artist and track info, and can even sync an RGB light's color to match the album art.

## Examples

![PIXOO_album_gallery](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71348538-2422-47e3-ac3d-aa1d7329333c)

Here's a summary of the main features:

*   **Dynamic Album Art:** Displays album art on your PIXOO64 when a track starts playing, scaling and preparing the image for the 64x64 pixel display.
*   **Intelligent Fallback:** If album art is unavailable, the script tries to find it online (Spotify, Discogs, Last.fm, MusicBrainz). If all else fails, it generates a unique image using AI.
*   **Lyrics Sync:** Fetches and displays synchronized lyrics for supported media sources, advancing as the song plays. (Note: Not all sources support lyrics.)
*   **Real-Time Info:** Displays the current time, artist's name, and track title on the screen.
*   **Spotify Album Slide:** Shows a slideshow of album covers related to the current track, using the Spotify API.
*   **Dynamic Lighting:** Synchronizes an RGB light's color with the album art's primary color.
*   **Special Mode:** An optional display mode combining album art with a clock, day, and temperature, plus artist/title info.

This script aims to create a seamless and enhanced experience by integrating your PIXOO64 with your music setup, providing visual and contextual elements.

## Key Features

*   **Automatic Album Art Display:** Shows album art on your PIXOO64 when music plays.
*   **Lyrics Display:** Option to display synchronized lyrics.
*   **AI Image Fallback:** Generates alternative images when album art isn't found.
*   **Cropped Images:** Removes borders from album art for better display.
*   **Synced Lights:** Matches any connected RGB light color to the album art's dominant color.
*   **Text Information:** Displays artist and track titles, and a clock.
*   **Spotify Album Slide:** Shows album art slideshows for the playing title from Spotify.
*   **Wide Compatibility:** Supports various media players and services.

## Prerequisites

1.  [DIVOOM PIXOO64](https://www.aliexpress.com/item/1005003116676867.html)
2.  Home Assistant (with add-on functionality)
3.  AppDaemon (Home Assistant add-on)

## Installation

This section will guide you through installing and setting up the PIXOO64 Media Album Art Display script. Please follow these steps carefully.

1.  **Install AppDaemon:**
    *   Open Home Assistant in your web browser.
    *   Navigate to **Settings** > **Add-ons**.
    *   Click the **Add-on Store** button (lower right corner). 
    *   Search for "AppDaemon" and install it.
    *   After installation, start the AppDaemon add-on.

2.  **Install Required Python Packages:**
    *   Go to the AppDaemon add-on configuration page (found in the Add-ons page where you started AppDaemon). 
    *   Locate the **Python packages** section.
    *   Add `pillow` to the list. This package is **required** for image processing.
    *   Optionally, add `python-bidi`. This is required to correctly display right-to-left text (e.g., Arabic, Hebrew). 
    *   Save the changes. This will install the necessary Python libraries.

    ```yaml
    python_packages:
        - pillow
        - python-bidi  # Optional: Required for RTL text support (e.g. Arabic, Hebrew)
    ```

3.  **Create a Toggle Helper:**
    *   In Home Assistant, go to **Settings** > **Devices & Services**.
    *   Click on **Helpers**.
    *   Click the **Create Helper** button (lower right corner).
    *   Select **Toggle** and give it an appropriate name (e.g., `PIXOO64 Album Art`).
    *   Note the `entity_id` of this helper (e.g., `input_boolean.pixoo64_album_art`); you will need it later for configuration.
        *   **Important:** Ensure this new helper entity is toggled **ON**. If it's off, the script will not run. This toggle allows you to easily disable the script when needed. 

4.  **Download the Script:**
    You can install the script using either **HACS** (Home Assistant Community Store, recommended) or by manually downloading the Python file.

**HACS (Recommended):**
> [!NOTE]
> When installing through HACS, you **MUST** manually move all files from `/addon_configs/a0d7b954_appdaemon/apps/` to `/homeassistant/appdaemon/apps/`.
> HACS places files in the `/homeassistant` directory (that can also maped as `/config` directory), while AppDaemon expects them in the `/addon_configs` directory.
> Note that when you are using the SAMBA SHARE add-on, Windows File Explorer will show the directory as `/config`, meaning that files should be moved to `/config/appdaemon/apps/`.
>
> Open `/addon_configs/a0d7b954_appdaemon/appdaemon.yaml` to configure it (add `app_dir: /homeassistant/appdaemon/apps/` line under `appdaemon:`).
>
> Do not remove any lines from the file, just add the new line and update the Latitude and Longitude values (the units that represent the coordinates at geographic coordinate system) to your own - https://www.latlong.net/): 
```yaml
appdaemon:
   app_dir: /homeassistant/appdaemon/apps/ # DO NOT CHANGE THIS LINE, even if the files located at /config directory (when using Samba Share addon)
   latitude: 51.507351 # Update value from https://www.latlong.net
   longitude: -0.127758 # Update value from https://www.latlong.net
```
   *   If you don't have HACS installed, follow the instructions on the [HACS's GitHub page](https://hacs.xyz/) to install it.
   *   After HACS is set up, go to the HACS page in Home Assistant.
   *   **If "AppDaemon" repositories are not found**: You need to enable AppDaemon apps discovery and tracking in HACS settings. Go to `Settings` > `Integrations` > `HACS` > `Configure` and enable `AppDaemon apps discovery & tracking`.
   *   Click on **Custom Repositories** and add `https://github.com/idodov/pixoo64-media-album-art` as an **AppDaemon** repository.
   *   Search for and download `PIXOO64 Media Album Art` in HACS.

   **Manual Download:**

   *   Alternatively, you can download the Python script directly from the GitHub repository:
        [https://github.com/idodov/pixoo64-media-album-art/blob/main/apps/pixoo64_media_album_art/pixoo64_media_album_art.py](https://github.com/idodov/pixoo64-media-album-art/blob/main/apps/pixoo64_media_album_art/pixoo64_media_album_art.py)
   *   Place this file into the directory `/addon_configs/a0d7b954_appdaemon/apps`.
   *   **Note:** With this method, you will not receive automatic updates. 

5.  **Configure AppDaemon:**
    *   You will need to modify the `apps.yaml` file to activate the script.
    *   This file is typically located in the `/appdaemon/apps` directory that you added in the previous step.
    *   You can use either a **Basic Configuration** for a quick start, or a **Full Configuration** for all features. 

## Basic Configuration:

For a minimal setup, add the following to your `/appdaemon/apps/apps.yaml` file, adjusting the `ha_url`, `media_player`, and `url` parameters to match your setup.  Note that when using the basic configuration the helper name that's need to be toggle on is `input_boolean.pixoo64_album_art`
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
 If you have more than one Pixcoo64 screen, you can add it by adding the code again and **changing the first line's name**. For example:
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
## Full Configuration:

For all features, add this to your `/appdaemon/apps/apps.yaml` file. You'll need to adjust the values to match your Home Assistant setup and PIXOO64's IP address. See the next section for parameter details.
```yaml
pixoo64_media_album_art:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    home_assistant:
        ha_url: "http://homeassistant.local:8123"   # Your Home Assistant URL.
        media_player: "media_player.living_room"    # The entity ID of your media player.
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
        tidal_client_secret: False                  # Your TIDAL client secret
        last.fm: False                              # Your Last.fm API key. Obtain from https://www.last.fm/api/account/create.
        discogs: False                              # Your Discogs API key. Obtain from https://www.discogs.com/settings/developers.
    pixoo:
        url: "192.168.86.21"                        # The IP address of your Pixoo64 device.
        full_control: True                          # If True, the script will control the Pixoo64's on/off state in sync with the media player's play/pause.
        contrast: True                              # If True, applies a 50% contrast filter to the images displayed on the Pixoo.
        colors: False                               # If True, enhanced colors
        kernel: False                               # If True, add embos/edge effect
        sharpness: False                            # If True, add sharpness efeect
        special_mode: False                         # Show day, time and temperature above in upper bar.
        info: False                                 # Show information while fallback
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
        only_at_night: False                        # Runs only at night hours
```

With these steps completed, you have installed and set up the script and can now configure it to fit your needs.

| Parameter | Description | Example Values |
| --- | --- | --- |
| `ha_url` | Home Assistant URL | `"http://homeassistant.local:8123"` |
| `media_player` | Media player entity ID | `"media_player.era300"` |
| `toggle` | Boolean sensor to control script execution (Optional) | `"input_boolean.pixoo64_album_art"` |
| `pixoo_sensor` | Sensor to store media data (Optional) | `"sensor.pixoo64_media_data"` |
| `light` | RGB light entity ID (if any) (Optional) | `False` or `light.rgb_light` |
| `ai_fallback` | Create alternative album art using AI. Options are `flux` or `turbo` | `turbo` |
| `temperature_sensor` | HomeAssistant Temperature sensor name instead of the Divoom weather | `sensor.temperature` |
| `musicbrainz` | Search for album art in MusicBrainz | `True` |
| `spotify_client_id` | Spotify Client ID. Use `False` or the actual key | `False` or `KEY` |
| `spotify_client_secret` | Spotify Client Secret. Use `False` or the actual key | `False` or `KEY` |
| `tidal_client_id` | Your TIDAL API client ID. | `False` or `key` |
| `tidal_client_secret` | Your TIDAL client secret | `False` or `key` |
| `last.fm` | Last.fm key. Use `False` or the actual key | `False` or `KEY` |
| `Discogs` | Discogs Personal token. Use `False` or the actual key | `False` or `KEY` |
| `url` | Pixoo device URL | `192.168.86.21` |
| `full_control` | Control display on/off with play/pause | `True` |
| `contrast` | Apply a 50% contrast filter | `True` |
| `sharpness` | Apply sharpness filter | `True` |
| `colors` | Enhanced colors | `True` |
| `special_mode` | Show day, time and temperature in upper bar | `False` |
| `clock` | Show a clock in the top corner | `False` |
| `clock_align` | Align the clock to `Left` or `Right` | `Left` |
| `tv_icon` | Show TV art when playing sound from TV | `True` |
| `lyrics` | Display synchronized lyrics | `True` |
| `lyrics_font` | Font to display the lyrics. More values can be found here: [DIVOOM PIXOO64 FONTS JSON](https://app.divoom-gz.com/Device/GetTimeDialFontList) (you need ID value) | Recommended values: `2`, `4`, `32`, `52`, `58`, `62`, `158`, `186`, `190`, `590` |
| `limit_colors` | Reduces the number of colors in the picture from 4 to 256, or set it to `False` for original colors | `4` to `256` or `False` |
| `spotify_slide` | Shows album art slideshows for the playing title from the Spotify API. To enable the slider, you must integrate Spotify API support by providing API keys for the client ID and client secret. In this mode, the clock, title, and crop features will be disabled. |  `False` or `True` |
| `images_cache` | The number of processed images to keep in memory. Use wisely to avoid memory issues (each image is approximately 17KB) | `1` to `500` |
| `show_text - enabled` | Show media info with the image | `False` |
| `show_text - clean_title` | Remove "Remaster" labels, track numbers, and file extensions from the title if any | `True` |
| `show_text - text_background` | Change background of the text area (also supports lyrics mode) | `True` |
| `special_mode_spotify_slider` | Use Spotify animation when `special_mode` is on and `show_text` is enabled | `False` |
| `crop_borders - enabled` | Crop image borders if present | `True` |
| `crop_borders - extra` | Apply enhanced border cropping | `True` |
| `wled_ip` | WLED IP Adress | `192.168.86.55` |
| `brightness` | WLED Brightness | `0` - `255` |
| `effect` | WLED Effect ID - https://kno.wled.ge/features/effects/ | `0` - `186` |
| `effect_speed` | WLED Effect Speed | `0` - `255` |
| `effect_intensity` | WLED Effect Intensity | `0` - `255` |
| `pallete` | WLED Pallete ID - https://kno.wled.ge/features/palettes/ | `0` - `70` |
| `only_at_night` | WLED (and RGB) automation runs only during night hours | `False` |

> [!NOTE]
> ### `light`
> The light feature is a built-in automation that sends a ‘turn on’ command with RGB values corresponding to the most dominant color in the image. If the image is black, white, or gray, the automation will select a soft random color. You can add more then one light by using the syntax:
> ```yaml
> pixoo64_media_album_art:
>   module: pixoo64_media_album_art
>   class: Pixoo64_Media_Album_Art
>   home_assistant:
>      light:
>        - "light.living_room"
>        - "light.bed_room"
> ```
>
> ### `WLED light`
> The WLED feature is a built-in automation specifically designed for WLED lights. It sends a ‘turn on’ command with 3 RGB values that correspond to the most dominant colors in the image. If the image is black, white, or gray, the automation will select a soft, random color. You can control the brightness, Effect ID (see: https://kno.wled.ge/features/effects/), effect speed, palette, and effect intensity. You also have the option to configure the automation to run only during nighttime hours.
> 
> ### `crop_borders`
> Given the Pixoo screen’s 64x64 pixel size, it is highly recommended to utilize the crop feature. Many album cover arts come with borders, occasionally wide ones, which can distort the display of the cover art on the screen. To rectify this, the script ensures the removal of the picture frame border.
>
> | Original | Crop | Extra |
> |---|---|---|
> | ![cover2](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71fda47e-f4fe-4142-9303-16d95d2c109e) | ![cover2_crop](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/ad32fb20-7b94-4795-a1af-16148dac473f) | ![kb-crop_extra](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/4e6bec64-0fa3-4bb3-a863-9e1ace780b58) |
> | ![psb-original](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/beb0d74c-5a27-4ad8-b7a8-f11f6ae8d3ea) | ![psb-crop](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/efc4f44a-4c7d-4aca-b1bf-a158b252b26d) | ![psb-crop_extra](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/b25cc2e7-aa22-4e73-9c7a-b30ea4ec73fb) |
>
> ### Display Lyrics
> For accessibility, when lyrics are available and displayed above the image, the image will appear 50% darker when `text_background` and `lyrics` are set to `True` (in `apps.yaml`). The lyrics feature is not supported for radio stations.
>
> ### Spotify Slider
> The Spotify album slide function enhances the Pixoo64 by searching for album art related to the current track, emphasizing the artist. To enable this mode, add your Spotify API keys (client ID and client secret) to `apps.yaml` and set `spotify_slide` to `True`.
____________
## You’re all set!
**Make sure that `input_boolean.pixoo64_album_art` is turned `on`. The next time you play a track, the album cover art will be displayed, and all the usable picture data will be stored in a new sensor.**

![animated-g](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/2a716425-dd65-429c-be0f-13acf862cb10)
_____________

## Fallback Image Handling

When the script cannot directly obtain the album art for the currently playing track, it activates a sophisticated fallback system to ensure that your PIXOO64 still displays relevant visual information. The script attempts several methods, in the following order, to find an image:

1.  **Original Album Art:** The script first tries to use the album art URL provided by the media player. This is the primary and most direct method, and is usually successful for most local media and some streaming services.

2.  **API Services (Spotify, Discogs, Last.fm, TIDAL):** If the original album art is unavailable, the script attempts to find album art by querying these services using their respective APIs.
    *   The script tries these services in the order listed above (Spotify, Discogs, Last.fm, TIDAL), using the first image URL it successfully retrieves.

3.  **MusicBrainz:** If API services fail, the script queries the MusicBrainz database, an open-source music encyclopedia. MusicBrainz is often a good source of album art URLs, especially for less common tracks.
    *   MusicBrainz is an open-source database containing URLs for album art. Although the database is extensive and includes many rare artworks and doesn't require API keys, it relies on very slow server connections. This means that often the album art may not be retrieved in a timely manner while the track is playing.

4.  **AI Image Generation:** If all previous methods fail, the script resorts to generating an image with artificial intelligence using [pollinations.ai](https://pollinations.ai).
    *   The script generates a unique image based on the artist and track title, creating an abstract interpretation if album art is truly unavailable, ensuring a visual representation even with less common tracks.
    *   In this scenario, the script will attempt to generate an alternative version of the album art using generative AI. This option will trigger only if the Spotify API fails (or is unavailable) and/or no album art is found, or there is a timeout from the MusicBrainz service. Be aware that as it is a free AI generative service, it may also be laggy or sometimes unavailable.
        *   You can select `flux` or `turbo` as an AI model. The `turbo` model tends to produce more vibrant images, while `flux` provides a more artistic and colorful style.

5.  **Black Screen with Text:** As a final resort, if the script is unable to generate or fetch an image, it will display a black screen and the artist and title information of the current track on the PIXOO64.

This multi-layered approach ensures that your PIXOO64 displays some form of visual content in virtually every scenario. The script will always try to find an image through the more accurate APIs and online databases before generating one using AI or falling back to a simple text representation.

## API KEYS
**Getting the Album API**: This is the most recommended option because servers are fast and reliable. You can choose one or more options. To use this method, you'll need at least one of the keys. Instructions on how to obtain them are provided beyond this text.
   - **Spotify**: the Client ID and the Client Secret
   - **Discogs**: Personal API Key
   - **Last.FM**: API Key
   - **TIDAL**:  the Client ID and the Client Secret

## Guide to help you get your Spotify Client ID and Client Secret from the developer site:

1.  **Log in to Spotify Developer Dashboard**: Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/login) and log in with your Spotify account.

2.  **Create an App**: Click on the "Create an App" button. You'll need to provide a name and a brief description for your app. These fields are mainly for display purposes, so you can keep them simple.

3. **Choose `Web API`** from the `Which API/SDKs are you planning to use` section and press `SAVE`.
    ![{22F7F6C8-CA87-4146-A035-B0BCEC99DF3B}](https://github.com/user-attachments/assets/d653366f-ac76-4204-a17f-c27b1dc6a051)

4.  **Copy Client ID and Client Secret**: Once your app is created, you'll be taken to the app overview page. At the Basic Information section you'll find your Client ID and Client Secret. Copy these values and store them in the `apps.yaml` file under `spotify_client_id` and `spotify_client_secret`.

## Guide to help you get your Discogs API key:

1.  **Log in to Discogs**: Go to the [Discogs website](https://www.discogs.com/) and log in with your account.

2.  **Create a Personal Key**: Navigate to the [Discogs API documentation](https://www.discogs.com/developers/) and follow the instructions to create a new personal key. You don't need to create an application.
3. Copy the value and store it in the `apps.yaml` file under `discogs`.

## Guide to help you get your Last.fm API key:

1.  **Log in to Last.fm**: Go to the [Last.fm website](https://www.last.fm/) and log in with your account.

2.  **Create an Application**: Navigate to the [Last.fm API documentation](https://www.last.fm/api) and follow the instructions to create a new application. You'll need to provide a name and a brief description for your application.

3.  **Obtain API Key**: Once your application is created, you'll be provided with an API key and a secret. You'll need just the API KEY.
4. Copy the value and store it in the `apps.yaml` file under `last.fm`.

## Guide to help you get your TIDAL API key:

1.  **Create an Application**: Go to the [TIDAL Dashboard](https://developer.tidal.com/dashboard) and log in with your TIDAL account.
2.  **Obtain API Key**: Once your application is created, you'll be provided with an API key and a secret.
3. Copy the values and store them in the `apps.yaml` file under `tidal_client_id` and `tidal_client_secret`.


## Sensor Attributes
The sensor `sensor.pixoo64_media_data` is a virtual entity created in Home Assistant. It’s designed to store useful picture data from the album cover art of the currently playing song. This includes the artist’s name, the title of the media, and color information such as the color of the font and the background. This sensor allows for dynamic visual experiences and automation possibilities based on the music being played.

| Attribute | Description |
|---|---|
| `artist` | The original name of the artist |
| `media_title` | The original title of the media |
| `font_color` | The color of the font |
| `background_color_brightness` | The brightness level of the background color |
| `background_color` | The color of the lower part in background |
| `background_color_rgb` | The RGB values of the background color (lower part) |
| `color_alternative` |  The most common color of the background |
| `color_alternative_rgb` | The RGB values of the most common color of the background |
| `images_in_cache` | Current number of images in memory cache |
| `image_memory_cache` | Memory used in KB or MB | 
| `process_duration` | The time it takes to send the image to the screen from the time the player starts |
| `spotify_frames` | Number of frames in animation |

Here’s an example of the sensor attributes:

<pre>
<code>
artist: Katy Perry
media_title: OK
font_color: "#7fff00"
background_color_brightness: 128
background_color: "#003cb2"
color_alternative_rgb: "#4f7cb7"
background_color_rgb:
  - 0
  - 60
  - 178
color_alternative:
  - 120
  - 59
  - 11
images_in_cache: 7
image_memory_cache: 114.71 KB
process_duration: 2.49 seconds
spotify_frames: 0
</code>
</pre>

__________
> [!NOTE]
> While experimenting with the device, you may notice occasional freezes. These could potentially be due to power issues. To address this, it’s suggested to use a USB charger with an output of 3A for optimal performance. If you’re using a charger with a lower voltage (2A, which is the minimum required), it’s advisable to limit the screen brightness to no more than 90%.
>
> Also, at times, an overloaded Wi-Fi network might result in the Pixoo64 responding slowly. Most often, rebooting the Wi-Fi network or the router rectifies this problem. 

**Disclaimer:**
*This software is **not** an official product from Divoom. As a result, Divoom bears **no responsibility** for any damages or issues arising from the use of this script. Additionally, Divoom does **not** offer end-user support for this script. Please utilize it at your own risk.*
