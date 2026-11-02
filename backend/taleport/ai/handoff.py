"""'Open in chat': the user's own chat account does the work.

The app never automates chat websites. It copies the full prompt to the clipboard and opens
the chat site in the default browser; the user sends it and pastes the answer back.
URL prefill is an experimental opt-in: the `?q=` patterns below are widely used but not
documented by the vendors, and could not be verified without signing in (checked 2026-11).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import quote

SITES = {
    "claude": ("https://claude.ai/new", "https://claude.ai/new?q={q}"),
    "chatgpt": ("https://chatgpt.com/", "https://chatgpt.com/?q={q}"),
    "grok": ("https://grok.com/", "https://grok.com/?q={q}"),
    "perplexity": ("https://www.perplexity.ai/", "https://www.perplexity.ai/search?q={q}"),
}
MAX_PREFILL_URL = 2000  # keep well under browser/server URL limits


@dataclass
class Handoff:
    site: str
    url: str
    prompt: str
    prefilled: bool

    def to_dict(self) -> dict:
        return asdict(self)


def build_handoff(site: str, prompt: str, *, prefill: bool) -> Handoff:
    base, template = SITES.get(site, SITES["claude"])
    if prefill:
        url = template.format(q=quote(prompt, safe=""))
        if len(url) <= MAX_PREFILL_URL:
            return Handoff(site=site, url=url, prompt=prompt, prefilled=True)
    return Handoff(site=site, url=base, prompt=prompt, prefilled=False)
