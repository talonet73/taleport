"""Statistical theme grouping (no AI).

Greedy seeding: the key phrase shared by the most items (excluding the topic's own
keywords, which appear almost everywhere) seeds a theme with all unassigned items that
mention it; repeat with the next phrase. Two-word phrases win ties over single words,
and a theme needs at least two items.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Doc:
    item_id: int
    terms: frozenset[str]
    source: str
    engagement: float = 0.0


@dataclass
class ThemeDraft:
    key: str
    members: list[Doc]
    related: list[str] = field(default_factory=list)

    @property
    def sources(self) -> set[str]:
        return {doc.source for doc in self.members}

    def representative(self) -> Doc:
        """The member sharing most terms with the rest of the theme; engagement breaks ties."""
        counts = Counter(t for doc in self.members for t in doc.terms)
        return max(
            self.members,
            key=lambda d: (sum(counts[t] - 1 for t in d.terms), d.engagement, -d.item_id),
        )


def build_themes(
    docs: list[Doc], exclude: set[str], max_themes: int = 8, min_items: int = 2
) -> list[ThemeDraft]:
    def usable(term: str) -> bool:
        # The topic's own keywords are in almost every item: a theme must be about
        # something else, so seeds never contain them.
        return not set(term.split()) & exclude

    frequency = Counter(t for doc in docs for t in doc.terms if usable(t))
    candidates = sorted(
        (t for t, n in frequency.items() if n >= min_items),
        key=lambda t: (-frequency[t], -len(t.split()), t),
    )

    assigned: set[int] = set()
    themes: list[ThemeDraft] = []
    for term in candidates:
        members = [d for d in docs if term in d.terms and d.item_id not in assigned]
        if len(members) < min_items:
            continue
        related_counts = Counter(
            t for d in members for t in d.terms if t != term and usable(t) and t not in term
        )
        related = [t for t, n in related_counts.most_common(5) if n >= 2]
        themes.append(ThemeDraft(key=term, members=members, related=related))
        assigned.update(d.item_id for d in members)
        if len(themes) == max_themes:
            break
    return themes
