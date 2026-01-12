# Raspberry Pi 5 Launcher

This launcher (`pi5_launcher.py`) is a specialized bridge that enables the **NHL-LED-SCOREBOARD** to run on the **Raspberry Pi 5**.

Because the Raspberry Pi 5 uses a new hardware architecture (RP1) for GPIO, the standard `rpi-rgb-led-matrix` library (and its Python bindings) does not currently support it directly. 

This solution uses **[Adafruit's Blinka Raspberry Pi 5 Piomatter](https://github.com/adafruit/Adafruit_Blinka_Raspberry_Pi5_Piomatter)** library to drive the matrix via the RP1's PIO (Programmable I/O) state machines, "bridged" through the **RGBMatrixEmulator**.

## How It Works

1.  **RGBMatrixEmulator**: The scoreboard application runs as if it were using the emulator.
2.  **Raw Adapter**: The emulator is configured to use its `raw` display adapter, which exposes the pixel data as a NumPy array.
3.  **Pi5 Launcher**: This script intercepts the emulator's initialization, reads the raw frame data, performs gamma correction, and sends it to the `piomatter` library to be displayed on the physical matrix.


## Prerequisites

### Hardware

*   **Raspberry Pi 5**
*   **RGB LED Matrix** (Adafruit Panels are recommended. **`128x64`** size works best with the `pi5_launcher.py` and nhl-led-scoreboard)
*   **RPi5 Power Supply** (Must supply direct to rpi5 and not power from Bonnet or HAT)
*   **RGB LED Matrix Power Supply** (Must supply direct to matrix)

### Software

Ensure you have the following installed (these are included in `requirements-pi5.txt`):

*   **Python 3**
*   **Python 3 virtual environment**: To isolate dependencies.
*   **Adafruit-Blinka-Raspberry-Pi5-Piomatter**: The hardware driver for Pi 5.
*   **RGBMatrixEmulator**: The matrix emulation layer.
*   **NumPy**: For efficient frame buffer manipulation.
*   **Adafruit-Blinka**: CircuitPython hardware compatibility layer.
*   **OS Packages**: Packages that the nhl-led-scoreboard depends on. These are included in `apt-requirements` and can be installed using the `scripts/sbtools/aptfile` script.


> [!CAUTION]
> Do **NOT** install the `rpi-rgb-led-matrix` library. It is not compatible with the Raspberry Pi 5.  Do not run the `scripts/install.sh` script.  It will install the `rpi-rgb-led-matrix` library.  An new install.sh will be created for the Pi5 at a future time.

> [!TIP]
> You can use the `"scripts/sbtools/sb-init"` script to skip the steps below and install the required dependencies.  It will create the virtual environment and install the required packages as well as the udev rules for the pi5.

## Manual Installation
To install the required dependencies, run in your virtual environment:

```bash
pip3 install -r requirements-pi5.txt
```

## Non-Root User Configuration

By default, root privilege is required to access the PIO hardware. To allow a standard user to run the launcher without `sudo`, you must configure a `udev` rule.

1.  Edit `/etc/udev/rules.d/99-com.rules`:
    ```bash
    sudo nano /etc/udev/rules.d/99-com.rules
    ```
2.  Add the following line to the file:
    ```
    SUBSYSTEM=="*-pio", GROUP="gpio", MODE="0660"
    ```
3.  Save and exit (Ctrl+S, Ctrl+X).
4.  Reboot the Pi:
    ```bash
    sudo reboot
    ```
Once you have configured the udev rules, you can run the launcher without `sudo`.  Disregard the use of `sudo` in the usage instructions.

## Configuration

The launcher relies on a specific configuration file for the emulator to ensure it exposes the raw data correctly. A sample configuration is provided as `pi5_emulator_config.json`. 

> [!IMPORTANT]
> You **MUST** rename `pi5_emulator_config.json` to `emulator_config.json` for the emulator to load it.

> [!CAUTION]
> Do **NOT** use the `pi5` adapter in the emulator configuration with the `pi5_launcher.py` script.  It will have double processing of the pixel data and cause the display to be garbled.  *ALWAYS* use the `raw` adapter instead.  

**File:** `emulator_config.json`

Ensure the following key settings are present:

```json
{
  "display_adapter": "raw",
  "pixel_style": "real", 
  "emulator_title": "NHL-LED-SCOREBOARD",
  "suppress_adapter_load_errors": true
}
```

*   `display_adapter`: **MUST** be set to `"raw"` for the bridge to work.
*   `pixel_style`: Can be ignored.  Any pixel settings are not applied for the `"raw"` display adapter.

### Hardware Configuration

The launcher accepts standard command-line arguments to configure the matrix dimensions and pinout mapping.

```bash
sudo python3 pi5_launcher.py --led-cols=64 --led-rows=32 --led-gpio-mapping=adafruit-hat
```

Supported Arguments:
*   `--led-cols`: Number of columns (default: 64)
*   `--led-rows`: Number of rows (default: 32)
*   `--led-gpio-mapping`: Pinout mapping. Options: `regular`, `adafruit-hat`.
*   `--led-rgb-sequence`: Color sequence (e.g., `RGB`, `BGR`, `RBG`). The launcher handles software reordering if the hardware doesn't support it natively.
*   `--led-pwm-bits`: PWM depth (1-10). Default: 10. Lowering this (e.g., to 6-8) can improve refresh rates at the cost of color depth.
*   `--led-row-addr-type`:  Number of address lines (e.g., 0-5). Useful for panels with different multiplexing.
*   `--led-pwm-dither-bits`: Amount of dithering to apply (0-2). 0 = no dithering, higher values use more temporal planes.
*   `--led-pixel-mapper`:  Apply pixel mapping modifications. Supports `U-Mapper` (for serpentine panels) and `Rotate:<angle>` (0, 90, 180, 270). Multiple mappers can be separated by a semicolon (e.g., `U-Mapper;Rotate:180`).
    *   *Note: Rotation and Serpentine options are only available for panels with < 5 address lines.*

### Brightness & Color Control
*   `--led-brightness`: (Integer 0-100) Sets the global brightness. 
*   `--led-color-correction`: (Format `R:G:B`) Adjusts the color balance. Useful if your panel behaves tinty. Example: `--led-color-correction=1.0:0.9:0.7` to reduce Green and Blue intensity.
*   `--led-control-mode`: ( `rgbme` | `launcher` ) Defines who controls the brightness.
    *   `rgbme` (Default): The RGBMatrixEmulator controls brightness.
    *   `launcher`: The `--led-brightness` flag set here overrides the application setting.

### Transition Effects
*   `--led-transition-mode`: Selects the transition effect. Options: `fade`, `fade-in`, `fade-out`, `wipe-left`, `wipe-right`, `wipe-up`, `wipe-down`, `curtain-open`, `curtain-close`, `clock-cw`, `clock-ccw`, `random`.
*   `--led-transition-steps`: Number of frames for the transition (default: 20).
*   `--led-transition-hold`: Seconds to hold the image before transitioning (default: 1.0).
*   `--led-transition-threshold`: Percentage of pixel change required to trigger a transition (default: 10).

### Color Test
### Color Test
*   `--led-color-test`: Displays a simple color test pattern (Red, Green, Blue squares with labels) to verify the matrix connection and orientation. 
    *   **Interactive Mode**: While running the test, keys `r`/`R`, `g`/`G`, and `b`/`B` can be used to adjust the color correction values in real-time. Keys `v`/`V` adjust the brightness. Key `0` resets the color correction. The new values are displayed on the matrix.
    *   **Exit**: Press `CTRL-C` to exit. The tool will print the final configuration flags needed to apply your settings permanently.


## Usage

To start the scoreboard on a Raspberry Pi 5:

```bash
sudo python3 pi5_launcher.py
```

**Example with Brightness Control:**
To force the brightness to 50% and tint the display slightly red (reducing blue/green):
```bash
sudo python3 pi5_launcher.py --led-control-mode=launcher --led-brightness=50 --led-color-correction=1.0:0.8:0.8
```

**Example Color Test:**
To verify your matrix colors and orientation:
```bash
sudo python3 pi5_launcher.py --led-color-test --led-cols=64 --led-rows=32
```

*Note: `sudo` is typically required for hardware GPIO access.*

## Troubleshooting

*   **Performance**: If the display is flickering or sluggish, try reducing `--led-pwm-bits` or ensuring no other heavy processes are running.
*   **Colors Swapped**: Use the `--led-rgb-sequence` argument to correct RGB/BGR mismatches (e.g., `--led-rgb-sequence=BGR`).
*   **Permission Errors**: Ensure you are running with `sudo`.

