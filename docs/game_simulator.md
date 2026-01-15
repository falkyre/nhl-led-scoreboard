# NHL Game Simulator

The Game Simulator is a tool designed to replay historical NHL games on your scoreboard. It fetches play-by-play data from the NHL API and feeds it into the `nhl-led-scoreboard` application, simulating the flow of the game including clock updates, score changes, and shots on goal.

## Features

- **Historical Replay:** Simulate any game from the past using its date and team.
- **Real-Time Simulation:** The game clock and events progress in real-time (by default).
- **Speed Control:** fast-forward the action with a speed multiplier (e.g. 10x speed).
- **Seamless Integration:** Uses monkeypatching to inject data without modifying the core scoreboard codebase.
- **Full Scoreboard Features:** Supports all standard scoreboard limitations and arguments (emulated mode, matrix options, etc.).

## Usage

Run the simulator script from the root of the project:

```bash
python3 src/scripts/start_simulation.py [options] [scoreboard_arguments]
```

### Options

| Option | Description | Example |
|--------|-------------|---------|
| `--team` | The 3-letter abbreviation of the team to play. | `--team WPG` |
| `--date` | The date of the game to simulate (YYYY-MM-DD). | `--date 2026-01-13` |
| `--speed` | Speed multiplier for the simulation. Default is 1.0 (real-time). | `--speed 10.0` |
| `--stop-at-end` | Stop the simulator when the game is finished (reaches FINAL). | `--stop-at-end` |

### Scoreboard Arguments

Any arguments not recognized by the simulator are passed directly to `main.py`. This includes arguments for defining LED matrix properties or running in emulator mode.

**Example: Run a game in emulator mode at 10x speed**
```bash
python3 src/scripts/start_simulation.py --team WPG --date 2023-10-11 --speed 10.0 --emulated --led-rows=64 --led-cols=128
```

**Example: Run interactivly (will prompt for team/date)**
```bash
python3 src/scripts/start_simulation.py --emulated
```

## How It Works

1.  **Data Fetching:** The script fetches the game schedule and detailed play-by-play data from the NHL API for the specified game.
2.  **Pre-Calculation:** It calculates "simulated timestamps" for every play event (Goals, Shots, Penalties, etc.) based on game logic (periods, intermissions).
3.  **Monkeypatching:** It intercepts calls to `nhl_api.data.get_game_overview` and `nhl_api.data.get_score_details`. Instead of hitting the live API, the application receives data from the `GameSimulator` class.
4.  **Simulation Loop:** As the scoreboard requests data updates, the simulator advances its internal clock based on the wall-clock time elapsed and the speed multiplier.
5.  **Event Emitting:** When the simulated time reaches the timestamp of a play, the event is "emitted" (added to the data payload), updating the score, shots on goal, and clock on the scoreboard.

## troubleshooting

- **Game Ends Immediately:** Ensure the date you provided has a valid past game.
- **"Unrecognized Arguments":** The simulator should pass unknown args to the scoreboard, but ensure you are using the correct syntax for scoreboard args.
- **Timezone Issues:** The simulation uses the raw UTC times from the API but simulates locally. If the time seems off, it might be due to the naive time handling which is designed to match the scoreboard's internal logic.
