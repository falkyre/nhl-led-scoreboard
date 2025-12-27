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
    'serpentine': False
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
    elif name == 'adafruit-hat-pwm': return piomatter.Pinout.AdafruitMatrixBonnetBGR if use_bgr_variant else piomatter.Pinout.AdafruitMatrixBonnet

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
        out = frame
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

# --- EXECUTION START ---
consume_arguments()
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
