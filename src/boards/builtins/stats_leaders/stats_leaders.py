"""
Stats Leaders board module implementation.
"""
import logging
import traceback

from PIL import Image, ImageDraw

from boards.base_board import BoardBase
from nhl_api.workers import StatsLeadersWorker

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
        self.large_font = self.get_config_value('large_font', False)
        self.scroll_speed = self.get_config_value('scroll_speed', 0.2)
        self.limit = self.get_config_value('limit', 10)

        # Set font and sizing based on use_large_font config
        if self.large_font and self.matrix.width >= 128:
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

                # Get data from cache instead of API call
                leaders_data = StatsLeadersWorker.get_category(category)


                if not leaders_data:
                    debug.warning(f"Stats leaders board: No cached data for {category}, skipping")
                    continue

                # Calculate image height (header + players, using dynamic font_height)
                im_height = ((self.limit + 1) * self.font_height)  # header + configured number of players

                # Create and draw the image
                image = self.draw_leaders(category, leaders_data.leaders, im_height, self.matrix.width)

                # Create header title for sticky header
                header_title = f"NHL {self.categories[category]} LEADERS"

                # Initial position (start at top)
                i = 0
                self.matrix.draw_image((0, i), image)
                # Draw sticky header on top
                self._draw_sticky_header(header_title)
                self.matrix.render()
                self.sleepEvent.wait(5)  # Show top for 5 seconds

                # Scroll the image if it's taller than the matrix
                while i > -(im_height - self.matrix.height) and not self.sleepEvent.is_set():
                    i -= 1
                    self.matrix.draw_image((0, i), image)
                    # Redraw sticky header on top of scrolled content
                    self._draw_sticky_header(header_title)
                    self.matrix.render()
                    self.sleepEvent.wait(self.scroll_speed)

                # Show bottom for rotation_rate seconds
                self.sleepEvent.wait(self.rotation_rate)

        except Exception as e:
            debug.error(f"Error rendering stats leaders: {str(e)}")
            debug.error(f"Stack trace: {traceback.format_exc()}")

    def _draw_sticky_header(self, title: str):
        """
        Draw a sticky header that stays at the top during scrolling.

        Args:
            title: The header text to display
        """
        # Draw black rectangle to cover the scrolling content behind the header
        self.matrix.draw_rectangle((0, 0), (self.matrix.width, self.font_height - 1), fill=(0, 0, 0))
        # Draw the title text on top
        self.matrix.draw_text((1 * self.width_multiplier, 0), title, font=self.font, fill=(200, 200, 200))

    def format_toi(self, seconds):
        """Convert seconds to MM:SS format for time on ice display."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

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
        for idx, player in enumerate(leaders_data):
            # Get player info from structured data
            last_name = player.last_name
            abbrev = player.team_abbrev
            # Format TOI as MM:SS, otherwise use raw value
            if category == 'toi':
                stat = self.format_toi(player.value)
            else:
                stat = str(player.value)
            rank = str(idx + 1)

            # Get team colors
            team_id = self.data.teams_info_by_abbrev[abbrev].details.id
            team_colors = self.data.config.team_colors
            bg_color = team_colors.color(f"{team_id}.primary")
            txt_color = team_colors.color(f"{team_id}.text")

            # Draw rank (white) - scale x position
            draw.text((1 * self.width_multiplier, row_pos), rank, font=self.font)

            # Calculate name width for background rectangle
            name_width = self.font.getlength(last_name)

            # Draw background rectangle for name - scale x positions
            rect_x = 8 * self.width_multiplier
            draw.rectangle(
                [rect_x, row_pos, rect_x + name_width, row_pos + row_height - 1],
                fill=(bg_color['r'], bg_color['g'], bg_color['b'])
            )

            # Draw last name (in team text color) - scale x position
            draw.text((9 * self.width_multiplier + self.last_name_offset, row_pos), last_name,
                     fill=(txt_color['r'], txt_color['g'], txt_color['b']),
                     font=self.font)

            # Right-align stat count (white) with black background overlay
            stat_width = self.font.getlength(stat)
            stat_x = width - stat_width - (1 * self.width_multiplier)
            # Draw black background with 1px left padding for visual separation
            draw.rectangle(
                [stat_x - 1, row_pos, width, row_pos + row_height - 1],
                fill=(0, 0, 0)
            )
            draw.text((stat_x, row_pos), stat, font=self.font)

            row_pos += row_height

        return image
