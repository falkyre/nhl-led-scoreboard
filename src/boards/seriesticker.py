"""
    Shows list of series summary (Table with each result of game).
"""
import logging
from datetime import datetime, timezone

from PIL import Image

from data.data import Data

# from data.playoffs import Series
from data.scoreboard import Scoreboard
from nhl_api.data import get_game
from renderer.matrix import Matrix, MatrixPixels
from utils import get_file

debug = logging.getLogger("scoreboard")

class Seriesticker:
    def __init__(self, data: Data, matrix: Matrix, sleepEvent):
        self.data = data
        self.matrix = matrix
        self.sleepEvent = sleepEvent
        self.sleepEvent.clear()

        self.layout = self.data.config.config.layout.get_board_layout('seriesticker')
        self.team_colors = self.data.config.team_colors


        self.top_seed_scores = [
            self.layout.top_seed_score_1,
            self.layout.top_seed_score_2,
            self.layout.top_seed_score_3,
            self.layout.top_seed_score_4,
            self.layout.top_seed_score_5,
            self.layout.top_seed_score_6,
            self.layout.top_seed_score_7,
        ]
        self.top_seed_scores_bg = [
            self.layout.top_seed_score_1_bg,
            self.layout.top_seed_score_2_bg,
            self.layout.top_seed_score_3_bg,
            self.layout.top_seed_score_4_bg,
            self.layout.top_seed_score_5_bg,
            self.layout.top_seed_score_6_bg,
            self.layout.top_seed_score_7_bg,
        ]

        self.bottom_seed_scores = [
            self.layout.bottom_seed_score_1,
            self.layout.bottom_seed_score_2,
            self.layout.bottom_seed_score_3,
            self.layout.bottom_seed_score_4,
            self.layout.bottom_seed_score_5,
            self.layout.bottom_seed_score_6,
            self.layout.bottom_seed_score_7,
        ]
        self.bottom_seed_scores_bg = [
            self.layout.bottom_seed_score_1_bg,
            self.layout.bottom_seed_score_2_bg,
            self.layout.bottom_seed_score_3_bg,
            self.layout.bottom_seed_score_4_bg,
            self.layout.bottom_seed_score_5_bg,
            self.layout.bottom_seed_score_6_bg,
            self.layout.bottom_seed_score_7_bg,
        ]

        # Adjustments for 128x64 screen
        if self.matrix.width >=128:
            self.header_padding = [2,2,2,2]
            self.status_message = "{} LEADS SERIES {} - {}"
            self.stanley_cup_logo = "assets/images/128x64_StanleyCup.png"
        else:
            self.header_padding = [1,1,1,1]
            self.status_message = "{} LEADS {}-{}"
            self.stanley_cup_logo = False

    def render(self):
        if not self.data.current_round:
            debug.debug("No Playoff to render on seriesticker")
            return
        playoff_series = self.data.series
        self.index = 0

        # Check option to hide completed rounds and filter
        if self.data.config.seriesticker_hide_completed_rounds:
            playoff_series = [
                s for s in self.data.series
                if getattr(s, "round_number", 0) >= self.data.current_round["roundNumber"]
            ]

        self.num_series = len(playoff_series)

        for series in playoff_series:
            self.matrix.clear()
            banner_text = "STANLEY CUP"
            color_banner_bg = (200,200,200)
            round_name = "FINAL"

            # Draw Stanley Cup logo on larger displays
            if self.stanley_cup_logo:
                img = get_file(self.stanley_cup_logo)
                img = Image.open(img)
                self.matrix.draw_image_layout(
                    self.layout.stanley_cup_logo,
                    img
                )

            if not series.round_number == 4:
                try:
                    color_conf = self.team_colors.color("{}.primary".format(series.conference))
                    banner_text = series.conference[:4].upper()
                except Exception:
                    color_conf = self.team_colors.color("{}.primary".format("Western"))
                    banner_text = "WEST"
                color_banner_bg = (color_conf['r'], color_conf['g'], color_conf['b'])
                round_name = series.round_name.replace("-"," ").upper()
                if round_name == "CONFERENCE FINALS":
                    round_name = "CONF FINALS"
                self.show_indicator(self.index, self.num_series)

            # STANLEY CUP FINAL or EAST/WEST CONFERENCE FINALS
            if series.round_number >= 3:
                banner_text = f"{banner_text} {round_name}"
            else:
                # EAST/WEST - 1ST/2ND ROUND
                banner_text = f"{banner_text} - {round_name}"


            top_team_wins = series.top_team.series_wins
            bottom_team_wins = series.bottom_team.series_wins

            # Determine the series overview message
            # Series hasn't started yet
            if top_team_wins == 0 and bottom_team_wins == 0:
                series_overview = "SERIES UPCOMING"
            # Series is tied
            elif top_team_wins == bottom_team_wins:
                series_overview = f"SERIES TIED {top_team_wins}-{bottom_team_wins}"
            # Top team won
            elif top_team_wins == 4:
                series_overview = f"{series.top_team.abbrev} WON SERIES {top_team_wins}-{bottom_team_wins}"
            # Bottom team won
            elif bottom_team_wins == 4:
                series_overview = f"{series.bottom_team.abbrev} WON SERIES {bottom_team_wins}-{top_team_wins}"
            # Top team is leading
            elif top_team_wins > bottom_team_wins:
                series_overview = self.status_message.format(series.top_team.abbrev, top_team_wins, bottom_team_wins)
            # Bottom team is leading
            else:
                series_overview = self.status_message.format(series.bottom_team.abbrev, bottom_team_wins, top_team_wins)

            # Conference banner, Round Title
            self.matrix.draw_text_layout(
                self.layout.header,
                banner_text,
                align="left",
                fillColor=(0,0,0,),
                backgroundColor=color_banner_bg,
                backgroundOffset=self.header_padding
            )

            self.draw_series_table(series)

            self.matrix.draw_text_layout(
                self.layout.overview,
                series_overview
            )

            self.matrix.render()
            self.index += 1
            self.sleepEvent.wait(self.data.config.seriesticker_rotation_rate)

    def draw_series_table(self, series):

        color_top_bg = self.team_colors.color("{}.primary".format(series.top_team.id))
        color_top_team = self.team_colors.color("{}.text".format(series.top_team.id))

        color_bottom_bg = self.team_colors.color("{}.primary".format(series.bottom_team.id))
        color_bottom_team = self.team_colors.color("{}.text".format(series.bottom_team.id))

        # Draw separator line between teams
        self.grid_row_y = self.layout.seperator.position[1]
        self.matrix.draw.line([(0,self.grid_row_y),(self.matrix.width,self.grid_row_y)], width=1, fill=(150,150,150))

        # Draw team abbrev and backgrounds
        self.matrix.draw_rectangle_layout(
            self.layout.top_seed_bg,
            fillColor=(color_top_bg['r'], color_top_bg['g'], color_top_bg['b'])
        )
        self.matrix.draw_text_layout(
            self.layout.top_seed,
            series.top_team.abbrev,
            fillColor=(color_top_team['r'], color_top_team['g'], color_top_team['b'])
        )

        self.matrix.draw_rectangle_layout(
            self.layout.bottom_seed_bg,
            fillColor=(color_bottom_bg['r'], color_bottom_bg['g'], color_bottom_bg['b'])
        )
        self.matrix.draw_text_layout(
            self.layout.bottom_seed,
            series.bottom_team.abbrev,
            fillColor=(color_bottom_team['r'], color_bottom_team['g'], color_bottom_team['b'])
        )

        loosing_color = (150,150,150)
        loosing_color_bg = (0,0,0)

        game_count = 0
        for game in series.games:
            game_count += 1
            attempts_remaining = 5
            while attempts_remaining > 0:
                try:
                    # Get the game object
                    game_obj = get_game(game["id"])

                    # Get the game overview
                    overview = series.get_game_overview(game["id"])

                    # get the scoreboard
                    try:
                        scoreboard = Scoreboard(overview, self.data, game_obj)
                    except Exception:
                        break

                    # If the game is final, draw the winning and loosing team scores
                    if (game_obj.is_final and hasattr(scoreboard, "winning_team_id")):
                        if scoreboard.winning_team_id == series.top_team.id:
                            winning_layout = self.top_seed_scores[game_count - 1]
                            winning_layout_bg = self.top_seed_scores_bg[game_count - 1]
                            loosing_layout = self.bottom_seed_scores[game_count - 1]
                            loosing_layout_bg = self.bottom_seed_scores_bg[game_count - 1]
                            winning_team_color = color_top_team
                            winning_bg_color = color_top_bg
                        else:
                            winning_layout = self.bottom_seed_scores[game_count - 1]
                            winning_layout_bg = self.bottom_seed_scores_bg[game_count - 1]
                            loosing_layout = self.top_seed_scores[game_count - 1]
                            loosing_layout_bg = self.top_seed_scores_bg[game_count - 1]
                            winning_team_color = color_bottom_team
                            winning_bg_color = color_bottom_bg

                        self.matrix.draw_rectangle_layout(
                            loosing_layout_bg,
                            fillColor=loosing_color_bg
                        )

                        self.matrix.draw_rectangle_layout(
                            winning_layout_bg,
                            fillColor=(winning_bg_color['r'], winning_bg_color['g'], winning_bg_color['b']),
                        )

                        self.matrix.draw_text_layout(
                            loosing_layout,
                            str(scoreboard.losing_score),
                            fillColor=loosing_color
                        )

                        self.matrix.draw_text_layout(
                            winning_layout,
                            str(scoreboard.winning_score),
                            fillColor=(winning_team_color['r'], winning_team_color['g'], winning_team_color['b']),
                        )

                    # process the "current game" -- which is the current or next game
                    if game["id"] == series.current_game_id:
                        # show the next game info on larger displays
                        series_overview_game = ""
                        next_game_number = series.top_team.series_wins + series.bottom_team.series_wins + 1
                        if self.matrix.width >= 128:
                            if game_obj.is_live:
                                series_overview_game = "GAME IS LIVE"
                            elif scoreboard.date == datetime.now(timezone.utc).strftime("%b %d"):
                                series_overview_game = f"GAME {next_game_number}: TODAY @ {scoreboard.start_time}"
                            else:
                                game_date = scoreboard.date.upper()
                                series_overview_game = f"GAME {next_game_number}: {game_date} @ {scoreboard.start_time}"

                            self.matrix.draw_text_layout(
                                self.layout.overview_game,
                                series_overview_game
                            )

                    # If the game doesnt hit a condition above, break the loop
                    # this assumes games are in order from oldest to newest
                    # we dont need to process future games so we break instead of looping through them
                    break

                except ValueError as error_message:
                    self.data.network_issues = True
                    debug.error(
                        "Failed to get the Games for the {} VS {} series: {} attempts remaining".format(
                            series.top_team.abbrev,
                            series.bottom_team.abbrev,
                            attempts_remaining,
                        )
                    )
                    debug.error(error_message)
                    attempts_remaining -= 1
                    self.sleepEvent.wait(1)
                except KeyError as error_message:
                    debug.error(
                        "Failed to get the overview for game id {}. Data unavailable or is TBD".format(
                            game["gameId"]
                        )
                    )
                    debug.error(error_message)
                    break
            # If one of the request for player info failed after 5 attempts, return an empty dictionary
            if attempts_remaining == 0:
                return False


    def show_indicator(self, index, slides):
        """
            TODO: This function need to be coded a better way. but it works :D

            Carousel indicator.
        """
        align = 0
        spacing = 3

        # if there is more then 11 games, reduce the spacing of each dots
        if slides > 10:
            spacing = 2

            # Move back the indicator by 1 pixel if the number of games is even.
            if slides % 2:
              align = -1

        pixels = []

        # Render the indicator
        for i in range(slides):
            dot_position = ((spacing * i) - 1) + 1

            color = (70, 70, 70)
            if i == index:
                color = (255, 50, 50)

            pixels.append(
              MatrixPixels(
                ((align + dot_position), 0),
                color
              )
            )

        self.matrix.draw_pixels_layout(
            self.layout.indicator_dots,
            pixels,
            (pixels[-1].position[0] - pixels[0].position[0], 1)
        )
