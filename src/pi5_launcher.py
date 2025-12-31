import sys
import runpy
import numpy as np
import atexit
import argparse
import threading
import time
import random
import math

# 1. Import Target Library
import RGBMatrixEmulator
from RGBMatrixEmulator import RGBMatrix

# 2. Import Piomatter Hardware
import adafruit_blinka_raspberry_pi5_piomatter as piomatter
from adafruit_blinka_raspberry_pi5_piomatter import Orientation
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

# --- 3. ARGUMENT INTERCEPTOR ---
GLOBAL_HW_CONFIG = {
    'cols': 64, 'rows': 32, 
    'mapping': 'regular', 'sequence': 'RGB',
    'pwm_dither_bits': 0, 'row_addr_type': None, 'pwm_bits': 10,
    'transition_mode': 'none', 
    'transition_steps': 20,
    'transition_hold': 1.0, 
    'transition_threshold': 10,
    'rotation': piomatter.Orientation.Normal,
    'serpentine': False,
    'brightness': 100,
    'color_correction': [1.0, 1.0, 1.0],
    'control_mode': 'app'
}

def consume_arguments():
    global GLOBAL_HW_CONFIG
    args_to_remove = []
    
    def get_arg_value(flag, default_type=str):
        val = None
        for i, arg in enumerate(sys.argv):
            if arg.startswith(flag + "="):
                val = arg.split("=", 1)[1]
                args_to_remove.append(arg)
            elif arg == flag:
                if i + 1 < len(sys.argv):
                    val = sys.argv[i+1]
                    args_to_remove.append(arg)
                    args_to_remove.append(val)
        if val: return default_type(val)
        return None

    # --- Extract Flags ---
    t_mode = get_arg_value("--led-transition-mode", str)
    if t_mode: GLOBAL_HW_CONFIG['transition_mode'] = t_mode
    
    t_steps = get_arg_value("--led-transition-steps", int)
    if t_steps: GLOBAL_HW_CONFIG['transition_steps'] = t_steps
    
    t_hold = get_arg_value("--led-transition-hold", float)
    if t_hold is not None: GLOBAL_HW_CONFIG['transition_hold'] = t_hold

    t_thresh = get_arg_value("--led-transition-threshold", int)
    if t_thresh is not None: GLOBAL_HW_CONFIG['transition_threshold'] = t_thresh

    # --- BRIGHTNESS & COLOR ---
    # Brightness (0-100)
    b_val = get_arg_value("--led-brightness", int)
    if b_val is not None: 
        GLOBAL_HW_CONFIG['brightness'] = max(0, min(100, b_val))

    # Control Mode ('launcher' or 'app')
    c_mode = get_arg_value("--led-control-mode", str)
    if c_mode: 
        if c_mode.lower() in ['launcher', 'app']:
            GLOBAL_HW_CONFIG['control_mode'] = c_mode.lower()

    # Color Correction ("R:G:B" floats)
    cc_val = get_arg_value("--led-color-correction", str)
    if cc_val:
        try:
            parts = [float(x) for x in cc_val.split(':')]
            if len(parts) == 3:
                GLOBAL_HW_CONFIG['color_correction'] = parts
                print(f"[Pi5 Bridge] Color Correction: {parts}")
        except ValueError:
            print(f"[Pi5 Bridge] Warning: Invalid color correction format. Use R:G:B (e.g. 1.0:1.0:1.0)")

    # --- PIXEL MAPPER PARSING ---
    mapper_arg = get_arg_value("--led-pixel-mapper", str)
    if mapper_arg:
        options = mapper_arg.split(';')
        for opt in options:
            opt = opt.strip()
            if opt == "U-Mapper":
                GLOBAL_HW_CONFIG['serpentine'] = True
                print(f"[Pi5 Bridge] Pixel Mapper: U-Mapper (Serpentine=True)")
            elif opt.startswith("Rotate:"):
                angle = opt.split(":")[1]
                if angle == "0":
                    GLOBAL_HW_CONFIG['rotation'] = piomatter.Orientation.Normal
                elif angle == "90":
                    GLOBAL_HW_CONFIG['rotation'] = piomatter.Orientation.CW
                    print(f"[Pi5 Bridge] Pixel Mapper: Rotate 90 (CW)")
                elif angle == "180":
                    GLOBAL_HW_CONFIG['rotation'] = piomatter.Orientation.R180
                    print(f"[Pi5 Bridge] Pixel Mapper: Rotate 180")
                elif angle == "270":
                    GLOBAL_HW_CONFIG['rotation'] = piomatter.Orientation.CCW
                    print(f"[Pi5 Bridge] Pixel Mapper: Rotate 270 (CCW)")
            elif opt.startswith("Mirror:"):
                print(f"[Pi5 Bridge] Warning: Mirror feature ('{opt}') is not available on this hardware.")

    # Hardware Peeking
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--led-cols", type=int)
    parser.add_argument("--led-rows", type=int)
    parser.add_argument("--led-gpio-mapping", type=str)
    parser.add_argument("--led-rgb-sequence", type=str)
    parser.add_argument("--led-pwm-dither-bits", type=int)
    parser.add_argument("--led-row-addr-type", type=int)
    parser.add_argument("--led-pwm-bits", type=int)
    
    known, _ = parser.parse_known_args()
    if known.led_cols: GLOBAL_HW_CONFIG['cols'] = known.led_cols
    if known.led_rows: GLOBAL_HW_CONFIG['rows'] = known.led_rows
    if known.led_gpio_mapping: GLOBAL_HW_CONFIG['mapping'] = known.led_gpio_mapping
    if known.led_rgb_sequence: GLOBAL_HW_CONFIG['sequence'] = known.led_rgb_sequence
    if known.led_pwm_dither_bits is not None: GLOBAL_HW_CONFIG['pwm_dither_bits'] = known.led_pwm_dither_bits
    if known.led_row_addr_type is not None: GLOBAL_HW_CONFIG['row_addr_type'] = known.led_row_addr_type
    if known.led_pwm_bits is not None: GLOBAL_HW_CONFIG['pwm_bits'] = known.led_pwm_bits

    # Clean sys.argv
    for arg in args_to_remove:
        if arg in sys.argv: sys.argv.remove(arg)

def get_pinout(mapping_name, is_bgr):
    name = mapping_name.lower()
    
    use_bgr_variant = is_bgr
    if name == 'regular': return piomatter.Pinout.Active3BGR if use_bgr_variant else piomatter.Pinout.Active3
    elif name == 'adafruit-hat': return piomatter.Pinout.AdafruitMatrixHatBGR if use_bgr_variant else piomatter.Pinout.AdafruitMatrixHat
    #elif name == 'adafruit-hat-pwm': return piomatter.Pinout.AdafruitMatrixBonnetBGR if use_bgr_variant else piomatter.Pinout.AdafruitMatrixBonnet

    return piomatter.Pinout.Active3BGR if use_bgr_variant else piomatter.Pinout.Active3



# --- The Threaded Matrix Class ---
class PiomatterMatrix(RGBMatrix):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        hw_conf = GLOBAL_HW_CONFIG
        self.hw_width = hw_conf['cols']
        self.hw_height = hw_conf['rows']
        
        # --- Configs ---
        self.trans_mode = hw_conf['transition_mode'].lower()
        self.trans_steps = hw_conf['transition_steps']
        self.trans_hold = hw_conf['transition_hold']
        self.trans_threshold = hw_conf['transition_threshold'] / 100.0
        
        self.valid_transitions = [
            'fade', 'fade-in', 'fade-out',
            'wipe-left', 'wipe-right', 'wipe-up', 'wipe-down',
            'curtain-open', 'curtain-close', 'clock-cw', 'clock-ccw'
        ]
        
        if 'clock' in self.trans_mode or 'random' in self.trans_mode:
            y, x = np.mgrid[0:self.hw_height, 0:self.hw_width]
            cy, cx = self.hw_height / 2.0, self.hw_width / 2.0
            angles = np.arctan2(y - cy, x - cx) + (np.pi / 2)
            angles = np.mod(angles, 2 * np.pi) / (2 * np.pi)
            self.angle_map = angles
        else:
            self.angle_map = None

        self.last_logical_frame = np.zeros((self.hw_height, self.hw_width, 3), dtype="uint8")
        self.last_update_time = time.time()
        
        print(f"[Pi5 Bridge] Transition: {self.trans_mode} | Hold: {self.trans_hold}s")

        # --- Brightness & Color & Gamma ---
        self.control_mode = hw_conf['control_mode']
        self.target_brightness = hw_conf['brightness']
        self.color_correction = hw_conf['color_correction']
        
        # We'll cache the active brightness to detect changes
        self.current_brightness = None 
        # Inherit base class brightness if in app mode, but start with config
        if hasattr(self, 'brightness'):
            # If the emulator/base set a value, track it. 
            # Note: RGBMatrixEmulator might initialize self.brightness. 
            # We assume 100 if not set.
            pass

        # Gamma LUTs (Lookup Tables)
        # We will generate these on the fly if brightness/color changes.
        self.gamma_luts = [None, None, None]
        self._update_luts(self.target_brightness)



        # --- Sequence ---
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

        # --- GEOMETRY CONSTRUCTION ---
        geometry_kwargs = {
            "width": self.hw_width, "height": self.hw_height,
            "n_planes": n_planes, "n_addr_lines": n_addr_lines, 
            "n_temporal_planes": n_temporal
        }
        
        # LOGIC FIX:
        # If n_addr_lines < 5, we CAN pass rotation and serpentine.
        # If n_addr_lines >= 5, we CANNOT pass them (driver limitation).
        if n_addr_lines < 5:
             geometry_kwargs["rotation"] = hw_conf['rotation']
             geometry_kwargs["serpentine"] = hw_conf['serpentine']
        else:
            # Check if user tried to set them and warn them
            if hw_conf['rotation'] != piomatter.Orientation.Normal:
                print(f"[Pi5 Bridge] Warning: Rotation ignored on 5-line panels.")
            if hw_conf['serpentine']:
                print(f"[Pi5 Bridge] Warning: Serpentine mapping ignored on 5-line panels.")

        mapping_key = hw_conf['mapping'].replace('-', '_').lower()
        if mapping_key == 'regular':
            geometry_kwargs["map"] = simple_multilane_mapper(self.hw_width, self.hw_height, n_addr_lines, n_lanes)

        # --- DEBUG INFO ---
        debug_geo = geometry_kwargs.copy()
        if 'map' in debug_geo:
            debug_geo['map'] = f"<PixelMap with {len(debug_geo['map'])} entries>"
        print(f"[Pi5 Bridge] DEBUG: Using Pinout: {selected_pinout}")
        print(f"[Pi5 Bridge] DEBUG: Geometry Config: {debug_geo}")

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

    def _push_frame(self, frame):
        # 1. Determine active brightness
        if self.control_mode == 'app':
            # Check native property (set by NHL-LED-Scoreboard via RGBMatrixEmulator)
            # RGBMatrixEmulator usually stores it in self.brightness (0-100)
            app_brightness = getattr(self, 'brightness', 10000) # Assuming 100 if missing
            if app_brightness != self.current_brightness:
                self._update_luts(app_brightness)
        
        # 2. Apply Look-Up Tables (Gamma + Brightness + Color)
        # frame is (H, W, 3). We apply LUTs per channel.
        # This is efficient in NumPy.
        out = np.empty_like(frame)
        out[:, :, 0] = self.gamma_luts[0][frame[:, :, 0]]
        out[:, :, 1] = self.gamma_luts[1][frame[:, :, 1]]
        out[:, :, 2] = self.gamma_luts[2][frame[:, :, 2]]

        # 3. Reorder for Hardware (if needed, e.g. RBG)
        if self.reorder_indices:
            out = out[:, :, self.reorder_indices]
            
        with self.buffer_lock:
            if not np.array_equal(out, self.shared_buffer):
                np.copyto(self.shared_buffer, out)
                self.new_frame_event.set()

    def SwapOnVSync(self, canvas, framerate_fraction=0):
        new_canvas = super().SwapOnVSync(canvas, framerate_fraction)

        try:
            adapter = self.canvas.display_adapter
            new_frame = adapter._last_frame()

            if np.array_equal(new_frame, self.last_logical_frame):
                pass 
            else:
                now = time.time()
                time_diff = now - self.last_update_time
                
                changed_pixels = np.count_nonzero(np.any(new_frame != self.last_logical_frame, axis=2))
                change_pct = changed_pixels / (self.hw_width * self.hw_height)

                should_transition = False
                if self.trans_mode != 'none' and self.trans_steps > 1:
                    if time_diff >= self.trans_hold:
                        if change_pct >= self.trans_threshold:
                            should_transition = True

                if should_transition:
                    self._run_transition(self.last_logical_frame, new_frame)
                else:
                    self._push_frame(new_frame)
                
                np.copyto(self.last_logical_frame, new_frame)
                self.last_update_time = now

        except Exception as e:
            pass
        return new_canvas

    def _run_transition(self, old_frame, new_frame):
        rows, cols, _ = old_frame.shape
        steps = self.trans_steps
        
        current_mode = self.trans_mode
        if current_mode == 'random':
            current_mode = random.choice(self.valid_transitions)
            
        if 'fade' in current_mode:
            f_old = old_frame.astype(np.float32)
            f_new = new_frame.astype(np.float32)

        for i in range(1, steps + 1):
            t = i / float(steps)
            
            # --- FADE LOGIC TWEAKED ---
            if current_mode == 'fade':
                # Cross Dissolve
                final = ((f_old * (1.0 - t)) + (f_new * t)).astype(np.uint8)
            elif current_mode == 'fade-in':
                # Black -> New
                final = (f_new * t).astype(np.uint8)
            elif current_mode == 'fade-out':
                # Old -> Black
                final = (f_old * (1.0 - t)).astype(np.uint8)

            # --- WIPES ---
            elif current_mode == 'wipe-right':
                split = int(cols * t)
                final = old_frame.copy()
                final[:, :split] = new_frame[:, :split]
            elif current_mode == 'wipe-left':
                split = int(cols * (1-t))
                final = old_frame.copy()
                final[:, split:] = new_frame[:, split:]
            elif current_mode == 'wipe-down':
                split = int(rows * t)
                final = old_frame.copy()
                final[:split, :] = new_frame[:split, :]
            elif current_mode == 'wipe-up':
                split = int(rows * (1-t))
                final = old_frame.copy()
                final[split:, :] = new_frame[split:, :]
            elif current_mode == 'curtain-open':
                split = int((cols / 2) * t)
                center = cols // 2
                final = old_frame.copy()
                final[:, center - split : center + split] = new_frame[:, center - split : center + split]
            elif current_mode == 'curtain-close':
                split = int((cols / 2) * t)
                final = old_frame.copy()
                final[:, :split] = new_frame[:, :split]
                final[:, cols - split:] = new_frame[:, cols - split:]
            elif current_mode == 'clock-cw':
                mask = self.angle_map <= t
                final = np.where(mask[:, :, None], new_frame, old_frame)
            elif current_mode == 'clock-ccw':
                mask = self.angle_map >= (1.0 - t)
                final = np.where(mask[:, :, None], new_frame, old_frame)
            else:
                final = new_frame

            self._push_frame(final)
            time.sleep(0.01)

        # --- CRITICAL FIX ---
        # Force the final frame to be the clean 'new_frame'.
        # This fixes "fade-out" hanging on black, and ensures all wipes finish completely.
        self._push_frame(new_frame)

    def stop_thread(self):
        self.running = False
        self.new_frame_event.set()
        self.thread.join(timeout=1.0)

    def _update_luts(self, brightness_val):
        """Re-calculates the 3-channel Gamma Correction LUT based on brightness & color correction."""
        # Standard Gamma for LEDs is often 2.2 to 2.8. 
        # We'll stick to 2.2 as a safe default for "rich" colors.
        gamma = 2.2
        
        # brightness_val is 0-100. Convert to 0.0-1.0
        b_factor = brightness_val / 100.0
        
        # Create a linear ramp 0-255
        raw_ramp = np.arange(256, dtype=np.float32) / 255.0
        
        for ch in range(3): # R, G, B
            # 1. Apply Color Correction (White Balance)
            scale = self.color_correction[ch]
            
            # 2. Apply Brightness
            linear = raw_ramp * scale * b_factor
            
            # 3. Apply Gamma Curve
            corrected = np.power(linear, gamma) * 255.0
            
            # Clip and cast
            self.gamma_luts[ch] = np.clip(corrected, 0, 255).astype(np.uint8)
            
        self.current_brightness = brightness_val


def run_color_test():
    """Displays a simple color test pattern (R, G, B) with labels."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import tty
        import termios
    except ImportError as e:
        print(f"[Pi5 Bridge] Error: Missing dependencies for color test ({e}). Please install them.")
        return

    print("[Pi5 Bridge] Starting Color Test Mode...")
    print("Controls: r/R (Red), g/G (Green), b/B (Blue) to adjust. CTRL-C to exit.")
    
    # Initialize Matrix
    # We need to pass an options object that mimics RGBMatrixOptions
    class MockOptions:
        def __init__(self):
            self.cols = GLOBAL_HW_CONFIG['cols']
            self.rows = GLOBAL_HW_CONFIG['rows']
            self.chain_length = 1
            self.parallel = 1
            self.pwm_bits = 11
            self.brightness = GLOBAL_HW_CONFIG['brightness']
            self.pwm_lsb_nanoseconds = 130
            self.led_rgb_sequence = "RGB"
            self.pixel_mapper_config = ""
            self.panel_type = ""
            self.drop_privileges = False
            self.gpio_slowdown = 1
            self.daemon = False
            self.drop_privileges = False

    options = MockOptions()
    matrix = PiomatterMatrix(options=options)
    
    # Create Image
    width, height = matrix.hw_width, matrix.hw_height
    
    # Calculate Dimensions
    row_h = height // 4
    # Use similar width to the old squares for the gradient bar
    bar_width = int(row_h * 0.8)
    padding = int(row_h * 0.1)
    
    try:
        # Try to load a font, otherwise use default
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(row_h * 0.6))
    except:
        font = ImageFont.load_default()

    def draw_test_pattern():
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # 1. Draw Grayscale Gradient Bar (Left Side)
        # We want a gradient from White (top) to Black (bottom) for checking tint at all intensities.
        x_start = padding
        x_end = padding + bar_width
        
        y_grad_start = padding
        y_grad_end = height - padding
        grad_height = y_grad_end - y_grad_start
        
        if grad_height > 0:
            for y in range(grad_height):
                # Value goes from 255 (top) to 0 (bottom)
                val = int(255 * (1.0 - (y / grad_height)))
                # Draw a horizontal line for this y
                draw.line([(x_start, y_grad_start + y), (x_end, y_grad_start + y)], fill=(val, val, val))

        # 2. Draw Labels with current correction values
        # Format: (Text, ValueIndex, Color)
        items = [
            ("R:", 0, (255, 0, 0)),
            ("G:", 1, (0, 255, 0)),
            ("B:", 2, (0, 0, 255))
        ]

        text_x = padding + bar_width + padding # Right of the bar

        for i, (text, val_idx, color) in enumerate(items):
            y_start = i * row_h
            
            # Draw Text centered in its row
            val = matrix.color_correction[val_idx]
            label = f"{text} {val:.1f}"
            
            # Centering text vertically in the row roughly
            text_y = y_start + (row_h - int(row_h * 0.6)) // 2 
            
            draw.text((text_x, text_y), label, font=font, fill=color)
        
        # 3. Draw Brightness Label in 4th row
        b_val = matrix.target_brightness
        label_bright = f"BR: {b_val}"
        
        y_start = 3 * row_h
        text_y = y_start + (row_h - int(row_h * 0.6)) // 2
        
        draw.text((text_x, text_y), label_bright, font=font, fill=(150, 150, 150))
        
        return np.array(image)

    # --- Helper for Key Input ---
    def get_key():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    # --- Initial Setup ---
    # Draw initial frame
    frame = draw_test_pattern()
    matrix._push_frame(frame)
    
    # Show initial correction
    cc = matrix.color_correction
    print(f"Current Correction: R:{cc[0]:.1f} G:{cc[1]:.1f} B:{cc[2]:.1f} Bright:{matrix.target_brightness}   ", end="", flush=True)

    # Loop with Input
    try:
        while True:
             # Wait for key
            key = get_key()
            if ord(key) == 3: # CTRL-C
                raise KeyboardInterrupt
            
            # Adjust values
            step = 0.1
            changed = False
            
            if key == 'r':
                matrix.color_correction[0] -= step
                changed = True
            elif key == 'R':
                matrix.color_correction[0] += step
                changed = True
            elif key == 'g':
                matrix.color_correction[1] -= step
                changed = True
            elif key == 'G':
                matrix.color_correction[1] += step
                changed = True
            elif key == 'b':
                matrix.color_correction[2] -= step
                changed = True
            elif key == 'B':
                matrix.color_correction[2] += step
                changed = True
            elif key == '0': # Reset
                matrix.color_correction = [1.0, 1.0, 1.0]
                changed = True
            elif key == 'v': # Brightness Down
                matrix.target_brightness = max(0, matrix.target_brightness - 5)
                changed = True
            elif key == 'V': # Brightness Up
                matrix.target_brightness = min(100, matrix.target_brightness + 5)
                changed = True
            
            if changed:
                # Clamp and update
                for i in range(3):
                    matrix.color_correction[i] = max(0.0, matrix.color_correction[i])
                
                # Update hardware LUTS
                matrix._update_luts(matrix.target_brightness)
                
                # Redraw frame with new values
                frame = draw_test_pattern()
                
                # Re-push frame to apply new LUTs
                matrix._push_frame(frame)
                
                # Update Text
                cc = matrix.color_correction
                print(f"\rCurrent Correction: R:{cc[0]:.1f} G:{cc[1]:.1f} B:{cc[2]:.1f} Bright:{matrix.target_brightness}   ", end="", flush=True)

    except KeyboardInterrupt:
        print("\n\n[Pi5 Bridge] Test Ended.")
        cc = matrix.color_correction
        print(f"To use these settings, add these flags to your command:")
        print(f"  --led-color-correction={cc[0]:.1f}:{cc[1]:.1f}:{cc[2]:.1f}")
        print(f"  --led-brightness={matrix.target_brightness}")
        print("")

    finally:
        matrix.stop_thread()
        print("")



# --- EXECUTION START ---
consume_arguments()

# Check for Color Test Flag
is_color_test = False
for arg in sys.argv:
    if arg == "--led-color-test":
        is_color_test = True
        break

if is_color_test:
    # Remove the flag so it doesn't mess up anything else potentially, though we aren't running main
    if "--led-color-test" in sys.argv:
        sys.argv.remove("--led-color-test")
    run_color_test()
else:
    RGBMatrixEmulator.RGBMatrix = PiomatterMatrix
    
    print("[Launcher] Starting Scoreboard...")
    try:
        runpy.run_module('main', run_name='__main__')
    except KeyboardInterrupt:
        print("\n[Launcher] CTRL-C detected.")
    except Exception as e:
        print(f"[Launcher] Error: {e}")
    finally:
        force_cleanup()