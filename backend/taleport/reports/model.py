"""A report as plain data (sections of typed blocks), rendered to PDF by `reports.pdf`.

Keeping the content apart from the layout makes the builders testable without reading
PDF files, and lets every report kind share the same renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BlockKind = Literal["text", "note", "stats", "table", "chart", "theme", "links"]


@dataclass
class Block:
    kind: BlockKind
    data: dict[str, Any]


@dataclass
class Section:
    title: str
    blocks: list[Block] = field(default_factory=list)

    def add(self, kind: BlockKind, **data: Any) -> Section:
        self.blocks.append(Block(kind, data))
        return self


@dataclass
class Report:
    kind: str  # daily, weekly, trends, ask, custom
    title: str
    period: str  # human-readable period, shown on the cover and in the footer
    language: str
    sections: list[Section] = field(default_factory=list)

    def section(self, title: str) -> Section:
        section = Section(title)
        self.sections.append(section)
        return section
