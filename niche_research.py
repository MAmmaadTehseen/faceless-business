"""One-off: score candidate faceless niches with live web research. Writes data/niche_report.md. Cost ~ $1."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.common import DATA_DIR, Claude, log  # noqa: E402
from pipeline.db import DB  # noqa: E402

CANDIDATES = [
    "AI and technology news explainers with a business angle",
    "Personal finance psychology (habits, not advice)",
    "History mysteries and forgotten events",
    "Space and physics explainers",
    "Geopolitics and economics explainers",
    "Productivity, focus and stoic philosophy",
    "How things actually work (engineering, infrastructure)",
    "Business case studies: rise and fall of companies",
    "Future of work and careers",
    "Cybersecurity stories for normal people",
    "Health and longevity science (news, not advice)",
    "True crime lite / corporate fraud stories",
]

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["ranked", "recommendation"],
          "properties": {"ranked": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                        "required": ["niche", "us_rpm_estimate", "footage_supply", "daily_news_supply", "competition", "policy_risk", "score", "notes", "keywords", "channel_name_ideas"],
                        "properties": {"niche": {"type": "string"}, "us_rpm_estimate": {"type": "string"}, "footage_supply": {"type": "integer"},
                                       "daily_news_supply": {"type": "integer"}, "competition": {"type": "integer"}, "policy_risk": {"type": "integer"},
                                       "score": {"type": "number"}, "notes": {"type": "string"}, "keywords": {"type": "array", "items": {"type": "string"}},
                                       "channel_name_ideas": {"type": "array", "items": {"type": "string"}}}}},
                         "recommendation": {"type": "string"}}}

if __name__ == "__main__":
    db = DB()
    claude = Claude(db)
    prompt = ("Score these faceless YouTube niches for an English channel targeting US/UK/CA/AU viewers, produced fully automatically "
              "(Claude scripts, free stock footage, neural TTS). Use web search for current RPM ranges by niche, recent YouTube policy "
              "changes on AI/mass-produced content, and examples of faceless channels that are monetized in each niche. Score 1-5 for "
              "footage_supply (stock video availability), daily_news_supply, competition (5 = least crowded), policy_risk (5 = safest). "
              "score = weighted total. Also give 6 Google News keywords and 3 channel name ideas per niche.\n\nNiches:\n- " + "\n- ".join(CANDIDATES))
    res, usd = claude.run("niche", prompt, schema=SCHEMA, effort="high", web_search=True, max_searches=15, max_tokens=16000, use_persona=False)
    lines = ["# Niche report", "", f"Recommendation: {res['recommendation']}", "",
             "| # | Niche | US RPM | Footage | News | Competition | Policy | Score |", "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(sorted(res["ranked"], key=lambda r: -r["score"]), 1):
        lines.append(f"| {i} | {r['niche']} | {r['us_rpm_estimate']} | {r['footage_supply']} | {r['daily_news_supply']} | {r['competition']} | {r['policy_risk']} | {r['score']} |")
    lines.append("")
    for r in sorted(res["ranked"], key=lambda r: -r["score"]):
        lines += [f"## {r['niche']}", r["notes"], f"Keywords: {', '.join(r['keywords'])}", f"Names: {', '.join(r['channel_name_ideas'])}", ""]
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "niche_report.md").write_text("\n".join(lines))
    log.info("wrote data/niche_report.md (%.2f USD)", usd)
