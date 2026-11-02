"""Shared services handed to the API layer."""

from __future__ import annotations

import logging
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from taleport import __version__
from taleport.ai.registry import build_provider
from taleport.ai.service import AIService, ProviderFactory
from taleport.ai.usage import UsageStore
from taleport.analysis.service import AnalysisService, today_local
from taleport.archive.service import ArchiveService
from taleport.ask.service import InsightsService
from taleport.collectors.base import Collector
from taleport.collectors.google_news import GoogleNewsCollector
from taleport.collectors.http import HttpClient
from taleport.collectors.quota import QuotaTracker
from taleport.collectors.reddit import HOST as REDDIT_HOST
from taleport.collectors.reddit import MIN_INTERVAL_SECONDS as REDDIT_INTERVAL
from taleport.collectors.reddit import RedditCollector
from taleport.collectors.rss import RssCollector
from taleport.collectors.trends import TrendsCollector
from taleport.collectors.youtube import YouTubeCollector
from taleport.core.errors import AppError
from taleport.core.events import EventBus
from taleport.core.logs import LogStore
from taleport.core.secrets import SecretStore
from taleport.core.settings import SettingsStore
from taleport.db.database import Database
from taleport.generator.service import GeneratorService
from taleport.notifications.service import NotificationService
from taleport.planner.service import PlannerService
from taleport.reports.service import ReportService
from taleport.results.service import ResultsService
from taleport.scan.items import ItemRepository
from taleport.scan.service import ScanService
from taleport.topics.service import TopicStore

log = logging.getLogger(__name__)


@dataclass
class AppContext:
    db: Database
    settings: SettingsStore
    secrets: SecretStore
    topics: TopicStore
    items: ItemRepository
    logs: LogStore
    quota: QuotaTracker
    scans: ScanService
    analysis: AnalysisService
    usage: UsageStore
    ai: AIService
    generator: GeneratorService
    insights: InsightsService
    notifications: NotificationService
    results: ResultsService
    planner: PlannerService
    archive: ArchiveService
    reports: ReportService
    token: str
    bus: EventBus
    version: str = __version__
    # Hooks set by the desktop shell (window, scheduler); absent in tests and --no-window.
    on_focus: Callable[[], None] | None = None
    next_scan_at: Callable[[], datetime | None] = lambda: None
    open_url: Callable[[str], object] = field(default=webbrowser.open)


def build_context(
    db: Database,
    token: str,
    *,
    secrets: SecretStore | None = None,
    http: HttpClient | None = None,
    collectors_factory: Callable[[], list[Collector]] | None = None,
    ai_provider_factory: ProviderFactory | None = None,
) -> AppContext:
    bus = EventBus()
    secrets = secrets or SecretStore()
    topics = TopicStore(db)
    items = ItemRepository(db)
    logs = LogStore(db)
    quota = QuotaTracker(db)
    http = http or HttpClient(min_interval={REDDIT_HOST: REDDIT_INTERVAL})

    def default_collectors() -> list[Collector]:
        # Fresh instances per scan: per-scan caches and circuit breakers start clean.
        return [
            GoogleNewsCollector(http),
            RssCollector(http),
            YouTubeCollector(
                http,
                quota,
                api_key=lambda: secrets.get("youtube"),
                resolved_get=topics.source_resolved,
                resolved_set=topics.set_source_resolved,
            ),
            RedditCollector(http),
            TrendsCollector(http),
        ]

    scans = ScanService(db, topics, items, logs, bus, collectors_factory or default_collectors)
    analysis = AnalysisService(db, topics)
    settings = SettingsStore(db)
    usage = UsageStore(db)
    notifications = NotificationService(db, bus, settings)
    ai = AIService(
        db,
        settings,
        secrets,
        topics,
        items,
        usage,
        provider_factory=ai_provider_factory or build_provider,
    )
    ai.on_usage = lambda: notifications.check_spend(
        usage.month_total(), settings.get(), datetime.now().astimezone()
    )
    generator = GeneratorService(db, ai, topics)
    insights = InsightsService(db, topics, ai)
    results = ResultsService(db)

    def analyse_after_scan(summary: dict) -> None:
        for topic in summary["topics"]:
            try:
                analysis.analyze(topic["id"])
            except Exception as exc:  # analysis problems must not hide the scan result
                log.exception("Analysis failed for topic %s", topic["id"])
                logs.add("error", "analysis", "internal", {}, repr(exc))
        bus.publish("analysis.finished", {"scan_id": summary["scan_id"]})
        current = settings.get()
        if current.ai_auto_insights and current.default_ai != "chat":
            for topic in summary["topics"]:
                try:
                    result = ai.theme_insights(topic["id"], current.default_ai)
                except AppError as exc:
                    if exc.code != "ai.no_themes":
                        logs.add("warning", "ai", exc.code, exc.params)
                    continue
                if "handoff" in result:  # provider unavailable: nothing to do unattended
                    logs.add("warning", "ai", result.get("fallback") or "ai.unavailable", {})
                    break
            bus.publish("analysis.finished", {"scan_id": summary["scan_id"], "ai": True})
        try:
            notifications.after_scan(summary, today_local())
        except Exception:
            log.exception("Scan notifications failed")

    scans.on_finished.append(analyse_after_scan)
    return AppContext(
        db=db,
        settings=settings,
        usage=usage,
        ai=ai,
        generator=generator,
        insights=insights,
        notifications=notifications,
        results=results,
        planner=PlannerService(db, settings, generator),
        archive=ArchiveService(db),
        reports=ReportService(db, settings, insights, results),
        secrets=secrets,
        topics=topics,
        items=items,
        logs=logs,
        quota=quota,
        scans=scans,
        analysis=analysis,
        token=token,
        bus=bus,
    )
