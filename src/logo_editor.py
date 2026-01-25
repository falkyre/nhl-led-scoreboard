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
                    default=None,
                    help='Path to the scoreboard root directory (default: auto-detected)')
parser.add_argument('--port', 
                    default=5000,
                    type=int,
                    help='Port to run the editor web server on (default: 5000)')

args, unknown = parser.parse_known_args()

if args.dir:
    INSTALL_DIR = os.path.abspath(args.dir)
else:
    # Use the directory of the script to find the root
    # Assuming script is in src/logo_editor.py, so root is one level up
    INSTALL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONFIG_DIR = os.path.join(INSTALL_DIR, 'config', 'layout')
ASSETS_DIR = os.path.join(INSTALL_DIR, 'assets')
DATA_DIR = os.path.join(INSTALL_DIR, 'src', 'data')
COLORS_FILE = os.path.join(INSTALL_DIR, 'config', 'colors', 'teams.json')
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

# --- TEAM DATA LOADING ---
TEAM_MAPPING = {} # triCode -> ID
try:
    with open(os.path.join(DATA_DIR, 'backup_teams_data.json'), 'r') as f:
        data = json.load(f)
        for team in data.get('data', []):
            code = team.get('triCode')
            tid = team.get('id')
            if code and tid:
                TEAM_MAPPING[code] = str(tid)
    print(f"[Backend] Loaded {len(TEAM_MAPPING)} teams into mapping.")
except Exception as e:
    print(f"[Backend] Error loading team data: {e}") 

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
        
        games_data = []
        for game in data.get("games", []):
            game_date = game.get("gameDate")
            # Determine if home or away
            is_home = (game.get("homeTeam", {}).get("abbrev") == team_abbr)
            games_data.append({
                "date": game_date,
                "type": "home" if is_home else "away"
            })
        return games_data
    except Exception as e:
        print(f"[Backend] Error fetching schedule: {e}")
        return []

@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    team = request.args.get('team')
    month = request.args.get('month') # YYYY-MM
    if not team or not month:
        return jsonify({"error": "Missing team or month"}), 400
    
    
    games = fetch_team_schedule(team, month)
    return jsonify({"games": games})


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

@app.route('/api/colors', methods=['GET', 'POST'])
def handle_colors():
    if request.method == 'GET':
        team = request.args.get('team')
        if not team:
            return jsonify({"error": "Missing team"}), 400
        
        # Clean team code
        if '|' in team:
            team = team.split('|')[0]
            
        tid = TEAM_MAPPING.get(team)
        if not tid:
             return jsonify({"error": f"Unknown team code: {team}"}), 404
             
        try:
            if not os.path.exists(COLORS_FILE):
                return jsonify({"error": "Colors file not found"}), 404
                
            with open(COLORS_FILE, 'r') as f:
                colors_data = json.load(f)
            
            team_colors = colors_data.get(tid, {})
            # Return defaults if empty
            if not team_colors:
                 return jsonify({"primary": {"r":0,"g":0,"b":0}, "text": {"r":255,"g":255,"b":255}})
                 
            return jsonify(team_colors)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if request.method == 'POST':
        data = request.json
        team = data.get('team')
        primary = data.get('primary') # {r,g,b}
        text = data.get('text')       # {r,g,b}
        
        if not team or not primary or not text:
            return jsonify({"error": "Missing data"}), 400

        # Clean team code
        if '|' in team:
            team = team.split('|')[0]

        tid = TEAM_MAPPING.get(team)
        if not tid:
             return jsonify({"error": f"Unknown team code: {team}"}), 404
        
        try:
            # Load existing
            if os.path.exists(COLORS_FILE):
                with open(COLORS_FILE, 'r') as f:
                    colors_data = json.load(f)
            else:
                colors_data = {}
            
            # Update
            if tid not in colors_data:
                colors_data[tid] = {}
            
            colors_data[tid]['primary'] = primary
            colors_data[tid]['text'] = text
            
            # Save
            with open(COLORS_FILE, 'w') as f:
                json.dump(colors_data, f, indent=4)
                
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/upload_alt', methods=['POST'])
def upload_alt_logo():
    team = request.form.get('team')
    create_hires = request.form.get('create_hires') == 'true'
    img_bytes = None
    
    # Check for file or URL
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        img_bytes = file.read()
    elif 'url' in request.form and request.form.get('url'):
        url = request.form.get('url')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                content_type = response.info().get_content_type()
                if content_type == 'text/html':
                    return jsonify({
                        "status": "error", 
                        "message": "The URL provided appears to be a webpage, not an image. Please right-click the image and select 'Copy Image Address' (or 'Copy Image Link')."
                    }), 400
                img_bytes = response.read()
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to download image: {str(e)}"}), 400
    else:
        return jsonify({"status": "error", "message": "No file or URL provided"}), 400

    if not team:
        return jsonify({"status": "error", "message": "Missing team"}), 400

    try:
        # Determine target dimensions based on current layout
        w = current_layout.get('w', 64)
        h = current_layout.get('h', 32)
        
        # Dimensions to generate
        targets = [{"w": w, "h": h}]
        if create_hires:
            targets.append({"w": 128, "h": 64})
            
        saved_files = []
        
        for tgt in targets:
            tw, th = tgt['w'], tgt['h']
            filename = f"{tw}x{th}.png"
            directory = os.path.join(ASSETS_DIR, 'logos', team, 'alt')
            full_path = os.path.join(directory, filename)
            
            os.makedirs(directory, exist_ok=True)
            
            # Backup existing
            if os.path.exists(full_path):
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy2(full_path, f"{full_path}.{timestamp}.bak")
                
                # Limit backups (optional, similar to config)
                try:
                    backups = sorted([
                        f for f in os.listdir(directory) 
                        if f.startswith(f"{filename}.") and f.endswith(".bak")
                    ])
                    while len(backups) > 5:
                        oldest = backups.pop(0)
                        os.remove(os.path.join(directory, oldest))
                except:
                    pass

            # Check if it's an SVG and convert if possible
            is_svg = False
            # Simple check for SVG header/content
            if img_bytes.strip().startswith(b'<svg') or (b'<?xml' in img_bytes[:100] and b'<svg' in img_bytes[:300]):
                is_svg = True
            
            # Additional check: If URL ends in .svg or file content type (touched via filename earlier but we have bytes now)
            
            if is_svg:
                if cairosvg:
                    print("[Upload] Detected SVG, converting to PNG...")
                    try:
                        img_bytes = cairosvg.svg2png(bytestring=img_bytes, output_height=512)
                    except Exception as e:
                        print(f"[Upload] SVG conversion failed: {e}")
                        # Let it fall through to PIL to fail if it really is bad
                else:
                    print("[Upload] Warning: SVG uploaded but cairosvg not available.")

            # Resize and Save
            with Image.open(io.BytesIO(img_bytes)) as img:
                # Convert to RGBA
                img = img.convert("RGBA")
                
                # Resize using thumbnail to preserve aspect ratio, then paste on center
                img.thumbnail((tw, th), Image.Resampling.LANCZOS)
                final_img = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
                ox = (tw - img.width) // 2
                oy = (th - img.height) // 2
                final_img.paste(img, (ox, oy))
                
                final_img.save(full_path)
                saved_files.append(filename)

        # --- UPDATE CONFIG ---
        # Ensure the 'alt' key exists in the current config file for this team
        # so it appears in the dropdown
        config_filename = f"logos_{w}x{h}.json"
        config_path = os.path.join(CONFIG_DIR, config_filename)
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                
                updated = False
                if 'scoreboard' in config_data and 'logos' in config_data['scoreboard']:
                    logos = config_data['scoreboard']['logos']
                    
                    # Ensure team exists
                    if team not in logos:
                        # Copy default if exists
                        default_logo = logos.get('_default')
                        if default_logo:
                             logos[team] = json.loads(json.dumps(default_logo))
                             updated = True
                    
                    if team in logos:
                        if 'alt' not in logos[team]:
                            # Create alt from default 'home' or just generic default
                            # Use home as base but ensure it's empty/resettable?
                            # Or just copy the structure.
                            # Usually alt structure mimics home/away structure
                            base_struct = logos[team].get('home', {
                                "zoom": "100%",
                                "position": [0, 0],
                                "flip": 0,
                                "rotate": 0,
                                "crop": [0, 0, 0, 0]
                            })
                            logos[team]['alt'] = json.loads(json.dumps(base_struct))
                            updated = True
                
                if updated:
                    with open(config_path, 'w') as f:
                        json.dump(config_data, f, indent=2)
                        
            except Exception as e:
                print(f"Warning: Failed to update config file for ALT logo: {e}")

        return jsonify({"status": "success", "files": saved_files})

    except Exception as e:
        print(f"Upload error: {e}")
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

        # If height is 32, force use of 64x32 logos (don't download 128x32 etc)
        if h == 32 and w != 64:
            return serve_assets(filename.replace(f"{w}x{h}", "64x32"))
        
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