#!/bin/bash

# Make script work regardless of where it is run from
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "${DIR}/.."

# Prevent Python from writing __pycache__ files which would have root permissions
# when running with sudo (required for LED matrix hardware access)
export PYTHONDONTWRITEBYTECODE=1

sudo -E python3 src/main.py --led-gpio-mapping=adafruit-hat-pwm --led-slowdown-gpio=3