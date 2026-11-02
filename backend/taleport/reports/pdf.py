"""PDF rendering of a `Report` with ReportLab: cover, table of contents, page numbers, date,
clickable links, vector charts, light (default) or dark theme.

Text uses DejaVu Sans, shipped with matplotlib: it covers Italian, English and Spanish
(accents, «», curly quotes) and is available offline in the packaged app.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import matplotlib
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors as rl
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents
from svglib.svglib import svg2rlg

from taleport import __version__
from taleport.core.i18n import tr
from taleport.reports import charts
from taleport.reports.builder import format_day
from taleport.reports.model import Block, Report

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN
FONT, FONT_BOLD = "DejaVuSans", "DejaVuSans-Bold"


@dataclass(frozen=True)
class Palette:
    page: str
    surface: str
    text: str
    muted: str
    line: str
    accent: str  # links and highlights (contrast checked on `page`)
    chart: charts.ChartColors


PALETTES = {
    "light": Palette(
        page="#FFFFFF",
        surface="#F1F3FF",
        text="#1E1B4B",
        muted="#4B4F8A",
        line="#D6DAF5",
        accent="#0E7490",
        chart=charts.ChartColors(
            "#FFFFFF",
            "#1E1B4B",
            "#4B4F8A",
            "#D6DAF5",
            ("#0891b2", "#eb6834", "#6250d6", "#eda100", "#e87ba4"),
        ),
    ),
    "dark": Palette(
        page="#1E1B4B",
        surface="#2F2C85",
        text="#E0E7FF",
        muted="#A5B4FC",
        line="#3B3A9A",
        accent="#22D3EE",
        chart=charts.ChartColors(
            "#2F2C85",
            "#E0E7FF",
            "#A5B4FC",
            "#3B3A9A",
            ("#1aa3c2", "#d95926", "#9085e9", "#c98500", "#d55181"),
        ),
    ),
}


@cache
def _register_fonts() -> None:
    folder = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont(FONT, str(folder / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(folder / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(
        FONT, normal=FONT, bold=FONT_BOLD, italic=FONT, boldItalic=FONT_BOLD
    )


def _styles(p: Palette) -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("body", fontName=FONT, fontSize=10.5, leading=15, textColor=p.text)
    return {
        "body": base,
        "note": ParagraphStyle("note", parent=base, fontSize=9, leading=13, textColor=p.muted),
        "h1": ParagraphStyle(
            "h1",
            parent=base,
            fontName=FONT_BOLD,
            fontSize=17,
            leading=22,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=base,
            fontName=FONT_BOLD,
            fontSize=11.5,
            leading=15,
            spaceBefore=6,
            spaceAfter=3,
        ),
        "meta": ParagraphStyle("meta", parent=base, fontSize=8.5, leading=12, textColor=p.muted),
        "cell": ParagraphStyle("cell", parent=base, fontSize=9, leading=12),
        "head": ParagraphStyle(
            "head", parent=base, fontName=FONT_BOLD, fontSize=8.5, leading=11, textColor=p.muted
        ),
        "toc": ParagraphStyle("toc", parent=base, fontSize=11, leading=20),
        "stat": ParagraphStyle("stat", parent=base, fontName=FONT_BOLD, fontSize=18, leading=22),
        "cover_title": ParagraphStyle(
            "cover_title", parent=base, fontName=FONT_BOLD, fontSize=30, leading=36
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base, fontSize=14, leading=20, textColor=p.muted
        ),
    }


def _text(value: str) -> str:
    return escape(value or "").replace("\n", "<br/>")


def _link(text: str, url: str | None, accent: str) -> str:
    if not url:
        return _text(text)
    return f'<a href="{escape(url, {chr(34): "&quot;"})}" color="{accent}"><u>{_text(text)}</u></a>'


def _scaled(drawing: Drawing, width: float, max_height: float | None = None) -> Drawing:
    factor = width / drawing.width
    if max_height and drawing.height * factor > max_height:
        factor = max_height / drawing.height
    drawing.width, drawing.height = drawing.width * factor, drawing.height * factor
    drawing.scale(factor, factor)
    return drawing


class _Heading(Paragraph):
    """A section title: goes in the table of contents and the PDF outline."""


class _Doc(BaseDocTemplate):
    def afterFlowable(self, flowable: Flowable) -> None:  # noqa: N802 (ReportLab API)
        if isinstance(flowable, _Heading):
            text = flowable.getPlainText()
            key = f"s{id(flowable)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=0)
            self.notify("TOCEntry", (0, text, self.page, key))


def render(
    report: Report,
    *,
    theme: str = "light",
    cover_name: str = "",
    logo: Path | None = None,
    generated_at: datetime | None = None,
) -> bytes:
    _register_fonts()
    p = PALETTES.get(theme, PALETTES["light"])
    st = _styles(p)
    lang = report.language
    generated_at = generated_at or datetime.now()
    stamp = f"{format_day(generated_at.date(), lang)}, {generated_at:%H:%M}"
    buffer = io.BytesIO()

    def background(canvas: Any) -> None:
        canvas.setFillColor(rl.HexColor(p.page))
        canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    def on_cover(canvas: Any, _doc: Any) -> None:
        canvas.saveState()
        background(canvas)
        canvas.setFillColor(rl.HexColor(p.accent))
        canvas.rect(0, PAGE_H - 6 * mm, PAGE_W, 6 * mm, stroke=0, fill=1)
        canvas.restoreState()

    def on_page(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        background(canvas)
        canvas.setStrokeColor(rl.HexColor(p.line))
        canvas.line(MARGIN, 14 * mm, PAGE_W - MARGIN, 14 * mm)
        canvas.setFont(FONT, 8)
        canvas.setFillColor(rl.HexColor(p.muted))
        canvas.drawString(MARGIN, 9.5 * mm, f"TALeport · {report.title} · {report.period}"[:110])
        canvas.drawRightString(PAGE_W - MARGIN, 9.5 * mm, tr(lang, "report.page", n=doc.page))
        canvas.restoreState()

    doc = _Doc(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=20 * mm,
        title=f"{report.title} — {report.period}",
        author=cover_name or "TALeport",
        creator=f"TALeport {__version__}",
        lang=lang,
    )
    frame = Frame(
        MARGIN,
        20 * mm,
        CONTENT_W,
        PAGE_H - MARGIN - 20 * mm,
        id="content",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates(
        [
            PageTemplate("cover", [frame], onPage=on_cover),
            PageTemplate("content", [frame], onPage=on_page),
        ]
    )

    story: list[Flowable] = []
    story += _cover(report, st, p, theme, cover_name, logo, stamp)
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())
    toc = TableOfContents(levelStyles=[st["toc"]], dotsMinLevel=0)
    story += [Paragraph(_text(tr(lang, "report.contents")), st["h1"]), toc, PageBreak()]
    for i, section in enumerate(report.sections):
        if i:
            story.append(CondPageBreak(70 * mm))
            story.append(Spacer(1, 6 * mm))
        story.append(_Heading(_text(section.title), st["h1"]))
        for block in section.blocks:
            story += _block(block, st, p)
    if not report.sections:
        story.append(Paragraph(_text(tr(lang, "report.empty.period")), st["note"]))
    doc.multiBuild(story)
    return buffer.getvalue()


def _logo_flowable(logo: Path | None, theme: str, width: float) -> Flowable | None:
    try:
        return _load_logo(logo, width)
    except Exception:  # an unreadable custom logo falls back to the TALeport one
        return None


def _load_logo(logo: Path | None, width: float) -> Flowable | None:
    if logo and logo.exists():
        if logo.suffix.lower() == ".svg":
            drawing = svg2rlg(str(logo))
            return _scaled(drawing, width, 30 * mm) if drawing else None
        image = Image(str(logo))
        factor = min(width / image.imageWidth, (30 * mm) / image.imageHeight)
        image.drawWidth, image.drawHeight = image.imageWidth * factor, image.imageHeight * factor
        image.hAlign = "LEFT"
        return image
    return None


def _cover(
    report: Report, st: dict, p: Palette, theme: str, cover_name: str, logo: Path | None, stamp: str
) -> list[Flowable]:
    from taleport.core.paths import bundle_root  # late: tests may run without the repo layout

    brand = bundle_root() / "assets" / "brand" / f"taleport-logo-{theme}.svg"
    story: list[Flowable] = [Spacer(1, 18 * mm)]
    mark = _logo_flowable(logo, theme, 70 * mm) or _logo_flowable(brand, theme, 70 * mm)
    if mark:
        story.append(mark)
    story += [
        Spacer(1, 45 * mm),
        Paragraph(_text(report.title), st["cover_title"]),
        Spacer(1, 4 * mm),
        Paragraph(_text(report.period), st["cover_sub"]),
    ]
    if cover_name:
        story += [Spacer(1, 10 * mm), Paragraph(_text(cover_name), st["h3"])]
    story += [
        Spacer(1, 70 * mm),
        Paragraph(_text(tr(report.language, "report.generated", when=stamp)), st["meta"]),
    ]
    return story


def _block(block: Block, st: dict, p: Palette) -> list[Flowable]:
    d = block.data
    match block.kind:
        case "text":
            return [Paragraph(_text(d["text"]), st["body"]), Spacer(1, 2 * mm)]
        case "note":
            return [Paragraph(_text(d["text"]), st["note"]), Spacer(1, 2 * mm)]
        case "stats":
            cells = [
                [Paragraph(_text(value), st["stat"]), Paragraph(_text(label), st["meta"])]
                for label, value in d["items"]
            ]
            table = Table([cells], colWidths=[CONTENT_W / len(cells)] * len(cells))
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), rl.HexColor(p.surface)),
                        ("LINEAFTER", (0, 0), (-2, -1), 3, rl.HexColor(p.page)),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            return [table, Spacer(1, 4 * mm)]
        case "table":
            return _table(d, st, p)
        case "chart":
            return _chart(d, st, p)
        case "theme":
            parts: list[Flowable] = [
                Paragraph(_text(d["title"]), st["h3"]),
                Paragraph(_text(d["meta"]), st["meta"]),
            ]
            if d.get("summary"):
                parts.append(Paragraph(_text(d["summary"]), st["body"]))
            if d.get("angle"):
                parts.append(
                    Paragraph(f"<b>{_text(d['angle_label'])}:</b> {_text(d['angle'])}", st["body"])
                )
            for title, url in d.get("links", []):
                parts.append(Paragraph(f"• {_link(title, url, p.accent)}", st["note"]))
            parts.append(Spacer(1, 4 * mm))
            return [KeepTogether(parts)]
        case "links":
            return [Paragraph(f"• {_link(t, u, p.accent)}", st["note"]) for t, u in d["items"]]
    return []


def _cell(value: Any, style: ParagraphStyle, accent: str) -> Paragraph:
    if isinstance(value, dict):
        return Paragraph(_link(value["text"], value.get("url"), accent), style)
    return Paragraph(_text(str(value)), style)


def _table(d: dict, st: dict, p: Palette) -> list[Flowable]:
    out: list[Flowable] = []
    if d.get("title"):
        out.append(Paragraph(_text(d["title"]), st["h3"]))
    align = d.get("align") or ["left"] * len(d["header"])
    right = {i for i, a in enumerate(align) if a == "right"}

    def style_for(i: int, base: ParagraphStyle) -> ParagraphStyle:
        return ParagraphStyle(f"{base.name}{i}", parent=base, alignment=2 if i in right else 0)

    head = [_cell(h, style_for(i, st["head"]), p.accent) for i, h in enumerate(d["header"])]
    rows = [
        [_cell(v, style_for(i, st["cell"]), p.accent) for i, v in enumerate(row)]
        for row in d["rows"]
    ]
    widths = d.get("widths")
    col_widths = [CONTENT_W * w for w in widths] if widths else None
    table = Table([head, *rows], colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, rl.HexColor(p.muted)),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, rl.HexColor(p.line)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    out += [table, Spacer(1, 5 * mm)]
    return out


def _chart(d: dict, st: dict, p: Palette) -> list[Flowable]:
    width = CONTENT_W
    match d["type"]:
        case "bars":
            drawing = charts.bars(d["labels"], d["values"], d["notes"], width, p.chart)
        case "lines":
            drawing = charts.lines(d["days"], d["series"], width, p.chart)
        case _:
            drawing = charts.daily(d["days"], d["values"], width, p.chart)
    drawing.hAlign = "LEFT"
    title = [Paragraph(_text(d["title"]), st["h3"])] if d.get("title") else []
    return [KeepTogether([*title, _scaled(drawing, width, 150 * mm)]), Spacer(1, 4 * mm)]
