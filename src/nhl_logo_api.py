import requests
import json

def get_nhl_logos(target_abbrev="WPG"):
    """
    Fetches historical and current logo URLs for a specific NHL franchise.
    Uses the standings API to figure out exact era divisions so logos never 404.
    Returns a dictionary structured for easy integration or configuration export.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    
    url = "https://api.nhle.com/stats/rest/en/franchise"
    params = [("include", "teams")]
    
    logo_data = {target_abbrev: {}}
    
    try:
        resp = session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        franchises = resp.json().get("data", [])
        
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
                    
        import re
        
        # Scrape through each abbreviation's active seasons to find exact logo URLs and eras
        for abbrev in team_abbrevs:
            seasons_resp = session.get(f"https://api-web.nhle.com/v1/roster-season/{abbrev}", timeout=10)
            if seasons_resp.status_code != 200:
                continue
                
            seasons = seasons_resp.json()
            if not seasons:
                continue
                
            seasons.sort()
            idx = 0
            while idx < len(seasons):
                season = seasons[idx]
                year2 = str(season)[4:]
                date_str = f"{year2}-02-01" # Safe mid-season date
                
                st_resp = session.get(f"https://api-web.nhle.com/v1/standings/{date_str}", timeout=10)
                if st_resp.status_code != 200:
                    idx += 1
                    continue
                    
                st = st_resp.json()
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
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from the NHL API: {e}")
        return None

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
    # Test the function by running this file directly
    logos = get_nhl_logos("CAR")
    
    # Example exports
    export_to_json(logos, "nhl_logos.json")
    export_to_toml(logos, "nhl_logos.toml")