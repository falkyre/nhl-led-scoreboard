import sys
import runpy
import numpy as np
import atexit
import argparse
import threading
import time

# 1. Import Target Library
import RGBMatrixEmulator
from RGBMatrixEmulator import RGBMatrix

# 2. Import Piomatter Hardware
import adafruit_blinka_raspberry_pi5_piomatter as piomatter
from adafruit_blinka_raspberry_pi5_piomatter.pixelmappers import simple_multilane_mapper

# --- Global Registry ---
_active_matrices = []

def force_cleanup():
    if _active_matrices:
        print("\n[Pi5 Bridge] Shutting down LED Hardware...")
        for matrix in _active_matrices:
            try:
                # Stop the thread first
                matrix.stop_thread()
                # Clear screen
                if hasattr(matrix, 'pm_framebuffer'):
                    matrix.pm_framebuffer.fill(0)
                    matrix.pm_matrix.show()
            except Exception as e:
                print(f"[Pi5 Bridge] Cleanup error: {e}")

atexit.register(force_cleanup)

# --- Argument Parsing Helper ---
def get_hardware_config():
    # Defaults
    config = {
        'cols': 64, 
        'rows': 32, 
        'mapping': 'regular', 
        'sequence': 'RGB',
        'brightness': 100 # Default to full brightness (0-100)
    }
    
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--led-cols", type=int)
    parser.add_argument("--led-rows", type=int)
    parser.add_argument("--led-gpio-mapping", type=str)
    parser.add_argument("--led-rgb-sequence", type=str)
    # Add brightness argument handling
    parser.add_argument("--led-brightness", type=int)
    
    args, _ = parser.parse_known_args()
    
    if args.led_cols: config['cols'] = args.led_cols
    if args.led_rows: config['rows'] = args.led_rows
    if args.led_gpio_mapping: config['mapping'] = args.led_gpio_mapping
    if args.led_rgb_sequence: config['sequence'] = args.led_rgb_sequence
    if args.led_brightness is not None: config['brightness'] = args.led_brightness

    return config

def get_pinout(mapping_name, is_bgr):
    name = mapping_name.replace('-', '_').lower()
    if name == 'regular':
        return piomatter.Pinout.Active3BGR if is_bgr else piomatter.Pinout.Active3
    elif name == 'adafruit_hat':
        return piomatter.Pinout.AdafruitMatrixHatBGR if is_bgr else piomatter.Pinout.AdafruitMatrixHat
    elif name == 'adafruit_bonnet':
        return piomatter.Pinout.AdafruitMatrixBonnetBGR if is_bgr else piomatter.Pinout.AdafruitMatrixBonnet
    return piomatter.Pinout.Active3BGR if is_bgr else piomatter.Pinout.Active3

# --- The Threaded Matrix Class ---
class PiomatterMatrix(RGBMatrix):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. Config & Hardware Setup
        hw_conf = get_hardware_config()
        self.hw_width = hw_conf['cols']
        self.hw_height = hw_conf['rows']
        is_bgr = (hw_conf['sequence'].upper() == "BGR")
        
        # Calculate Brightness Factor (0.0 to 1.0)
        # We ensure it stays within bounds
        safe_brightness = max(0, min(100, hw_conf['brightness']))
        self.brightness_factor = safe_brightness / 100.0
        
        print(f"[PiomatterMatrix] Initializing Threaded Hardware ({self.hw_width}x{self.hw_height})...")
        print(f"   Brightness: {safe_brightness}% (Factor: {self.brightness_factor})")

        selected_pinout = get_pinout(hw_conf['mapping'], is_bgr)
        n_addr_lines = 5 if self.hw_height >= 64 else 4
        n_lanes = 2

        pixelmap = simple_multilane_mapper(self.hw_width, self.hw_height, n_addr_lines, n_lanes)
        geometry = piomatter.Geometry(
            width=self.hw_width, height=self.hw_height,
            n_addr_lines=n_addr_lines, n_planes=10, 
            n_temporal_planes=0, map=pixelmap, n_lanes=n_lanes
        )

        # Hardware Buffer (Owned by Background Thread)
        self.pm_framebuffer = np.zeros((self.hw_height, self.hw_width, 3), dtype="uint8")
        self.pm_matrix = piomatter.PioMatter(
            colorspace=piomatter.Colorspace.RGB888Packed,
            pinout=selected_pinout,
            framebuffer=self.pm_framebuffer,
            geometry=geometry
        )

        # 2. Threading Setup
        self.shared_buffer = np.zeros((self.hw_height, self.hw_width, 3), dtype="uint8")
        self.buffer_lock = threading.Lock()
        self.new_frame_event = threading.Event()
        self.running = True

        self.thread = threading.Thread(target=self._hardware_loop, daemon=True)
        self.thread.start()

        _active_matrices.append(self)

    def _hardware_loop(self):
        """
        Runs on a separate core/thread. Waits for new data, then pushes to hardware.
        """
        while self.running:
            if self.new_frame_event.wait(timeout=1.0):
                self.new_frame_event.clear()
                
                with self.buffer_lock:
                    np.copyto(self.pm_framebuffer, self.shared_buffer)
                
                try:
                    self.pm_matrix.show()
                except Exception:
                    pass

    def SwapOnVSync(self, canvas, framerate_fraction=0):
        # 1. Update Emulator State
        new_canvas = super().SwapOnVSync(canvas, framerate_fraction)

        # 2. Process Frame and Copy to Shared Buffer
        try:
            adapter = self.canvas.display_adapter
            raw_frame = adapter._last_frame()

            with self.buffer_lock:
                # OPTIMIZATION: Check if we need to apply brightness
                if self.brightness_factor < 1.0:
                    # Apply brightness scaling
                    # 1. Cast to float32 for math
                    # 2. Multiply by factor
                    # 3. Cast back to uint8
                    processed_frame = (raw_frame.astype(np.float32) * self.brightness_factor).astype(np.uint8)
                    
                    if not np.array_equal(processed_frame, self.shared_buffer):
                        np.copyto(self.shared_buffer, processed_frame)
                        self.new_frame_event.set()
                else:
                    # Full brightness - direct copy
                    if not np.array_equal(raw_frame, self.shared_buffer):
                        np.copyto(self.shared_buffer, raw_frame)
                        self.new_frame_event.set()

        except Exception as e:
            pass

        return new_canvas

    def stop_thread(self):
        self.running = False
        self.new_frame_event.set()
        self.thread.join(timeout=1.0)

# --- Injection & Launch ---
RGBMatrixEmulator.RGBMatrix = PiomatterMatrix

print("[Launcher] Starting Threaded NHL Scoreboard...")
try:
    runpy.run_module('main', run_name='__main__')
except KeyboardInterrupt:
    print("\n[Launcher] CTRL-C detected.")
except Exception as e:
    print(f"[Launcher] Error: {e}")
finally:
    force_cleanup()
