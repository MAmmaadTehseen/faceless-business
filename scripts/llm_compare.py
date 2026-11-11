"""Owner-run fixture comparison. Uses exported configuration, never loads .env.

    PYTHON_DOTENV_DISABLED=1 .venv/bin/python scripts/llm_compare.py --out out/llm-compare

Makes model calls only; never publishes or writes the production database.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw
from pipeline.common import Claude, Channel, write_json
from pipeline.script import SCRIPT_SCHEMA
from pipeline.article import ARTICLE_SCHEMA
from pipeline.qa import QA_SCHEMA
from pipeline.engage import REPLY_SCHEMA

FIXTURE = {
    "topic": "How an office team can check an AI meeting summary",
    "source_url": "https://example.org/fixture/meeting-study",
    "source_text": "Synthetic comparison fixture, not a real study: a team checked ten meeting summaries. "
                   "Two summaries missed action owners. Human review caught both before tasks were assigned. "
                   "This small fictional example does not establish a general error rate.",
    "comment": "How could our small team check summaries without reviewing the entire meeting again?",
}


class ComparisonLog:
    def __init__(self):
        self.costs = []

    def setting(self, key, default=None):
        return default

    def month_to_date_cost(self):
        return sum(row["usd"] for row in self.costs)

    def insert(self, table, row):
        if table != "costs":
            raise ValueError("Comparison only records model costs")
        self.costs.append(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("out/llm-compare"))
    parser.add_argument("--channel", default="futurework", choices=Channel.keys())
    args = parser.parse_args()
    db = ComparisonLog()
    client = Claude(db, channel=Channel(args.channel))
    dest = args.out / client.provider
    dest.mkdir(parents=True, exist_ok=True)
    write_json(dest / "fixture.json", FIXTURE)
    context = ("Use only this supplied fictional fixture. Only its source URL may be cited. "
               "Explicitly identify its numbers as synthetic. Do not use web search.\n" + json.dumps(FIXTURE))
    try:
        script, _ = client.run("script", context + "\nWrite one complete 1300-1900 word video script with four distinct Shorts.",
                               schema=SCRIPT_SCHEMA, max_tokens=24000)
        write_json(dest / "script.json", script)
        article, _ = client.run("article", context + "\nAdapt this script into an educational article with evidence boxes:\n" + json.dumps(script),
                                schema=ARTICLE_SCHEMA, max_tokens=20000)
        write_json(dest / "article.json", article)
        image_path = dest / "vision-fixture.png"
        image = Image.new("RGB", (1280, 720), "#101828")
        ImageDraw.Draw(image).text((100, 100), "CHECK AI NOTES", fill="white", font_size=90)
        image.save(image_path)
        qa, _ = client.vision("qa", "Review this fixture thumbnail for readability and safety. No video frames are supplied.",
                              [image_path], QA_SCHEMA)
        write_json(dest / "vision-qa.json", qa)
        reply, _ = client.run("engage", context + "\nWrite a useful two-sentence reply to the supplied viewer comment.",
                              schema=REPLY_SCHEMA, max_tokens=2000)
        write_json(dest / "reply.json", reply)
    finally:
        write_json(dest / "costs.json", db.costs)
    print(f"Saved comparison outputs to {dest}")


if __name__ == "__main__":
    main()
