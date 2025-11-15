"""
Stats Leaders board module implementation.
"""
from PIL import Image, ImageDraw
from utils import get_file
from nhl_api.data import get_skater_stats_leaders
import logging
import traceback

from boards.base_board import BoardBase

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
                if not category in self.categories:
                    debug.error(f"Stats leaders board unavailable due to missing information from the API for category: {category}")
                    return

                # Use the imported function directly
                leaders_data = get_skater_stats_leaders(category=category, limit=10)

                if not leaders_data or category not in leaders_data:
                    debug.error(f"Stats leaders board unavailable due to missing information from the API for category: {category}")
                    return

                # Calculate image height (header + 10 players * 7 pixels per row)
                im_height = (11 * 7)  # 11 rows total (1 header + 10 players)

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
                    self.sleepEvent.wait(0.2)  # Scroll speed

                # Show bottom for rotation_rate seconds
                self.sleepEvent.wait(self.rotation_rate)

        except Exception as e:
            debug.error(f"Error rendering stats leaders: {str(e)}")
            debug.error(f"Stack trace: {traceback.format_exc()}")

    def draw_leaders(self, category, leaders_data, img_height, width):
        """Draw an image showing the top goal scorers"""

        # Create a new image
        image = Image.new('RGB', (width, img_height))
        draw = ImageDraw.Draw(image)

        # Start position
        row_pos = 0
        row_height = 7
        top = row_height - 1

        # Draw header
        draw.text((1, 0), f"NHL {self.categories[category]} LEADERS", font=self.layout.font)
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

            # Draw rank (white)
            draw.text((1, row_pos), rank + ".", font=self.layout.font)

            # Calculate name width for background rectangle
            name_width = self.layout.font.getlength(last_name)

            # Draw background rectangle for name
            draw.rectangle(
                [14, row_pos, 14 + name_width, row_pos + row_height - 1],
                fill=(bg_color['r'], bg_color['g'], bg_color['b'])
            )

            # Draw last name (in team text color)
            draw.text((15, row_pos), last_name,
                     fill=(txt_color['r'], txt_color['g'], txt_color['b']),
                     font=self.layout.font)

            # Right-align goals count (white)
            stat_width = self.layout.font.getlength(stat)
            draw.text((width - stat_width - 1, row_pos), stat, font=self.layout.font)

            row_pos += row_height

        return image
