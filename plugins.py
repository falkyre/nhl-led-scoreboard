#!/usr/bin/env python3
"""
Barebones Plugin Manager for NHL LED Scoreboard

Manages board plugins as separate git repositories. Each plugin is cloned,
copied into src/boards/plugins/<name>, and tracked in plugins.lock.json
for reproducible installs.

Usage:
    python plugins.py add NAME URL [--ref REF]
    python plugins.py rm NAME [--keep-config]
    python plugins.py list
    python plugins.py sync
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Environment overrides for flexibility
PLUGINS_DIR = Path(os.getenv("PLUGINS_DIR", "src/boards/plugins"))
PLUGINS_JSON_DEFAULT = Path("plugins.json.example")
PLUGINS_JSON_USER = Path(os.getenv("PLUGINS_JSON", "plugins.json"))
PLUGINS_LOCK = Path(os.getenv("PLUGINS_LOCK", "plugins.lock.json"))

# Default patterns for files to preserve during updates/removals
DEFAULT_PRESERVE_PATTERNS = ["config.json", "*.csv", "data/*", "custom_*"]

logger = logging.getLogger(__name__)


def get_plugins_json_path() -> Path:
    """
    Get the active plugins.json path.
    Uses plugins.json if it exists (user customization),
    otherwise falls back to plugins.json.example (defaults).
    """
    if PLUGINS_JSON_USER.exists():
        return PLUGINS_JSON_USER
    elif PLUGINS_JSON_DEFAULT.exists():
        logger.debug(f"Using default: {PLUGINS_JSON_DEFAULT}")
        return PLUGINS_JSON_DEFAULT
    else:
        logger.error(f"Neither {PLUGINS_JSON_USER} nor {PLUGINS_JSON_DEFAULT} found!")
        logger.error(f"Create {PLUGINS_JSON_USER} or copy from {PLUGINS_JSON_DEFAULT}")
        sys.exit(1)


def load_json(path: Path) -> dict:
    """Load JSON file, returning empty dict if not found."""
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {path}: {e}")
        sys.exit(1)


def save_json_atomic(path: Path, data: dict):
    """Save JSON atomically using temp file + rename."""
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")  # trailing newline
    tmp_path.replace(path)


def load_plugin_metadata(plugin_path: Path) -> Optional[dict]:
    """
    Load plugin.json metadata file.

    Args:
        plugin_path: Path to the plugin directory

    Returns:
        Dict with plugin metadata, or None if file not found/invalid
    """
    plugin_json = plugin_path / "plugin.json"

    if not plugin_json.exists():
        logger.debug(f"No plugin.json found in {plugin_path}")
        return None

    try:
        return load_json(plugin_json)
    except Exception as e:
        logger.warning(f"Could not read plugin.json from {plugin_path}: {e}")
        return None


def check_git_available():
    """Ensure git is installed and available."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("Git is not installed or not in PATH. Please install git.")
        sys.exit(1)


def run_git(args: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a git command, returning CompletedProcess for inspection."""
    cmd = ["git"] + args
    logger.debug(f"Running: {' '.join(cmd)} (cwd={cwd})")
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def clone_plugin(url: str, ref: Optional[str], tmp_dir: Path) -> Optional[str]:
    """
    Clone a git repo into tmp_dir and optionally checkout a ref.
    Returns the resolved commit SHA, or None on failure.
    """
    # If a ref is specified, try to clone that branch/tag directly
    if ref:
        logger.debug(f"Cloning branch/ref: {ref}")
        result = run_git(["clone", "--depth", "1", "--branch", ref, url, str(tmp_dir)])
        if result.returncode != 0:
            # --branch doesn't work with commit SHAs, so clone default and checkout
            logger.debug(f"Could not clone ref '{ref}' directly, trying checkout method")
            result = run_git(["clone", "--depth", "1", url, str(tmp_dir)])
            if result.returncode != 0:
                logger.error(f"Failed to clone {url}")
                logger.error(result.stderr)
                return None

            # Fetch the specific commit
            result = run_git(["fetch", "--depth", "1", "origin", ref], cwd=tmp_dir)
            if result.returncode != 0:
                logger.error(f"Failed to fetch ref '{ref}' from {url}")
                logger.error(result.stderr)
                return None

            # Checkout the commit
            result = run_git(["checkout", ref], cwd=tmp_dir)
            if result.returncode != 0:
                logger.error(f"Failed to checkout ref '{ref}'")
                logger.error(result.stderr)
                return None
    else:
        # Clone with depth 1 for speed (default branch)
        result = run_git(["clone", "--depth", "1", url, str(tmp_dir)])
        if result.returncode != 0:
            logger.error(f"Failed to clone {url}")
            logger.error(result.stderr)
            return None

    # Get resolved commit SHA
    result = run_git(["rev-parse", "HEAD"], cwd=tmp_dir)
    if result.returncode != 0:
        logger.error("Failed to get commit SHA")
        return None

    commit_sha = result.stdout.strip()
    logger.debug(f"Resolved commit: {commit_sha}")
    return commit_sha


def copy_plugin_files(src: Path, dest: Path):
    """
    Copy plugin files from src to dest, excluding .git directory.
    Removes dest first if it exists to avoid stale files.
    """
    # Remove destination if it exists
    if dest.exists():
        logger.debug(f"Removing existing plugin at {dest}")
        shutil.rmtree(dest)

    # Copy files, ignoring .git
    def ignore_git(directory, contents):
        return [".git"] if ".git" in contents else []

    shutil.copytree(src, dest, ignore=ignore_git)
    logger.debug(f"Copied plugin files to {dest}")


def validate_plugin(plugin_path: Path) -> bool:
    """
    Check if plugin folder contains expected files and valid metadata.
    Returns True if valid, False with warning if suspicious.
    """
    plugin_json = plugin_path / "plugin.json"

    if not plugin_json.exists():
        logger.warning(f"Plugin at {plugin_path} missing plugin.json")
        return False

    # Load and validate metadata
    try:
        metadata = load_plugin_metadata(plugin_path)
        if not metadata:
            logger.warning(f"Plugin at {plugin_path} has invalid plugin.json")
            return False

        # Check for boards declaration
        boards = metadata.get("boards", [])
        if not boards:
            logger.warning(f"Plugin at {plugin_path} declares no boards")
            return False

        # Verify each declared board module exists
        for board in boards:
            if isinstance(board, dict):
                module_name = board.get("module", "board")
            else:
                # Legacy format support (simple list of board IDs)
                module_name = "board"

            module_file = plugin_path / f"{module_name}.py"

            if not module_file.exists():
                logger.warning(
                    f"Plugin at {plugin_path} declares board module '{module_name}.py' but file not found"
                )
                return False

        return True

    except Exception as e:
        logger.warning(f"Could not validate plugin at {plugin_path}: {e}")
        return False


def install_plugin_dependencies(plugin_path: Path) -> bool:
    """
    Install Python dependencies for a plugin from its requirements.txt.

    Args:
        plugin_path: Path to the plugin directory

    Returns:
        True if dependencies were installed successfully or no dependencies exist,
        False if installation failed
    """
    requirements_file = plugin_path / "requirements.txt"

    if not requirements_file.exists():
        logger.debug(f"No requirements.txt found for plugin at {plugin_path}")
        return True

    plugin_name = plugin_path.name
    logger.info(f"Installing dependencies for plugin '{plugin_name}'...")

    # Determine pip command based on environment
    pip_cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]

    try:
        result = subprocess.run(
            pip_cmd,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0:
            logger.info(f"✓ Dependencies installed for '{plugin_name}'")
            return True
        else:
            logger.error(f"Failed to install dependencies for '{plugin_name}'")
            if result.stderr:
                logger.debug(f"pip error: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error installing dependencies for '{plugin_name}': {e}")
        return False


def get_plugin_id_from_repo(repo_path: Path) -> Optional[str]:
    """
    Extract the canonical plugin ID from the plugin's plugin.json.

    Args:
        repo_path: Path to the cloned repository

    Returns:
        Plugin ID string if found, None if plugin.json not present or error occurs
    """
    metadata = load_plugin_metadata(repo_path)

    if not metadata:
        return None

    if "name" not in metadata:
        logger.warning("Plugin metadata missing required 'name' field")
        return None

    plugin_id = metadata["name"]
    logger.debug(f"Found plugin name: {plugin_id}")
    return plugin_id


def get_preserve_patterns(plugin_path: Path) -> List[str]:
    """
    Get list of file patterns to preserve from plugin's plugin.json.
    Falls back to DEFAULT_PRESERVE_PATTERNS if not specified.
    """
    metadata = load_plugin_metadata(plugin_path)

    if not metadata:
        logger.debug("No plugin.json found, using default preserve patterns")
        return DEFAULT_PRESERVE_PATTERNS

    if "preserve_files" in metadata:
        patterns = metadata["preserve_files"]
        logger.debug(f"Using plugin-specified preserve patterns: {patterns}")
        return patterns

    logger.debug("Using default preserve patterns")
    return DEFAULT_PRESERVE_PATTERNS


def collect_preserved_files(plugin_path: Path, patterns: List[str]) -> Dict[str, bytes]:
    """
    Collect files matching patterns from plugin directory.
    Returns dict of relative_path -> file_content (bytes).
    """
    preserved = {}

    if not plugin_path.exists():
        return preserved

    for pattern in patterns:
        # Handle both simple filenames and glob patterns
        if "/" in pattern:
            # Pattern with directory (e.g., "data/*")
            parts = pattern.split("/")
            base_dir = plugin_path / parts[0]
            glob_pattern = "/".join(parts[1:])

            if base_dir.exists() and base_dir.is_dir():
                for file_path in base_dir.rglob(glob_pattern):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(plugin_path)
                        try:
                            preserved[str(rel_path)] = file_path.read_bytes()
                            logger.debug(f"Preserved: {rel_path}")
                        except Exception as e:
                            logger.warning(f"Could not preserve {rel_path}: {e}")
        else:
            # Simple pattern (e.g., "config.json", "*.csv")
            for file_path in plugin_path.rglob(pattern):
                if file_path.is_file():
                    rel_path = file_path.relative_to(plugin_path)
                    try:
                        preserved[str(rel_path)] = file_path.read_bytes()
                        logger.debug(f"Preserved: {rel_path}")
                    except Exception as e:
                        logger.warning(f"Could not preserve {rel_path}: {e}")

    return preserved


def restore_preserved_files(plugin_path: Path, preserved: Dict[str, bytes]):
    """Restore preserved files to plugin directory."""
    if not preserved:
        return

    logger.info(f"Restoring {len(preserved)} preserved file(s)")

    for rel_path, content in preserved.items():
        file_path = plugin_path / rel_path
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(content)
            logger.debug(f"Restored: {rel_path}")
        except Exception as e:
            logger.warning(f"Could not restore {rel_path}: {e}")


def install_plugin(url: str, ref: Optional[str], name_override: Optional[str] = None, preserve_user_files: bool = True) -> Optional[Dict]:
    """
    Install or update a single plugin.
    Auto-detects plugin name from __plugin_id__ in the repo's __init__.py.

    Args:
        url: Git repository URL
        ref: Git ref (tag, branch, SHA) to checkout
        name_override: Optional override for plugin name (ignores __plugin_id__)
        preserve_user_files: Whether to preserve user files during updates

    Returns:
        Lock entry dict on success, None on failure
    """
    logger.info(f"Installing plugin from {url}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Clone and get commit SHA
        commit_sha = clone_plugin(url, ref, tmp_path)
        if not commit_sha:
            return None

        # Auto-detect plugin ID from __init__.py
        if name_override:
            plugin_name = name_override
            logger.info(f"Using override name: {plugin_name}")
        else:
            plugin_name = get_plugin_id_from_repo(tmp_path)
            if not plugin_name:
                logger.error(
                    "Could not determine plugin name. Plugin must have 'name' field in plugin.json, "
                    "or use --name to specify manually."
                )
                return None
            logger.info(f"Detected plugin ID: {plugin_name}")

        plugin_dest = PLUGINS_DIR / plugin_name
        preserved_files = {}

        # If updating an existing plugin, preserve user files
        if preserve_user_files and plugin_dest.exists():
            patterns = get_preserve_patterns(plugin_dest)
            preserved_files = collect_preserved_files(plugin_dest, patterns)
            if preserved_files:
                logger.info(f"Preserving {len(preserved_files)} user file(s) during update")

        # Copy to plugins directory
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        copy_plugin_files(tmp_path, plugin_dest)

        # Restore preserved files
        if preserved_files:
            restore_preserved_files(plugin_dest, preserved_files)

        # Validate plugin structure
        validate_plugin(plugin_dest)

        # Install plugin dependencies
        if not install_plugin_dependencies(plugin_dest):
            logger.warning(f"Plugin '{plugin_name}' installed but dependency installation failed")
            logger.warning(f"You may need to manually install dependencies from: {plugin_dest}/requirements.txt")

        logger.info(f"✓ Plugin '{plugin_name}' installed successfully (commit: {commit_sha[:7]})")

        # Return lock entry
        return {
            "name": plugin_name,
            "url": url,
            "ref": ref or "default",
            "commit": commit_sha,
        }


def cmd_add(args):
    """Add or update a plugin in plugins.json and install it."""
    check_git_available()

    # Install the plugin (auto-detects name from __plugin_id__)
    lock_entry = install_plugin(args.url, args.ref, args.name)
    if not lock_entry:
        logger.error(f"Failed to install plugin from {args.url}")
        sys.exit(1)

    # Get the detected/assigned plugin name
    plugin_name = lock_entry["name"]

    # Always write to user's plugins.json (create if doesn't exist)
    plugins_json_path = PLUGINS_JSON_USER

    # Load current plugins.json (may use default as template)
    plugins_data = load_json(get_plugins_json_path())
    if "plugins" not in plugins_data:
        plugins_data["plugins"] = []

    # Remove existing entry if present (by name or URL)
    plugins_data["plugins"] = [
        p for p in plugins_data["plugins"]
        if p["name"] != plugin_name and p["url"] != args.url
    ]

    # Add new entry
    new_entry = {"name": plugin_name, "url": args.url}
    if args.ref:
        new_entry["ref"] = args.ref
    plugins_data["plugins"].append(new_entry)

    # Save to user's plugins.json
    save_json_atomic(plugins_json_path, plugins_data)
    logger.info(f"Added '{plugin_name}' to {plugins_json_path}")

    # Update lock file
    lock_data = load_json(PLUGINS_LOCK)
    if "locked" not in lock_data:
        lock_data["locked"] = []

    # Remove existing lock entry
    lock_data["locked"] = [p for p in lock_data["locked"] if p["name"] != plugin_name]
    lock_data["locked"].append(lock_entry)

    save_json_atomic(PLUGINS_LOCK, lock_data)
    logger.info(f"Updated {PLUGINS_LOCK}")


def cmd_rm(args):
    """Remove a plugin from plugins.json and delete its files."""
    # Always write to user's plugins.json
    plugins_json_path = PLUGINS_JSON_USER

    # Load current plugins.json
    plugins_data = load_json(get_plugins_json_path())
    if "plugins" not in plugins_data:
        plugins_data["plugins"] = []

    # Remove from plugins.json
    original_count = len(plugins_data["plugins"])
    plugins_data["plugins"] = [p for p in plugins_data["plugins"] if p["name"] != args.name]

    if len(plugins_data["plugins"]) == original_count:
        logger.warning(f"Plugin '{args.name}' not found in plugin configuration")
    else:
        save_json_atomic(plugins_json_path, plugins_data)
        logger.info(f"Removed '{args.name}' from {plugins_json_path}")

    # Remove from lock
    lock_data = load_json(PLUGINS_LOCK)
    if "locked" in lock_data:
        lock_data["locked"] = [p for p in lock_data["locked"] if p["name"] != args.name]
        save_json_atomic(PLUGINS_LOCK, lock_data)

    # Delete plugin files
    plugin_path = PLUGINS_DIR / args.name
    if plugin_path.exists():
        preserved_files = {}

        # Preserve user files if requested
        if args.keep_config:
            patterns = get_preserve_patterns(plugin_path)
            preserved_files = collect_preserved_files(plugin_path, patterns)
            if preserved_files:
                logger.info(f"Preserving {len(preserved_files)} user file(s)")

        # Remove plugin directory
        shutil.rmtree(plugin_path)
        logger.info(f"Deleted plugin directory: {plugin_path}")

        # Restore preserved files if any
        if preserved_files:
            plugin_path.mkdir(parents=True, exist_ok=True)
            restore_preserved_files(plugin_path, preserved_files)
            logger.info(f"Preserved files saved to {plugin_path}")
    else:
        logger.warning(f"Plugin directory not found: {plugin_path}")


def cmd_list(args):
    """List all plugins with their status."""
    plugins_json_path = get_plugins_json_path()
    plugins_data = load_json(plugins_json_path)
    lock_data = load_json(PLUGINS_LOCK)

    plugins = plugins_data.get("plugins", [])
    locked = {p["name"]: p for p in lock_data.get("locked", [])}

    if not plugins:
        print(f"No plugins configured in {plugins_json_path}")
        return

    # Print table header
    print(f"{'NAME':<20} {'VERSION':<12} {'STATUS':<12} {'COMMIT':<10}")
    print("-" * 57)

    for plugin in plugins:
        name = plugin["name"]
        plugin_path = PLUGINS_DIR / name
        status = "present" if plugin_path.exists() else "missing"
        commit = locked.get(name, {}).get("commit", "")[:7] if status == "present" else "-"

        # Get version from plugin.json
        version = "-"
        if status == "present":
            metadata = load_plugin_metadata(plugin_path)
            if metadata and "version" in metadata:
                version = metadata["version"]

        print(f"{name:<20} {version:<12} {status:<12} {commit:<10}")


def cmd_sync(args):
    """Sync all plugins from plugins.json."""
    check_git_available()

    plugins_json_path = get_plugins_json_path()
    plugins_data = load_json(plugins_json_path)
    plugins = plugins_data.get("plugins", [])

    if not plugins:
        logger.warning(f"No plugins configured in {plugins_json_path}")
        return

    logger.info(f"Syncing {len(plugins)} plugin(s)...")

    lock_entries = []
    failed = []

    for plugin in plugins:
        url = plugin["url"]
        ref = plugin.get("ref")
        name_hint = plugin.get("name")  # Use name from config as hint/override

        lock_entry = install_plugin(url, ref, name_hint)
        if lock_entry:
            lock_entries.append(lock_entry)
        else:
            failed.append(name_hint or url)

    # Update lock file with all successful installs
    lock_data = {"locked": lock_entries}
    save_json_atomic(PLUGINS_LOCK, lock_data)

    # Summary
    print()
    logger.info(f"✓ Sync complete: {len(lock_entries)} installed, {len(failed)} failed")
    if failed:
        logger.error(f"Failed plugins: {', '.join(failed)}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Manage board plugins for NHL LED Scoreboard")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Add command (aliases: install)
    add_parser = subparsers.add_parser("add", aliases=["install"], help="Add or update a plugin")
    add_parser.add_argument("url", help="Git repository URL")
    add_parser.add_argument("--ref", help="Git ref (tag, branch, or SHA)")
    add_parser.add_argument("--name", help="Override plugin name (uses __plugin_id__ from repo by default)")
    add_parser.set_defaults(func=cmd_add)

    # Remove command (aliases: rm, delete, uninstall)
    remove_parser = subparsers.add_parser("remove", aliases=["rm", "delete", "uninstall"], help="Remove a plugin")
    remove_parser.add_argument("name", help="Plugin name to remove")
    remove_parser.add_argument("--keep-config", action="store_true", help="Preserve config.json when removing")
    remove_parser.set_defaults(func=cmd_rm)

    # List command (aliases: ls, show)
    list_parser = subparsers.add_parser("list", aliases=["ls", "show"], help="List all plugins")
    list_parser.set_defaults(func=cmd_list)

    # Sync command (aliases: update)
    sync_parser = subparsers.add_parser("sync", aliases=["update"], help="Install/update all plugins from plugins.json")
    sync_parser.set_defaults(func=cmd_sync)

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    # Execute command
    args.func(args)


if __name__ == "__main__":
    main()
