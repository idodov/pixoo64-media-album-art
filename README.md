# 🎨 Pixoo64 Media Album Art for Home Assistant

[![Current Version](https://img.shields.io/badge/version-1.0.0-blue.svg?style=for-the-badge)](https://github.com/idodov/pixoo64_art)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blueviolet.svg?style=for-the-badge&logo=home-assistant)](https://www.home-assistant.io/)
[![HACS Default](https://img.shields.io/badge/HACS-Custom%20Repo-orange.svg?style=for-the-badge&logo=hacs)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

Transform your **Divoom Pixoo64** into an intelligent, responsive, high-end media dashboard seamlessly integrated with Home Assistant.

Evolving from its AppDaemon origins, this project is now a fully native Home Assistant custom integration—**no AppDaemon required**. It offers a frictionless, one-click UI setup via Config Flow, automatic LAN device discovery, and dynamic dashboard controls. Experience real-time synchronized lyrics, ambient room lighting that adapts to your music, and an animated notification engine featuring onboard buzzer support. 

![PIXOO_album_gallery](https://github.com/idodov/pixoo64-media-album-art/assets/19820046/71348538-2422-47e3-ac3d-aa1d7329333c)

---

## ✨ Key Features

* 🖼️ **High-Precision Image Processing:** Enjoy optimized visuals with dynamic resizing, aspect-ratio correction, color quantization, and intelligent edge-cropping specifically tailored for the Pixoo's 64x64 LED matrix.
* 🧠 **Multi-Tier Fallback Waterfall & AI Generation:** Never stare at a blank screen. If your media player lacks cover art (e.g., streaming radio, local files), the integration automatically fetches art from **Spotify**, **MusicBrainz**, **TIDAL**, **Last.fm**, or **Discogs**. As a final fallback, it utilizes **Pollinations AI** to generate unique, conceptually relevant art on the fly based on the track title and artist.
* 🎤 **Live Synced Lyrics Engine:** Turn your Pixoo into a karaoke display. Fetches synchronized `.lrc` lyrics via LRCLIB utilizing event-driven scheduling. It features smart multi-line wrapping, bidirectional (RTL) language rendering (perfect for Hebrew and Arabic), and millisecond time-offset calibration for perfect sync.
* 📊 **Smooth Dual-Layer Progress Bar:** Keep track of your tunes with a real-time visual progress bar that automatically matches the album's contrasting colors.
* 💡 **Ambient Lighting Sync:** Extend the music to your room. The integration extracts the dominant color palette from the album art in real-time and maps it to your **Home Assistant RGB lights** and **WLED fixtures**, complete with configurable effects, speeds, and nighttime-only filters.
* 🔔 **Animated Interrupt Notifications:** Stay informed without missing a beat. Media is temporarily paused to display animated alerts for alarms, smart doorbells, appliance cycles, weather, and more. These visual alerts are paired with the Pixoo's hardware buzzer for acoustic chimes.
* 🎛️ **Comprehensive Dashboard Control:** Take charge of your display. Every setting—including crop modes, clock/temperature overlays, text placement, and the AI generation toggle—is exposed as a native Home Assistant switch, select, or number entity for effortless dashboard integration.

---

## 🤖 The Power of AI Generation

One of the standout features of this integration is its ability to generate album art when none exists, ensuring a continuous visual experience. 

Powered by [Pollinations AI](https://gen.pollinations.ai/), this integration acts as a creative fallback. If standard metadata providers fail to return an image, the system constructs a precise prompt using the current track and artist name and sends it to the selected AI model[cite: 4]. 

You have full control over the AI engine powering this feature. The integration allows you to dynamically fetch the latest available image generation models directly from Pollinations AI and sort them by cost, ensuring you always have access to the most efficient and up-to-date options without needing an integration update. 

Available models include[cite: 1, 4]:
* **Flux Schnell (Black Forest Labs):** Fast, high-quality images.
* **Recraft V4.1 Vector (Recraft):** Best for generating vector-style graphics suited for the 64x64 LED grid.
* **Lightning Turbo (InferencePort):** Focused on rapid image generation.
* **MAI Image 2.5 Flash (Microsoft):** Quick photorealistic generation.
* **Qwen Image 2.1 (Qwen):** Highly efficient image generation.
* **GPT Image 1 Mini (OpenAI):** Affordable image creation.
* **Gemini Flash (Google):** Speedy, affordable image generation.

*Note: Generating images via Pollinations AI requires a free API key from [enter.pollinations.ai/keys](https://enter.pollinations.ai/keys).*

---

## 📦 Installation

### Option 1: Via HACS (Recommended)

1. Open **HACS** within your Home Assistant instance.
2. Click the three dots in the top-right corner and select **Custom repositories**.
3. Paste the repository URL: `https://github.com/idodov/pixoo64_art`
4. Choose **Integration** as the category and click **Add**.
5. Locate **Pixoo64 Media Album Art** in the integration list, click **Download**, and restart Home Assistant.

### Option 2: Manual Installation

1. Download the latest release `.zip` from the GitHub repository.
2. Extract the archive and copy the `pixoo64_art` folder into your Home Assistant directory:  
   `<config>/custom_components/pixoo64_art/`
3. Restart Home Assistant.

---

## ⚙️ Initial Configuration (Config Flow)

Forget YAML files! Everything is seamlessly configured via the Home Assistant UI:

1. Navigate to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Pixoo64 Media Album Art**.
3. **Step 1: Device & Media Player Setup**
   * **Pixoo IP:** Select your automatically discovered Pixoo64 from the LAN list or choose *Manual Entry*.
   * **Media Player:** Select the target `media_player` entity you wish to track.
   * **Temperature Sensor (Optional):** Select a temperature sensor entity to render local weather data on the display.
4. **Step 2: Ambient Lighting Sync (Optional)**
   * **Light Entities:** Choose one or more RGB lights to sync with the dominant colors of the current album art.
   * **WLED IP:** Enter the IP address of a WLED controller to mirror the color palette and effects.
   * **Only at Night:** Enable this to restrict lighting changes to hours when the sun is below the horizon.
5. **Step 3: External APIs & Metadata Providers (Optional)**
   * **AI Generation:** Choose your preferred AI model from the dynamically loaded list (e.g., Flux, Turbo, GPT, Gemini) and enter your [Pollinations AI Key](https://enter.pollinations.ai/keys).
   * **MusicBrainz:** Toggle open-source cover art queries.
   * **Spotify API:** Enter your Client ID & Secret to enable high-res art fetching and animated gallery modes.
   * **TIDAL / Last.fm / Discogs:** Provide API keys for these services to maximize fallback redundancy.

> 💡 **Reconfiguration:** You can easily update your API credentials, light targets, temperature sensors, and AI model preferences at any time by clicking **Configure** on the integration card.

---

## 🎛️ Dashboard Controls & Entity Reference

Once configured, the integration creates a Home Assistant Device exposing the following entities for total control:

### 🔘 Switches

| Entity Name | Entity ID | Description |
| :--- | :--- | :--- |
| **Pixoo64 Master Control** | `switch.pixoo64_master_control` | Master On/Off switch for the integration. Turning this off clears text and gracefully turns off/restores the screen. |
| **Pixoo64 Full Control** | `switch.pixoo64_full_control` | When enabled, turns the Pixoo screen completely off when media playback stops. When disabled, restores the previous clock/channel. |
| **Pixoo64 Progress Bar** | `switch.pixoo64_progress_bar` | Toggles the dual-layer, auto-contrasting track progress bar at the bottom of the screen. |
| **Pixoo64 Force AI Art** | `switch.pixoo64_force_ai` | Bypasses original cover art entirely, generating custom conceptual AI art for every playing song. |
| **Pixoo64 Text Background** | `switch.pixoo64_text_background` | Adds an automatic dimmed background behind text and overlay zones to guarantee readability on bright album covers. |

---

### 🎚️ Selects (Display & Layout)

#### 1. Display Mode (`select.pixoo64_display_mode`)
* **Standard:** High-contrast cover art with optional overlays (clock, temperature, title).
* **Lyrics:** Full-screen live synchronized lyrics fetched from LRCLIB.
* **Burned:** Stylistically burns the artist and title directly into the image canvas using contrasting typography.
* **Special Mode:** Elegant centered mini-album art framed inside dynamic background gradients.
* **Spotify Slider:** *(Available when Spotify credentials are provided)* Cycles through animated album variants and artist profiles in a smooth gallery animation.

#### 2. Artist & Track Text (`select.pixoo64_artist_track_text`)
* **Bottom:** Displays scrolling text along the bottom row.
* **Top:** Displays scrolling text along the top row.
* **Hidden:** Hides title and artist text completely for pure, unobstructed artwork.

#### 3. Overlay Info (`select.pixoo64_overlay_info`)
* **None:** Disables the overlay layer entirely.
* **Clock:** Displays a real-time digital clock.
* **Temperature:** Displays live temperature from the linked sensor.
* **Clock + Temp:** Renders both clock and temperature simultaneously.

#### 4. Overlay Vertical Position (`select.pixoo64_overlay_vertical_position`)
* **Auto (Opposite of Text):** Automatically places clock/temp on the opposite edge of the track text to prevent visual collisions.
* **Top:** Forces clock/temp to the top row.
* **Bottom:** Forces clock/temp to the bottom row.

#### 5. Overlay Alignment (`select.pixoo64_overlay_alignment`)
* **Clock Right, Temp Left:** Clock aligns to the right corner; temperature aligns to the left corner.
* **Clock Left, Temp Right:** Clock aligns to the left corner; temperature aligns to the right corner.
* **Centered:** Places elements toward the center of the display.

#### 6. Crop Mode (`select.pixoo64_crop_mode`)
* **No Crop:** Preserves exact original dimensions with letterbox padding (Default).
* **Crop:** Trims exterior borders, letterboxing, and empty whitespace.
* **Extra Crop:** Advanced multi-component subject isolation. Rejects outer album borders and background text to tightly frame the subject.

---

### 🔢 Numbers

| Entity Name | Entity ID | Range | Description |
| :--- | :--- | :--- | :--- |
| **Lyrics Sync Offset** | `number.pixoo64_lyrics_sync_offset` | `-5.0s` to `+5.0s` (Step: `0.5s`) | Fine-tune lyrics synchronization in real-time to perfectly match speaker latency or Bluetooth lag. |

---

### 📊 Sensors

#### **Pixoo64 Status** (`sensor.pixoo64_status`)
Displays the current state formatted as `Artist - Title`. Includes comprehensive diagnostic attributes:
* `image_source`: Where the current art came from (`Original`, `Spotify`, `MusicBrainz`, `TIDAL`, `AI`, etc.).
* `image_url`: Full URL or source path of the active artwork.
* `font_color`: Auto-calculated hex color optimized for legibility.
* `background_color` & `background_color_rgb`: Dominant color extracted from the artwork.
* `process_duration`: Time taken to fetch, crop, filter, and render the frame.
* `lyrics_found` & `lyrics_count`: Synced lyrics availability and total lines parsed.
* `pixoo64_channel`: Last active Pixoo device channel before takeover.

---

## 🔔 Custom Notifications Service (`pixoo64_art.send_notification`)

Send instant text or animated icon alerts directly to your Pixoo64. Notifications temporarily interrupt playback, paint a high-contrast black frame with custom themed pixel icons, sound the hardware buzzer (optional), and gracefully restore previous artwork when finished.

### Service Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `message` | string | **Yes** | — | Text to display (supports automatic Hebrew/Arabic RTL). |
| `type` | string | No | `text` | The visual theme and animated icon (see list below). |
| `duration` | int | No | `5` | Time in seconds before returning to media art. |
| `play_buzzer` | boolean| No | `false` | Trigger the Pixoo64 onboard acoustic buzzer chime. |
| `buzzer_active`| int | No | `500` | Beep tone active duration in milliseconds. |
| `buzzer_off` | int | No | `500` | Silence duration between beeps in milliseconds. |
| `buzzer_total` | int | No | `3000` | Total buzzer cycle time in milliseconds. |
| `color` | string | No | — | Optional custom HEX color override (e.g., `#00FFCC`). |

#### Supported Notification Types
* **Status & Alert:** `text`, `info`, `success`, `warning`, `error`, `v` (Checkmark), `x` (Cancel), `alert` (Animated bell), `attack` (Animated rocket).
* **Smart Home:** `door`, `lock`, `boiler`, `shutter`, `washer`, `car`, `trash`, `mail`, `fire`, `water`.
* **Devices & Sensors:** `battery`, `wifi`, `phone` (Animated wiggle), `camera`, `calendar`, `timer` (Animated clock hand), `weather` (Sun & Cloud).
* **Atmosphere:** `music`, `sun`, `moon` / `sleep`.

### Automation Example

```yaml
alias: "Front Door Bell - Pixoo Notification"
trigger:
  - platform: state
    entity_id: binary_sensor.front_door_bell
    to: "on"
action:
  - service: pixoo64_art.send_notification
    data:
      message: "Visitor at the Door!"
      type: "door"
      duration: 7
      play_buzzer: true
      buzzer_active: 300
      buzzer_off: 200
      buzzer_total: 2000
