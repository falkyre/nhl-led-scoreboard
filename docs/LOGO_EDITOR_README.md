# NHL LED Scoreboard Logo Editor

A web-based WYSIWYG (What You See Is What You Get) editor for positioning, sizing, and rotating team logos for the `nhl-led-scoreboard`. This tool allows you to visually tweak logo layouts for different matrix resolutions (64x32, 128x32 or 128x64) without manually editing JSON coordinates.

## Features

* **Visual Interface**: Drag-and-drop positioning relative to the specific matrix size.
* **Live Preview**: View the actual scoreboard emulator running in real-time below the editor. You can also select to simulate past games.
* **Multi-Resolution Support**: Switch between 64x32, 128x64, and 128x32 layouts seamlessly.
* **Asset Management**: Automatically downloads and converts high-quality logos from the NHL API if local assets are missing.
* **Alt Logo Support**: Easily upload and manage alternate logos for any team. Upload local files or fetch images via URL (supports PNG and SVG)
* **Emulator Control**: Launch, stop, and toggle the emulator window directly from the web browser.
* **Smart Configuration**: Automatically manages default values and maintains a rolling history of the last 5 configuration backups.

---

## Prerequisites

Before running the editor, ensure you have the required Python libraries installed. It is recommended to install these in your scoreboard's virtual environment.  

>[!note]
> These requirements are already installed as part of main installation.

```bash
# Activate your virtual environment first
source ~/nhlsb-venv/bin/activate

# Install dependencies
pip install flask pillow cairosvg
```

*(Note: `cairosvg` is required for auto-downloading and converting missing vector logos).*

---

## Installation

1. Place `logo_editor.py` in the root directory of your `nhl-led-scoreboard` installation (same level as `main.py`).
2. Create a folder named `templates` in the root directory.
3. Place `editor.html` inside the `templates` folder.

---

## Usage

### Starting the Editor

Run the script using Python. By default, it will detect your virtual environment and scoreboard location.

```bash
python3 logo_editor.py
```

Open your web browser and navigate to: <http://localhost:5000>

### Command Line Arguments

If you have a custom setup, you can specify paths using arguments:

| Argument | Description | Default |
| --- | --- | --- |
| `--port` | The port to run the web editor on. | `5000` |
| `--dir` | The root directory of the scoreboard installation. | Current Directory |
| `--venv` | Path to your python virtual environment. | Auto-detects active env, or defaults to `~/nhlsb-venv` |

**Example:**

```bash
python3 logo_editor.py --port 8080 --dir /opt/nhl-led-scoreboard --venv /opt/my_venv
```

---

## Interface Guide

### 1. Configuration Panel (Left Sidebar)

* **Matrix Size:** Select the resolution of your board (e.g., 64x32). This resizes the editor grid and automatically loads the corresponding `logos_WxH.json` file.
* **Config File:** Shows the currently loaded JSON file.
* **Team:** Select the team logo you wish to edit. Use the dropdown to select specific teams or their **ALT** variants.
* **Stance:** Select **Home** (Left) or **Away** (Right).
* **Opponent (Visual Only):** Select a second team to render on the opposite side. This helps visualize spacing.
* **Show Gradient Layer:** Toggles the background gradient asset to ensure logos blend correctly.

### 2. Emulator Control

Located in the sidebar, these buttons control the actual `src/main.py` scoreboard script.

* **Launch:** Starts the scoreboard in emulator mode with the currently selected resolution.
* **Open/Collapse:** Toggles the visibility of the emulator iframe.
* **Stop:** Kills the emulator process.

*> **Note:** If you change the Matrix Size in the dropdown while the emulator is running, the tool will ask if you want to restart the emulator to match the new resolution.*

### 3. Visual Editor (Workspace)

The large grid represents your LED Matrix.

* **Move:** Click and drag the logo to position it.
* **Zoom/Resize:**
  * **Scroll Wheel:** Hover over the logo and scroll up/down to zoom.
  * **Shift + Drag:** Hold `Shift`, click the logo, and drag up/down to resize.

* **Reference Lines:** Red anchor dots help align your images.
* **Overlays:** Static renders of game text (Score, Time) help prevent overlaps.

### 4. Adjustments & Saving

* **Numeric Inputs:** Use the X, Y, Zoom, and Rotate inputs for pixel-perfect adjustments.
* **Flip Horizontal:** Useful for logos that face a specific direction.
* **Replace Logo:** Upload a new image to replace the current team's logo.
  * **File Upload:** Select a local PNG or JPG.
  * **URL Upload:** Paste a direct link to an image (supports SVG).
* **Reset:** Reverts the logo to the values from the last save.
* **SAVE CHANGES:** Writes values to the JSON file. **A backup of the previous file is created (last 5 kept).**

---

## Troubleshooting

**The Emulator iframe says "Connection Refused"**

This happens when the emulator process is starting up or has stopped.

1. Click the **Stop** button.
2. Click **Launch**.
3. Wait for the "Loading..." overlay to disappear.

**My logo isn't showing up**

If a specific resolution PNG is missing, the editor will attempt to download the SVG from the NHL API. Check your terminal for errors.

**The Editor Grid is the wrong size**

Ensure you selected the correct **Matrix Size** from the dropdown.