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
    python plugins.py sync [PLUGIN_NAME] [-f|--force] [-y|--yes]
    python plugins.py cleanup

Sync options:
    PLUGIN_NAME  Optional plugin name to sync only that plugin
    -f, --force  Force reinstall even if already up to date
    -y, --yes    Skip confirmation prompts and install automatically

Cleanup command:
    Automatically runs before add/sync operations to clean up cache files
    and fix root-owned file permissions that could block plugin updates.
    Can also be run manually with 'python plugins.py cleanup'
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
from typing import Dict, List, Optional, Tuple

# Environment overrides for flexibility
PLUGINS_DIR = Path(os.getenv("PLUGINS_DIR", "src/boards/plugins"))
PLUGINS_JSON_DEFAULT = Path("plugins.json.example")
PLUGINS_JSON_USER = Path(os.getenv("PLUGINS_JSON", "plugins.json"))
PLUGINS_LOCK = Path(os.getenv("PLUGINS_LOCK", "plugins.lock.json"))

# Default patterns for files to preserve during updates/removals
DEFAULT_PRESERVE_PATTERNS = ["config.json", "*.csv", "data/*", "custom_*"]

logger = logging.getLogger(__name__)


def cleanup_pycache_directories() -> Tuple[int, int]:
    """
    Delete all __pycache__ directories in the project.

    Returns:
        Tuple of (removed_count, failed_count)
    """
    cache_dirs = []

    # Find all __pycache__ directories
    try:
        for root, dirs, _ in os.walk("."):
            if "__pycache__" in dirs:
                cache_dirs.append(Path(root) / "__pycache__")
    except Exception as e:
        logger.debug(f"Error scanning for cache directories: {e}")
        return 0, 0

    if not cache_dirs:
        logger.debug("No __pycache__ directories found")
        return 0, 0

    removed = 0
    failed = 0

    for cache_dir in cache_dirs:
        try:
            shutil.rmtree(cache_dir)
            removed += 1
            logger.debug(f"Removed: {cache_dir}")
        except PermissionError:
            # Try with sudo if we have permission
            try:
                result = subprocess.run(
                    ["sudo", "-n", "rm", "-rf", str(cache_dir)],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    removed += 1
                    logger.debug(f"Removed (with sudo): {cache_dir}")
                else:
                    failed += 1
                    logger.debug(f"Failed to remove: {cache_dir}")
            except (subprocess.SubprocessError, FileNotFoundError):
                failed += 1
                logger.debug(f"Failed to remove: {cache_dir}")
        except Exception as e:
            failed += 1
            logger.debug(f"Error removing {cache_dir}: {e}")

    return removed, failed


def cleanup_sb_cache_dir() -> bool:
    """
    Clean up /tmp/sb_cache directory if it's owned by root.

    Returns:
        True if cleanup succeeded or not needed, False on failure
    """
    sb_cache = Path("/tmp/sb_cache")

    if not sb_cache.exists():
        logger.debug("/tmp/sb_cache does not exist")
        return True

    try:
        # Check ownership
        import stat
        st = sb_cache.stat()

        # If not owned by root (uid 0), no cleanup needed
        if st.st_uid != 0:
            logger.debug(f"/tmp/sb_cache is owned by uid {st.st_uid}, not root")
            return True

        # Owned by root, try to remove it
        logger.debug("/tmp/sb_cache is owned by root, attempting removal")

        try:
            shutil.rmtree(sb_cache)
            logger.debug("Removed /tmp/sb_cache")
            return True
        except PermissionError:
            # Try with sudo
            try:
                result = subprocess.run(
                    ["sudo", "-n", "rm", "-rf", str(sb_cache)],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.debug("Removed /tmp/sb_cache (with sudo)")
                    return True
                else:
                    logger.debug("Failed to remove /tmp/sb_cache with sudo")
                    return False
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.debug("Could not remove /tmp/sb_cache")
                return False
    except Exception as e:
        logger.debug(f"Error checking /tmp/sb_cache: {e}")
        return True  # Don't fail the entire operation


def fix_root_owned_files() -> Tuple[int, int]:
    """
    Find and fix ownership of root-owned files (excluding __pycache__).

    Returns:
        Tuple of (fixed_count, failed_count)
    """
    # Find root-owned files, excluding __pycache__ directories
    try:
        result = subprocess.run(
            ["find", ".", "-user", "root", "-not", "-path", "*/__pycache__/*", "-not", "-name", "__pycache__"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            logger.debug("Could not search for root-owned files (not running as root or sudo)")
            return 0, 0

        root_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

        if not root_files:
            logger.debug("No root-owned files found")
            return 0, 0

        logger.debug(f"Found {len(root_files)} root-owned file(s)")

        # Determine target user
        target_user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "pi"
        logger.debug(f"Target user for ownership: {target_user}")

        # Try to fix ownership
        fixed = 0
        failed = 0

        for file_path in root_files:
            try:
                # Try with sudo
                result = subprocess.run(
                    ["sudo", "-n", "chown", "-R", f"{target_user}:{target_user}", file_path],
                    capture_output=True,
                    timeout=5
                )

                if result.returncode == 0:
                    fixed += 1
                    logger.debug(f"Fixed ownership: {file_path}")
                else:
                    failed += 1
                    logger.debug(f"Failed to fix ownership: {file_path}")
            except (subprocess.SubprocessError, FileNotFoundError, Exception) as e:
                failed += 1
                logger.debug(f"Error fixing ownership of {file_path}: {e}")

        return fixed, failed

    except Exception as e:
        logger.debug(f"Error searching for root-owned files: {e}")
        return 0, 0


def cleanup_cache_and_permissions(verbose: bool = False) -> bool:
    """
    Perform cache cleanup and permission fixes.
    This integrates the functionality from scripts/sbtools/sb-cleanup-cache.

    Args:
        verbose: Whether to show detailed output

    Returns:
        True if cleanup succeeded, False if there were errors (non-fatal)
    """
    if verbose:
        logger.info("Cleaning up cache files and fixing permissions...")

    # Clean up __pycache__ directories
    removed, failed = cleanup_pycache_directories()
    if verbose and removed > 0:
        logger.info(f"✓ Removed {removed} __pycache__ director(y/ies)")
    if failed > 0:
        logger.debug(f"Could not remove {failed} __pycache__ director(y/ies)")

    # Clean up /tmp/sb_cache
    sb_cache_ok = cleanup_sb_cache_dir()
    if verbose and sb_cache_ok:
        logger.debug("✓ /tmp/sb_cache cleanup completed")

    # Fix root-owned files
    fixed, failed_perms = fix_root_owned_files()
    if verbose and fixed > 0:
        logger.info(f"✓ Fixed ownership of {fixed} root-owned file(s)")
    if failed_perms > 0:
        logger.debug(f"Could not fix {failed_perms} root-owned file(s)")

    # Return success even if some operations failed (they're often permission-related and non-fatal)
    return True


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


def get_remote_commit(url: str, ref: Optional[str] = None) -> Optional[str]:
    """
    Get the commit SHA from remote repository using git ls-remote.

    Args:
        url: Git repository URL
        ref: Git ref (tag, branch, SHA) to check. If None, uses default branch

    Returns:
        Commit SHA string, or None on failure
    """
    # If no ref specified, use HEAD to get default branch
    ref_to_check = ref if ref else "HEAD"

    # Use git ls-remote to get commit SHA without cloning
    result = run_git(["ls-remote", url, ref_to_check])

    if result.returncode != 0:
        logger.debug(f"Failed to get remote commit for {ref_to_check}: {result.stderr}")
        return None

    # Parse output (format: "commit_sha\trefs/...")
    lines = result.stdout.strip().split("\n")
    if not lines or not lines[0]:
        return None

    commit_sha = lines[0].split()[0] if lines[0] else None
    logger.debug(f"Remote commit for {ref_to_check}: {commit_sha}")
    return commit_sha


def check_plugin_update_available(plugin_name: str, url: str, ref: Optional[str]) -> Dict:
    """
    Check if an update is available for a plugin by comparing commits.

    Args:
        plugin_name: Name of the plugin
        url: Git repository URL
        ref: Git ref (tag, branch, SHA) to check

    Returns:
        Dict with keys:
            - needs_update: bool
            - local_commit: str or None
            - remote_commit: str or None
            - status: str (one of: 'not_installed', 'update_available', 'up_to_date', 'unknown')
    """
    result = {
        "needs_update": False,
        "local_commit": None,
        "remote_commit": None,
        "status": "unknown"
    }

    plugin_path = PLUGINS_DIR / plugin_name

    # Check if plugin is installed locally
    if not plugin_path.exists():
        result["status"] = "not_installed"
        result["needs_update"] = True
        return result

    # Get local commit from lock file
    lock_data = load_json(PLUGINS_LOCK)
    for locked in lock_data.get("locked", []):
        if locked.get("name") == plugin_name:
            result["local_commit"] = locked.get("commit")
            break

    if not result["local_commit"]:
        logger.debug(f"No lock entry found for {plugin_name}, will update")
        result["status"] = "unknown"
        result["needs_update"] = True
        return result

    # Get remote commit without cloning
    remote_commit = get_remote_commit(url, ref)
    if not remote_commit:
        logger.warning(f"Could not check remote version for {plugin_name}")
        result["status"] = "unknown"
        return result

    result["remote_commit"] = remote_commit

    # Compare commits
    if result["local_commit"] == remote_commit:
        result["status"] = "up_to_date"
        result["needs_update"] = False
    else:
        result["status"] = "update_available"
        result["needs_update"] = True

    return result


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
    Install Python dependencies for a plugin.

    Checks plugin.json for python_dependencies first, falls back to requirements.txt
    for backward compatibility.

    Args:
        plugin_path: Path to the plugin directory

    Returns:
        True if dependencies were installed successfully or no dependencies exist,
        False if installation failed
    """
    plugin_name = plugin_path.name
    dependencies = []

    # First, try to get dependencies from plugin.json
    metadata = load_plugin_metadata(plugin_path)
    if metadata:
        deps = metadata.get("requirements", {}).get("python_dependencies", [])
        if deps:
            logger.debug(f"Found {len(deps)} dependencies in plugin.json")
            dependencies = deps

    # Fallback to requirements.txt if no dependencies in metadata
    if not dependencies:
        requirements_file = plugin_path / "requirements.txt"
        if requirements_file.exists():
            logger.debug("Using requirements.txt for dependencies")
            try:
                with open(requirements_file) as f:
                    # Read dependencies, skip comments and empty lines
                    dependencies = [
                        line.strip()
                        for line in f
                        if line.strip() and not line.strip().startswith("#")
                    ]
            except Exception as e:
                logger.error(f"Failed to read requirements.txt: {e}")
                return False
        else:
            logger.debug(f"No dependencies found for plugin at {plugin_path}")
            return True

    if not dependencies:
        logger.debug(f"No dependencies to install for plugin '{plugin_name}'")
        return True

    logger.info(f"Installing {len(dependencies)} dependenc(y/ies) for plugin '{plugin_name}'...")

    # Install each dependency
    for dep in dependencies:
        logger.debug(f"  Installing: {dep}")
        pip_cmd = [sys.executable, "-m", "pip", "install", dep]

        try:
            result = subprocess.run(
                pip_cmd,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                logger.error(f"Failed to install '{dep}' for '{plugin_name}'")
                if result.stderr:
                    logger.debug(f"pip error: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error installing '{dep}' for '{plugin_name}': {e}")
            return False

    logger.info(f"✓ Dependencies installed for '{plugin_name}'")
    return True


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
    Combines DEFAULT_PRESERVE_PATTERNS with plugin-specific patterns.

    Returns:
        Combined list of default patterns + plugin-specific patterns (duplicates removed)
    """
    metadata = load_plugin_metadata(plugin_path)

    # Start with default patterns
    patterns = DEFAULT_PRESERVE_PATTERNS.copy()

    if not metadata:
        logger.debug("No plugin.json found, using default preserve patterns")
        return patterns

    # Add plugin-specific patterns if defined
    if "preserve_files" in metadata:
        plugin_patterns = metadata["preserve_files"]
        if plugin_patterns:
            # Combine and remove duplicates while preserving order
            for pattern in plugin_patterns:
                if pattern not in patterns:
                    patterns.append(pattern)
            logger.debug(f"Combined preserve patterns: {patterns}")
        else:
            logger.debug("Using default preserve patterns")
    else:
        logger.debug("Using default preserve patterns")

    return patterns


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


def install_plugin(
    url: str,
    ref: Optional[str],
    name_override: Optional[str] = None,
    preserve_user_files: bool = True,
) -> Optional[Dict]:
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
            logger.warning(f"Check plugin.json or requirements.txt in: {plugin_dest}")

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

    # Clean up cache and fix permissions before installing
    # This prevents issues with root-owned files blocking updates
    verbose = args.verbose if hasattr(args, 'verbose') else False
    cleanup_cache_and_permissions(verbose=verbose)

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
    check_git_available()

    plugins_json_path = get_plugins_json_path()
    plugins_data = load_json(plugins_json_path)
    lock_data = load_json(PLUGINS_LOCK)

    plugins = plugins_data.get("plugins", [])
    locked = {p["name"]: p for p in lock_data.get("locked", [])}

    if not plugins:
        print(f"No plugins configured in {plugins_json_path}")
        return

    # Print table header
    print(f"{'NAME':<20} {'VERSION':<12} {'STATUS':<15} {'COMMIT':<10}")
    print("-" * 60)

    for plugin in plugins:
        name = plugin["name"]
        url = plugin["url"]
        ref = plugin.get("ref")
        plugin_path = PLUGINS_DIR / name

        # Get version from plugin.json
        version = "-"
        commit = "-"

        if plugin_path.exists():
            metadata = load_plugin_metadata(plugin_path)
            if metadata and "version" in metadata:
                version = metadata["version"]

            commit = locked.get(name, {}).get("commit", "")[:7]

            # Check for updates
            update_info = check_plugin_update_available(name, url, ref)

            if update_info["status"] == "up_to_date":
                status = "up-to-date"
            elif update_info["status"] == "update_available":
                status = "update avail"
            elif update_info["status"] == "unknown":
                status = "present"
            else:
                status = "present"
        else:
            status = "not installed"

        print(f"{name:<20} {version:<12} {status:<15} {commit:<10}")


def cmd_cleanup(args):
    """Clean up cache files and fix permissions."""
    verbose = args.verbose if hasattr(args, 'verbose') else True  # Default to verbose for standalone command

    logger.info("Cleaning up cache files and fixing permissions...")
    cleanup_cache_and_permissions(verbose=verbose)
    logger.info("✓ Cleanup completed successfully")


def cmd_sync(args):
    """Sync all plugins from plugins.json."""
    check_git_available()

    # Clean up cache and fix permissions before syncing
    # This prevents issues with root-owned files blocking updates
    verbose = args.verbose if hasattr(args, 'verbose') else False
    cleanup_cache_and_permissions(verbose=verbose)

    plugins_json_path = get_plugins_json_path()
    plugins_data = load_json(plugins_json_path)
    all_plugins = plugins_data.get("plugins", [])

    if not all_plugins:
        logger.warning(f"No plugins configured in {plugins_json_path}")
        return

    # Filter plugins if specific name provided
    if args.plugin:
        plugins = [p for p in all_plugins if p.get("name") == args.plugin]
        if not plugins:
            logger.error(f"Plugin '{args.plugin}' not found in {plugins_json_path}")
            logger.info(f"Available plugins: {', '.join([p.get('name', 'unnamed') for p in all_plugins])}")
            sys.exit(1)
    else:
        plugins = all_plugins

    logger.info(f"Checking {len(plugins)} plugin(s) for updates...")

    # Check which plugins need updates
    plugins_to_update = []
    plugins_up_to_date = []
    plugins_not_installed = []
    plugins_unknown = []

    for plugin in plugins:
        name = plugin.get("name", "unnamed")
        url = plugin["url"]
        ref = plugin.get("ref")

        if args.force:
            # Force update, skip version check
            plugins_to_update.append(plugin)
        else:
            # Check if update is needed
            update_info = check_plugin_update_available(name, url, ref)

            if update_info["status"] == "not_installed":
                plugins_not_installed.append((plugin, update_info))
                plugins_to_update.append(plugin)
            elif update_info["status"] == "update_available":
                plugins_to_update.append(plugin)
            elif update_info["status"] == "up_to_date":
                plugins_up_to_date.append((plugin, update_info))
            else:
                plugins_unknown.append((plugin, update_info))
                # For unknown status, update if forced or assume safe to skip
                if not args.yes:
                    plugins_to_update.append(plugin)

    # Display status
    if not args.force and plugins_up_to_date:
        logger.info(f"✓ {len(plugins_up_to_date)} plugin(s) already up to date")
        for plugin, info in plugins_up_to_date:
            local_commit_short = info["local_commit"][:7] if info["local_commit"] else "unknown"
            logger.info(f"  - {plugin.get('name')} (commit: {local_commit_short})")

    if plugins_not_installed:
        logger.info(f"ℹ {len(plugins_not_installed)} plugin(s) not installed")
        for plugin, _ in plugins_not_installed:
            logger.info(f"  - {plugin.get('name')}")

    if not args.force and plugins_unknown:
        logger.warning(f"⚠ {len(plugins_unknown)} plugin(s) have unknown status (cannot check remote)")
        for plugin, _ in plugins_unknown:
            logger.warning(f"  - {plugin.get('name')}")

    # If no plugins need updating and not forced, exit
    if not plugins_to_update:
        logger.info("All plugins are up to date!")
        return

    # Show what will be updated
    if not args.force:
        updates_needed = [p for p in plugins_to_update if p not in [p[0] for p in plugins_not_installed]]
        if updates_needed:
            logger.info(f"↻ {len(updates_needed)} plugin(s) have updates available")
            for plugin in updates_needed:
                logger.info(f"  - {plugin.get('name')}")

    # Prompt user unless --yes flag is set
    if not args.yes:
        if args.force:
            action = "reinstall"
            count = len(plugins_to_update)
        else:
            action = "install/update"
            count = len(plugins_to_update)

        response = input(f"\n{action.capitalize()} {count} plugin(s)? [y/N]: ").strip().lower()
        if response not in ['y', 'yes']:
            logger.info("Sync cancelled by user")
            return

    # Install/update plugins
    logger.info(f"Installing/updating {len(plugins_to_update)} plugin(s)...")

    lock_entries = []
    failed = []
    updated = []
    installed = []

    # Keep existing lock entries for plugins we're not updating
    if not args.force and args.plugin is None:
        lock_data = load_json(PLUGINS_LOCK)
        existing_locked = lock_data.get("locked", [])
        for locked in existing_locked:
            if locked["name"] not in [p.get("name") for p in plugins_to_update]:
                lock_entries.append(locked)

    for plugin in plugins_to_update:
        url = plugin["url"]
        ref = plugin.get("ref")
        name_hint = plugin.get("name")

        was_installed = (PLUGINS_DIR / name_hint).exists() if name_hint else False

        lock_entry = install_plugin(url, ref, name_hint)
        if lock_entry:
            lock_entries.append(lock_entry)
            if was_installed:
                updated.append(lock_entry["name"])
            else:
                installed.append(lock_entry["name"])
        else:
            failed.append(name_hint or url)

    # Update lock file with all lock entries
    lock_data = {"locked": lock_entries}
    save_json_atomic(PLUGINS_LOCK, lock_data)

    # Summary
    print()
    if installed:
        logger.info(f"✓ {len(installed)} plugin(s) installed: {', '.join(installed)}")
    if updated:
        logger.info(f"✓ {len(updated)} plugin(s) updated: {', '.join(updated)}")
    if failed:
        logger.error(f"✗ {len(failed)} plugin(s) failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        logger.info("Sync completed successfully!")


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
    sync_parser.add_argument("plugin", nargs="?", help="Specific plugin name to sync (optional)")
    sync_parser.add_argument("-f", "--force", action="store_true", help="Force reinstall even if up to date")
    sync_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompts")
    sync_parser.set_defaults(func=cmd_sync)

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up cache files and fix root-owned file permissions")
    cleanup_parser.set_defaults(func=cmd_cleanup)

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    # Execute command
    args.func(args)


if __name__ == "__main__":
    main()
