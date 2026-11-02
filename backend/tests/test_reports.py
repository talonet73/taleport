"""PDF reports: content of each report kind, PDF rendering, files, templates, cover logo."""

from __future__ import annotations

import base64
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from taleport.api.context import AppContext, build_context
from taleport.ask.plan import PRESETS
from taleport.ask.scope import Filters, Period
from taleport.core.errors import AppError
from taleport.core.paths import exports_dir
from taleport.reports import pdf
from taleport.reports.builder import ReportBuilder, format_day
from taleport.reports.service import CustomReport
from taleport.results.service import ResultsService
from tests.conftest import TEST_TOKEN
from tests.test_insights import TODAY, seeded  # noqa: F401 (fixture)


def _report(db, make, language: str = "it"):
    with db.connect() as conn:
        return make(ReportBuilder(conn, language, ResultsService(db)))


def _kinds(section) -> list[str]:
    return [b.kind for b in section.blocks]


def _pdf_text(data: bytes) -> tuple[PdfReader, str]:
    reader = PdfReader(io.BytesIO(data))
    return reader, "\n".join(page.extract_text() for page in reader.pages)


@pytest.fixture
def linked(seeded):  # noqa: F811
    """The seeded data plus a source item linked to today's theme (for clickable links)."""
    db, t1, t2 = seeded
    with db.connect() as conn:
        theme_id = conn.execute("SELECT id FROM themes WHERE key = 'reels'").fetchone()[0]
        conn.execute(
            "UPDATE themes SET summary = 'Instagram spinge i Reels lunghi.', "
            "angle = 'Mostrare un caso pratico.' WHERE id = ?",
            (theme_id,),
        )
        item = conn.execute(
            "INSERT INTO items (source, url, canonical_url, title, title_key, language) VALUES "
            "('news', 'https://example.com/reels', 'https://example.com/reels', "
            "'Reels più lunghi per tutti', 'reels', 'it')"
        ).lastrowid
        conn.execute("INSERT INTO theme_items (theme_id, item_id) VALUES (?, ?)", (theme_id, item))
    return db, t1, t2


# -- content ---------------------------------------------------------------------------


def test_format_day_in_three_languages() -> None:
    assert format_day(date(2026, 11, 2), "it") == "2 novembre 2026"
    assert format_day("2026-11-02", "en") == "2 November 2026"
    assert format_day(date(2026, 1, 5), "es") == "5 enero 2026"


def test_weekly_report_sections(linked) -> None:
    db, *_ = linked
    report = _report(db, lambda b: b.weekly(TODAY))
    titles = [s.title for s in report.sections]
    assert titles == [
        "Riepilogo", "Temi caldi", "Parole e hashtag in tendenza", "Parole emergenti e in calo",
        "Andamento delle parole principali", "Post generati e pubblicati", "Risultati dei post",
    ]  # fmt: skip
    assert report.period == "27 ottobre 2026 – 2 novembre 2026"
    summary = report.sections[0]
    assert _kinds(summary) == ["stats", "text", "text", "text", "chart"]
    assert summary.blocks[0].data["items"][0] == ("elementi raccolti", "42")
    assert "«reels»" in summary.blocks[1].data["text"]
    assert summary.blocks[3].data["text"] == "Instagram spinge i Reels lunghi."
    theme = report.sections[1].blocks[0].data
    assert theme["links"] == [("Reels più lunghi per tutti", "https://example.com/reels")]
    assert theme["angle"] == "Mostrare un caso pratico." and theme["angle_label"]
    chart = report.sections[2].blocks[0].data
    assert chart["labels"][:2] == ["reels", "tiktok shop"] and chart["notes"][0] == "100%"
    changes = [b.data.get("title") for b in report.sections[3].blocks if b.kind == "table"]
    assert changes == ["Emergenti", "In calo"]
    assert report.sections[4].blocks[0].data["type"] == "lines"
    assert report.sections[6].blocks[0].data["text"].startswith("Non sono ancora")


def test_custom_report_keeps_a_fixed_order_and_filters(linked) -> None:
    db, _t1, t2 = linked
    report = _report(db, lambda b: b.custom(
        "Client X", Period(preset="last_7_days"), Filters(topics=[t2]),
        ["compare", "keywords"], TODAY,
    ), "en")  # fmt: skip
    assert report.title == "Client X"
    assert [s.title for s in report.sections] == [
        "Trending keywords and hashtags", "Comparison by language and source",
    ]  # fmt: skip
    assert report.sections[0].blocks[0].data["labels"] == ["tiktok shop"]
    by_language = report.sections[1].blocks[0].data
    assert by_language["rows"][0][0] == "English"


def test_ask_report_runs_the_validated_plan(ctx: AppContext) -> None:
    result = ctx.insights.run_plan_json(PRESETS["this_vs_last_week"])
    report = _report(ctx.db, lambda b: b.ask("Cosa è cambiato?", result))
    assert report.sections[0].title == "Domanda"
    assert report.sections[1].title == "Confronto tra periodi"
    assert report.sections[1].blocks[0].data["text"].startswith("Periodo A:")
    a = result["steps"][0]["scope"]["period_a"]["start"]
    assert report.period.startswith(format_day(a, "it"))  # the cover covers both periods
    with pytest.raises(AppError):
        ctx.reports.build_ask({"steps": [{"function": "run_sql"}]})


# -- PDF -------------------------------------------------------------------------------


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_pdf_has_cover_contents_page_numbers_and_links(linked, theme: str) -> None:
    db, *_ = linked
    report = _report(db, lambda b: b.weekly(TODAY))
    data = pdf.render(report, theme=theme, cover_name="Agenzia Rossi")
    assert data.startswith(b"%PDF")
    reader, text = _pdf_text(data)
    assert len(reader.pages) >= 4
    first = reader.pages[0].extract_text()
    assert "Report settimanale" in first and "Agenzia Rossi" in first
    assert "Indice" in text and "Riepilogo" in text and "Pagina 3" in text
    assert "Reels più lunghi per tutti" in text  # accents survive (embedded DejaVu font)
    links = [
        annot.get_object()["/A"]["/URI"]
        for page in reader.pages
        for annot in page.get("/Annots", []) or []
        if annot.get_object().get("/A", {}).get("/URI")
    ]
    assert "https://example.com/reels" in links
    assert reader.outline  # sections are bookmarks too


def test_pdf_of_an_empty_period_still_renders(ctx: AppContext) -> None:
    data = ctx.reports.render(ctx.reports.build_daily(date(2020, 1, 1)))
    _reader, text = _pdf_text(data)
    assert "Nessun elemento raccolto" in text


# -- files, templates, logo ------------------------------------------------------------


def test_save_list_and_refuse_unsafe_names(ctx: AppContext) -> None:
    saved = ctx.reports.save(ctx.reports.build_weekly(), "dark")
    assert saved["name"].startswith("TALeport_settimanale_") and saved["name"].endswith(".pdf")
    assert (exports_dir() / saved["name"]).read_bytes().startswith(b"%PDF")
    assert ctx.reports.recent_files()[0]["name"] == saved["name"]
    for bad in ("../taleport.db", "..\\x.pdf", "nope.pdf", "a/b.pdf"):
        with pytest.raises(AppError):
            ctx.reports.file_path(bad)


def test_templates_save_and_regenerate(ctx: AppContext) -> None:
    params = CustomReport(sections=["summary", "keywords"], period=Period(preset="last_30_days"))
    template = ctx.reports.save_template("Mensile cliente", params)
    assert template["params"]["sections"] == ["summary", "keywords"]
    assert template["last_run_at"] is None
    saved = ctx.reports.run_template(template["id"])
    assert saved["title"] == "Mensile cliente"
    assert ctx.reports.template(template["id"])["last_run_at"]
    renamed = ctx.reports.save_template("Mese", params, template["id"])
    assert renamed["name"] == "Mese" and len(ctx.reports.templates()) == 1
    with pytest.raises(AppError):
        ctx.reports.save_template("  ", params)
    with pytest.raises(ValueError):
        CustomReport(sections=[])
    with pytest.raises(ValueError):
        CustomReport(sections=["summary"], period={"preset": "custom"})
    ctx.reports.delete_template(template["id"])
    assert ctx.reports.templates() == []


def test_cover_logo(ctx: AppContext) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), "#22D3EE").save(buffer, format="PNG")
    info = ctx.reports.set_logo("marchio.png", base64.b64encode(buffer.getvalue()).decode())
    assert info == {"custom": True, "name": "cover_logo.png"}
    assert ctx.reports.render(ctx.reports.build_daily()).startswith(b"%PDF")
    for name, data in (("logo.gif", b"GIF89a"), ("logo.png", b"not an image")):
        with pytest.raises(AppError):
            ctx.reports.set_logo(name, base64.b64encode(data).decode())
    ctx.reports.delete_logo()
    assert ctx.reports.logo_info()["custom"] is False


def test_reports_api(client: TestClient) -> None:
    saved = client.post("/api/reports/weekly", json={}).json()
    response = client.get(f"/api/reports/files/{saved['name']}")
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
    assert client.get("/api/reports/files").json()[0]["name"] == saved["name"]
    assert client.post("/api/reports/trends", json={"period": "last_30_days"}).status_code == 200
    assert (
        client.post(
            "/api/reports/ask", json={"plan": PRESETS["emerging"], "question": "?"}
        ).status_code
        == 200
    )
    bad = client.post("/api/reports/custom", json={"sections": ["gossip"]}).json()
    assert bad["error"]["code"] == "validation"
    template = client.post(
        "/api/reports/templates", json={"name": "T", "params": {"sections": ["trend"]}}
    ).json()
    assert client.post(f"/api/reports/templates/{template['id']}/run").status_code == 200
    assert client.get("/api/reports/files/..%5Ctaleport.db").status_code == 404
    assert client.get("/api/reports/logo").json() == {"custom": False, "name": None}


def test_context_has_reports(db) -> None:
    assert build_context(db, TEST_TOKEN, collectors_factory=lambda: []).reports
