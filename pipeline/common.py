"""Shared config, Claude client with cost logging, persona loading, cost guard."""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

OUT_DIR = Path(os.getenv("OUT_DIR", ROOT / "out")).resolve()
DATA_DIR = ROOT / "data"
PERSONA_DIR = ROOT / "persona"          # shared: formulas.md
CHANNELS_DIR = ROOT / "channels"        # one folder per channel: channel.json, beliefs.md, style.md, examples/
DEFAULT_CHANNEL = "futurework"
ASSETS_DIR = ROOT / "assets"
MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("pipeline")

# USD per million tokens. Keep in sync with the models you use.
PRICES = {
    "claude-opus-5-5": {"in": 4.0, "out": 20.0, "cache_read": 0.20},
    "claude-opus-4-8": {"in": 5.0, "out": 25.0, "cache_read": 0.50},
    "claude-sonnet-5-5": {"in": 2.0, "out": 10.0, "cache_read": 0.20},
    "claude-haiku-5-5": {"in": 0.10, "out": 0.50, "cache_read": 0.01},
}
WEB_SEARCH_USD = 0.01  # per search


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(text: str, max_len: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "item"


class Channel:
    """A channel = config + persona. Loaded from channels/<key>/."""

    def __init__(self, key: str = DEFAULT_CHANNEL):
        self.key = key
        self.dir = CHANNELS_DIR / key
        if not (self.dir / "channel.json").exists():
            raise ValueError(f"unknown channel {key!r}; expected {self.dir}/channel.json")
        self.cfg = json.loads((self.dir / "channel.json").read_text())
        self.name = self.cfg["name"]
        self.handle = self.cfg["handle"]
        self.voice = self.cfg.get("voice", {})
        self.style = self.cfg.get("style", {})
        self.keywords = self.cfg.get("niche_keywords", [])
        self.shorts_per_long = int(self.cfg.get("shorts_per_long", 2))
        self.footage = self.cfg.get("footage", {"providers": ["pixabay", "pexels"]})

    @staticmethod
    def keys() -> list[str]:
        return sorted(p.parent.name for p in CHANNELS_DIR.glob("*/channel.json"))

    def env(self, base: str, default: str | None = None) -> str | None:
        """Per-channel secret: BASE_<KEY>, falling back to BASE for the default channel."""
        v = os.getenv(f"{base}_{self.key.upper()}")
        if v:
            return v
        if self.key == DEFAULT_CHANNEL:
            return os.getenv(base, default)
        return default

    def persona(self) -> str:
        return load_persona(self)

    def __repr__(self):
        return f"Channel({self.key})"


def load_persona(channel: "Channel | None" = None) -> str:
    """Concatenate persona files into one stable system prompt (cached by the API)."""
    channel = channel or Channel()
    parts = []
    for name in ("beliefs.md", "style.md"):
        p = channel.dir / name
        if p.exists():
            parts.append(f"<{name[:-3]}>\n{p.read_text().strip()}\n</{name[:-3]}>")
    shared = PERSONA_DIR / "formulas.md"
    if shared.exists():
        parts.append(f"<formulas>\n{shared.read_text().strip()}\n</formulas>")
    examples = sorted((channel.dir / "examples").glob("*.md"))
    if examples:
        ex = "\n\n".join(f"<example name=\"{e.stem}\">\n{e.read_text().strip()}\n</example>" for e in examples[:8])
        parts.append(f"<reference_scripts>\n{ex}\n</reference_scripts>")
    return (
        "You are the narrator persona described below. Write AS this persona, not for them. "
        "Follow the style and formulas exactly. Everything you produce goes straight to production "
        "with no human edit, so be correct, specific, and policy-safe.\n\n" + "\n\n".join(parts)
    )


class CostGuard:
    """Reads month-to-date spend from the DB and refuses expensive work past the budget."""

    def __init__(self, db):
        self.db = db
        self.budget = min(95.0, float(db.setting("monthly_budget_usd", 95)))

    def mtd(self) -> float:
        return self.db.month_to_date_cost()

    def check(self, step: str, est_usd: float = 0.5) -> bool:
        spent = self.mtd()
        if spent + est_usd > self.budget:
            log.warning("Budget guard: %.2f spent of %.2f, skipping %s", spent, self.budget, step)
            return False
        return True


class Claude:
    """Thin wrapper: structured output, persona caching, fallbacks, usage logging."""

    def __init__(self, db=None, model: str = MODEL, channel: "Channel | None" = None):
        self.client = anthropic.Anthropic()
        self.db = db
        self.model = model
        self.channel = channel or Channel()
        self.persona = load_persona(self.channel)

    def _usage_usd(self, usage, model: str, searches: int = 0) -> float:
        p = PRICES.get(model, PRICES["claude-opus-5-5"])
        inp = getattr(usage, "input_tokens", 0) or 0
        out = getattr(usage, "output_tokens", 0) or 0
        cr = getattr(usage, "cache_read_input_tokens", 0) or 0
        cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
        usd = (inp + cw) * p["in"] / 1e6 + cr * p["cache_read"] / 1e6 + out * p["out"] / 1e6
        return usd + searches * WEB_SEARCH_USD

    def _log(self, step: str, content_id: str | None, resp, searches: int = 0) -> float:
        usd = self._usage_usd(resp.usage, resp.model, searches)
        if self.db:
            self.db.insert("costs", {
                "step": step, "content_id": content_id, "model": resp.model, "channel": self.channel.key,
                "input_tokens": getattr(resp.usage, "input_tokens", 0),
                "cache_read_tokens": getattr(resp.usage, "cache_read_input_tokens", 0),
                "output_tokens": getattr(resp.usage, "output_tokens", 0),
                "usd": round(usd, 5),
            })
        log.info("claude %s: %.4f USD (%s)", step, usd, resp.model)
        return usd

    def run(
        self,
        step: str,
        user: str | list[dict],
        *,
        schema: dict | None = None,
        effort: str = "high",
        use_persona: bool = True,
        system_extra: str = "",
        web_search: bool = False,
        max_searches: int = 8,
        max_tokens: int = 16000,
        content_id: str | None = None,
        retries: int = 2,
    ) -> tuple[Any, float]:
        """Returns (parsed JSON dict if schema else text, usd)."""
        system = []
        if use_persona:
            system.append({"type": "text", "text": self.persona, "cache_control": {"type": "ephemeral"}})
        if system_extra:
            system.append({"type": "text", "text": system_extra})
        kwargs: dict[str, Any] = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system or anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": effort, **({"format": {"type": "json_schema", "schema": schema}} if schema else {})},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        if web_search:
            kwargs["tools"] = [{"type": "web_search_20260209", "name": "web_search", "max_uses": max_searches}]

        last_err = None
        for attempt in range(retries + 1):
            try:
                with self.client.beta.messages.stream(**kwargs) as stream:
                    resp = stream.get_final_message()
                if resp.stop_reason == "refusal":
                    raise RuntimeError(f"Claude refused step {step}: {getattr(resp, 'stop_details', None)}")
                searches = 0
                su = getattr(resp.usage, "server_tool_use", None)
                if su is not None:
                    searches = getattr(su, "web_search_requests", 0) or 0
                usd = self._log(step, content_id, resp, searches)
                text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                if resp.stop_reason == "max_tokens":
                    raise RuntimeError(f"max_tokens hit in step {step}")
                if schema:
                    return json.loads(text), usd
                return text, usd
            except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as e:
                last_err = e
                wait = 15 * (attempt + 1)
                log.warning("claude %s attempt %d failed (%s), retry in %ds", step, attempt + 1, type(e).__name__, wait)
                time.sleep(wait)
            except json.JSONDecodeError as e:
                last_err = e
                log.warning("claude %s returned non-JSON, retrying", step)
        raise RuntimeError(f"Claude step {step} failed after retries: {last_err}")

    def vision(self, step: str, prompt: str, image_paths: list[Path], schema: dict, content_id: str | None = None) -> tuple[dict, float]:
        import base64
        content: list[dict] = []
        for p in image_paths:
            data = base64.standard_b64encode(p.read_bytes()).decode()
            mt = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            content.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}})
        content.append({"type": "text", "text": prompt})
        return self.run(step, content, schema=schema, effort="low", use_persona=False, max_tokens=2000, content_id=content_id)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())
