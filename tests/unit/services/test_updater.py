"""
tests.unit.services.test_updater
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.services.updater`.

All tests are fully offline — no real network calls are made.  The
``_fetch_latest_release`` private method is patched to simulate GitHub API
responses.
"""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from vector_tracer_pro.services.updater import UpdateChecker, _is_newer, _parse_version


# ===========================================================================
# Version parsing helpers
# ===========================================================================


@pytest.mark.unit
class TestParseVersion:
    def test_plain_semver(self) -> None:
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_leading_v(self) -> None:
        assert _parse_version("v1.2.3") == (1, 2, 3)

    def test_leading_capital_v(self) -> None:
        assert _parse_version("V2.0.0") == (2, 0, 0)

    def test_pre_release_suffix_stripped(self) -> None:
        assert _parse_version("1.0.0-alpha.1") == (1, 0, 0)

    def test_build_metadata_stripped(self) -> None:
        assert _parse_version("1.0.0+build.42") == (1, 0, 0)

    def test_minor_only(self) -> None:
        assert _parse_version("0.10.0") == (0, 10, 0)

    def test_invalid_falls_back_to_zero(self) -> None:
        assert _parse_version("not-a-version") == (0,)

    def test_empty_string_falls_back_to_zero(self) -> None:
        assert _parse_version("") == (0,)


@pytest.mark.unit
class TestIsNewer:
    def test_newer_patch(self) -> None:
        assert _is_newer("1.0.1", "1.0.0") is True

    def test_newer_minor(self) -> None:
        assert _is_newer("1.1.0", "1.0.9") is True

    def test_newer_major(self) -> None:
        assert _is_newer("2.0.0", "1.99.99") is True

    def test_same_version_is_not_newer(self) -> None:
        assert _is_newer("1.0.0", "1.0.0") is False

    def test_older_is_not_newer(self) -> None:
        assert _is_newer("0.9.0", "1.0.0") is False

    def test_pre_release_ignored_in_comparison(self) -> None:
        # "v1.1.0-alpha" stripped to (1,1,0) > (1,0,0) → True
        assert _is_newer("v1.1.0-alpha.1", "1.0.0") is True


# ===========================================================================
# UpdateChecker QThread
# ===========================================================================


@pytest.mark.unit
class TestUpdateChecker:
    """Tests for UpdateChecker._fetch_latest_release and run() behaviour.

    We patch ``_fetch_latest_release`` to avoid any real network activity.
    The Qt event loop is *not* started — we call ``run()`` synchronously.
    """

    def _make_checker(
        self,
        current_version: str = "0.1.0",
        api_url: str = "http://mock-api",
    ) -> UpdateChecker:
        return UpdateChecker(current_version=current_version, api_url=api_url)

    # ------------------------------------------------------------------
    # Signal emission when update available
    # ------------------------------------------------------------------

    def test_emits_signal_when_newer_version(self) -> None:
        checker = self._make_checker(current_version="0.1.0")
        received: list[str] = []
        checker.update_available.connect(received.append)

        with patch.object(
            checker,
            "_fetch_latest_release",
            return_value={"tag_name": "v1.0.0", "html_url": "https://github.com/releases/1"},
        ):
            checker.run()

        assert len(received) == 1
        assert "v1.0.0" in received[0]
        assert "https://github.com/releases/1" in received[0]

    def test_signal_message_contains_emoji_bell(self) -> None:
        checker = self._make_checker(current_version="0.0.1")
        received: list[str] = []
        checker.update_available.connect(received.append)

        with patch.object(
            checker,
            "_fetch_latest_release",
            return_value={"tag_name": "v1.0.0", "html_url": "https://example.com"},
        ):
            checker.run()

        assert received[0].startswith("🔔")

    # ------------------------------------------------------------------
    # No signal when already up to date
    # ------------------------------------------------------------------

    def test_no_signal_when_already_up_to_date(self) -> None:
        checker = self._make_checker(current_version="1.0.0")
        received: list[str] = []
        checker.update_available.connect(received.append)

        with patch.object(
            checker,
            "_fetch_latest_release",
            return_value={"tag_name": "v1.0.0", "html_url": ""},
        ):
            checker.run()

        assert received == []

    def test_no_signal_when_local_is_newer(self) -> None:
        checker = self._make_checker(current_version="2.0.0")
        received: list[str] = []
        checker.update_available.connect(received.append)

        with patch.object(
            checker,
            "_fetch_latest_release",
            return_value={"tag_name": "v1.9.9", "html_url": ""},
        ):
            checker.run()

        assert received == []

    # ------------------------------------------------------------------
    # Fail-silent on errors
    # ------------------------------------------------------------------

    def test_no_signal_on_network_error(self) -> None:
        checker = self._make_checker()
        received: list[str] = []
        checker.update_available.connect(received.append)

        with patch.object(
            checker,
            "_fetch_latest_release",
            side_effect=urllib.error.URLError("DNS failure"),
        ):
            checker.run()  # must not raise

        assert received == []

    def test_no_signal_on_json_error(self) -> None:
        checker = self._make_checker()
        received: list[str] = []
        checker.update_available.connect(received.append)

        with patch.object(
            checker,
            "_fetch_latest_release",
            side_effect=json.JSONDecodeError("bad json", "", 0),
        ):
            checker.run()

        assert received == []

    def test_no_signal_on_http_non_200(self) -> None:
        checker = self._make_checker()
        received: list[str] = []
        checker.update_available.connect(received.append)

        with patch.object(
            checker,
            "_fetch_latest_release",
            side_effect=ValueError("GitHub API returned HTTP 403"),
        ):
            checker.run()

        assert received == []

    def test_no_signal_when_tag_name_missing(self) -> None:
        """Response without tag_name (malformed GitHub response)."""
        checker = self._make_checker()
        received: list[str] = []
        checker.update_available.connect(received.append)

        with patch.object(
            checker,
            "_fetch_latest_release",
            return_value={"html_url": "https://github.com"},  # no tag_name
        ):
            checker.run()

        assert received == []

    # ------------------------------------------------------------------
    # Message without URL (html_url absent or empty)
    # ------------------------------------------------------------------

    def test_signal_message_without_url_when_html_url_empty(self) -> None:
        checker = self._make_checker(current_version="0.0.1")
        received: list[str] = []
        checker.update_available.connect(received.append)

        with patch.object(
            checker,
            "_fetch_latest_release",
            return_value={"tag_name": "v2.0.0", "html_url": ""},
        ):
            checker.run()

        assert len(received) == 1
        assert "v2.0.0" in received[0]
        # When html_url is empty the URL suffix must not appear
        assert "http" not in received[0]

    # ------------------------------------------------------------------
    # Constructor defaults
    # ------------------------------------------------------------------

    def test_default_api_url_is_github(self) -> None:
        checker = UpdateChecker(current_version="0.1.0")
        assert "github.com" in checker._api_url  # noqa: SLF001

    def test_custom_api_url_accepted(self) -> None:
        checker = UpdateChecker(
            current_version="0.1.0", api_url="http://localhost:9999/api"
        )
        assert checker._api_url == "http://localhost:9999/api"  # noqa: SLF001

    def test_default_timeout_is_five_seconds(self) -> None:
        checker = UpdateChecker(current_version="0.1.0")
        assert checker._timeout == 5  # noqa: SLF001
