# Plugin Manager

The plugin manager (`plugins.py`) makes it easy to install, update, and manage board plugins for the NHL LED Scoreboard. Each plugin is a separate git repository that gets cloned into `src/boards/plugins/`.

## Quick Start

```bash
# First time setup: copy the example configuration
cp plugins.json.example plugins.json

# Install all configured plugins
python plugins.py sync

# List installed plugins (shows version, status, commit)
python plugins.py list

# Add a new plugin
python plugins.py add https://github.com/kas21/nls-plugin-nfl_board.git

# Remove a plugin but keep your configuration
python plugins.py rm nfl_board --keep-config

# Enable verbose logging for troubleshooting
python plugins.py --verbose sync
```

## Configuration Files

- **`plugins.json.example`** - Template with recommended plugins
- **`plugins.json`** - Your customized plugin list (you edit this)
- **`plugins.lock.json`** - Auto-generated lock file with exact commit SHAs (tracks what's installed)

## Commands

### `list` - Show Installed Plugins

List all configured plugins with their current version, status, and git commit SHA.

```bash
python plugins.py list
```

**Example output:**

```text
NAME                 VERSION      STATUS       COMMIT
---------------------------------------------------------
nfl_board            2025.11.02   present      a1b2c3d
holiday_countdown    2025.x.x     present      e4f5g6h
example_board        1.0.0        present      i7j8k9l
```

This shows:

- **VERSION** - Plugin version from `plugin.json`
- **STATUS** - Whether plugin files are present or missing
- **COMMIT** - Git commit SHA (first 7 characters)

### `sync` - Install/Update All Plugins

Install or update all plugins defined in `plugins.json`. **This is the main command you'll use regularly.**

```bash
python plugins.py sync
```

**What it does:**

- Installs any plugins that aren't present
- Updates existing plugins to the latest version from main branch
- Preserves your configuration files automatically (see User File Preservation)
- Updates `plugins.lock.json` with exact commit SHAs for reproducibility

**When to use:** Run this after editing `plugins.json` or when you want to update plugins to their latest versions.

### `add` - Install a New Plugin

Add and install a plugin from a git repository. The plugin manager auto-detects the plugin name from the repository's `plugin.json` file.

```bash
# Most common: Install latest version from main branch
python plugins.py add https://github.com/kas21/nls-plugin-nfl_board.git
```

This automatically:

1. Clones the repository
2. Detects the plugin name from `plugin.json`
3. Installs the plugin files
4. Adds an entry to your `plugins.json`
5. Updates `plugins.lock.json` with the commit SHA

**Advanced options** (rarely needed):

```bash
# Install a specific version/tag (for testing or compatibility)
python plugins.py add https://github.com/kas21/nls-plugin-nfl_board.git --ref v1.2.0

# Install from a development branch (for beta testing)
python plugins.py add https://github.com/kas21/nls-plugin-nfl_board.git --ref develop

# Override the detected plugin name (very rare)
python plugins.py add https://github.com/kas21/nls-plugin-nfl_board.git --name custom_name
```

> **Note:** Most users should use the simple `add` command without `--ref`. The `--ref` option is mainly for developers testing specific versions or beta branches.

### `rm` - Remove a Plugin

Remove a plugin from your installation. **Recommended: Always use `--keep-config` to preserve your settings.**

```bash
# Remove plugin but keep your config files (RECOMMENDED)
python plugins.py rm nfl_board --keep-config

# Remove plugin completely including config (rarely needed)
python plugins.py rm nfl_board
```

**What it does:**

- Removes the plugin from `plugins.json`
- Deletes the plugin directory
- If `--keep-config` is used: Preserves your configuration files in the plugin directory

## User File Preservation

The plugin manager automatically preserves your customized files during updates and removals to prevent data loss. **You don't need to do anything special - it just works!**

### What Gets Preserved

By default, these files are automatically preserved:

- `config.json` - Your plugin configuration
- `*.csv` - Any CSV data files
- `data/*` - All files in the data directory
- `custom_*` - Any files starting with "custom_"

Plugins can specify additional files to preserve in their `plugin.json` (see the [plugin development guide](src/boards/plugins/example_board/README.md) for details).

### How It Works

**During updates** (`sync` or `add`):

1. Your files are backed up
2. Plugin is updated to the new version
3. Your files are restored automatically

**During removal** (`rm --keep-config`):

1. Plugin files are deleted
2. Your config files are preserved in the plugin directory
3. You can safely reinstall later without losing your settings

**Example:**

```bash
# Normal workflow - your config is preserved automatically
python plugins.py sync

# Remove plugin but keep your settings for later
python plugins.py rm holiday_countdown_board --keep-config

# Reinstall later - your old config.json will still be there!
python plugins.py add https://github.com/kas21/nls-plugin-holiday-countdown.git
```

## Using Plugins

After installing plugins with the plugin manager, you need to configure them in your main scoreboard configuration.

### 1. Copy Plugin Configuration

Each plugin has a `config.sample.json` file. Copy it to create your configuration:

```bash
cd src/boards/plugins/your_plugin
cp config.sample.json config.json
nano config.json
```

### 2. Add to Main Configuration

Edit `config/config.json` to add the plugin to your board rotation:

```json
"states": {
    "off_day": [
        "your_plugin",
        "clock",
        "scoreticker"
    ]
}
```

### 3. Restart Scoreboard

Restart the scoreboard for changes to take effect:

```bash
sudo systemctl restart nhl-scoreboard
```

## First Time Setup

**Step-by-step guide to get plugins working:**

1. **Clone the nhl-led-scoreboard repo** - It includes `plugins.json.example` with recommended plugins

2. **Copy the example configuration:**

   ```bash
   cp plugins.json.example plugins.json
   ```

3. **Edit `plugins.json`** to customize which plugins you want:

   ```bash
   nano plugins.json
   ```

4. **Install all plugins:**

   ```bash
   python plugins.py sync
   ```

5. **Configure each plugin** (see "Using Plugins" above)

6. **Add plugins to your board rotation** in `config/config.json`

7. **Restart the scoreboard:**

   ```bash
   sudo systemctl restart nhl-scoreboard
   ```

## Troubleshooting

### Plugin Not Loading

**Check these in order:**

1. **Verify plugin is installed:**

   ```bash
   python plugins.py list
   ```

   Look for your plugin - STATUS should be "present"

2. **Check plugin is in your board rotation:**

   Open `config/config.json` and verify the plugin ID is listed in one of the states (e.g., `off_day`, `intermission`)

3. **Check scoreboard logs for errors:**

   ```bash
   sudo tail -50 /var/log/supervisor/nhl-scoreboard-error.log
   sudo tail -50 /var/log/supervisor/nhl-scoreboard.log 
   ```

   Look for error messages mentioning your plugin name

4. **Verify plugin configuration exists:**

   ```bash
   ls src/boards/plugins/your_plugin/config.json
   ```

   If missing, copy from `config.sample.json`

### Update Failed

If `python plugins.py sync` fails to update a plugin:

1. **Check your internet connection**
2. **Try with verbose logging to see detailed errors:**

   ```bash
   python plugins.py --verbose sync
   ```

3. **Verify the git repository URL is correct** in `plugins.json`
4. **Check if the repository is accessible** (try opening the GitHub URL in a browser)

The plugin manager automatically restores the previous version if an update fails, so your installation is safe.

### Configuration Missing After Update

Your configuration should be preserved automatically! If it's missing:

1. **Check if config.json exists:**

   ```bash
   ls src/boards/plugins/your_plugin/config.json
   ```

2. **Look for backup files** in the plugin directory

3. **Copy from the sample:**

   ```bash
   cd src/boards/plugins/your_plugin
   cp config.sample.json config.json
   ```

4. **Report the issue** if this keeps happening - it may be a bug

### Verbose Logging

Enable verbose logging to see detailed information about what the plugin manager is doing:

```bash
python plugins.py --verbose sync
python plugins.py --verbose add https://github.com/user/plugin.git
```

This shows:

- Git commands being executed
- Files being preserved/restored
- Detailed error messages
- Plugin detection process

## Creating Plugins

For detailed information about developing your own plugins, see the [Example Board Plugin README](src/boards/plugins/example_board/README.md), which provides:

- Complete plugin structure documentation
- Code examples and patterns
- Step-by-step development guide
- Best practices and conventions
