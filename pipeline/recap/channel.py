"""A dedicated channel kept out of Channel.keys() and all automatic jobs."""
import json

from pipeline.common import Channel, CHANNELS_DIR


class FilmReviewChannel(Channel):
    def __init__(self):
        self.key = "filmreview"
        self.dir = CHANNELS_DIR / self.key
        self.cfg = json.loads((self.dir / "local.json").read_text())
        self.name = self.cfg["name"]
        self.handle = self.cfg["handle"]
        self.voice = self.cfg["voice"]
        self.style = self.cfg["style"]
        self.keywords = self.cfg["niche_keywords"]
        self.shorts_per_long = 4
        self.footage = {"providers": []}
