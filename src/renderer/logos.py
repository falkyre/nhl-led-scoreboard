import errno
import os
import platform

from PIL import Image

from images.image_helper import ImageHelper
from utils import get_file, round_normal

# uid = int(os.stat("./VERSION").st_uid)
# gid = int(os.stat("./VERSION").st_uid)

PATH = "assets/logos"
LOCAL_LOGO_URL = PATH + "/_local/{}_{}.svg"
LOGO_URL = "https://assets.nhle.com/logos/nhl/svg/{}_{}.svg"


class LogoRenderer:
    def __init__(self, matrix, config, element_layout, team_abbrev, board, gameLocation=None, img=None):
        self.matrix = matrix

        self.logo_variant = config.config.logos.get_team_logo(team_abbrev)
        self.layout = config.config.layout.get_scoreboard_logo(team_abbrev, board, gameLocation, self.logo_variant)

        self.element_layout = element_layout

        # Passing optional img to load method
        self.load(team_abbrev, img)

    def get_size(self):
        return (
            int(round_normal(self.matrix.width * self.layout.zoom)),
            int(round_normal(self.matrix.height * self.layout.zoom)),
        )

    def get_path(self, team_abbrev):
        size = self.get_size()
        return get_file("{}/{}/{}/{}x{}.png".format(PATH, team_abbrev, self.logo_variant, size[0], size[1]))

    def load(self, team_abbrev, img):
        try:
            # If img is not None, load the image, else lookup team logo
            if img:
                self.logo = Image.open(img)
            else:
                filename = self.get_path(team_abbrev)
                self.logo = Image.open(filename)
        except FileNotFoundError:
            self.save_image(filename, team_abbrev)

        rotate = self.layout.rotate
        flip = self.layout.flip
        crop = self.layout.crop

        if rotate != 0:
            self.logo = self.logo.rotate(rotate, expand=True)
        if flip == 1:
            self.logo = self.logo.transpose(method=Image.FLIP_LEFT_RIGHT)
        if crop != 0:
            self.logo = self.logo.crop(
                (
                    self.logo.width * (crop[0]),
                    self.logo.height * (crop[1]),
                    self.logo.width - (self.logo.width * (crop[2])),
                    self.logo.height - (self.logo.height * (crop[3])),
                )
            )

    def save_image(self, filename, team_abbrev):
        if not os.path.exists(os.path.dirname(filename)):
            try:
                os.makedirs(os.path.dirname(filename))
                self.change_ownership(team_abbrev)
            except OSError as exc:  # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise
        try:
            self.logo = ImageHelper.image_from_svg(LOGO_URL.format(team_abbrev, self.logo_variant))
        except Exception:
            self.logo = ImageHelper.image_from_svg(LOCAL_LOGO_URL.format(team_abbrev, self.logo_variant))

        self.logo.thumbnail(self.get_size())
        self.logo.save(filename)

    def change_ownership(self, team_abbrev, target_user=None):
        import os
        import pwd
        if platform.system() != "Linux" or not hasattr(os, "chown") or os.geteuid() != 0:
            return
        target_user = target_user or os.environ.get("SUDO_USER") or "rpi"
        try:
            pw = pwd.getpwnam(target_user)
        except KeyError:
            return
        uid, gid = pw.pw_uid, pw.pw_gid
        path = os.path.dirname(f"{PATH}/{team_abbrev}")
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chown(os.path.join(root, d), uid, gid)
            for f in files:
                os.chown(os.path.join(root, f), uid, gid)

    def render(self):
        self.matrix.draw_image_layout(self.element_layout, self.logo, self.layout.position)
