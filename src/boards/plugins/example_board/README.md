# Example Board Plugin

A simple example board plugin demonstrating the NHL LED Scoreboard plugin architecture. This serves as both a working example and a comprehensive development guide for creating your own plugins.

## Table of Contents

- [Using This Plugin](#using-this-plugin)
- [Plugin Development Guide](#plugin-development-guide)
  - [Required Files](#required-files)
  - [Plugin Structure](#plugin-structure)
  - [plugin.json - Metadata](#pluginjson---metadata)
  - [\_\_init\_\_.py - Module Initialization](#__init__py---module-initialization)
  - [board.py - Implementation](#boardpy---implementation)
  - [Configuration Files](#configuration-files)
  - [Layout Files](#layout-files)
- [Creating Your Own Plugin](#creating-your-own-plugin)
- [Best Practices](#best-practices)

## Using This Plugin

This plugin is included with the NHL LED Scoreboard as an example. To enable it:

### 1. Copy Configuration

```bash
cd src/boards/plugins/example_board
cp config.sample.json config.json
nano config.json
```

### 2. Configure Display

Edit the configuration options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `message` | String | "Plugin System Works!" | Custom message to display |
| `text_color` | String | "cyan" | Color of the message text |
| `display_seconds` | Integer | 5 | Seconds to display the board |
| `enabled` | Boolean | true | Enable/disable the board |

### 3. Add to Board Rotation

Edit `config/config.json` to add the plugin to your board rotation:

```json
"states": {
    "off_day": [
        "example_board",
        "clock",
        "scoreticker"
    ]
}
```

### 4. Restart Scoreboard

```bash
sudo systemctl restart nhl-scoreboard
```

---

## Plugin Development Guide

This section provides comprehensive documentation for developing your own plugins.

### Required Files

Every plugin must contain these files:

```text
my_custom_board/
├── plugin.json          # Plugin metadata (REQUIRED)
├── __init__.py          # Module initialization
├── board.py             # Board implementation
├── config.sample.json   # Sample configuration (REQUIRED)
├── config.json          # User configuration (created by user)
├── layout_64x32.json    # Layout for 64x32 displays (optional)
├── layout_128x64.json   # Layout for 128x64 displays (optional)
└── README.md            # Plugin documentation (recommended)
```

### Plugin Structure

The NHL LED Scoreboard uses a metadata-driven plugin architecture where `plugin.json` is the single source of truth for all plugin information.

### plugin.json - Metadata

The `plugin.json` file defines all plugin metadata and is __required__ for every plugin.

__Example:__

```json
{
  "name": "example_board",
  "version": "1.0.0",
  "description": "Example board module for demonstration",
  "author": "NHL LED Scoreboard",
  "enabled": true,

  "boards": [
    {
      "id": "example_board",
      "class_name": "ExampleBoard",
      "module": "board"
    }
  ],

  "requirements": {
    "app_version": ">=2025.9.0",
    "python_dependencies": []
  },

  "preserve_files": [
    "config.json"
  ]
}
```

#### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | Yes | Plugin identifier (folder name). Must be valid Python module name (lowercase, underscores). |
| `version` | String | Yes | Plugin version (semantic versioning recommended). |
| `description` | String | Yes | Short description of plugin functionality. |
| `author` | String | No | Plugin author name. |
| `enabled` | Boolean | No | Whether plugin is enabled (default: true). Set to false to disable without uninstalling. |
| `boards` | Array | Yes | List of board classes this plugin provides (see below). |
| `requirements` | Object | No | Version and dependency requirements (see below). |
| `preserve_files` | Array | No | Files to preserve during updates/removal (default: config.json, *.csv, data/*, custom_*). |

#### boards Array

Each plugin can register one or multiple board classes. Each board entry requires:

```json
{
  "id": "my_board",           // Board identifier used in config.json states
  "class_name": "MyBoard",    // Python class name (must exist in module)
  "module": "board"           // Python module name (the file name without .py extension)
}
```

__Multiple Boards Example:__

```json
{
  "boards": [
    {
      "id": "nfl_board",
      "class_name": "NFLBoard",
      "module": "board"
    },
    {
      "id": "nfl_standings",
      "class_name": "NFLStandingsBoard",
      "module": "nfl_standings_board"
    }
  ]
}
```

This allows a single plugin to provide multiple related boards (e.g., game display + standings).

#### requirements Object

Specify version and dependency requirements. The board loader validates these before loading the plugin.

```json
{
  "requirements": {
    "app_version": ">=2025.10.0",
    "python": ">=3.11",
    "python_dependencies": [
      "pillow>=10.0.0",
      "holidays>=0.35"
    ]
  }
}
```

Supported operators: `>=`, `>`, `<=`, `<`, `==`, `!=`

### \_\_init\_\_.py - Module Initialization

The `__init__.py` file loads metadata from `plugin.json` and exposes it as module variables for backward compatibility.

__Pattern (copy this):__

```python
"""
My Custom Board Plugin

Detailed description of what your plugin does.
"""
import json
from pathlib import Path

# Load plugin metadata from plugin.json
_plugin_dir = Path(__file__).parent
with open(_plugin_dir / "plugin.json") as f:
    _metadata = json.load(f)

# Expose metadata as module variables (backward compatibility)
__plugin_id__ = _metadata["name"]
__version__ = _metadata["version"]
__description__ = _metadata["description"]
__board_name__ = _metadata["description"]
__author__ = _metadata.get("author", "")
__requirements__ = _metadata.get("requirements", {}).get("python_dependencies", [])
__min_app_version__ = _metadata.get("requirements", {}).get("app_version", "")
__preserve_files__ = _metadata.get("preserve_files", [])
```

This pattern ensures:

- `plugin.json` is the single source of truth
- Existing code expecting `__plugin_id__` variables continues to work
- No metadata duplication

### board.py - Implementation

Your board class must inherit from `BoardBase` and implement the `render()` method.

The file can be named something other than `board.py`.  The boards module `plugin.json` reference this file.

__Basic Structure:__

```python
"""
My Custom Board implementation.
"""
from boards.base_board import BoardBase
from . import __version__, __description__, __board_name__
import logging

debug = logging.getLogger("scoreboard")

class MyCustomBoard(BoardBase):
    """
    Brief description of what this board does.
    """

    def __init__(self, data, matrix, sleepEvent):
        super().__init__(data, matrix, sleepEvent)

        # Board metadata from package
        self.board_name = __board_name__
        self.board_version = __version__
        self.board_description = __description__

        # Get plugin-specific configuration with defaults
        self.my_setting = self.board_config.get("my_setting", "default_value")

        # Access standard application config
        self.font = data.config.layout.font

    def render(self):
        """
        Render the board content.
        """
        self.matrix.clear()

        # Your rendering code here

        self.matrix.render()
        self.sleepEvent.wait(self.display_seconds)
```

#### Key BoardBase Features

Your board class inherits these useful properties and methods:

__Properties:__

- `self.data` - Access to scoreboard data and configuration
- `self.matrix` - Matrix renderer for drawing
- `self.sleepEvent` - For timing control
- `self.board_config` - Your plugin's configuration from `config.json`
- `self.display_width` - Display width in pixels
- `self.display_height` - Display height in pixels

__Methods:__

- `self.get_board_layout(layout_name)` - Get layout for current screen size
- `self.matrix.clear()` - Clear the display
- `self.matrix.render()` - Render to display
- `self.matrix.draw_text_layout(layout, text, fillColor)` - Draw text using layout positioning
- `self.matrix.draw_text_centered(y, text, font, color)` - Draw centered text
- `self.sleepEvent.wait(seconds)` - Sleep with interrupt support

### Configuration Files

#### config.sample.json (REQUIRED)

This file provides a template for users and should include all available options with sensible defaults and comments.

```json
{
    "my_setting": "default_value",
    "another_setting": 42,
    "enabled": true,
    "display_seconds": 5,
    "description": "Configuration for my custom board"
}
```

#### config.json (User File)

Users copy `config.sample.json` to `config.json` and customize it. This file is automatically preserved during plugin updates.

__Accessing Configuration in Code:__

```python
def __init__(self, data, matrix, sleepEvent):
    super().__init__(data, matrix, sleepEvent)

    # Always provide defaults
    self.my_setting = self.board_config.get("my_setting", "default_value")
    self.display_seconds = self.board_config.get("display_seconds", 5)
```

### Layout Files

Layout files define positioning for different screen sizes. They're optional but recommended for responsive design.

__layout_64x32.json:__

```json
{
    "_default": {
        "position": [0, 0],
        "align": "left-top"
    },
    "my_board": {
        "title": {
            "position": ["50%", 6],
            "align": "center-top",
            "font": "medium"
        },
        "content": {
            "position": ["50%", 16],
            "align": "center-top",
            "font": "small"
        }
    }
}
```

__Using Layouts in Code:__

```python
def render(self):
    self.matrix.clear()

    # Get layout for this plugin
    layout = self.get_board_layout('my_board')

    if layout:
        # Use layout positioning
        if 'title' in layout:
            self.matrix.draw_text_layout(layout['title'], "My Title", fillColor='white')
        if 'content' in layout:
            self.matrix.draw_text_layout(layout['content'], "Content", fillColor='cyan')
    else:
        # Fallback without layout
        self.matrix.draw_text_centered(10, "My Title", self.font, 'white')
        self.matrix.draw_text_centered(20, "Content", self.font, 'cyan')

    self.matrix.render()
```

__Position Options:__

- Absolute: `[10, 20]` - 10 pixels from left, 20 from top
- Percentage: `["50%", 20]` - Centered horizontally, 20 from top

__Alignment Options:__

- `left-top`, `center-top`, `right-top`
- `left-center`, `center-center`, `right-center`
- `left-bottom`, `center-bottom`, `right-bottom`

---

## Creating Your Own Plugin

Follow these steps to create a new plugin:

### 1. Copy Example Board

```bash
cd src/boards/plugins
cp -r example_board my_custom_board
cd my_custom_board
```

### 2. Update plugin.json

```json
{
  "name": "my_custom_board",
  "version": "1.0.0",
  "description": "My custom board for displaying XYZ",
  "author": "Your Name",
  "enabled": true,

  "boards": [
    {
      "id": "my_custom_board",
      "class_name": "MyCustomBoard",
      "module": "board"
    }
  ],

  "requirements": {
    "app_version": ">=2025.10.0",
    "python_dependencies": []
  },

  "preserve_files": [
    "config.json"
  ]
}
```

### 3. Update __init__.py

The example `__init__.py` will automatically load from your `plugin.json`, so no changes needed unless you want to customize the module docstring.

### 4. Implement board.py

Rename the class and implement your functionality:

```python
class MyCustomBoard(BoardBase):
    def __init__(self, data, matrix, sleepEvent):
        super().__init__(data, matrix, sleepEvent)
        # Your initialization

    def render(self):
        # Your rendering logic
        pass
```

### 5. Update Configuration

Edit `config.sample.json` with your plugin's settings.

### 6. Adjust Layouts (Optional)

Edit `layout_64x32.json` and `layout_128x64.json` for your content positioning.

### 7. Update README.md

Document your plugin's features, configuration, and usage.

### 8. Test

Run the scoreboard to test

---

## Best Practices

### Single Source of Truth

- Always define metadata in `plugin.json`
- Use `__init__.py` to expose it as module variables
- Don't duplicate information

### Configuration Defaults

Always provide sensible defaults:

```python
# Good
self.setting = self.board_config.get("setting", "default")

# Bad - will crash if setting missing
self.setting = self.board_config["setting"]
```

### Graceful Fallbacks

Your code should work even without optional features:

```python
layout = self.get_board_layout('my_board')
if layout:
    # Use layout positioning
else:
    # Fallback to absolute positioning
```

### Logging

Use the debug logger for helpful messages:

```python
debug = logging.getLogger("scoreboard")

debug.info("Plugin initialized successfully")
debug.debug(f"Using configuration: {self.my_setting}")
debug.error("Failed to fetch data")
```

### Version Requirements

Specify minimum versions if you use newer features:

```json
{
  "requirements": {
    "app_version": ">=2025.10.0",
    "python_dependencies": ["requests>=2.28.0"]
  }
}
```

### File Preservation

Specify files to preserve during updates:

```json
{
  "preserve_files": [
    "config.json",
    "custom_data.csv",
    "data/*.json",
    "user_*"
  ]
}
```

Supports glob patterns for flexible matching.

### Documentation

- Document all configuration options in README
- Add comments to complex code
- Provide usage examples
- Include screenshots

---

## Additional Resources

- __Plugin Manager Documentation__: See [PLUGINS.md](../../../../../PLUGINS.md) for installing and managing plugins
