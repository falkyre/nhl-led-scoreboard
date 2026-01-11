"""
Standings board module implementation.
"""
import logging

from PIL import Image, ImageDraw

from boards.base_board import BoardBase
from nhl_api.workers import StandingsWorker

debug = logging.getLogger("scoreboard")


class StandingsBoard(BoardBase):
    """
    NHL Standings Board.

    Displays NHL standings by conference, division, or wild card with scrolling display.
    """

    def __init__(self, data, matrix, sleepEvent):
        super().__init__(data, matrix, sleepEvent)

        self.conferences = ["eastern", "western"]
        self.divisions = ["metropolitan", "atlantic", "central", "pacific"]
        self.team_colors = data.config.team_colors

        # Load config with automatic priority: central config -> board config -> defaults
        self.standing_type = self.get_config_value('standing_type', 'division')
        self.preferred_standings_only = self.get_config_value('preferred_standings_only', False)
        self.preferred_conference = self.get_config_value('preferred_conference', 'eastern')
        self.preferred_divisions = self.get_config_value('preferred_divisions', 'metropolitan')
        self.wildcard_limit = self.get_config_value('wildcard_limit', 8)
        self.use_large_font = self.get_config_value('standings_large_font', False)
        self.scroll_speed = self.get_config_value('scroll_speed', 0.2)
        self.rotation_rate = self.get_config_value('rotation_rate', 5)

        # Set font and sizing based on use_large_font config
        if self.use_large_font and self.matrix.width >= 128:
            self.font = data.config.layout.font_large
            self.font_height = 13
            self.width_multiplier = 2
        else:
            self.font = data.config.layout.font
            self.font_height = 7
            self.width_multiplier = 1

    def render(self):
        # Get standings data from worker cache
        standings = StandingsWorker.get_cached_data()

        if not standings:
            debug.error("Standing board unavailable due to missing standings data from worker cache")
            return

        # Store standings reference for rendering methods
        self._standings = standings

        if self.preferred_standings_only:
            self._render_preferred_standings()
        else:
            self._render_all_standings()

    def _render_preferred_standings(self):
        """Render only the preferred conference/division standings"""
        if self.standing_type == 'conference':
            records = getattr(self._standings.by_conference, self.preferred_conference)
            self._render_standing_table(self.preferred_conference, records)

        elif self.standing_type == 'division':
            records = getattr(self._standings.by_division, self.preferred_divisions)
            self._render_standing_table(self.preferred_divisions, records)

        elif self.standing_type == 'wild_card':
            self._render_wildcard_standings(self.preferred_conference)

    def _render_all_standings(self):
        """Render all conferences/divisions standings"""
        if self.standing_type == 'conference':
            for conference in self.conferences:
                if self.sleepEvent.is_set():
                    break
                records = getattr(self._standings.by_conference, conference)
                self._render_standing_table(conference, records, show_indicators=True)

        elif self.standing_type == 'division':
            for division in self.divisions:
                if self.sleepEvent.is_set():
                    break
                records = getattr(self._standings.by_division, division)
                self._render_standing_table(division, records)

        elif self.standing_type == 'wild_card':
            for conf_name, conf_data in vars(self._standings.by_wildcard).items():
                if self.sleepEvent.is_set():
                    break
                self._render_wildcard_standings(conf_name)

    def _render_standing_table(self, name, records, show_indicators=False):
        """Render a single standings table with scrolling and sticky header"""
        # Calculate the image height
        im_height = (len(records) + 1) * self.font_height

        # Create the standings image
        image = self._draw_standing(name, records, im_height, self.matrix.width)

        # Start at the top
        i = 0
        self.matrix.draw_image((0, i), image)
        # Draw sticky header on top
        self._draw_sticky_header(name)
        self.matrix.render()

        if show_indicators:
            if self.data.network_issues:
                self.matrix.network_issue_indicator()
            if self.data.newUpdate and not self.data.config.clock_hide_indicators:
                self.matrix.update_indicator()

        self.sleepEvent.wait(5)

        # Scroll the image up until we hit the bottom
        while i > -(im_height - self.matrix.height) and not self.sleepEvent.is_set():
            i -= 1
            self.matrix.draw_image((0, i), image)
            # Redraw sticky header on top of scrolled content
            self._draw_sticky_header(name)
            self.matrix.render()

            if show_indicators:
                if self.data.network_issues:
                    self.matrix.network_issue_indicator()
                if self.data.newUpdate and not self.data.config.clock_hide_indicators:
                    self.matrix.update_indicator()

            self.sleepEvent.wait(self.scroll_speed)

        # Show the bottom before moving to next table
        self.sleepEvent.wait(self.rotation_rate)

    def _draw_sticky_header(self, title: str):
        """
        Draw a sticky header that stays at the top during scrolling.

        Args:
            title: The header text to display
        """
        # Draw black rectangle to cover the scrolling content behind the header
        self.matrix.draw_rectangle((0, 0), (self.matrix.width, self.font_height - 1), fill=(0, 0, 0))
        # Draw the title text on top
        self.matrix.draw_text((1, 0), title, font=self.font, fill=(200, 200, 200))

    def _render_wildcard_standings(self, conf_name):
        """Render wildcard standings for a conference"""
        conf_data = getattr(self._standings.by_wildcard, conf_name)
        wildcard_records = {
            "conference": conf_name,
            "wild_card": conf_data.wild_card,
            "division_leaders": conf_data.division_leaders
        }

        # Calculate image height
        number_of_rows = 10 + self.wildcard_limit
        table_offset = 3
        img_height = (number_of_rows * self.font_height) + (table_offset * 2)

        # Create the wildcard image
        image = self._draw_wild_card(
            wildcard_records,
            self.matrix.width,
            img_height,
            table_offset
        )

        # Start at the top
        i = 0
        self.matrix.draw_image((0, i), image)
        # Draw sticky header on top
        self._draw_sticky_header(conf_name)
        self.matrix.render()
        self.sleepEvent.wait(5)

        # Scroll the image up until we hit the bottom
        while i > -(img_height - self.matrix.height) and not self.sleepEvent.is_set():
            i -= 1
            self.matrix.draw_image((0, i), image)
            # Redraw sticky header on top of scrolled content
            self._draw_sticky_header(conf_name)
            self.matrix.render()
            self.sleepEvent.wait(self.scroll_speed)

        self.sleepEvent.wait(self.rotation_rate)

    def _draw_standing(self, name, records, img_height, width):
        """Draw an image of standings records for each team"""
        image = Image.new('RGB', (width, img_height))
        draw = ImageDraw.Draw(image)

        row_pos = 0
        row_height = self.font_height
        top = row_height - 1

        # Draw header
        draw.text((1, 0), name, font=self.font)
        row_pos += row_height

        # Draw each team
        for team in records:
            abbrev = team["teamAbbrev"]["default"]
            team_id = self.data.teams_info_by_abbrev[abbrev].details.id
            points = str(team["points"])
            wins = team["wins"]
            losses = team["losses"]
            ot = team["otLosses"]

            # Get team colors
            bg_color = self.team_colors.color(f"{team_id}.primary")
            txt_color = self.team_colors.color(f"{team_id}.text")

            # Draw team abbreviation with background
            draw.rectangle(
                [0, row_pos, 12 * self.width_multiplier, top + row_pos],
                fill=(bg_color['r'], bg_color['g'], bg_color['b'])
            )
            draw.text(
                (1 * self.width_multiplier, row_pos),
                abbrev,
                fill=(txt_color['r'], txt_color['g'], txt_color['b']),
                font=self.font
            )

            # Draw record (W-L-OT)
            draw.text(
                (19 * self.width_multiplier, row_pos),
                f"{wins}-{losses}-{ot}",
                font=self.font
            )

            # Draw points (right-aligned)
            if len(points) == 3:
                draw.text((54 * self.width_multiplier, row_pos), points, font=self.font)
            else:
                draw.text((57 * self.width_multiplier, row_pos), points, font=self.font)

            row_pos += row_height

        return image

    def _draw_wild_card(self, wildcard_records, width, img_height, offset):
        """Draw wildcard standings with division leaders and wild card teams"""
        image = Image.new('RGB', (width, img_height))
        draw = ImageDraw.Draw(image)

        row_pos = 0
        row_height = self.font_height
        top = row_height - 1

        # Draw conference name
        draw.text((1, 0), wildcard_records["conference"], font=self.font)
        row_pos += row_height

        # Division pairs for each conference
        division_pairs = {
            'eastern': ["metropolitan", "atlantic"],
            'western': ["central", "pacific"]
        }

        divisions = division_pairs.get(wildcard_records["conference"].lower(), ["metropolitan", "atlantic"])

        # Draw division leaders
        for division_name in divisions:
            draw.text((1, row_pos), division_name, font=self.font)
            row_pos += row_height

            teams = getattr(wildcard_records["division_leaders"], division_name, [])
            for team in teams:
                row_pos = self._draw_wildcard_team(draw, team, row_pos, top)

            row_pos += offset

        # Draw wild card teams
        draw.text((1, row_pos), "wild card", font=self.font)
        row_pos += row_height

        for team in wildcard_records["wild_card"][:self.wildcard_limit]:
            row_pos = self._draw_wildcard_team(draw, team, row_pos, top, show_clinch=False)

        return image

    def _draw_wildcard_team(self, draw, team, row_pos, top, show_clinch=True):
        """Draw a single team in the wildcard standings"""
        abbrev = team["teamAbbrev"]["default"]
        team_id = self.data.teams_info_by_abbrev[abbrev].details.id
        points = str(team["points"])
        wins = team["wins"]
        losses = team["losses"]
        ot = team["otLosses"]
        clinched = team.get("clinchIndicator", False) if show_clinch else False

        # Get team colors
        bg_color = self.team_colors.color(f"{team_id}.primary")
        txt_color = self.team_colors.color(f"{team_id}.text")

        # Draw team abbreviation with background
        draw.rectangle(
            [0, row_pos, 12 * self.width_multiplier, top + row_pos],
            fill=(bg_color['r'], bg_color['g'], bg_color['b'])
        )
        draw.text(
            (1 * self.width_multiplier, row_pos),
            abbrev,
            fill=(txt_color['r'], txt_color['g'], txt_color['b']),
            font=self.font
        )

        # Draw record (W-L-OT)
        draw.text(
            (19 * self.width_multiplier, row_pos),
            f"{wins}-{losses}-{ot}",
            font=self.font
        )

        # Draw points (green if clinched, white otherwise)
        pts_color = (0, 255, 0) if clinched else (255, 255, 255)
        pts_x_pos = 57 * self.width_multiplier if len(points) < 3 else 54 * self.width_multiplier
        draw.text((pts_x_pos, row_pos), points, fill=pts_color, font=self.font)

        row_pos += self.font_height
        return row_pos
