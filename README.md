# PIXOO64 Media Album Art Display

This AppDaemon script for Home Assistant enhances your music experience by displaying relevant information on your DIVOOM PIXOO64 screen. When you play music, this script automatically fetches and displays the album art of the currently playing track. If the album art is not available, it can generate an image using AI, ensuring a visually engaging experience. Additionally, the script supports displaying synchronized lyrics, artist and track information, and can even synchronize an RGB light's color to match the album art.

## Examples
![PIXOO_album_gallery](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71348538-2422-47e3-ac3d-aa1d7329333c)
 
Here's a breakdown of the main functionalities:

*   **Dynamic Album Art Display:** When a track starts playing, the script queries your media player to find the associated album art and displays it on your PIXOO64. The image is scaled and prepared for the PIXOO64's 64x64 pixel display.
*   **Intelligent Fallback System:** If album art is not directly available (e.g., from some streaming services), the script attempts to retrieve it using several fallback methods. This includes searching online databases (like Spotify, Discogs, Last.fm, MusicBrainz) and, if all else fails, generating a unique image using an AI art generator.
*   **Lyrics Synchronization:** For supported media sources, the script can fetch and display synchronized lyrics. The lyrics are displayed in a readable format, and the display advances as the song progresses. (Note: This feature is not available for all media sources.)
*   **Real-Time Information Display:** In addition to album art and lyrics, the script displays the current time, the artist's name and the title of the current track on the screen, allowing you to view track information quickly.
*  **Spotify Album Slide**: This feature allows you to experience a slideshow of different album covers related to the current track. It uses the Spotify API to search for relevant albums and cycles through them on your PIXOO64.
*   **Dynamic Lighting:**  If you have an RGB light set up in your Home Assistant, this script can synchronize the light's color with the primary color of the displayed album art, adding an extra layer of immersion to your listening experience.
* **Special Mode**:  An optional display mode that combines the album art with a clock, current day and the temperature and can also display the artist name and the title.

By combining these features, the script aims to create a seamless and enhanced experience for users who want to integrate their PIXOO64 with their music playback setup. It not only visualizes the music but provides additional contextual and visual elements.

## Key Features

*   **Automatic Album Art Display:** Shows album art on your PIXOO64 when music plays.
*   **Lyrics Display:** Option to display synchronized lyrics.
*   **AI Image Fallback:** Generates alternative images when album art isn't found.
*   **Cropped Images:** Removes borders from album art for better display.
*   **Synced Lights:** Matches any connected RGB light color to the album art's dominant color.
*   **Text Information:** Displays artist and track titles, clock.
*  **Spotify Album Slide**: Shows album arts for the playing title, taken from Spotify.
*   **Wide Compatibility:** Supports various media players and services.


## Prerequisites
1. [DIVOOM PIXOO64](https://www.aliexpress.com/item/1005003116676867.html)
2. Home Assistant (with add-on functionality)
3. AppDaemon (Home Assistant add-on)

## Installation

This section will guide you through installing and setting up the PIXOO64 Media Album Art Display script. Please follow these steps carefully.

1.  **Install AppDaemon:**
    *   Open Home Assistant in your web browser.
    *   Navigate to "Settings" -> "Add-ons."
    *   Click on the "Add-on Store" button (lower right).
    *   Search for "AppDaemon" and install it.
    *   After installation, start the AppDaemon add-on.

2.  **Install Required Python Packages:**
    *   Go to the AppDaemon add-on configuration page (found in the same add-ons page where you started AppDaemon).
    *   Locate the section for "Python packages."
    *   Add `pillow` to the list. It's mandatory for image processing.
    *   Optionally add `python-bidi`. This is required if you need to correctly display right-to-left text, such as Arabic or Hebrew.
    *   Save the changes. This will install the necessary Python libraries.
        <pre>
        <code>
        python_packages:
          - pillow
          - python-bidi  # Optional: Required for RTL text support (e.g. Arabic, Hebrew)
        </code>
        </pre>

3.  **Create a Toggle Helper:**
    *   In Home Assistant, go to "Settings" -> "Devices & Services".
    *   Click on "Helpers".
    *   Click on the "Create Helper" button (lower right).
    *   Select "Toggle" and give it an appropriate name (e.g., `PIXOO64 Album Art`).
    *   Note the `entity_id` of this helper (e.g., `input_boolean.pixoo64_album_art`); you will need it later for configuration.
        Make sure that the new helper entity is toggled on. If not, the script won't work! The reason for this is that sometimes you may want to disable the script, so to do that, just toggle off the helper.
       

4.  **Download the Script:**
    *   You can install the script either through HACS (Home Assistant Community Store, which is the recommended method) or by manually downloading the Python file.

        *   **HACS (Recommended):**
            *   If you don't have HACS installed, follow the instructions on [HACS's GitHub page](https://hacs.xyz/) to install it.
            *   After HACS is set up, go to the HACS page in Home Assistant.
            *   **If "AppDaemon" type repositories are not found, you will need to enable AppDaemon apps discovery & tracking in the HACS settings**. Navigate to `Settings` -> `Integrations` -> `HACS` -> `Configure` and enable `AppDaemon apps discovery & tracking`.
            *   Click on "Custom Repositories" and add `https://github.com/idodov/pixoo64-media-album-art` as an "AppDaemon" repository.
            *   Search for and download `PIXOO64 Media Album Art` in HACS.
            *   **Important:** After installing through HACS, you **MUST** manually transfer all the files from `/addon_configs/a0d7b954_appdaemon/apps/` to `/homeassistant/appdaemon/apps/`. This step is necessary because HACS places files in the `/addon_configs` directory, while AppDaemon expects them in the `/homeassistant` directory.
            * Open `/addon_configs/a0d7b954_appdaemon/appdaemon.yaml` to configute it (add `app_dir` line under `appdaemon:`). Do not remove any lines from the file, just add the new line:
            <pre>
            <code>
               appdaemon:
                   app_dir: /homeassistant/appdaemon/apps/
             </code>
             </pre>


        *   **Manual Download:**
            *   Alternatively, you can download the Python script directly from the GitHub repository:
                [https://github.com/idodov/pixoo64-media-album-art/blob/main/apps/pixoo64_media_album_art/pixoo64_media_album_art.py](https://github.com/idodov/pixoo64-media-album-art/blob/main/apps/pixoo64_media_album_art/pixoo64_media_album_art.py)
            *   Place this file into the directory `/addon_configs/a0d7b954_appdaemon/apps`
            *   Note that in this method you won't get updates.

5.  **Configure AppDaemon:**

    *   You will need to modify the `apps.yaml` file to activate the script.
    *   This file is typically located in the `/appdaemon/apps` directory that you added in the previous step.
    *   You can use a **Basic Configuration** for a quick start, or a **Full Configuration** for all features.

        *   **Basic Configuration:**
            *   For a minimal setup, add the following to your `/appdaemon/apps/apps.yaml` file, adjusting the `ha_url`, `media_player`, and `url` parameters to match your setup.  Note that when using the basic configuration the helper name that's need to be toggle on is `input_boolean.pixoo64_album_art`
            <pre>
             <code>
            pixoo64_media_album_art:
                module: pixoo64_media_album_art
                class: Pixoo64_Media_Album_Art
                home_assistant:
                    ha_url: "http://homeassistant.local:8123"   # Your Home Assistant URL.
                    media_player: "media_player.living_room"    # The entity ID of your media player.
                pixoo:
                    url: "192.168.86.21"                        # The IP address of your Pixoo64 device.
            </code>
            </pre>
              
            *   If you have more than one Pixcoo64 screen, you can add it by adding the code again and **changing the first line's name**. For example:
            <pre>
             <code>
            pixoo64_media_album_art_2:
                module: pixoo64_media_album_art
                class: Pixoo64_Media_Album_Art
                home_assistant:
                    ha_url: "http://homeassistant.local:8123"   # Your Home Assistant URL.
                    media_player: "media_player.kitchen"        # The entity ID of your media player.
                pixoo:
                    url: "192.168.86.22"                        # The IP address of your Pixoo64 device.
            </code>
            </pre>

        *   **Full Configuration:**
            *   For all features, add this to your `/appdaemon/apps/apps.yaml` file. You'll need to adjust the values to match your Home Assistant setup and PIXOO64's IP address. See the next section for parameter details.
            <pre>
            <code>
                pixoo64_media_album_art:
                    module: pixoo64_media_album_art
                    class: Pixoo64_Media_Album_Art
                    home_assistant:
                        ha_url: "http://homeassistant.local:8123"  # Your Home Assistant URL
                        media_player: "media_player.your_player"   # Your media player entity ID
                        toggle: "input_boolean.pixoo64_album_art"  # The toggle you created
                        pixoo_sensor: "sensor.pixoo64_media_data"  # (Optional) Sensor to store extracted data
                        light: "light.your_rgb_light"  # (Optional) RGB light entity ID
                        ai_fallback: "turbo"  # 'flux' or 'turbo' for AI image generation
                        force_ai: False # If true, only AI images will show
                        musicbrainz: True # Search MusicBrainz for missing album art
                        spotify_client_id: False  # Your Spotify API client ID (See below for instructions)
                        spotify_client_secret: False # Your Spotify API client Secret (See below for instructions)
                        last.fm: False  # Your Last.fm API key (See below for instructions)
                        discogs: False   # Your Discogs API key (See below for instructions)
                    pixoo:
                        url: "192.168.1.100" # Your PIXOO64 IP address
                        full_control: True  # Control display on/off based on playback
                        contrast: True  # Apply 50% contrast to the image
                        special_mode: False # Show day, time and temperature in upper bar
                        clock: True   # Show a clock
                        clock_align: "Right"  # "Left" or "Right"
                        tv_icon: True   # Show a TV icon when audio is from a TV source
                        lyrics: False # Show Lyrics when available
                        lyrics_font: 2 # Lyrics font ID, look up from https://app.divoom-gz.com/Device/GetTimeDialFontList (you need ID value)
                        limit_colors: False  # reduce the number of colors in the picture
                        spotify_slide: False # Use Spotify's album art slider, disables clock and title, need spotify keys
                        images_cache: 25 # Number of images stored in memory
                        show_text:
                            enabled: False # Enable / Disable text below image
                            clean_title: True # Remove "Remaster" labels, track numbers, and file extensions from the title if any
                            text_background: True # Change background of text area
                            special_mode_spotify_slider: False #Use spotify animation when special_mode is on
                        crop_borders:
                            enabled: True # Crop image borders if present
                            extra: True # Apply enhanced border cropping
             </code>
             </pre>

    *  Note that after changing `apps.yaml`, you don't need to restart AppDaemon.

With these steps completed, you have installed and set up the script and can now configure it to fit your needs.

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
| `special_mode` | Show day, time and temperature in upper bar | `False` |
| `clock` | Show a clock in the top corner | `False` |
| `clock_align` | Align the clock to `Left` or `Right` | `Left` |
| `tv_icon` | Show TV art when playing sound from TV | `True` |
| `lyrics` | Display sync lyrics | `True` |
| `lyrics_font` | Font to display the lyrics. More values can be found here: [DIVOOM PIXOO64 FONTS JSON](https://app.divoom-gz.com/Device/GetTimeDialFontList) (you need ID value) | Recommend values: `2`, `4`, `32`, `52`, `58`, `62`, `158`, `186`, `190`, `590` |
| `limit_colors` | Reduces the number of colors in the picture from 4 to 256, or set it to False for original colors | `4` to `256` or `False` |
| `spotify_slide` | Shows album arts for the playing title taken from Spotify API. To enable the slider, you must integrate Spotify API support by providing API keys for the client ID and client secret. In this mode, the clock, title, and crop features will be disabled. |  `False` or `True` |
| `images_cache` | The number of processed images to keep in the memory cache. Use wisely to avoid memory issues (each image is approximately 17KB) | `1` to `500` |
| `show_text - enabled` | Show media info with image | `False` |
| `show_text - clean_title` | Remove "Remaster" labels, track numbers, and file extensions from the title if any | `True` |
| `show_text - text_background` | Change background of text area (support lytics mode also) | `True` |
| `special_mode_spotify_slider` |  Use spotify animation when special_mode is on and show text is enabled | `False` |
| `crop_borders - enabled` | Crop image borders if present | `True` |
| `crop_borders - extra` | Apply enhanced border cropping | `True` |

> [!NOTE]
> ### `light`
> The light feature is a built-in automation that sends a ‘turn on’ command with RGB values corresponding to the most dominant color in the image. If the image is black, white, or gray, the automation will select a soft random color.
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
> For accessibility, when lyrics are available and displayed above the image, the image will appear 50% darker when `text_background` and `lyrics` is `True` (apps.yaml). Lyrics feture is not support radio stations.
>
> ### Spotify Slider
> The Spotify album slide function will elevate the Pixoo64 to a new level by searching for album art that features the currently playing track and emphasizes the playing artist. To enable this mode, you need to add Spotify keys (client ID and client secret) to `apps.yaml`. Additionally, under the Pixoo arguments in `apps.yaml`, ensure that `spotify_slide` is set to `True`.
____________
## You’re all set!
**Make sure that `input_boolean.pixoo64_album_art` is turned `on`. The next time you play a track, the album cover art will be displayed, and all the usable picture data will be stored in a new sensor.**

![animated-g](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/2a716425-dd65-429c-be0f-13acf862cb10)
_____________

## Fallback Image Handling

When the script cannot directly obtain the album art for the currently playing track, it activates a sophisticated fallback system to ensure that your PIXOO64 still displays relevant visual information. The script attempts several methods, in the following order, to find an image:

1.  **Original Album Art:** The script first tries to use the album art URL provided by the media player. This is the primary and most direct method, and is usually successful for most local media and some streaming services.

2.  **API Services (Spotify, Discogs, Last.fm):** If the original album art is unavailable, the script attempts to find album art by querying these services using their respective APIs.
    *   **Spotify:** If you have provided your Spotify API credentials, the script will search for the current track and its associated album art in the Spotify database. Spotify is often a reliable source for music from mainstream streaming services.
    *  **Discogs:** Using a personal Discogs API key, the script searches for the release information of the current track and fetches the cover image from the Discogs database. Discogs is useful for finding album art for more obscure or independently released music.
    *  **Last.fm:** If you provide your Last.fm API key, the script will query Last.fm to get the information of the currently playing track and it's album art.
    *   The script tries these services in the order listed above (Spotify, Discogs, Last.fm), using the first image URL it successfully retrieves.

3.  **MusicBrainz:** If API services fail, the script queries the MusicBrainz database, an open-source music encyclopedia. MusicBrainz is often a good source of album art URLs, especially for less common tracks.
    *   This search uses the artist's name and track title. If it finds a matching release, it fetches a URL for the album's cover art from the Cover Art Archive (a sister project).
    *   MusicBrainz is an open-source database containing URLs for album art. Although the database is extensive and includes many rare artworks and doesn't require API keys, it relies on very slow server connections. This means that often the album art may not be retrieved in a timely manner while the track is playing.

4.  **AI Image Generation:** If all previous methods fail, the script resorts to generating an image with artificial intelligence using [pollinations.ai](https://pollinations.ai).
    *   The script generates a unique image based on the artist and track title, creating an abstract interpretation if album art is truly unavailable, ensuring a visual representation even with less common tracks.
    *   In this scenario, the script will attempt to generate an alternative version of the album art using generative AI. This option will trigger only if the Spotify API fails (or is unavailable) and/or no album art is found, or there is a timeout from the MusicBrainz service. Be aware that as it is a free AI generative service, it may also be laggy or sometimes unavailable.
        *   You can select `flux` or `turbo` as an AI model. The `turbo` model tends to produce more vibrant images, while `flux` provides a more artistic and colorful style.

5.  **Black Screen with Text:** As a final resort, if the script is unable to generate or fetch an image, it will display a black screen and the artist and title information of the current track on the PIXOO64.

This multi-layered approach ensures that your PIXOO64 displays some form of visual content in virtually every scenario. The script will always try to find an image through the more accurate APIs and online databases, before generating one using AI or falling back to a simple text representation.


## API KEYS
**Getting the Album API**: This is the most recommended option because servers are fast and reliable. You can choose one or more options. To use this method, you'll need at least one of the keys. Instructions on how to obtain them are provided beyond this text.
   - **Spotify**: the Client ID and the Client Secret.
   - **Discogs**: Personal API Key
   - **Last.FM**: API Key


## Guide to help you get your Spotify Client ID and Client Secret from the developer site:

1. **Log in to Spotify Developer Dashboard**: Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/login) and log in with your Spotify account.

2. **Create an App**: Click on the "Create an App" button. You'll need to provide a name and a brief description for your app. These fields are mainly for display purposes, so you can keep them simple.

3. **Choose `Web API`** from the `Which API/SDKs are you planning to use` section and press `SAVE`.
    ![{22F7F6C8-CA87-4146-A035-B0BCEC99DF3B}](https://github.com/user-attachments/assets/d653366f-ac76-4204-a17f-c27b1dc6a051)

4. **Copy Client ID and Client Secret**: Once your app is created, you'll be taken to the app overview page. At the Basic Information section you'll find your Client ID and Client Secret. Copy these values and store them on `apps.yaml` file under `spotify_client_id` and `spotify_client_secret`.

## Guide to help you get your Discogs API key:

1. **Log in to Discogs**: Go to the [Discogs website](https://www.discogs.com/) and log in with your account.

2. **Create a Personal Key**: Navigate to the [Discogs API documentation](https://www.discogs.com/developers/) and follow the instructions to create a new personal key. You don't need to create application.
3. Copy the value and store it on `apps.yaml` file under `discogs`.

## Guide to help you get your Last.fm API key:

1. **Log in to Last.fm**: Go to the [Last.fm website](https://www.last.fm/) and log in with your account.

2. **Create an Application**: Navigate to the [Last.fm API documentation](https://www.last.fm/api) and follow the instructions to create a new application. You'll need to provide a name and a brief description for your application.

3. **Obtain API Key**: Once your application is created, you'll be provided with an API key and a secret. You'll need just the API KEY.
4. Copy the value and store it on `apps.yaml` file under `last.fm`.

That's it! You now have your API keys for Spotify, Discogs, and Last.fm, which you can use to authenticate your Pixoo64 with these services.


## Sensor Attribues
The sensor  `sensor.pixoo64_media_data` is a virtual entity created in Home Assistant. It’s designed to store useful picture data from the album cover art of the currently playing song. This includes the artist’s name, the title of the media and color information such as the color of the font and the background. This sensor allows for dynamic visual experiences and automation possibilities based on the music being played.

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
| `process_duration` | The time until the image send to the screen from the time the player start |
| `spotify_frames` | Number of frames in animation |

Here’s an examples of the sensor attributes:

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
