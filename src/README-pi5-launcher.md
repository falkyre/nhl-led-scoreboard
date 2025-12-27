# Raspberry Pi 5 Launcher

This launcher (`pi5_launcher.py`) is a specialized bridge that enables the **NHL-LED-SCOREBOARD** to run on the **Raspberry Pi 5**.

Because the Raspberry Pi 5 uses a new hardware architecture (RP1) for GPIO, the standard `rpi-rgb-led-matrix` library (and its Python bindings) does not currently support it directly. 

This solution uses **[Adafruit's Piomatter](https://github.com/adafruit/Adafruit_CircuitPython_PioMatter)** library to drive the matrix via the RP1's PIO (Programmable I/O) state machines, "bridged" through the **RGBMatrixEmulator**.

## How It Works

1.  **RGBMatrixEmulator**: The scoreboard application runs as if it were using the emulator.
2.  **Raw Adapter**: The emulator is configured to use its `raw` display adapter, which exposes the pixel data as a NumPy array.
3.  **Pi5 Launcher**: This script intercepts the emulator's initialization, reads the raw frame data, performs gamma correction, and sends it to the `piomatter` library to be displayed on the physical matrix.

## Prerequisites

Ensure you have the following installed (these are included in `requirements-pi5.txt`):

*   **Python 3**
*   **Adafruit-Blinka-Raspberry-Pi5-Piomatter**: The hardware driver for Pi 5.
*   **RGBMatrixEmulator**: The matrix emulation layer.
*   **NumPy**: For efficient frame buffer manipulation.
*   **Adafruit-Blinka**: CircuitPython hardware compatibility layer.

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
*   `pixel_style`: Can be set to `"real"` (no effects) for best performance.

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
*   `--led-brightness`: Brightness (0-100). **Note:** This is simulated in software (gamma correction), not hardware. Values below 25 may result in poor color/image reproduction.
*   `--led-pwm-bits`: PWM depth (1-10). Default: 10. Lowering this (e.g., to 6-8) can improve refresh rates at the cost of color depth.
*   `--led-row-addr-type`:  Number of address lines (e.g., 0-5). Useful for panels with different multiplexing.
*   `--led-pwm-dither-bits`: Amount of dithering to apply (0-2). 0 = no dithering, higher values use more temporal planes.
*   `--led-pixel-mapper`:  Apply pixel mapping modifications. Supports `U-Mapper` (for serpentine panels) and `Rotate:<angle>` (0, 90, 180, 270). Multiple mappers can be separated by a semicolon (e.g., `U-Mapper;Rotate:180`).
    *   *Note: Rotation and Serpentine options are only available for panels with < 5 address lines.*
*   `--led-transition-mode`: Visual transition effect between screen updates. Options: `none` (default), `fade`, `fade-in`, `fade-out`, `wipe-left`, `wipe-right`, `wipe-up`, `wipe-down`, `curtain-open`, `curtain-close`, `clock-cw`, `clock-ccw`, `random`.
*   `--led-transition-steps`: Number of steps/frames for the transition animation (default: 20).
*   `--led-transition-hold`: Time (in seconds) to hold the previous frame before starting the transition (default: 1.0).
*   `--led-transition-threshold`: Percentage of changed pixels required to trigger a transition (0-100, default: 10).

## Usage

To start the scoreboard on a Raspberry Pi 5:

```bash
sudo python3 pi5_launcher.py
```

*Note: `sudo` is typically required for hardware GPIO access.*

## Troubleshooting

*   **Performance**: If the display is flickering or sluggish, try reducing `--led-pwm-bits` or ensuring no other heavy processes are running.
*   **Colors Swapped**: Use the `--led-rgb-sequence` argument to correct RGB/BGR mismatches (e.g., `--led-rgb-sequence=BGR`).
*   **Permission Errors**: Ensure you are running with `sudo`.

