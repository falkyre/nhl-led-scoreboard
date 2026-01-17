"""
Score Ticker board module implementation.
"""
import logging

from boards.base_board import BoardBase
from data.scoreboard import GameSummaryBoard
from nhl_api.workers import GamesWorker
from renderer.matrix import MatrixPixels
from renderer.scoreboard import ScoreboardRenderer

debug = logging.getLogger("scoreboard")


class Scoreticker(BoardBase):
    """
    NHL Score Ticker Board.

    Displays a rotating ticker of all games for the day, showing scores and game status.
    Uses background worker for data fetching to avoid blocking render loop.
    """

    def __init__(self, data, matrix, sleepEvent):
        super().__init__(data, matrix, sleepEvent)

        # Load config with automatic priority: central config -> board config -> defaults
        self.rotation_rate = self.get_config_value('rotation_rate', 5)
        self.spacing = self.get_config_value('spacing', 3)

        # Get layout from main config system
        self.layout = self.data.config.config.layout.get_board_layout('scoreticker')

    def render(self):
        """Render the score ticker with rotating games."""
        # Get cached games from worker instead of fetching on each render
        games = GamesWorker.get_games_raw()

        if not games:
            debug.info("Score ticker: No games available to display")
            return

        # Filter out current game if in live mode
        games = self._filter_games(games)

        if not games:
            debug.info("Score ticker: No games to display after filtering")
            return

        num_games = len(games)

        try:
            for index, game in enumerate(games):
                if self.sleepEvent.is_set():
                    break

                self.matrix.clear()

                # Render game using cached data
                ScoreboardRenderer(
                    self.data,
                    self.matrix,
                    GameSummaryBoard(game, self.data)
                ).render()

                # Show carousel indicator dots
                self._show_indicator(index, num_games)

                self.matrix.render()

                # Show network/update indicators
                if self.data.network_issues:
                    self.matrix.network_issue_indicator()

                if self.data.newUpdate and not self.data.config.clock_hide_indicators:
                    self.matrix.update_indicator()

                # Wait before showing next game
                self.sleepEvent.wait(self.rotation_rate)

        except IndexError:
            debug.info("Score ticker: No games to display, preferred teams only or NHL off day")
            return

    def _filter_games(self, games):
        """
        Filter games list based on configuration.

        Removes the current live game from ticker if in live mode, so it doesn't
        duplicate the main scoreboard display.

        Args:
            games: List of game dictionaries

        Returns:
            Filtered list of games
        """
        # In live mode, filter out the current game being displayed on main board
        if not self.data.is_pref_team_offday() and self.data.config.live_mode:
            if hasattr(self.data, 'current_game_id'):
                games = [g for g in games if g["id"] != self.data.current_game_id]

        return games

    def _show_indicator(self, current_index, num_games):
        """
        Show carousel indicator dots at bottom of screen.

        Displays a row of dots showing which game in the rotation is currently displayed.
        Active game is shown in red, others in gray.

        Args:
            current_index: Index of currently displayed game
            num_games: Total number of games in rotation
        """
        align = 0
        spacing = self.spacing

        # Reduce spacing if more than 10 games to fit on screen
        if num_games > 10:
            spacing = 2

            # Adjust alignment for even number of games
            if num_games % 2:
                align = -1

        # Build pixel list for indicator dots
        pixels = []

        for i in range(num_games):
            dot_position = ((spacing * i) - 1) + 1

            # Highlight current game in red, others in gray
            color = (255, 50, 50) if i == current_index else (70, 70, 70)

            pixels.append(
                MatrixPixels(
                    ((align + dot_position), 0),
                    color
                )
            )

        # Draw pixels using layout positioning
        self.matrix.draw_pixels_layout(
            self.layout.indicator_dots,
            pixels,
            (pixels[-1].position[0] - pixels[0].position[0], 1)
        )
