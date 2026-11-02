"""Entry point: local API, scheduler, tray icon and desktop window."""

from __future__ import annotations

import argparse
import logging
import secrets
import threading

from taleport import __version__
from taleport.api.app import create_app
from taleport.api.context import AppContext, build_context
from taleport.autostart import set_autostart
from taleport.core.errors import AppError
from taleport.core.logging_setup import setup_logging
from taleport.core.paths import bundle_root, db_path, instance_file
from taleport.core.settings import AppSettings
from taleport.db.database import Database
from taleport.scan.scheduler import ScanScheduler
from taleport.server import ApiServer
from taleport.single_instance import (
    SingleInstance,
    focus_running_instance,
    remove_instance_file,
    write_instance_file,
)

log = logging.getLogger("taleport")

DEV_API_PORT = 8765
DEV_UI_URL = "http://localhost:5173"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="taleport")
    parser.add_argument(
        "--dev", action="store_true", help="UI from the Vite dev server, fixed API port"
    )
    parser.add_argument(
        "--no-window", action="store_true", help="run the API only and print the UI URL"
    )
    parser.add_argument("--minimized", action="store_true", help="start hidden in the tray")
    parser.add_argument("--port", type=int, default=None, help="API port (default: random)")
    return parser.parse_args(argv)


def _wire_settings(ctx: AppContext, scheduler: ScanScheduler, on_language: list) -> None:
    def on_change(old: AppSettings, new: AppSettings) -> None:
        if old.scan_time != new.scan_time:
            scheduler.reschedule(new.scan_time)
        if old.start_with_windows != new.start_with_windows:
            set_autostart(new.start_with_windows)
        if old.language != new.language:
            for callback in on_language:
                callback()

    ctx.settings.add_listener(on_change)


def _start_scan_from_shell(ctx: AppContext) -> None:
    try:
        ctx.scans.start("manual")
    except AppError as exc:
        log.info("Scan not started: %s", exc.code)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    setup_logging(logging.DEBUG if args.dev else logging.INFO)
    log.info("Starting TALeport %s", __version__)

    instance = SingleInstance()
    if not instance.acquire():
        log.info("Another instance is running; focusing it")
        focus_running_instance(instance_file())
        return 0

    db = Database(db_path())
    log.info("Database schema version %d", db.migrate())

    ctx = build_context(db, secrets.token_urlsafe(32))
    ctx.scans.mark_interrupted()
    settings = ctx.settings.get()

    scheduler = ScanScheduler(ctx.scans)
    scheduler.start(settings.scan_time)
    ctx.next_scan_at = scheduler.next_run_at
    on_language: list = []
    _wire_settings(ctx, scheduler, on_language)
    set_autostart(settings.start_with_windows)  # keep the registry in sync (e.g. after a move)
    scheduler.catch_up_if_needed(settings.scan_time)

    port = args.port if args.port is not None else (DEV_API_PORT if args.dev else 0)
    server = ApiServer(create_app(ctx), port=port)
    server.start()
    write_instance_file(instance_file(), server.port, ctx.token)
    log.info("API listening on %s", server.url)

    ui_url = f"{DEV_UI_URL if args.dev else server.url}/#t={ctx.token}"
    tray = None
    try:
        if args.no_window:
            print(f"TALeport UI: {ui_url}", flush=True)
            server.wait()
        else:
            from taleport.tray import Tray
            from taleport.window import AppWindow

            window = AppWindow(
                ui_url,
                hidden=args.minimized,
                close_to_tray=lambda: ctx.settings.get().close_to_tray,
            )
            ctx.on_focus = window.focus
            tray = Tray(
                bundle_root() / "assets" / "brand" / "taleport.ico",
                language=lambda: ctx.settings.get().language,
                on_open=window.focus,
                on_scan=lambda: threading.Thread(
                    target=_start_scan_from_shell, args=(ctx,), daemon=True
                ).start(),
                on_quit=window.quit,
            )
            on_language.append(tray.refresh)
            tray.start()
            window.run(debug=args.dev)
    except KeyboardInterrupt:
        pass
    finally:
        if tray:
            tray.stop()
        ctx.scans.cancel()
        scheduler.shutdown()
        server.stop()
        remove_instance_file(instance_file())
        log.info("TALeport stopped")
    return 0
