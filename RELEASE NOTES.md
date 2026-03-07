# Release Notes - March 6, 2026 (v2026.03.0)

## **New Features**

*   **Advanced Web-Based Logo Editor**: Added a comprehensive web-based editor (`/editor`) to manage team summary logos, SVG alternate logo uploads (with PNG conversion), and dynamic configuration via `logos.json`.
*   **Alternative Logo Management**: Users can now discard alternative logos, perform factory resets of logo configurations, and toggle easily between Scoreboard Editor and Team Summary Editor.
*   **NHL Historical Logo AP**I: Added an API (`/api/logos`) to fetch historical and current team logos with era-specific parameters and the ability to export them as JSON/TOML.
*   **CLI Automation**: Enhanced update scripts (`sb-upgrade` and `nhl_setup`) with self-update mechanisms, explicitly stashing changes during upgrade, and repository checks for `nls-controlhub` apt packages.

## **Fixes & Improvements**

*   **Security & Stability**: Updated project dependencies to resolve Pillow vulnerabilities.
*   **Error Handling**: Improved image library import error handling in the editor, and client-side validation for SVG-only alternate logo uploads.
*   **Unsaved Changes Protection**: Added unsaved changes banner, warning prompts when navigating away or toggling editors, and visual indicators for modified configurations.
*   **Installation/Update Scripts**: Enhanced argument parsing with `--version` and `--no-self-check`, and reordered root user execution checks for safer operation.

## **Merged Pull Requests**

*   *(Placeholder for PR links)*

---

# Release Notes - February 11, 2026 (v2026.02.1)

## **New Features**

*   **Alternative Logo Selection**: Added support for selecting and persisting alternative team logos via the UI and API.
*   **External Access**: The Flask application now binds to `0.0.0.0`, allowing access from other devices. A new health check endpoint (`/health`) has been added.
*   **Logo Download Control**: Disabled automatic downloading of 'alt' logos to give users more control over storage and bandwidth.
*   **Olympic & National Team Support**: Added support for national team logos and handling fallback abbreviations for the Olympics. (PR #109)

## **Fixes & Improvements**

*   **Environment Sanitization**: Implemented environment variable sanitization to prevent library path conflicts in frozen applications (PyInstaller).
*   **Stats Board Improvements**: Replaced name truncation with a black overlay for better visibility on the stats board. (PR #105)
*   **Timing Fixes**: Updated `end_of_day` preference handling and refactored date fetching to correctly handle new day transitions. (PR #105)
*   **Configuration**: Refactored board configuration handling for improved clarity and consistency. (PR #105)
*   **Scroll Speed**: Updated scroll speed in standings and stats leaders configuration. (PR #105)
*   **Crash Loop Backoff**: Introduce application crash count, OWM API backoff, and crash logging for improved stability.

## **Merged Pull Requests**

*   **#105**: Closes #102, #103, and #104. Includes fixes for day transition timing, stats board display improvements, and configuration refactoring.
*   **#109**: Support for national team logos and fallback abbreviations for Olympics.
