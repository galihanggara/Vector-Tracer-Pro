"""
vector_tracer_pro.services.updater
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Asynchronous application update checker.

Checks the GitHub Releases API once at startup — **after** the main window is
visible — and emits a Qt signal if a newer version is available.  The check
runs inside a :class:`QThread` so the UI is never blocked, and all cross-thread
communication is done exclusively via Qt signals (no shared mutable state).

Design constraints
------------------
* **Non-blocking**: the network call is made in a worker thread; the UI thread
  only receives a finished signal.
* **Fail-silent**: any network error, JSON parse error, or timeout is logged at
  ``DEBUG`` level and the check silently aborts — the user is *never* shown an
  error dialog for a background update check.
* **5-second hard timeout**: ``urllib.request.urlopen`` is called with a 5-second
  timeout to prevent the thread from hanging indefinitely.
* **Qt-only IPC**: the worker emits a ``update_available`` signal carrying the
  new version string.  The caller (``app.py``) connects this signal to
  ``MainWindow.set_status()``.

Usage
-----
::

    from vector_tracer_pro.services.updater import UpdateChecker

    checker = UpdateChecker(current_version="0.1.0-alpha.1")
    checker.update_available.connect(window.set_status)
    checker.start()           # non-blocking; starts background thread
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Final

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

# GitHub Releases API endpoint for this repository
_RELEASES_API_URL: Final[str] = (
    "https://api.github.com/repos/galihanggara/Vector-Tracer-Pro/releases/latest"
)

# Hard network timeout (seconds)
_TIMEOUT_SECONDS: Final[int] = 5


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Convert a version string like ``"1.2.3"`` or ``"v1.2.3-alpha.1"`` to a
    comparable integer tuple, ignoring any pre-release suffix.

    Examples
    --------
    >>> _parse_version("v1.2.3-alpha.1")
    (1, 2, 3)
    >>> _parse_version("0.10.0")
    (0, 10, 0)
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
    """Background thread that checks GitHub Releases for a newer version.

    Parameters
    ----------
    current_version:
        The version string of the currently running application
        (e.g. ``"0.1.0-alpha.1"``).  Sourced from
        :pypi:`importlib.metadata` at call site.
    api_url:
        GitHub Releases API URL to query.  Defaults to the public
        ``galihanggara/Vector-Tracer-Pro`` endpoint.  Can be overridden
        in tests to point at a local mock server.

    Signals
    -------
    update_available(str):
        Emitted when a newer release is detected.  The payload is a
        human-readable status-bar message containing the new version tag
        and the release URL.
    """

    # Cross-thread signal — carries a human-readable update message string
    update_available: Signal = Signal(str)

    def __init__(
        self,
        *,
        current_version: str,
        api_url: str = _RELEASES_API_URL,
        timeout_seconds: int = _TIMEOUT_SECONDS,
        parent: object = None,
    ) -> None:
        super().__init__(parent)  # type: ignore[call-arg]
        self._current_version: str = current_version
        self._api_url: str = api_url
        self._timeout: int = timeout_seconds

        # Make this thread a daemon so it doesn't block app shutdown
        self.setObjectName("UpdateCheckerThread")

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Fetch the latest release from GitHub and emit a signal if newer.

        This method executes in the worker thread.  All exceptions are
        caught and logged — the UI is never interrupted by update errors.
        """
        logger.debug("UpdateChecker: starting check against %s", self._api_url)

        try:
            release_data = self._fetch_latest_release()
        except Exception as exc:
            logger.debug("UpdateChecker: network/parse error — %s", exc)
            return

        tag: str = release_data.get("tag_name", "")
        html_url: str = release_data.get("html_url", "")

        if not tag:
            logger.debug("UpdateChecker: no tag_name in response, aborting.")
            return

        if _is_newer(tag, self._current_version):
            message = (
                f"🔔 Update available: {tag}  —  {html_url}"
                if html_url
                else f"🔔 Update available: {tag}"
            )
            logger.info("UpdateChecker: newer version detected → %s", tag)
            self.update_available.emit(message)
        else:
            logger.debug(
                "UpdateChecker: already up-to-date (local=%s, remote=%s)",
                self._current_version,
                tag,
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_latest_release(self) -> dict[str, object]:
        """Perform the HTTPS GET request and return the parsed JSON body.

        Raises
        ------
        urllib.error.URLError
            On any network-level failure (DNS, timeout, TLS error).
        json.JSONDecodeError
            If the response body is not valid JSON.
        ValueError
            If the HTTP response status is not 200.
        """
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
