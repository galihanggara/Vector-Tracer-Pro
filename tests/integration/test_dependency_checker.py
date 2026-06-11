"""
tests.integration.test_dependency_checker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for :mod:`vector_tracer_pro.core.dependency_checker`.

These tests invoke the **real** checker against the **real** system —
no mocking.  Tests for external binaries are skipped automatically when
the binary is not present on PATH.

Run with::

    pytest -m integration tests/integration/test_dependency_checker.py -v

The ``self-hosted`` GitHub Actions runner (with Potrace + Inkscape installed)
will run these on every push to ``develop``.
"""

from __future__ import annotations

import shutil
import sys

import pytest

from vector_tracer_pro.core.dependency_checker import (
    CheckStatus,
    DependencyChecker,
    ValidationReport,
    _parse_version,
    _version_meets_minimum,
)
from vector_tracer_pro.core.path_manager import PathManager

# ---------------------------------------------------------------------------
# Availability flags (evaluated once at collection time)
# ---------------------------------------------------------------------------
_POTRACE_AVAILABLE: bool = shutil.which("potrace") is not None
_INKSCAPE_AVAILABLE: bool = shutil.which("inkscape") is not None


# ===========================================================================
# Python check — always passes (we are running Python)
# ===========================================================================


@pytest.mark.integration
class TestPythonCheckIntegration:
    def test_python_check_passes_on_current_interpreter(self) -> None:
        checker = DependencyChecker()
        result = checker._check_python()  # noqa: SLF001
        assert result.passed, (
            f"Python {sys.version} should pass the >= 3.12 gate. "
            f"Message: {result.message}"
        )

    def test_python_check_detected_version_matches_sys(self) -> None:
        checker = DependencyChecker()
        result = checker._check_python()  # noqa: SLF001
        vi = sys.version_info
        expected = f"{vi.major}.{vi.minor}.{vi.micro}"
        assert result.detected_version == expected


# ===========================================================================
# Potrace check
# ===========================================================================


@pytest.mark.integration
@pytest.mark.skipif(not _POTRACE_AVAILABLE, reason="Potrace not installed on PATH")
class TestPotraceCheckIntegration:
    def test_potrace_check_returns_ok(self) -> None:
        checker = DependencyChecker()
        result = checker._check_potrace()  # noqa: SLF001
        assert result.passed, f"Potrace check failed: {result.message}"

    def test_potrace_detected_version_is_parseable(self) -> None:
        checker = DependencyChecker()
        result = checker._check_potrace()  # noqa: SLF001
        assert result.detected_version is not None
        parts = result.detected_version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_potrace_detected_path_exists(self) -> None:
        checker = DependencyChecker()
        result = checker._check_potrace()  # noqa: SLF001
        from pathlib import Path
        assert result.detected_path is not None
        assert Path(result.detected_path).exists()

    def test_potrace_meets_minimum_version(self) -> None:
        from vector_tracer_pro.config.defaults import POTRACE_MINIMUM_VERSION

        checker = DependencyChecker()
        result = checker._check_potrace()  # noqa: SLF001
        assert result.detected_version is not None
        assert _version_meets_minimum(
            result.detected_version, POTRACE_MINIMUM_VERSION
        ), (
            f"Installed Potrace {result.detected_version} is below "
            f"minimum {POTRACE_MINIMUM_VERSION}"
        )


@pytest.mark.integration
@pytest.mark.skipif(_POTRACE_AVAILABLE, reason="Only runs when Potrace is absent")
class TestPotraceAbsent:
    def test_missing_potrace_returns_missing_status(self) -> None:
        checker = DependencyChecker()
        result = checker._check_potrace()  # noqa: SLF001
        assert result.status == CheckStatus.MISSING
        assert result.is_critical is True


# ===========================================================================
# Inkscape check
# ===========================================================================


@pytest.mark.integration
@pytest.mark.skipif(not _INKSCAPE_AVAILABLE, reason="Inkscape not installed on PATH")
class TestInkscapeCheckIntegration:
    def test_inkscape_check_returns_ok(self) -> None:
        checker = DependencyChecker()
        result = checker._check_inkscape()  # noqa: SLF001
        assert result.passed, f"Inkscape check failed: {result.message}"

    def test_inkscape_detected_version_parseable(self) -> None:
        checker = DependencyChecker()
        result = checker._check_inkscape()  # noqa: SLF001
        assert result.detected_version is not None
        parts = result.detected_version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_inkscape_meets_minimum_version(self) -> None:
        from vector_tracer_pro.config.defaults import INKSCAPE_MINIMUM_VERSION

        checker = DependencyChecker()
        result = checker._check_inkscape()  # noqa: SLF001
        assert result.detected_version is not None
        assert _version_meets_minimum(
            result.detected_version, INKSCAPE_MINIMUM_VERSION
        ), (
            f"Installed Inkscape {result.detected_version} is below "
            f"minimum {INKSCAPE_MINIMUM_VERSION}"
        )


@pytest.mark.integration
@pytest.mark.skipif(_INKSCAPE_AVAILABLE, reason="Only runs when Inkscape is absent")
class TestInkscapeAbsent:
    def test_missing_inkscape_returns_missing(self) -> None:
        checker = DependencyChecker()
        result = checker._check_inkscape()  # noqa: SLF001
        assert result.status == CheckStatus.MISSING


# ===========================================================================
# Write permissions check
# ===========================================================================


@pytest.mark.integration
class TestWritePermissionsIntegration:
    def test_writable_temp_dir_passes(self, tmp_path: object) -> None:
        from pathlib import Path

        checker = DependencyChecker(write_check_paths=[Path(str(tmp_path))])
        result = checker._check_write_permissions()  # noqa: SLF001
        assert result.passed

    def test_path_manager_paths_are_writable(self, tmp_path: object) -> None:
        from pathlib import Path

        pm = PathManager(
            output_root=Path(str(tmp_path)) / "output",
            temp_root=Path(str(tmp_path)) / "temp",
        )
        checker = DependencyChecker.from_path_manager(pm)
        result = checker._check_write_permissions()  # noqa: SLF001
        assert result.passed, f"Write permission check failed: {result.message}"


# ===========================================================================
# Disk space check
# ===========================================================================


@pytest.mark.integration
class TestDiskSpaceIntegration:
    def test_disk_space_check_runs_without_error(self) -> None:
        checker = DependencyChecker(min_disk_space_mb=1.0)
        result = checker._check_disk_space()  # noqa: SLF001
        # At minimum, the check should run without raising
        assert result.status in list(CheckStatus)

    def test_disk_space_check_is_non_critical(self) -> None:
        checker = DependencyChecker()
        result = checker._check_disk_space()  # noqa: SLF001
        assert result.is_critical is False

    def test_absurdly_high_threshold_returns_insufficient(self) -> None:
        """Requesting 999 TB should always fail."""
        checker = DependencyChecker(min_disk_space_mb=999 * 1024 * 1024)
        result = checker._check_disk_space()  # noqa: SLF001
        assert result.status == CheckStatus.INSUFFICIENT_DISK


# ===========================================================================
# Full check_all (real binaries, conditional)
# ===========================================================================


@pytest.mark.integration
class TestCheckAllIntegration:
    def test_check_all_returns_validation_report(self, tmp_path: object) -> None:
        from pathlib import Path

        checker = DependencyChecker(
            write_check_paths=[Path(str(tmp_path))],
            min_disk_space_mb=1.0,
        )
        report = checker.check_all()
        assert isinstance(report, ValidationReport)
        assert len(report.all_checks) == 5

    def test_summary_is_non_empty_string(self, tmp_path: object) -> None:
        from pathlib import Path

        checker = DependencyChecker(write_check_paths=[Path(str(tmp_path))])
        report = checker.check_all()
        summary = report.summary()
        assert isinstance(summary, str)
        assert len(summary) > 50  # must be a meaningful report

    @pytest.mark.skipif(
        not (_POTRACE_AVAILABLE and _INKSCAPE_AVAILABLE),
        reason="Requires both Potrace and Inkscape on PATH",
    )
    def test_all_critical_pass_when_tools_available(self, tmp_path: object) -> None:
        from pathlib import Path

        checker = DependencyChecker(
            write_check_paths=[Path(str(tmp_path))],
            min_disk_space_mb=1.0,
        )
        report = checker.check_all()
        failed_critical = [c for c in report.critical_checks if c.failed]
        assert not failed_critical, (
            f"Critical checks failed even with tools available: "
            f"{[c.name for c in failed_critical]}"
        )
