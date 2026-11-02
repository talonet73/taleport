"""Runs the FastAPI app with uvicorn in a background thread on a loopback port."""

from __future__ import annotations

import socket
import threading
import time

import uvicorn
from fastapi import FastAPI


class ApiServer:
    def __init__(self, app: FastAPI, port: int = 0) -> None:
        # Bind ourselves so port 0 yields a free random port we know before serving.
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", port))
        self.port: int = self._sock.getsockname()[1]
        config = uvicorn.Config(app, log_config=None, access_log=False, lifespan="on")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run,
            kwargs={"sockets": [self._sock]},
            name="api-server",
            daemon=True,
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout: float = 15.0) -> None:
        self._thread.start()
        deadline = time.monotonic() + timeout
        while not self._server.started:
            if not self._thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("API server failed to start")
            time.sleep(0.05)

    def wait(self) -> None:
        while self._thread.is_alive():
            self._thread.join(0.5)

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
