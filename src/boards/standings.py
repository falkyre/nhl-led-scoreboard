import logging

from PIL import Image, ImageDraw

import driver

if driver.is_hardware():
    pass
else:
    pass


debug = logging.getLogger("scoreboard")

class Standings:
    """
        TODO: Change draw standings to use new matrix layout system
    """
    def __init__(self, data, matrix,sleepEvent):
        self.conferences = ["eastern", "western"]
        self.divisions = ["metropolitan", "atlantic", "central", "pacific"]
        self.data = data
        self.matrix = matrix
        self.team_colors = data.config.team_colors
        self.sleepEvent= sleepEvent
        self.sleepEvent.clear()
        self.wildcard_limit = data.config.wildcard_limit

        if data.config.standings_large_font and self.matrix.width >= 128:
            self.font = data.config.layout.font_large
            self.font_height = 13
            self.width_multiplier = 2
        else:
            self.font = data.config.layout.font
            self.font_height = 7
            self.width_multiplier = 1

    def render(self):
        if self.data.standings:
            type = self.data.config.standing_type
            if self.data.config.preferred_standings_only:
                if type == 'conference':
                    conference = self.data.config.preferred_conference
                    records = getattr(self.data.standings.by_conference, conference)
                    # calculate the image height
                    im_height = (len(records) + 1) * self.font_height
                    # Increment to move image up
                    i = 0
                    image = draw_standing(
                        self.data,
                        conference,
                        records,
                        im_height,
                        self.matrix.width,
                        self.font,
                        self.font_height,
                        self.width_multiplier
                    )
                    self.matrix.draw_image((0, i), image)
                    self.matrix.render()
                    #sleep(5)
                    self.sleepEvent.wait(5)
                    # Move the image up until we hit the bottom.
                    while i > -(im_height - self.matrix.height) and not self.sleepEvent.is_set():
                        i -= 1
                        self.matrix.draw_image((0, i), image)
                        self.matrix.render()
                        #sleep(0.2)
                        self.sleepEvent.wait(0.2)
                    # Show the bottom before we change to the next table.
                    #sleep(5)
                    self.sleepEvent.wait(5)

                elif type == 'division':
                    division = self.data.config.preferred_divisions
                    records = getattr(self.data.standings.by_division, division)
                    # calculate the image height
                    im_height = (len(records) + 1) * self.font_height
                    # Increment to move image up
                    i = 0
                    image = draw_standing(
                        self.data,
                        division,
                        records,
                        im_height,
                        self.matrix.width,
                        self.font,
                        self.font_height,
                        self.width_multiplier
                    )
                    self.matrix.draw_image((0, i), image)
                    self.matrix.render()
                    #sleep(5)
                    self.sleepEvent.wait(5)

                    # Move the image up until we hit the bottom.
                    while i > -(im_height - self.matrix.height) and not self.sleepEvent.is_set():
                        i -= 1
                        self.matrix.draw_image((0, i), image)
                        self.matrix.render()
                        #sleep(0.2)
                        self.sleepEvent.wait(0.2)
                    # Show the bottom before we change to the next table.
                    #sleep(5)
                    self.sleepEvent.wait(5)

                elif type == 'wild_card':
                    wildcard_records = {}
                    conf_name = self.data.config.preferred_conference
                    conf_data = getattr(self.data.standings.by_wildcard, conf_name)
                    wildcard_records["conference"] = conf_name
                    wildcard_records["wild_card"] = conf_data.wild_card
                    wildcard_records["division_leaders"] = conf_data.division_leaders

                    # initialize the number_of_rows
                    number_of_rows = 10 + self.wildcard_limit
                    table_offset = 3
                    img_height = (number_of_rows * self.font_height) + (table_offset * 2)

                    i = 0
                    image = draw_wild_card(
                        self.data,
                        wildcard_records,
                        self.matrix.width,
                        img_height,
                        table_offset,
                        self.wildcard_limit,
                        self.font,
                        self.font_height,
                        self.width_multiplier
                    )
                    self.matrix.draw_image((0, i), image)
                    self.matrix.render()
                    #sleep(5)
                    self.sleepEvent.wait(5)
                    # Move the image up until we hit the bottom.
                    while i > -(img_height - self.matrix.height) and not self.sleepEvent.is_set():
                        i -= 1
                        self.matrix.draw_image((0, i), image)
                        self.matrix.render()
                        #sleep(0.2)
                        self.sleepEvent.wait(0.2)
                    #sleep(5)
                    self.sleepEvent.wait(5)
            else:
                if type == 'conference':
                    for conference in self.conferences:
                        records = getattr(self.data.standings.by_conference, conference)
                        # calculate the image height
                        im_height = (len(records) + 1) * self.font_height
                        # Increment to move image up
                        i = 0
                        image = draw_standing(
                            self.data,
                            conference,
                            records,
                            im_height,
                            self.matrix.width,
                            self.font,
                            self.font_height,
                            self.width_multiplier
                        )
                        self.matrix.draw_image((0, i), image)
                        self.matrix.render()
                        if self.data.network_issues:
                            self.matrix.network_issue_indicator()

                        if self.data.newUpdate and not self.data.config.clock_hide_indicators:
                            self.matrix.update_indicator()

                        #sleep(5)
                        self.sleepEvent.wait(5)

                        # Move the image up until we hit the bottom.
                        while i > -(im_height - self.matrix.height) and not self.sleepEvent.is_set():
                            i -= 1
                            self.matrix.draw_image((0, i), image)
                            self.matrix.render()
                            if self.data.network_issues:
                                self.matrix.network_issue_indicator()

                            if self.data.newUpdate and not self.data.config.clock_hide_indicators:
                                self.matrix.update_indicator()

                            #sleep(0.2)
                            self.sleepEvent.wait(0.2)
                        # Show the bottom before we change to the next table.
                        #sleep(5)
                        self.sleepEvent.wait(5)

                elif type == 'division':
                    for division in self.divisions:
                        records = getattr(self.data.standings.by_division, division)
                        # calculate the image height
                        # image height is 7 rows per team
                        im_height = (len(records) + 1) * self.font_height
                        # Increment to move image up
                        i = 0
                        image = draw_standing(
                            self.data,
                            division,
                            records,
                            im_height,
                            self.matrix.width,
                            self.font,
                            self.font_height,
                            self.width_multiplier)

                        self.matrix.draw_image((0, i), image)
                        self.matrix.render()
                        #sleep(5)
                        self.sleepEvent.wait(5)

                        # Move the image up until we hit the bottom.
                        while i > -(im_height - self.matrix.height) and not self.sleepEvent.is_set():
                            i -= 1
                            self.matrix.draw_image((0, i), image)
                            self.matrix.render()
                            #sleep(0.2)
                            self.sleepEvent.wait(0.2)
                        # Show the bottom before we change to the next table.
                        #sleep(5)
                        self.sleepEvent.wait(5)
                elif type == 'wild_card':
                    wildcard_records = {}
                    for conf_name, conf_data in vars(self.data.standings.by_wildcard).items():
                        conf_data = getattr(self.data.standings.by_wildcard, conf_name)
                        wildcard_records["conference"] = conf_name
                        wildcard_records["wild_card"] = conf_data.wild_card
                        wildcard_records["division_leaders"] = conf_data.division_leaders

                        # initialize the number_of_rows
                        number_of_rows = 10 + self.wildcard_limit
                        table_offset = 3
                        img_height = (number_of_rows * self.font_height) + (table_offset * 2)

                        i = 0
                        image = draw_wild_card(
                            self.data,
                            wildcard_records,
                            self.matrix.width,
                            img_height,
                            table_offset,
                            self.wildcard_limit,
                            self.font,
                            self.font_height,
                            self.width_multiplier
                        )
                        self.matrix.draw_image((0, i), image)
                        self.matrix.render()
                        #sleep(5)
                        self.sleepEvent.wait(5)
                        # Move the image up until we hit the bottom.
                        while i > -(img_height - self.matrix.height) and not self.sleepEvent.is_set():
                            i -= 1
                            self.matrix.draw_image((0, i), image)
                            self.matrix.render()
                            #sleep(0.2)
                            self.sleepEvent.wait(0.2)
                        #sleep(5)
                        self.sleepEvent.wait(5)
        else:
            debug.error("Standing board unavailable due to missing information from the API")


def draw_standing(data, name, records, img_height, width, font, font_height, width_multiplier):
    """
        Draw an image of a list of standing record of each team.
        :return the image
    """
    image = Image.new('RGB', (width, img_height))
    draw = ImageDraw.Draw(image)

    row_pos = 0
    row_height = font_height
    top = row_height - 1

    draw.text((1, 0), name, font=font)
    row_pos += row_height

    for team in records:
        abbrev = team["teamAbbrev"]["default"]
        team_id = data.teams_info_by_abbrev[abbrev].details.id
        points = str(team["points"])
        wins = team["wins"]
        losses = team["losses"]
        ot = team["otLosses"]
        team_colors = data.config.team_colors
        bg_color = team_colors.color("{}.primary".format(team_id))
        txt_color = team_colors.color("{}.text".format(team_id))
        draw.rectangle(
            [0, row_pos, 12 * width_multiplier, top + row_pos],
            fill=(bg_color['r'], bg_color['g'], bg_color['b'])
        )
        draw.text(
            (1 * width_multiplier, row_pos),
            abbrev,
            fill=(txt_color['r'], txt_color['g'], txt_color['b']),
            font=font
        )
        if len(points) == 3:
            draw.text((54 * width_multiplier, row_pos), points, font=font)
        else:
            draw.text((57 * width_multiplier, row_pos), points, font=font)
        draw.text(
            (19 * width_multiplier, row_pos),
            "{}-{}-{}".format(wins, losses, ot),
            font=font
        )
        row_pos += row_height

    return image


def draw_wild_card(data, wildcard_records, width, img_height, offset, limit, font, font_height, width_multiplier):
    image = Image.new('RGB', (width, img_height))
    draw = ImageDraw.Draw(image)

    row_pos = 0
    row_height = font_height
    top = row_height - 1

    # Draw conference name
    draw.text((1, 0), wildcard_records["conference"], font=font)
    row_pos += row_height

    # Draw division leaders
    division_pairs = {
        'eastern': ["metropolitan", "atlantic"],
        'western': ["central", "pacific"]
    }

    divisions = division_pairs.get(wildcard_records["conference"].lower(), ["metropolitan", "atlantic"])

    for division_name in divisions:
        draw.text((1, row_pos), division_name, font=font)
        row_pos += row_height
        teams = getattr(wildcard_records["division_leaders"], division_name, [])
        for team in teams:
            abbrev = team["teamAbbrev"]["default"]
            team_id = data.teams_info_by_abbrev[abbrev].details.id
            points = str(team["points"])
            wins = team["wins"]
            losses = team["losses"]
            ot = team["otLosses"]
            clinched = team.get("clinchIndicator", False)

            team_colors = data.config.team_colors
            bg_color = team_colors.color("{}.primary".format(team_id))
            txt_color = team_colors.color("{}.text".format(team_id))

            draw.rectangle(
                [0, row_pos, 12 * width_multiplier, top + row_pos],
                fill=(bg_color['r'], bg_color['g'], bg_color['b'])
            )
            draw.text(
                (1 * width_multiplier, row_pos), abbrev,
                fill=(txt_color['r'], txt_color['g'], txt_color['b']), font=font
            )

            draw.text(
                (19 * width_multiplier, row_pos),
                "{}-{}-{}".format(wins, losses, ot),
                font=font
            )
            if clinched:
                pts_color = (0, 255, 0)
            else:
                pts_color = (255, 255, 255)
            pts_x_pos = 57 * width_multiplier if len(points) < 3 else 54 * width_multiplier
            draw.text((pts_x_pos, row_pos), points, fill=pts_color, font=font)
            row_pos += row_height
        row_pos += offset

    # Draw wild card teams
    draw.text((1, row_pos), "wild card", font=font)
    row_pos += row_height
    for team in wildcard_records["wild_card"][:limit]:
        abbrev = team["teamAbbrev"]["default"]
        team_id = data.teams_info_by_abbrev[abbrev].details.id
        points = str(team["points"])
        wins = team["wins"]
        losses = team["losses"]
        ot = team["otLosses"]

        team_colors = data.config.team_colors
        bg_color = team_colors.color("{}.primary".format(team_id))
        txt_color = team_colors.color("{}.text".format(team_id))

        draw.rectangle(
            [0, row_pos, 12 * width_multiplier, top + row_pos],
            fill=(bg_color['r'], bg_color['g'], bg_color['b'])
        )
        draw.text(
            (1 * width_multiplier, row_pos), abbrev,
            fill=(txt_color['r'], txt_color['g'], txt_color['b']), font=font
        )
        draw.text(
            (19 * width_multiplier, row_pos),
            "{}-{}-{}".format(wins, losses, ot),
            font=font
        )
        pts_x_pos = 57 * width_multiplier if len(points) < 3 else 54 * width_multiplier
        draw.text((pts_x_pos, row_pos), points, font=font)
        row_pos += row_height

    return image
