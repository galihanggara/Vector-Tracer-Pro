"""
vector_tracer_pro.services.updater
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Asynchronous application update checker.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

# Hard network timeout (seconds)
_TIMEOUT_SECONDS: Final[int] = 5


@dataclass
class UpdateInfo:
    version: str
    release_url: str
    release_notes: str


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Convert a version string like ``"1.2.3"`` or ``"v1.2.3-alpha.1"`` to a
    comparable integer tuple, ignoring any pre-release suffix.
    """
    # Strip leading "v" or "V"
    cleaned = version_str.lstrip("vV")
    # Drop pre-release suffix (e.g. "-alpha.1", "-beta", "+build.42")
    for separator in ("-", "+"):
        cleaned = cleaned.split(separator)[0]
    parts = cleaned.split(".")
    result: list[int] = []
    for part in parts:
        try:
            result.append(int(part))
        except ValueError:
            break
    return tuple(result) if result else (0,)


def _is_newer(remote_version: str, current_version: str) -> bool:
    """Return ``True`` if *remote_version* is strictly newer than
    *current_version* (semantic comparison, pre-release suffix ignored).
    """
    return _parse_version(remote_version) > _parse_version(current_version)


class UpdateChecker(QThread):
    """Background thread that checks GitHub Releases for a newer version."""

    RELEASES_URL: Final[str] = "https://api.github.com/repos/{owner}/{repo}/releases/latest"
    CURRENT_VERSION: Final[str] = "1.0.0"

    # Cross-thread signal — carries a human-readable update message string
    update_available: Signal = Signal(str)

    def __init__(
        self,
        *,
        current_version: str = "1.0.0",
        api_url: str | None = None,
        timeout_seconds: int = _TIMEOUT_SECONDS,
        parent: object = None,
    ) -> None:
        super().__init__(parent)  # type: ignore[call-arg]
        self._current_version: str = current_version
        if api_url is not None:
            self._api_url: str = api_url
        else:
            self._api_url = self.RELEASES_URL.format(
                owner="galihanggara", repo="Vector-Tracer-Pro"
            )
        self._timeout: int = timeout_seconds

        # Make this thread a daemon so it doesn't block app shutdown
        self.setObjectName("UpdateCheckerThread")

    def check(self, timeout: float = 5.0) -> UpdateInfo | None:
        """Fetch the latest release information synchronously."""
        try:
            old_timeout = self._timeout
            self._timeout = timeout
            try:
                data = self._fetch_latest_release()
            finally:
                self._timeout = old_timeout

            tag = data.get("tag_name", "")
            if not tag:
                return None

            latest = tag.lstrip("vV")
            if _is_newer(tag, self._current_version):
                return UpdateInfo(
                    version=latest,
                    release_url=data.get("html_url", ""),
                    release_notes=data.get("body", "")[:300],
                )
        except Exception as exc:
            logger.debug("UpdateChecker.check: error - %s", exc)
        return None

    def _fetch_latest_release(self) -> dict[str, object]:
        """Backward compatibility private helper for unit tests."""
        req = urllib.request.Request(
            self._api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "VectorTracerPro-UpdateChecker/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as response:
            if response.status != 200:
                raise ValueError(f"GitHub API returned HTTP {response.status}")
            raw: bytes = response.read()
        data: dict[str, object] = json.loads(raw)
        return data

    def run(self) -> None:
        """Fetch the latest release from GitHub and emit a signal if newer.

        This method executes in the worker thread.
        """
        logger.debug("UpdateChecker: starting check against %s", self._api_url)

        info = self.check(self._timeout)
        if info is None:
            return

        tag_name = f"v{info.version}"
        html_url = info.release_url
        message = (
            f"🔔 Update tersedia: {tag_name}  —  {html_url}"
            if html_url
            else f"🔔 Update tersedia: {tag_name}"
        )
        logger.info("UpdateChecker: newer version detected -> %s", tag_name)
        self.update_available.emit(message)
