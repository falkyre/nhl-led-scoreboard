"""
Stats Leaders board module implementation.
"""
import logging
import traceback

from PIL import Image, ImageDraw

from boards.base_board import BoardBase
from nhl_api.data import get_skater_stats_leaders

debug = logging.getLogger("scoreboard")

class StatsLeadersBoard(BoardBase):
    """
    NHL Statistics Leaders Board.

    Displays top NHL skater statistics across various categories like goals,
    assists, points, etc. with scrolling display of top 10 players.
    """

    def __init__(self, data, matrix, sleepEvent):
        super().__init__(data, matrix, sleepEvent)

        self.team_colors = data.config.team_colors
        self.layout = data.config.layout

        # Load config with automatic priority: central config -> board config -> defaults
        self.enabled_categories = self.get_config_value('categories', ['goals', 'assists', 'points'])
        self.rotation_rate = self.get_config_value('rotation_rate', 5)
        self.use_large_font = self.get_config_value('use_large_font', False)
        self.scroll_speed = self.get_config_value('scroll_speed', 0.2)
        self.limit = self.get_config_value('limit', 10)

        # Set font and sizing based on use_large_font config
        if self.use_large_font and self.matrix.width >= 128:
            self.font = data.config.layout.font_large
            self.font_height = 13
            self.width_multiplier = 2
            self.last_name_offset = -1
        else:
            self.font = data.config.layout.font
            self.font_height = 7
            self.width_multiplier = 1
            self.last_name_offset = 0

        # Dictionary mapping API categories to display names
        self.categories = {
            'goals': 'GOAL',
            'points': 'POINT',
            'assists': 'ASSIST',
            'toi': 'TOI',
            'plusMinus': '+/-',
            'penaltyMins': 'PIM',
            'faceoffLeaders': 'FO%',
            'goalsPp': 'PPG',
            'goalsSh': 'SHG'
        }

    def render(self):
        try:
            for category in self.enabled_categories:
                # Check if the category is valid
                if category not in self.categories:
                    debug.error(f"Stats leaders board unavailable. Missing API information for category: {category}")
                    return

                # Use the imported function directly
                leaders_data = get_skater_stats_leaders(category=category, limit=self.limit)

                if not leaders_data or category not in leaders_data:
                    debug.error(f"Stats leaders board unavailable. Missing API information for category: {category}")
                    return

                # Calculate image height (header + players, using dynamic font_height)
                im_height = ((self.limit + 1) * self.font_height)  # header + configured number of players

                # Create and draw the image
                image = self.draw_leaders(category, leaders_data[category], im_height, self.matrix.width)

                # Initial position (start at top)
                i = 0
                self.matrix.draw_image((0, i), image)
                self.matrix.render()
                self.sleepEvent.wait(5)  # Show top for 5 seconds

                # Scroll the image if it's taller than the matrix
                while i > -(im_height - self.matrix.height) and not self.sleepEvent.is_set():
                    i -= 1
                    self.matrix.draw_image((0, i), image)
                    self.matrix.render()
                    self.sleepEvent.wait(self.scroll_speed)

                # Show bottom for rotation_rate seconds
                self.sleepEvent.wait(self.rotation_rate)

        except Exception as e:
            debug.error(f"Error rendering stats leaders: {str(e)}")
            debug.error(f"Stack trace: {traceback.format_exc()}")

    def draw_leaders(self, category, leaders_data, img_height, width):
        """Draw an image showing the stat leaders with dynamic font sizing"""

        # Create a new image
        image = Image.new('RGB', (width, img_height))
        draw = ImageDraw.Draw(image)

        # Start position
        row_pos = 0
        row_height = self.font_height
        top = row_height - 1

        # Draw header
        draw.text((1 * self.width_multiplier, 0), f"NHL {self.categories[category]} LEADERS", font=self.font)
        row_pos += row_height

        # Draw each player's stats
        for player in leaders_data:
            # Get player info
            last_name = player['lastName']['default']
            abbrev = player['teamAbbrev']
            stat = str(player['value'])
            rank = str(leaders_data.index(player) + 1)

            # Get team colors
            team_id = self.data.teams_info_by_abbrev[abbrev].details.id
            team_colors = self.data.config.team_colors
            bg_color = team_colors.color(f"{team_id}.primary")
            txt_color = team_colors.color(f"{team_id}.text")

            # Draw rank (white) - scale x position
            draw.text((1 * self.width_multiplier, row_pos), rank + ".", font=self.font)

            # Calculate name width for background rectangle
            name_width = self.font.getlength(last_name)

            # Draw background rectangle for name - scale x positions
            rect_x = 14 * self.width_multiplier
            draw.rectangle(
                [rect_x, row_pos, rect_x + name_width, row_pos + row_height - 1],
                fill=(bg_color['r'], bg_color['g'], bg_color['b'])
            )

            # Draw last name (in team text color) - scale x position
            draw.text((15 * self.width_multiplier + self.last_name_offset, row_pos), last_name,
                     fill=(txt_color['r'], txt_color['g'], txt_color['b']),
                     font=self.font)

            # Right-align stat count (white)
            stat_width = self.font.getlength(stat)
            draw.text((width - stat_width - (1 * self.width_multiplier), row_pos), stat, font=self.font)

            row_pos += row_height

        return image
