import logging

from PIL import Image

from data.scoreboard import Scoreboard
from renderer.logos import LogoRenderer
from utils import get_file

debug = logging.getLogger("scoreboard")
class ScoreboardRenderer:
    def __init__(self, data, matrix, scoreboard: Scoreboard, shot_on_goal=False):
        self.data = data
        self.status = data.status
        self.layout = self.data.config.config.layout.get_board_layout('scoreboard')
        self.font = self.data.config.layout.font
        self.font_large = self.data.config.layout.font_large
        self.team_colors = data.config.team_colors
        self.scoreboard = scoreboard
        self.matrix = matrix
        self.show_SOG = shot_on_goal

        self.home_logo_renderer = LogoRenderer(
            self.matrix,
            data.config,
            self.layout.home_logo,
            self.scoreboard.home_team.abbrev,
            'scoreboard',
            'home'
        )
        self.away_logo_renderer = LogoRenderer(
            self.matrix,
            data.config,
            self.layout.away_logo,
            self.scoreboard.away_team.abbrev,
            'scoreboard',
            'away'
        )

    def render(self):
        self.matrix.clear()
        # bg_away = self.team_colors.color("{}.primary".format(self.scoreboard.away_team.id))
        # bg_home = self.team_colors.color("{}.primary".format(self.scoreboard.home_team.id))
        # self.matrix.draw_rectangle((0,0), (64,64), (bg_away['r'],bg_away['g'],bg_away['b']))
        # self.matrix.draw_rectangle((64,0), (128,64), (bg_home['r'],bg_home['g'],bg_home['b']))
        display_width = self.matrix.width
        display_height = self.matrix.height

        self.matrix.draw_rectangle((0,0), ((display_width/2),display_height), (0,0,0))
        self.away_logo_renderer.render()

        self.matrix.draw_rectangle(((display_width/2),0), ((display_width),display_height), (0,0,0))
        self.home_logo_renderer.render()

        gradient = Image.open(get_file('assets/images/64x32_scoreboard_center_gradient.png'))

        # For 128x64 use the bigger gradient image.
        if display_height == 64:
            gradient = Image.open(get_file('assets/images/128x64_scoreboard_center_gradient.png'))

        self.matrix.draw_image((display_width/2,0), gradient, align="center")

        if self.scoreboard.is_scheduled:
            self.draw_scheduled()

        if self.scoreboard.is_live:
            self.draw_live()

        if self.scoreboard.is_game_over:
            self.draw_final()

        if self.scoreboard.is_final:
            self.draw_final()

        if self.scoreboard.is_irregular:
            self.draw_irregular()

    def draw_scheduled(self):
        start_time = self.scoreboard.start_time

        # Draw the text on the Data image.
        self.matrix.draw_text_layout(
          self.layout.scheduled_date,
          'TODAY'
        )
        self.matrix.draw_text_layout(
          self.layout.scheduled_time,
          start_time
        )

        self.matrix.draw_text_layout(
          self.layout.vs,
          'VS'
        )


        self.matrix.render()

    def draw_live(self):
        # Get the Info
        period = self.scoreboard.periods.ordinal
        clock = self.scoreboard.periods.clock
        score = '{}-{}'.format(self.scoreboard.away_team.goals, self.scoreboard.home_team.goals)

        if self.show_SOG:
            self.draw_SOG()
            self.show_SOG = False
        else:
            # Draw the info
            self.matrix.draw_text_layout(
                self.layout.period,
                period,
            )
            self.matrix.draw_text_layout(
                self.layout.clock,
                clock
            )

        self.matrix.draw_text_layout(
            self.layout.score,
            score
        )

        self.matrix.render()

        if self.scoreboard.away_team.powerplay or self.scoreboard.home_team.powerplay:
            debug.debug("Drawing power play info")
            self.draw_power_play()


    def draw_final(self):
        # Get the Info
        period = self.scoreboard.periods.ordinal
        score = '{}-{}'.format(self.scoreboard.away_team.goals, self.scoreboard.home_team.goals)

        # Draw the info
        self.matrix.draw_text_layout(
            self.layout.center_top,
            str(self.scoreboard.date)
        )

        end_text = "FINAL"
        if self.scoreboard.periods.number >= 3:
            end_text = "F/{}".format(period)

        self.matrix.draw_text_layout(
            self.layout.period_final,
            end_text
        )

        self.matrix.draw_text_layout(
            self.layout.score,
            score
        )

        self.matrix.render()

    def draw_irregular(self):
        status = self.scoreboard.status
        if status == "Postponed":
            status = "PPD"

        # Draw the text on the Data image.
        self.matrix.draw_text_layout(
            self.layout.center_top,
            'TODAY'
        )
        self.matrix.draw_text_layout(
            self.layout.irregular_status,
            status
        )
        self.matrix.draw_text_layout(
            self.layout.vs,
            'VS'
        )
        self.matrix.render()

    def draw_power_play(self):
        # Get the Info - power play time remaining and skater counts
        pp_time = self.scoreboard.home_team.pp_time_remaining or self.scoreboard.away_team.pp_time_remaining or "1:23"
        max_skaters = max(self.scoreboard.home_team.num_skaters, self.scoreboard.away_team.num_skaters)
        min_skaters = min(self.scoreboard.home_team.num_skaters, self.scoreboard.away_team.num_skaters)

        # Is home team or away team on power play
        pp_team = self.scoreboard.home_team if self.scoreboard.home_team.powerplay else self.scoreboard.away_team

        # Get the team colors
        pp_team_color = self.team_colors.color("{}.primary".format(pp_team.id))
        text_color = self.team_colors.color("{}.text".format(pp_team.id))

        # Build the power play text - varies on matrix size
        if self.matrix.width < 128:
            pp_text = "PP"
        else:
            pp_text = f"{pp_team.abbrev} PP {max_skaters}-{min_skaters}"

        debug.debug("Power Play Info: {} {} {}".format(pp_team.abbrev, max_skaters, min_skaters))

        # Home team Powerplay
        if self.scoreboard.home_team.powerplay:
            self.matrix.draw_text_layout(
                self.layout.pp_badge_home_time,
                pp_time
            )
            self.matrix.draw_text_layout(
                self.layout.pp_badge_home,
                pp_text,
                backgroundColor=(pp_team_color['r'], pp_team_color['g'], pp_team_color['b']),
                fillColor=(text_color['r'], text_color['g'], text_color['b'])
            )

        # Away team Powerplay
        if self.scoreboard.away_team.powerplay:
            self.matrix.draw_text_layout(
                self.layout.pp_badge_away_time,
                pp_time
            )
            self.matrix.draw_text_layout(
                self.layout.pp_badge_away,
                pp_text,
                backgroundColor=(pp_team_color['r'], pp_team_color['g'], pp_team_color['b']),
                fillColor=(text_color['r'], text_color['g'], text_color['b'])
            )

        self.matrix.render()

    def draw_SOG(self):

        # Draw the Shot on goal
        SOG = '{}-{}'.format(self.scoreboard.away_team.shot_on_goal, self.scoreboard.home_team.shot_on_goal)

        self.matrix.draw_text_layout(
            self.layout.SOG_label,
            "SHOTS"
        )
        self.matrix.draw_text_layout(
            self.layout.SOG,
            SOG
        )
