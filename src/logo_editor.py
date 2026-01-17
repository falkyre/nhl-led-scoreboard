import os
import json
import re
import io
import urllib.request
import urllib.error
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
except (ImportError, OSError) as e:
    print(f"Warning: Image libraries not found or system dependency missing ({e}). Logo generation will not work.")
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
    emulator_pixel_size = 10 
    
    if os.path.exists(EMULATOR_CONFIG_PATH):
        try:
            with open(EMULATOR_CONFIG_PATH, 'r') as f:
                data = json.load(f)
                emulator_port = data.get('browser', {}).get('port', 8888)
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

# --- HELPER FUNCTIONS ---

def fetch_opponent_team(team_abbr, date_str):
    try:
        # Strip suffix if present (e.g. WSH|alt -> WSH)
        if '|' in team_abbr:
            team_abbr = team_abbr.split('|')[0]
            
        url = f"https://api-web.nhle.com/v1/club-schedule/{team_abbr}/week/{date_str}"
        print(f"[Backend] Fetching schedule: {url}")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        
        target_date = date_str
        for game in data.get("games", []):
            if game.get("gameDate") == target_date:
                # Find opponent
                if game["homeTeam"]["abbrev"] == team_abbr:
                     # We are HOME, Opponent is AWAY
                    return game["awayTeam"]["abbrev"], False
                else:
                    # We are AWAY, Opponent is HOME
                    return game["homeTeam"]["abbrev"], True
        return None
    except Exception as e:
        print(f"[Backend] Error fetching opponent: {e}")
        return None

@app.route('/api/opponent', methods=['GET'])
def get_opponent():
    team = request.args.get('team')
    date_str = request.args.get('date')
    if not team or not date_str:
        return jsonify({"error": "Missing team or date"}), 400
    
    
    result = fetch_opponent_team(team, date_str)
    if result:
        opp_abbr, is_away = result
        return jsonify({"opponent": opp_abbr, "is_away": is_away})
    else:
        return jsonify({"opponent": None}), 404

def fetch_team_schedule(team_abbr, month_str):
    try:
        # Strip suffix if present (e.g. WSH|alt -> WSH)
        if '|' in team_abbr:
            team_abbr = team_abbr.split('|')[0]

        # month_str expected as YYYY-MM
        url = f"https://api-web.nhle.com/v1/club-schedule/{team_abbr}/month/{month_str}"
        print(f"[Backend] Fetching monthly schedule: {url}")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
        
        dates = []
        for game in data.get("games", []):
            dates.append(game.get("gameDate"))
        return dates
    except Exception as e:
        print(f"[Backend] Error fetching schedule: {e}")
        return []

@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    team = request.args.get('team')
    month = request.args.get('month') # YYYY-MM
    if not team or not month:
        return jsonify({"error": "Missing team or month"}), 400
    
    
    dates = fetch_team_schedule(team, month)
    return jsonify({"dates": dates})


@app.route('/api/emulator/check_ready', methods=['GET'])
def emulator_check_ready():
    # Read port from config or default
    port = 8888
    if os.path.exists(EMULATOR_CONFIG_PATH):
        try:
            with open(EMULATOR_CONFIG_PATH, 'r') as f:
                data = json.load(f)
                port = data.get('browser', {}).get('port', 8888)
        except:
            pass
            
    # Check if port is open
    import socket
    try:
        with socket.create_connection(("localhost", port), timeout=1):
            return jsonify({"ready": True})
    except (socket.timeout, ConnectionRefusedError):
        return jsonify({"ready": False})
    except Exception as e:
        print(f"Error checking port: {e}")
        return jsonify({"ready": False})

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

@app.route('/api/emulator/log', methods=['GET'])
def emulator_log():
    try:
        if os.path.exists("emulator.log"):
            with open("emulator.log", "r") as f:
                content = f.read()
            return jsonify({"log": content})
        return jsonify({"log": "No log file found."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    mode = data.get('mode', 'live')
    current_layout = {"w": cols, "h": rows}
    
    cmd_parts = []
    
    if USE_CURRENT_ENV:
        cmd_parts.append(f"cd {INSTALL_DIR}")
        executable = sys.executable
    else:
        cmd_parts.append(f"source {VENV_ACTIVATE_SCRIPT}")
        cmd_parts.append(f"cd {INSTALL_DIR}")
        executable = "python3"

    if mode == 'simulator':
        team = data.get('team')
        date_str = data.get('date')
        speed = data.get('speed', 1.0)
        stop_at_end = data.get('stop_at_end', False)
        
        script_args = f"src/scripts/start_simulation.py --team {team} --date {date_str} --speed {speed}"
        if stop_at_end:
            script_args += " --stop-at-end"
            
        # Add scoreboard args (still needed for main.py invoked by start_simulation?)
        # Actually start_simulation invokes main.py internally.
        # But we need to pass cols/rows to main.py? 
        # start_simulation.py calls generic 'main.run()', which parses args.
        # So we should pass the scoreboard args to start_simulation.py too so it can pass them along?
        # Looking at start_simulation.py: it parses known args, then sets sys.argv for main.
        # So we append scoreboard args to the command line.
        script_args += f" --led-cols={cols} --led-rows={rows} --emulated"
        
        if USE_CURRENT_ENV:
             cmd_parts.append(f"{executable} {script_args}")
        else:
             cmd_parts.append(f"{executable} {script_args}")
             
    else:
        # LIVE MODE
        if USE_CURRENT_ENV:
            cmd_parts.append(f"{executable} src/main.py --led-cols={cols} --led-rows={rows} --emulated")
        else:
            cmd_parts.append(f"{executable} src/main.py --led-cols={cols} --led-rows={rows} --emulated")
            
    cmd_str = " && ".join(cmd_parts)
    
    print(f"[Emulator] Launching: {cmd_str}")
    
    print(f"[Emulator] Launching: {cmd_str}")
    
    try:
        # Open log file
        log_file = open("emulator.log", "w")
        emulator_process = subprocess.Popen(
            cmd_str, 
            shell=True, 
            executable='/bin/bash', 
            stdout=log_file, 
            stderr=subprocess.STDOUT, # Merge stderr into stdout
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
        # Only list logos_*.json for the main dropdown
        files = [f for f in os.listdir(CONFIG_DIR) if f.startswith('logos') and f.endswith('.json')]
    except FileNotFoundError:
        files = []
    return jsonify(files)

@app.route('/api/config/<filename>', methods=['GET', 'POST'])
def handle_config(filename):
    file_path = os.path.join(CONFIG_DIR, filename)
    
    if request.method == 'GET':
        if not os.path.exists(file_path):
            # If requesting a missing logos_ file, create from default
            if filename.startswith('logos_'):
                base_file = os.path.join(CONFIG_DIR, 'logos_64x32.json')
                if os.path.exists(base_file):
                    try:
                        with open(base_file, 'r') as f:
                            base_data = json.load(f)
                        
                        # Inject requested defaults
                        if 'scoreboard' in base_data and 'logos' in base_data['scoreboard']:
                            # Clear out existing team data, keeping only _default structure to be overwritten
                            base_data['scoreboard']['logos'] = {}
                            
                            base_data['scoreboard']['logos']['_default'] = {
                                "zoom": "100%",
                                "position": [0, 0],
                                "flip": 0,
                                "rotate": 0,
                                "crop": [0, 0, 0, 0],
                                "home": {
                                    "zoom": "100%",
                                    "position": [0, 0],
                                    "flip": 0,
                                    "rotate": 0,
                                    "crop": [0, 0, 0, 0]
                                },
                                "away": {
                                    "zoom": "100%",
                                    "position": [0, 0],
                                    "flip": 0,
                                    "rotate": 0,
                                    "crop": [0, 0, 0, 0]
                                }
                            }
                        
                        # Also clean up team_summary logos if present to be consistent
                        if 'team_summary' in base_data and 'logos' in base_data['team_summary']:
                             base_data['team_summary']['logos'] = {
                                 "_default": base_data['team_summary']['logos'].get('_default', {
                                    "zoom": "100%",
                                    "position": [0, 0]
                                 })
                             }

                        return jsonify(base_data)
                    except Exception as e:
                        return jsonify({"status": "error", "message": str(e)}), 500
            
            # If it's a layout_ file or other that doesn't exist, return empty
            if not os.path.exists(file_path):
                return jsonify({})

        with open(file_path, 'r') as f:
            data = json.load(f)
            
        # Ensure _default exists and inject for missing teams
        if filename.startswith('logos_') and 'scoreboard' in data and 'logos' in data['scoreboard']:
            logos = data['scoreboard']['logos']
            default_logo = logos.get('_default')
            
            # If _default is missing in the file, we might want to inject a hardcoded one or one from 64x32?
            # For now, let's assume if it's missing we can't do much or use a safe fallback.
            # But the user request implies using THE _default (which usually exists).
            if default_logo:
                for team in TEAMS:
                    if team not in logos:
                        logos[team] = json.loads(json.dumps(default_logo)) # Deep copy
            
        return jsonify(data)
    
    if request.method == 'POST':
        try:
            if os.path.exists(file_path):
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy2(file_path, f"{file_path}.{timestamp}.bak")
                
                # Limit backups to 5 copies
                try:
                    backups = sorted([
                        f for f in os.listdir(CONFIG_DIR) 
                        if f.startswith(f"{filename}.") and f.endswith(".bak")
                    ])
                    while len(backups) > 5:
                        oldest = backups.pop(0)
                        os.remove(os.path.join(CONFIG_DIR, oldest))
                except Exception as cleanup_error:
                    print(f"Warning: Failed to cleanup old backups: {cleanup_error}")
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
    
    match = re.search(r'logos/([^/]+)/([^/]+)/(\d+)x(\d+)\.png', filename)
    
    if match and cairosvg:
        team = match.group(1)
        logo_type = match.group(2)
        w = int(match.group(3))
        h = int(match.group(4))
        
        svg_suffix = 'light'
        if logo_type in ['alt', 'dark']:
            svg_suffix = 'dark'
            
        svg_url = f"https://assets.nhle.com/logos/nhl/svg/{team}_{svg_suffix}.svg"
        
        try:
            with urllib.request.urlopen(svg_url) as response:
                svg_data = response.read()
        except urllib.error.HTTPError:
            if svg_suffix == 'dark':
                fallback_url = f"https://assets.nhle.com/logos/nhl/svg/{team}_light.svg"
                try:
                    with urllib.request.urlopen(fallback_url) as response:
                        svg_data = response.read()
                except:
                    return abort(404)
            else:
                return abort(404)
        except:
            return abort(404)

        try:
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