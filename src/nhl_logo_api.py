import json
import urllib.request
import urllib.error
import re
import sys

def _fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def get_nhl_logos(target_abbrev="WPG"):
    """
    Fetches historical and current logo URLs for a specific NHL franchise.
    Uses the standings API to figure out exact era divisions so logos never 404.
    Returns a dictionary structured for easy integration or configuration export.
    """
    url = "https://api.nhle.com/stats/rest/en/franchise?include=teams"
    logo_data = {target_abbrev: {}}
    
    resp_data = _fetch_json(url)
    if not resp_data:
        return logo_data
        
    franchises = resp_data.get("data", [])
    
    target_team_name = ""
    primary_franchise_id = None
    
    # Determine the target's primary franchise and its base name (e.g. without year suffixes)
    for f in franchises:
        for t in f.get("teams", []):
            if t.get("triCode") == target_abbrev:
                target_team_name = t.get("fullName", "").split(" (")[0].strip()
                primary_franchise_id = f.get("id")
                break
        if primary_franchise_id:
            break
            
    if not primary_franchise_id:
        return logo_data
        
    # Find all team abbreviations inside the primary franchise, AND any identically named historic franchises
    team_abbrevs = set()
    for f in franchises:
        is_primary = f.get("id") == primary_franchise_id
        for t in f.get("teams", []):
            abbrev = t.get("triCode")
            if not abbrev:
                continue
            team_base_name = t.get("fullName", "").split(" (")[0].strip()
            if is_primary or team_base_name == target_team_name:
                team_abbrevs.add(abbrev)
                
    # Scrape through each abbreviation's active seasons to find exact logo URLs and eras
    for abbrev in team_abbrevs:
        seasons = _fetch_json(f"https://api-web.nhle.com/v1/roster-season/{abbrev}")
        if getattr(seasons, 'get', None) and seasons.get('message') == 'Not Found': continue
        if not seasons or not isinstance(seasons, list):
            continue
            
        seasons.sort()
        idx = 0
        while idx < len(seasons):
            season = seasons[idx]
            year2 = str(season)[4:]
            date_str = f"{year2}-02-01" # Safe mid-season date
            
            st = _fetch_json(f"https://api-web.nhle.com/v1/standings/{date_str}")
            if not st:
                idx += 1
                continue
                
            logo_url = None
            for t in st.get("standings", []):
                if t.get("teamAbbrev", {}).get("default") == abbrev:
                    logo_url = t.get("teamLogo")
                    break
                    
            if not logo_url:
                idx += 1
                continue
                
            # Extract era from the URL, if it exists
            match = re.search(r"_(\d{8})-(\d{8})_", logo_url)
            if match:
                start_year = match.group(1)[:4]
                end_year = match.group(2)[:4]
                era_key = f"{start_year}-{end_year}"
                logo_end_season = int(match.group(2))
                
                # Fast-forward our sequence past this era
                while idx < len(seasons) and seasons[idx] <= logo_end_season:
                    idx += 1
            else:
                # 'current' logos don't have an era string, assuming they persist to the end
                era_key = "current"
                idx = len(seasons)
                
            light_url = logo_url
            dark_url = logo_url.replace("_light.svg", "_dark.svg")
            
            logo_data[target_abbrev][era_key] = {
                "team_abbrev": abbrev,
                "light_svg": light_url,
                "dark_svg": dark_url
            }
            
    return logo_data

def export_to_json(data, filename="logos.json"):
    """Exports the logo dictionary to a JSON file."""
    if not data:
        return
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    print(f"Successfully exported logos to {filename}")

def export_to_toml(data, filename="config.toml"):
    """Exports the logo dictionary to a TOML file."""
    if not data:
        return
    try:
        import tomli_w
        with open(filename, 'wb') as f:
            tomli_w.dump(data, f)
        print(f"Successfully exported logos to {filename}")
    except ImportError:
        print("To export to TOML, install the library: pip install tomli-w")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: You must provide the triCode of the NHL team to search logos (e.g., WPG)")
        sys.exit(1)
        
    team_code = sys.argv[1].upper()
    logos = get_nhl_logos(team_code)
    
    # Example exports
    export_to_json(logos, f"{team_code}_logos.json")
    export_to_toml(logos, f"{team_code}_logos.toml")