#!/bin/bash

# Make script work regardless of where it is run from
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "${DIR}/.."

# Prevent Python from writing __pycache__ files which would have root permissions
# when running with sudo (required for LED matrix hardware access)
export PYTHONDONTWRITEBYTECODE=1

# Check for venv Python
if [ ! -f "$HOME/nhlsb-venv/bin/python3" ]; then
    echo "Error: Virtual environment not found at $HOME/nhlsb-venv"
    echo "Please run the installation script first: ./scripts/sbtools/sb-init"
    exit 1
fi

sudo -E "$HOME/nhlsb-venv/bin/python3" src/main.py --led-gpio-mapping=adafruit-hat-pwm --led-slowdown-gpio=3