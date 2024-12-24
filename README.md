### Album Art Display on PIXOO64
Elevate your musical experience on the DIVOOM PIXOO64 screen with this powerful Appdaemon script for Home Assistant. This script fetches and displays the album cover art of the currently playing track. By default, the album art will automatically appear on the Pixoo64 screen when a track is playing.

Additionally, the script supports lyrics display and uses AI-generated images as a fallback if no album art is found.

## Examples
![PIXOO_album_gallery](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71348538-2422-47e3-ac3d-aa1d7329333c)
 
#### Key Features:
- **Image Cropping**: The script cuts out wide borders from album art to present the main object on the screen.
- **Synchronized Lyrics Display**: Displays synchronized lyrics of the song.
- **Display Clock**: Shows the current time.
- **Artist and Track Title Display**: Shows the artist and track title.
- **Album Arts Slider**: Shows a various album arts for the playing title.
- **Full Fallback Support**: If album art doesn't exist or can't be fetched, the script provides fallback options. These fallbacks support API services like MusicBrainz, Spotify, Discogs, and Last.FM. If all else fails, the script creates a dedicated AI image using [pollinations.ai](https://pollinations.ai), ensuring that 99% of the time, an image will be displayed on the Pixoo64 screen while music is playing.

The script is compatible with speaker systems such as Chromecast, AirPlay 2, and Sonos, and fully supports services like Spotify, Tidal, Apple Music, YouTube Music, MixCloud, TuneIn, Sonos Radio, and more!

#### More Features & Functional Advantages:
- **Image Enhancer**: Amplifies the color vibrancy of the image for a more striking display.
- **Sensor Data Storage**: Stores all extracted data in a dedicated sensor entity within Home Assistant for further automation possibilities.
- **RTL Support**: Displays the artist’s name or song title correctly in right-to-left languages.
- **Title Normalization**: Normalizes titles and artist names for easier integration with automations and consistent display. For instance, “Beyoncé” would be normalized to “Beyonce”.
- **Light Dynamic Color Integration**: Uses the dominant color from the album art to set the background color on any RGB light.

## Prerequisites
1. [DIVOOM PIXOO64](https://www.aliexpress.com/item/1005003116676867.html)
2. Home Assistant (with add-on functionality)
3. AppDaemon (Home Assistant add-on)
## Installation
> [!TIP]
> Create a **Toggle Helper** in Home Assistant. For example, `input_boolean.pixoo64_album_art` can be used to control when the script runs. This means that whenever the player starts a track, the album art will appear if the toggle is on. Establish this helper within the Home Assistant User Interface or YAML code. It’s best to do this prior to installation.
> **Ensure that the helper sensor is created prior to executing the script for the first time.**
1. Install **AppDaemon** from the Home Assistant add-on store.
2. On the AppDaemon [Configuration page](http://homeassistant.local:8123/hassio/addon/a0d7b954_appdaemon/config), install the **`pillow`**, **`python-bidi`** *(optional)* and **`unidecode`** *(optional)* Python packages.

> [!IMPORTANT]
> Not installing the packadges may cause the script not work
```yaml
# http://homeassistant.local:8123/hassio/addon/a0d7b954_appdaemon/config
system_packages: []
python_packages:
  - pillow
  - unidecode
  - python-bidi
init_commands: []
```
### Manual Download
1. Download the Python file from [This Link](https://github.com/idodov/pixoo64-media-album-art/blob/main/apps/pixoo64_media_album_art/pixoo64_media_album_art.py).
2. Place the downloaded file inside the `appdaemon/apps` directory and proceed to the final step
### HACS Download
1. In Home Assistant: Navigate to `Settings` > `Integrations` > `HACS` > `Configure` and enable `AppDaemon apps discovery & tracking`. After enabling, return to the main HACS screen.
   * ![{D6AD7841-B9A6-460A-A1C6-B1C680188B66}](https://github.com/user-attachments/assets/18a39041-57a8-4acd-89e9-7ce44874c894)

2. Navigate to the `Custom Repositories` page and add the following repository as `AppDaemon`: `https://github.com/idodov/pixoo64-media-album-art/`
3. Return to the main `HACS` screen and search for `PIXOO64 Media Album Art`.  Click on `Download`
> [!IMPORTANT]  
> In AppDaemon, make sure to specify the apps directory in `/addon_configs/a0d7b954_appdaemon/appdaemon.yaml`.
> Also, remember to transfer all files from `/addon_configs/a0d7b954_appdaemon/apps/` to `/homeassistant/appdaemon/apps/`.
```yaml
#/addon_configs/a0d7b954_appdaemon/appdaemon.yaml
---
appdaemon:
  app_dir: /homeassistant/appdaemon/apps/
```
_________
## Final Step - Configuration
Open `/appdaemon/apps/apps.yaml` and add this code:
> [!TIP]
>  If you’re using the File Editor add-on, it’s set up by default to only allow file access to the main Home Assistant directory. However, the AppDaemon add-on files are located in the root directory. To access these files, follow these steps:
1. Go to `Settings` > `Add-ons` > `File Editor` > `Configuration`
2. Toggle off the `Enforce Basepath` option.
3. In the File Editor, click on the arrow next to the directory name (which will be ‘homeassistant’). This should give you access to the root directory where the AppDaemon add-on files are located at `/addon_configs/a0d7b954_appdaemon/`.

![arrow](https://github.com/idodov/RedAlert/assets/19820046/e57ea52d-d677-45b0-90c4-87723c5ddfea)

```yaml
# appdaemon/apps/apps.yaml
---
pixoo64_media_album_art:
    module: pixoo64_media_album_art
    class: Pixoo64_Media_Album_Art
    home_assistant:
        ha_url: "http://homeassistant.local:8123"   # Your Home Assistant URL.
        media_player: "media_player.era300"         # The entity ID of your media player.
        toggle: "input_boolean.pixoo64_album_art"   # (Optional) An input boolean to enable or disable the script's execution.
        pixoo_sensor: "sensor.pixoo64_media_data"   # (Optional) A sensor to store extracted media data.
        light: "light.strip_stone"                  # (Optional) The entity ID of an RGB light to synchronize with the album art colors.
        ai_fallback: "turbo"                        # The AI model to use for generating alternative album art when needed (supports 'flux' or 'turbo').
        force_ai: False                             # If True, only AI-generated images will be displayed.
        musicbrainz: True                           # If True, attempts to find a fallback image on MusicBrainz if other sources fail.
        spotify_client_id: False                    # Your Spotify API client ID (needed for Spotify features). Obtain from https://developers.spotify.com.
        spotify_client_secret: False                # Your Spotify API client secret (needed for Spotify features).
        last.fm: False                              # Your Last.fm API key. Obtain from https://www.last.fm/api/account/create.
        discogs: False                              # Your Discogs API key. Obtain from https://www.discogs.com/settings/developers.
    pixoo:
        url: "192.168.86.21"                        # The IP address of your Pixoo64 device.
        full_control: True                          # If True, the script will control the Pixoo64's on/off state in sync with the media player's play/pause.
        contrast: True                              # If True, applies a 50% contrast filter to the images displayed on the Pixoo.
        clock: True                                 # If True, a clock is displayed in the top corner of the screen.
        clock_align: "Right"                        # Clock alignment: "Left" or "Right".
        tv_icon: True                               # If True, displays a TV icon when audio is playing from a TV source.
        lyrics: False                               # If True, attempts to display lyrics on the Pixoo64 (show_text and clock will be disabled).
        lyrics_font: 2                              # Recommend values: 2, 4, 32, 52, 58, 62, 158, 186, 190, 590. More values can be found at https://app.divoom-gz.com/Device/GetTimeDialFontList (you need ID value)
        limit_colors: False                         # Reduces the number of colors in the picture from 4 to 256, or set it to False for original colors.
        spotify_slide: False                        # If True, forces an album art slide (requires a Spotify client ID and secret). Note: clock and title will be disabled in this mode.
        images_cache: 25                            # The number of processed images to keep in the memory cache. Use wisely to avoid memory issues (each image is approximately 17KB).
        show_text:
            enabled: False                          # If True, displays the artist and title of the current track.
            clean_title: True                       # If True, removes "Remastered," track numbers, and file extensions from the title.
            text_background: True                   # If True, adjusts the background color behind the text for improved visibility.
            font: 2                                 # The font to use for text (Pixoo64 built-in fonts in ultimate fallback screen, 0-7).
        crop_borders:
            enabled: True                           # If True, attempts to crop any borders from the album art.
            extra: True                             # If True, applies an enhanced border cropping algorithm.
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
| `lyrics` | Display sync lyrics | `True` |
| `lyrics_font` | Font to display the lyrics. More values can be found here: [DIVOOM PIXOO64 FONTS JSON](https://app.divoom-gz.com/Device/GetTimeDialFontList) (you need ID value) | Recommend values: `2`, `4`, `32`, `52`, `58`, `62`, `158`, `186`, `190`, `590` |
| `limit_colors` | Reduces the number of colors in the picture from 4 to 256, or set it to False for original colors | `4` to `256` or `False` |
| `spotify_slide` | Shows album arts for the playing title taken from Spotify API. To enable the slider, you must integrate Spotify API support by providing API keys for the client ID and client secret. In this mode, the clock, title, and crop features will be disabled. |  `False` or `True` |
| `images_cache` | The number of processed images to keep in the memory cache. Use wisely to avoid memory issues (each image is approximately 17KB) | `1` to `500` |
| `show_text - enabled` | Show media info with image | `False` |
| `show_text - clean_title` | Remove "Remaster" labels, track numbers, and file extensions from the title if any | `True` |
| `show_text - text_background` | Change background of text area (support lytics mode also) | `True` |
| `show_text - font` | Pixoo internal font type (0-7). Used in fallback screen only | `2` |
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

## Fallback Image

When there's no image associated with the music file, or if the image can't be fetched, the fallback function will activate. By default, the supported fallbacks are MusicBrainz and the AI Image generator because neither requires an API key. However, these services are not 100% reliable, so it's recommended to use any of the APIs that this script supports (Spotify/Discogs/Last.fm). **You can choose to use one, two, or all three.** The fallback will first try to find the album art on Discogs, and if it fails, it will try Spotify, then Last.fm. No matter what, 99.9% of the time when a track is played, the Pixoo64 will present artwork graphics.

### There are four types of fallbacks:

1. **Getting the Album API**: This is the most recommended option because servers are fast and reliable. You can choose one or more options. To use this method, you'll need keys. Instructions on how to obtain them are provided beyond this text.
   - **Spotify**: the Client ID and the Client Secret.
   - **Discogs**: Personal API Key
   - **Last.FM**: API Key
   
2. **Fetching Album Art from MusicBrainz**: MusicBrainz is an open-source database containing URLs for album art. Although the database is extensive and includes many rare artworks and doesn't require API keys, it relies on very slow server connections. This means that often the album art may not be retrieved in a timely manner while the track is playing.

3. **Generating Art with Special AI**: In this scenario, the script will attempt to generate an alternative version of the album art using generative AI. This option will trigger only if the Spotify API fails (or is unavailable) and/or no album art is found, or there is a timeout from the MusicBrainz service. Be aware that as it is a free AI generative service, it may also be laggy or sometimes unavailable.

4. **Fallback Text Display**: If no image is available at all, text displaying the artist's name and the track title will be shown.

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
| `normalized_artist` | The artist's name in Latin letters |
| `media_title` | The original title of the media |
| `normalized_title` | The media title in Latin letters |
| `font_color` | The color of the font |
| `background_color_brightness` | The brightness level of the background color |
| `background_color` | The color of the lower part in background |
| `background_color_rgb` | The RGB values of the background color (lower part) |
| `color_alternative` |  The most common color of the background |
| `images_in_cache` | Current number of images in memory cache |
| `image_memory_cache` | Memory used in KB or MB | 
| `process_duration` | The time until the image send to the screen from the time the player start |
| `spotify_frames` | Number of frames in animation |

Here’s an examples of the sensor attributes:

```yaml
artist: Katy Perry
normalized_artist: Katy Perry
media_title: OK
normalized_title: OK
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
```
Arabic Title When Normalized (letters changed to English):
```yaml
....
media_title: آمين
normalized_title: amyn
....
```

__________
> [!NOTE]
> While experimenting with the device, you may notice occasional freezes. These could potentially be due to power issues. To address this, it’s suggested to use a USB charger with an output of 3A for optimal performance. If you’re using a charger with a lower voltage (2A, which is the minimum required), it’s advisable to limit the screen brightness to no more than 90%.
>
> Also, at times, an overloaded Wi-Fi network might result in the Pixoo64 responding slowly. Most often, rebooting the Wi-Fi network or the router rectifies this problem. 

**Disclaimer:**
*This software is **not** an official product from Divoom. As a result, Divoom bears **no responsibility** for any damages or issues arising from the use of this script. Additionally, Divoom does **not** offer end-user support for this script. Please utilize it at your own risk.*
