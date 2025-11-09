from PIL import Image, ImageFont, ImageDraw, ImageSequence
from utils import center_text, convert_date_format, get_file
from renderer.matrix import MatrixPixels
import logging

from nhl_api.info import TeamInfo
from renderer.matrix import MatrixPixels

debug = logging.getLogger("scoreboard")

"""
    Show the details of a goal:
            - Time of the goal and which period
            - The players number, name and the team abbrev badge.
"""

class PenaltyRenderer:
    def __init__(self, data, matrix, sleepEvent, team):
        penalty_details = team.penalties[-1] # Get the last goal of the list of plays
        team_colors = data.config.team_colors
        team_id = penalty_details.team_id
        self.team: TeamInfo = data.teams_info[team_id]
        self.player = penalty_details.player
        self.periodTime = penalty_details.periodTime
        self.penaltyMinutes = penalty_details.penaltyMinutes # TODO: I don't know if we have this
        self.severity = penalty_details.severity
        self.rotation_rate = 10
        self.disable_animation = data.config.disable_penalty_animation
        self.matrix = matrix
        self.font = data.config.layout.font
        self.font_medium = data.config.layout.font_medium
        self.layout = data.config.config.layout.get_board_layout('penalty')
        self.sleepEvent = sleepEvent
        self.sleepEvent.clear()

        self.team_bg_color = team_colors.color("{}.primary".format(team_id))
        self.team_txt_color = team_colors.color("{}.text".format(team_id))

    def render(self):
        debug.debug("rendering goal detail board.")
        self.matrix.clear()
        self.draw_penalty()
        self.matrix.render()

        if not self.disable_animation:
            # Load the GIF once
            toaster = Image.open(get_file("assets/animations/penalty/penalty_animation.gif"))
            max_frames = toaster.n_frames
            debug.debug("Total frames in penalty GIF: {}".format(max_frames))

            # Calculate resize dimensions if needed (for smaller displays)
            resize_needed = self.matrix.width < 128
            if resize_needed:
                new_size = (toaster.width // 2, toaster.height // 2)
                debug.debug("Will resize penalty GIF frames to: {}".format(new_size))

            # Get frame duration (in milliseconds) from GIF, default to 100ms if not specified
            try:
                gif_duration = toaster.info.get('duration', 100)
                # Convert to seconds, but use default if duration is 0 or invalid
                frame_duration = gif_duration / 1000.0 if gif_duration > 0 else 0.1
                debug.debug("Frame duration from GIF: {} ms ({} seconds)".format(gif_duration, frame_duration))
            except (KeyError, AttributeError, TypeError):
                debug.debug("Frame duration not found in GIF info; defaulting to 0.1 seconds")
                frame_duration = 0.1

            # Ensure we start at frame 0
            toaster.seek(0)

            self.sleepEvent.wait(1)

            # Loop through all frames exactly once
            for frame_num in range(max_frames):
                debug.debug("Playing frame {} of {}".format(frame_num, max_frames))

                self.matrix.clear()

                # Convert frame to RGBA if needed
                frame = toaster.convert('RGBA')

                # Resize frame if needed (for smaller displays)
                if resize_needed:
                    frame = frame.resize(new_size, Image.Resampling.LANCZOS)

                # Flip the frame horizontally
                frame = frame.transpose(Image.FLIP_LEFT_RIGHT)

                # Draw the current frame
                self.matrix.draw_image(("75%", "25%"), frame, "center")

                # Draw penalty details on top of the frame
                self.draw_penalty()
                self.matrix.render()

                # Wait for the appropriate frame duration
                self.sleepEvent.wait(frame_duration)

                # Move to next frame (except for the last frame)
                if frame_num < max_frames - 1:
                    toaster.seek(frame_num + 1)


        # Final pause after animation completes
        self.sleepEvent.wait(self.rotation_rate)

    def draw_penalty(self):

        # self.matrix.draw_text(
        #     (1, 1),
        #     "Penalty @ {}".format(self.periodTime),
        #     font=self.font,
        #     fill=(0, 0, 0),
        #     backgroundColor=(255,195,12)
        # )

        self.matrix.draw_text_layout(
            self.layout.header,
            "PENALTY @ {}".format(self.periodTime),
            fillColor=(0, 0, 0),
            backgroundColor=(255,195,12)
        )

        self.matrix.draw_text_layout(
            self.layout.team_name,
            self.team.details.abbrev,
            fillColor=(self.team_txt_color['r'], self.team_txt_color['g'], self.team_txt_color['b']),
            backgroundColor=(self.team_bg_color['r'], self.team_bg_color['g'], self.team_bg_color['b'])
        )

        self.draw_hashtag()

        self.matrix.draw_text_layout(
            self.layout.jersey_number,
            str(self.player["sweaterNumber"])
        )

        self.matrix.draw_text_layout(
            self.layout.last_name,
            self.player["lastName"]["default"]
        )
        self.matrix.draw_text_layout(
            self.layout.minutes,
            "{}:00".format(self.penaltyMinutes),
        )
        self.matrix.draw_text_layout(
            self.layout.severity,
            self.severity,
            fillColor=(255,195,12),
        )

    def draw_hashtag(self):
        hashtag_dots = [
            (2,0),(4,0),
            (1,1),(2,1),(3,1),(4,1),(5,1),
            (2,2),(4,2),
            (1,3),(2,3),(3,3),(4,3),(5,3),
            (2,4),(4,4),
            ]
        pixels = []

        for dots_coord in range(len(hashtag_dots)):
            color = (255, 255, 255)
            pixels.append(
              MatrixPixels(
                hashtag_dots[dots_coord],
                color
              )
            )

        self.matrix.draw_pixels_layout(
            self.layout.hashtag_dots,
            pixels,
            (32, 10)
        )
