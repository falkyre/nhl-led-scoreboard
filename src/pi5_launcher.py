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
                matrix.stop_thread()
                if hasattr(matrix, 'pm_framebuffer'):
                    matrix.pm_framebuffer.fill(0)
                    matrix.pm_matrix.show()
            except Exception as e:
                print(f"[Pi5 Bridge] Cleanup error: {e}")

atexit.register(force_cleanup)

# --- Argument Parsing Helper ---
def get_hardware_config():
    config = {
        'cols': 64, 'rows': 32, 
        'mapping': 'regular', 'sequence': 'RGB',
        'brightness': 100,
        'pwm_dither_bits': 0, 'row_addr_type': None, 'pwm_bits': 10 
    }
    
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--led-cols", type=int)
    parser.add_argument("--led-rows", type=int)
    parser.add_argument("--led-gpio-mapping", type=str)
    parser.add_argument("--led-rgb-sequence", type=str)
    parser.add_argument("--led-brightness", type=int)
    parser.add_argument("--led-pwm-dither-bits", type=int)
    parser.add_argument("--led-row-addr-type", type=int)
    parser.add_argument("--led-pwm-bits", type=int)
    
    args, _ = parser.parse_known_args()
    
    if args.led_cols: config['cols'] = args.led_cols
    if args.led_rows: config['rows'] = args.led_rows
    if args.led_gpio_mapping: config['mapping'] = args.led_gpio_mapping
    if args.led_rgb_sequence: config['sequence'] = args.led_rgb_sequence
    if args.led_brightness is not None: config['brightness'] = args.led_brightness
    if args.led_pwm_dither_bits is not None: config['pwm_dither_bits'] = args.led_pwm_dither_bits
    if args.led_row_addr_type is not None: config['row_addr_type'] = args.led_row_addr_type
    if args.led_pwm_bits is not None: config['pwm_bits'] = args.led_pwm_bits

    return config

def get_pinout(mapping_name, is_bgr):
    name = mapping_name.replace('-', '_').lower()
    use_bgr_variant = is_bgr
    if name == 'regular': return piomatter.Pinout.Active3BGR if use_bgr_variant else piomatter.Pinout.Active3
    elif name == 'adafruit_hat': return piomatter.Pinout.AdafruitMatrixHatBGR if use_bgr_variant else piomatter.Pinout.AdafruitMatrixHat
    elif name == 'adafruit_bonnet': return piomatter.Pinout.AdafruitMatrixBonnetBGR if use_bgr_variant else piomatter.Pinout.AdafruitMatrixBonnet
    return piomatter.Pinout.Active3BGR if use_bgr_variant else piomatter.Pinout.Active3


# --- THE RESHADER CLASS ---
class FrameReshader:
    """
    Adapts the palette reshading logic to work on full framebuffers.
    Uses Linear scaling + a 'Floor Clamp' to prevent pixels from vanishing.
    """
    def __init__(self, brightness_percent):
        # Store brightness as a float 0.0 - 1.0
        self.brightness = max(0.01, brightness_percent / 100.0) 

    def reshade(self, frame):
        """
        Takes a raw uint8 frame, scales it by brightness, 
        and ensures no non-black pixel becomes black.
        """
        # 1. Linear Scaling (mimicking the reshader math)
        # We use float32 for intermediate precision
        shaded = frame.astype(np.float32) * self.brightness
        
        # 2. Convert back to integer (truncating)
        output = shaded.astype(np.uint8)

        # 3. The "Rescue" Mask (Crucial for Low Brightness)
        # If the original frame had a pixel > 0, but the output is 0,
        # we force it to 1. This prevents the "missing portions" issue.
        if self.brightness < 0.1: # Only needed at very low brightness
            mask = (frame > 0) & (output == 0)
            output[mask] = 1
            
        return output


# --- The Threaded Matrix Class ---
class PiomatterMatrix(RGBMatrix):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        hw_conf = get_hardware_config()
        self.hw_width = hw_conf['cols']
        self.hw_height = hw_conf['rows']
        
        # --- Initialize Reshader ---
        print(f"[Pi5 Bridge] Reshader Active | Brightness: {hw_conf['brightness']}%")
        self.reshader = FrameReshader(hw_conf['brightness'])

        # --- Sequence Handling ---
        seq = hw_conf['sequence'].upper()
        is_native_bgr = (seq == "BGR")
        is_native_rgb = (seq == "RGB")
        self.reorder_indices = None
        if not (is_native_rgb or is_native_bgr):
            try:
                channel_map = {'R': 0, 'G': 1, 'B': 2}
                self.reorder_indices = [channel_map[char] for char in seq]
            except KeyError:
                self.reorder_indices = None

        # --- Hardware Config ---
        dither_input = hw_conf['pwm_dither_bits']
        n_temporal = 2 if dither_input == 1 else (4 if dither_input >= 2 else 0)
        raw_pwm_bits = hw_conf['pwm_bits']
        n_planes = min(10, max(1, raw_pwm_bits))
        n_addr_lines = hw_conf['row_addr_type'] if hw_conf['row_addr_type'] is not None else (5 if self.hw_height >= 64 else 4)

        selected_pinout = get_pinout(hw_conf['mapping'], is_native_bgr)
        n_lanes = 2

        geometry_kwargs = {
            "width": self.hw_width, "height": self.hw_height,
            "n_addr_lines": n_addr_lines, "n_planes": n_planes,
            "n_temporal_planes": n_temporal, "n_lanes": n_lanes
        }
        mapping_key = hw_conf['mapping'].replace('-', '_').lower()
        if mapping_key == 'regular':
            geometry_kwargs["map"] = simple_multilane_mapper(self.hw_width, self.hw_height, n_addr_lines, n_lanes)

        geometry = piomatter.Geometry(**geometry_kwargs)

        self.pm_framebuffer = np.zeros((self.hw_height, self.hw_width, 3), dtype="uint8")
        self.pm_matrix = piomatter.PioMatter(
            colorspace=piomatter.Colorspace.RGB888Packed,
            pinout=selected_pinout,
            framebuffer=self.pm_framebuffer,
            geometry=geometry
        )

        # --- Threading ---
        self.shared_buffer = np.zeros((self.hw_height, self.hw_width, 3), dtype="uint8")
        self.buffer_lock = threading.Lock()
        self.new_frame_event = threading.Event()
        self.running = True

        self.thread = threading.Thread(target=self._hardware_loop, daemon=True)
        self.thread.start()

        _active_matrices.append(self)

    def _hardware_loop(self):
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
        new_canvas = super().SwapOnVSync(canvas, framerate_fraction)

        try:
            adapter = self.canvas.display_adapter
            raw_frame = adapter._last_frame()

            with self.buffer_lock:
                # 1. Reshade (Apply Linear Brightness + Rescue Mask)
                processed_frame = self.reshader.reshade(raw_frame)
                
                # 2. Reorder Color Channels if needed
                if self.reorder_indices:
                    processed_frame = processed_frame[:, :, self.reorder_indices]

                if not np.array_equal(processed_frame, self.shared_buffer):
                    np.copyto(self.shared_buffer, processed_frame)
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

print("[Launcher] Starting Reshader Bridge...")
try:
    runpy.run_module('main', run_name='__main__')
except KeyboardInterrupt:
    print("\n[Launcher] CTRL-C detected.")
except Exception as e:
    print(f"[Launcher] Error: {e}")
finally:
    force_cleanup()
