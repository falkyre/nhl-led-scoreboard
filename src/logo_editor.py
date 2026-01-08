import os
import json
import re
import io
import urllib.request
import shutil
import datetime
import subprocess
import signal
import sys
import argparse
from flask import Flask, render_template, request, jsonify, send_from_directory, abort

# --- ARGUMENT PARSING & CONFIGURATION ---
parser = argparse.ArgumentParser(description='NHL LED Scoreboard Logo Editor')
parser.add_argument('--venv', 
                    default=None,
                    help='Path to the virtual environment (default: Detect Active or ~/nhlsb-venv)')
parser.add_argument('--dir', 
                    default=os.getcwd(),
                    help='Path to the scoreboard root directory (default: current working directory)')
parser.add_argument('--port', 
                    default=5000,
                    type=int,
                    help='Port to run the editor web server on (default: 5000)')

args, unknown = parser.parse_known_args()

INSTALL_DIR = os.path.abspath(args.dir)
CONFIG_DIR = os.path.join(INSTALL_DIR, 'config', 'layout')
ASSETS_DIR = os.path.join(INSTALL_DIR, 'assets')
EMULATOR_CONFIG_PATH = os.path.join(INSTALL_DIR, 'emulator_config.json')

# --- ENVIRONMENT DETECTION LOGIC ---
USE_CURRENT_ENV = False
VENV_ACTIVATE_SCRIPT = None

if args.venv:
    VENV_ACTIVATE_SCRIPT = os.path.join(os.path.abspath(args.venv), "bin", "activate")
    print(f"Configuration:")
    print(f" - Scoreboard Dir:     {INSTALL_DIR}")
    print(f" - Virtual Env:        {os.path.abspath(args.venv)} (Explicit)")

elif (hasattr(sys, 'real_prefix') or 
      (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or 
      os.environ.get('CONDA_DEFAULT_ENV')):
    USE_CURRENT_ENV = True
    print(f"Configuration:")
    print(f" - Scoreboard Dir:     {INSTALL_DIR}")
    print(f" - Virtual Env:        Active Environment Detected ({sys.prefix})")

else:
    default_venv = os.path.join(os.path.expanduser("~"), "nhlsb-venv")
    VENV_ACTIVATE_SCRIPT = os.path.join(default_venv, "bin", "activate")
    print(f"Configuration:")
    print(f" - Scoreboard Dir:     {INSTALL_DIR}")
    print(f" - Virtual Env:        {default_venv} (Default)")


try:
    import cairosvg
    from PIL import Image
except ImportError as e:
    print(f"Warning: Image libraries not found ({e}). Logo generation will not work.")
    cairosvg = None

app = Flask(__name__, template_folder='templates')

emulator_process = None
current_layout = {"w": 64, "h": 32} 

TEAMS = [
    "ANA", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NSH", "NJD", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "UTA", "VAN", "VGK", 
    "WSH", "WPG"
]

@app.route('/')
def index():
    emulator_port = 8888
    # Default pixel size if not found in config
    emulator_pixel_size = 10 
    
    if os.path.exists(EMULATOR_CONFIG_PATH):
        try:
            with open(EMULATOR_CONFIG_PATH, 'r') as f:
                data = json.load(f)
                emulator_port = data.get('browser', {}).get('port', 8888)
                
                # Check various locations for pixel_size
                if 'pixel_size' in data:
                    emulator_pixel_size = int(data['pixel_size'])
                elif 'display' in data and 'pixel_size' in data['display']:
                    emulator_pixel_size = int(data['display']['pixel_size'])
        except:
            pass
            
    return render_template('editor.html', 
                           teams=TEAMS, 
                           emulator_port=emulator_port, 
                           emulator_pixel_size=emulator_pixel_size)

# --- EMULATOR CONTROL API ---

@app.route('/api/emulator/status', methods=['GET'])
def emulator_status():
    global emulator_process, current_layout
    running = False
    if emulator_process:
        if emulator_process.poll() is None:
            running = True
        else:
            emulator_process = None 
    return jsonify({
        "running": running,
        "w": current_layout["w"],
        "h": current_layout["h"]
    })

@app.route('/api/emulator/start', methods=['POST'])
def emulator_start():
    global emulator_process, current_layout
    
    if emulator_process:
        if emulator_process.poll() is None:
            try:
                os.killpg(os.getpgid(emulator_process.pid), signal.SIGTERM)
                try:
                    emulator_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(emulator_process.pid), signal.SIGKILL)
            except Exception as e:
                print(f"[Emulator] Error killing previous process: {e}")
        emulator_process = None

    data = request.json
    cols = data.get('w', 64)
    rows = data.get('h', 32)
    current_layout = {"w": cols, "h": rows}
    
    if USE_CURRENT_ENV:
        cmd_str = f"cd {INSTALL_DIR} && {sys.executable} src/main.py --led-cols={cols} --led-rows={rows} --emulated"
    else:
        cmd_str = f"source {VENV_ACTIVATE_SCRIPT} && cd {INSTALL_DIR} && python3 src/main.py --led-cols={cols} --led-rows={rows} --emulated"
    
    print(f"[Emulator] Launching: {cmd_str}")
    
    try:
        emulator_process = subprocess.Popen(
            cmd_str, 
            shell=True, 
            executable='/bin/bash', 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid 
        )
        return jsonify({"status": "success", "pid": emulator_process.pid})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/emulator/stop', methods=['POST'])
def emulator_stop():
    global emulator_process
    if emulator_process:
        try:
            os.killpg(os.getpgid(emulator_process.pid), signal.SIGTERM)
            emulator_process = None
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "not_running"})

# --- EXISTING ROUTES ---

@app.route('/api/files')
def list_files():
    try:
        files = [f for f in os.listdir(CONFIG_DIR) if f.startswith('logos') and f.endswith('.json')]
    except FileNotFoundError:
        files = []
    return jsonify(files)

@app.route('/api/config/<filename>', methods=['GET', 'POST'])
def handle_config(filename):
    file_path = os.path.join(CONFIG_DIR, filename)
    
    if request.method == 'GET':
        if not os.path.exists(file_path):
            base_file = os.path.join(CONFIG_DIR, 'logos_64x32.json')
            if os.path.exists(base_file):
                try:
                    with open(base_file, 'r') as f:
                        base_data = json.load(f)
                    with open(file_path, 'w') as f:
                        json.dump(base_data, f, indent=2)
                except Exception as e:
                    return jsonify({"status": "error", "message": str(e)}), 500
            else:
                return jsonify({})

        with open(file_path, 'r') as f:
            return jsonify(json.load(f))
    
    if request.method == 'POST':
        try:
            if os.path.exists(file_path):
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy2(file_path, f"{file_path}.{timestamp}.bak")
            new_data = request.json
            with open(file_path, 'w') as f:
                json.dump(new_data, f, indent=2)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    full_path = os.path.join(ASSETS_DIR, filename)
    if os.path.exists(full_path):
        return send_from_directory(ASSETS_DIR, filename)
    
    match = re.search(r'logos/([^/]+)/light/(\d+)x(\d+)\.png', filename)
    if match and cairosvg:
        team = match.group(1)
        w = int(match.group(2))
        h = int(match.group(3))
        svg_url = f"https://assets.nhle.com/logos/nhl/svg/{team}_light.svg"
        try:
            with urllib.request.urlopen(svg_url) as response:
                svg_data = response.read()
            png_data = cairosvg.svg2png(bytestring=svg_data, output_height=512)
            with Image.open(io.BytesIO(png_data)) as img:
                img.thumbnail((w, h), Image.Resampling.LANCZOS)
                final_img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
                ox = (w - img.width) // 2
                oy = (h - img.height) // 2
                final_img.paste(img, (ox, oy))
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                final_img.save(full_path)
            return send_from_directory(ASSETS_DIR, filename)
        except:
            pass
    return abort(404)

if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')
    print(f"Starting Editor on http://localhost:{args.port}")
    app.run(port=args.port, debug=True)