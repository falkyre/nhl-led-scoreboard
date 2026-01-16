"""
Team Summary board module implementation.

Displays a summary of favorite teams including record, last game, and next game.
"""
import logging
from datetime import datetime

from PIL import Image, ImageDraw

from boards.base_board import BoardBase
from nhl_api.workers import StandingsWorker, TeamScheduleWorker
from renderer.logos import LogoRenderer
from utils import convert_time, get_file

debug = logging.getLogger("scoreboard")

# Irregular game states that should be displayed differently
IRREGULAR_GAME_STATES = {"POSTPONED", "CANCELLED", "SUSPENDED", "TBD"}


class TeamSummaryBoard(BoardBase):
    """
    Team Summary Board.

    Displays favorite team summary with scrolling display showing:
    - Team record (GP, Points, W-L-OT)
    - Last game result
    - Next game info
    """

    def __init__(self, data, matrix, sleepEvent):
        super().__init__(data, matrix, sleepEvent)

        self.preferred_teams = data.pref_teams
        self.team_colors = data.config.team_colors
        self.font = data.config.layout.font
        self.layout = data.config.config.layout.get_board_layout('team_summary')
        self.time_format = data.config.time_format

        # Load config with automatic priority: central config -> board config -> defaults
        self.scroll_speed = self.get_config_value('scroll_speed', 0.3)
        self.rotation_rate = self.get_config_value('rotation_rate', 5)

    def render(self):
        # Get schedule data from TeamScheduleWorker
        schedules = TeamScheduleWorker.get_cached_data()
        # Get standings data from StandingsWorker
        standings = StandingsWorker.get_cached_data()

        if not schedules:
            debug.error("Team summary board unavailable due to missing schedule data from worker cache")
            return

        self.matrix.clear()

        for team_id in self.preferred_teams:
            if self.sleepEvent.is_set():
                break

            self._render_team(team_id, schedules, standings)

    def _render_team(self, team_id: int, schedules: dict, standings):
        """Render summary for a single team."""
        # Get cached schedule data for this team
        schedule_data = schedules.get(team_id)
        if not schedule_data:
            debug.warning(f"Team {team_id} not found in schedule worker cache")
            return

        team_abbrev = schedule_data.team_abbrev
        prev_game = schedule_data.previous_game
        next_game = schedule_data.next_game

        # Get record from standings worker (domain-specific data source)
        record = None
        if standings:
            team_standing = standings.get_team_by_id(team_id)
            if team_standing:
                record = {
                    'gamesPlayed': team_standing.games_played,
                    'points': team_standing.points,
                    'wins': team_standing.record.wins,
                    'losses': team_standing.record.losses,
                    'otLosses': team_standing.record.ot_losses
                }

        # Get team colors
        bg_color = self.team_colors.color(f"{team_id}.primary")
        txt_color = self.team_colors.color(f"{team_id}.text")

        # Create logo renderer
        logo_renderer = LogoRenderer(
            self.matrix,
            self.data.config,
            self.layout.logo,
            team_abbrev,
            'team_summary'
        )

        # Calculate image height for scrolling content
        im_height = 67

        if not self.sleepEvent.is_set():
            # Draw the team summary image
            image = self._draw_team_summary(
                team_id,
                record,
                prev_game,
                next_game,
                bg_color,
                txt_color,
                im_height
            )

            self.matrix.clear()

            # Load gradient image
            gradient = Image.open(get_file('assets/images/64x32_scoreboard_center_gradient.png'))
            if self.matrix.height == 64:
                gradient = Image.open(get_file('assets/images/128x64_scoreboard_center_gradient.png'))

            # Initial render
            logo_renderer.render()
            self.matrix.draw_image((25, 0), gradient, align="center")
            self.matrix.draw_image_layout(self.layout.info, image)
            self.matrix.render()

            self._render_indicators()

        self.sleepEvent.wait(self.rotation_rate)

        # Scroll the content
        i = 0
        while i > -(im_height - self.matrix.height) and not self.sleepEvent.is_set():
            i -= 1

            self.matrix.clear()
            logo_renderer.render()
            self.matrix.draw_image((25, 0), gradient, align="center")
            self.matrix.draw_image_layout(self.layout.info, image, (0, i))
            self.matrix.render()

            self._render_indicators()

            self.sleepEvent.wait(self.scroll_speed)

        # Show bottom before moving to next team
        self.sleepEvent.wait(self.rotation_rate)

    def _render_indicators(self):
        """Render network issue and update indicators."""
        if self.data.network_issues:
            self.matrix.network_issue_indicator()
        if self.data.newUpdate and not self.data.config.clock_hide_indicators:
            self.matrix.update_indicator()

    def _is_irregular_game(self, game: dict) -> bool:
        """Check if a game has an irregular status."""
        if not game:
            return False
        state = game.get("gameState", "")
        return state in IRREGULAR_GAME_STATES

    def _get_game_info(self, game: dict, team_id: int) -> dict:
        """Extract display info from a game dict without API calls."""
        if not game:
            return None

        away_team = game.get("awayTeam", {})
        home_team = game.get("homeTeam", {})

        away_id = away_team.get("id")
        home_id = home_team.get("id")
        away_abbrev = away_team.get("abbrev", "")
        home_abbrev = home_team.get("abbrev", "")
        away_score = away_team.get("score", 0)
        home_score = home_team.get("score", 0)

        # Determine opponent and location
        if away_id == team_id:
            opponent_abbrev = home_abbrev
            location = "@"
        else:
            opponent_abbrev = away_abbrev
            location = "VS"

        # Determine winner/loser for finished games
        game_state = game.get("gameState", "")
        winning_team_id = None
        losing_team_id = None

        if game_state in ("OFF", "FINAL", "OVER"):
            if away_score > home_score:
                winning_team_id = away_id
                losing_team_id = home_id
            else:
                winning_team_id = home_id
                losing_team_id = away_id

        # Parse date and time
        game_date = ""
        start_time = ""
        if game.get("gameDate"):
            game_date = datetime.strptime(game["gameDate"], '%Y-%m-%d').strftime("%b %d")
        if game.get("startTimeUTC"):
            start_dt = datetime.strptime(game["startTimeUTC"], '%Y-%m-%dT%H:%M:%SZ')
            start_time = convert_time(start_dt).strftime(self.time_format)

        return {
            "away_id": away_id,
            "home_id": home_id,
            "away_abbrev": away_abbrev,
            "home_abbrev": home_abbrev,
            "away_score": away_score,
            "home_score": home_score,
            "opponent_abbrev": opponent_abbrev,
            "location": location,
            "winning_team_id": winning_team_id,
            "losing_team_id": losing_team_id,
            "game_state": game_state,
            "is_irregular": game_state in IRREGULAR_GAME_STATES,
            "date": game_date,
            "start_time": start_time,
        }

    def _draw_team_summary(self, team_id, stats, prev_game, next_game,
                           bg_color, txt_color, im_height):
        """Draw the team summary image with record, last game, and next game info."""
        image = Image.new('RGB', (37, im_height))
        draw = ImageDraw.Draw(image)

        # Extract game info without API calls
        prev_info = self._get_game_info(prev_game, team_id)
        next_info = self._get_game_info(next_game, team_id)

        # Draw RECORD section
        draw.rectangle([0, -1, 26, 6], fill=(bg_color['r'], bg_color['g'], bg_color['b']))
        draw.text((1, 0), "RECORD:", fill=(txt_color['r'], txt_color['g'], txt_color['b']), font=self.font)

        if stats:
            draw.text(
                (0, 7),
                f"GP:{stats['gamesPlayed']} P:{stats['points']}",
                fill=(255, 255, 255),
                font=self.font
            )
            draw.text(
                (0, 13),
                f"{stats['wins']}-{stats['losses']}-{stats['otLosses']}",
                fill=(255, 255, 255),
                font=self.font
            )
        else:
            draw.text((1, 7), "--------", fill=(200, 200, 200), font=self.font)

        # Draw LAST GAME section
        draw.rectangle([0, 21, 36, 27], fill=(bg_color['r'], bg_color['g'], bg_color['b']))
        draw.text((1, 21), "LAST GAME:", fill=(txt_color['r'], txt_color['g'], txt_color['b']), font=self.font)

        if prev_info:
            # Show opponent
            draw.text(
                (0, 28),
                f"{prev_info['location']} {prev_info['opponent_abbrev']}",
                fill=(255, 255, 255),
                font=self.font
            )

            # Show result
            if prev_info['is_irregular']:
                draw.text((0, 34), prev_info['game_state'], fill=(255, 0, 0), font=self.font)
            else:
                score_text = f"{prev_info['away_score']}-{prev_info['home_score']}"
                if prev_info['winning_team_id'] == team_id:
                    draw.text((0, 34), "W", fill=(50, 255, 50), font=self.font)
                    draw.text((5, 34), score_text, fill=(255, 255, 255), font=self.font)
                elif prev_info['losing_team_id'] == team_id:
                    draw.text((0, 34), "L", fill=(255, 50, 50), font=self.font)
                    draw.text((5, 34), score_text, fill=(255, 255, 255), font=self.font)
        else:
            draw.text((1, 27), "--------", fill=(200, 200, 200), font=self.font)

        # Draw NEXT GAME section
        draw.rectangle([0, 42, 36, 48], fill=(bg_color['r'], bg_color['g'], bg_color['b']))
        draw.text((1, 42), "NEXT GAME:", fill=(txt_color['r'], txt_color['g'], txt_color['b']), font=self.font)

        if next_info:
            # Show date
            draw.text((0, 49), next_info['date'].upper(), fill=(255, 255, 255), font=self.font)

            # Show time or status
            if next_info['is_irregular']:
                status = next_info['game_state']
                if status == "Scheduled (Time TBD)":
                    status = "TBD"
                draw.text((0, 55), status.upper(), fill=(255, 0, 0), font=self.font)
            else:
                draw.text((0, 55), next_info['start_time'], fill=(255, 255, 255), font=self.font)

            # Show opponent
            draw.text(
                (0, 61),
                f"{next_info['location']} {next_info['opponent_abbrev']}",
                fill=(255, 255, 255),
                font=self.font
            )
        else:
            draw.text((1, 52), "--------", fill=(200, 200, 200), font=self.font)

        return image
