"""
tests.unit.core.test_dependency_checker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.core.dependency_checker`.

All subprocess and ``shutil.which`` calls are mocked so these tests run
without Potrace or Inkscape installed.  See
``tests/integration/test_dependency_checker.py`` for tests with real binaries.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vector_tracer_pro.core.dependency_checker import (
    CheckResult,
    CheckStatus,
    DependencyChecker,
    ValidationReport,
    _parse_version,
    _version_meets_minimum,
)


# ===========================================================================
# _parse_version helper
# ===========================================================================


@pytest.mark.unit
class TestParseVersion:
    def test_parses_major_minor_patch(self) -> None:
        assert _parse_version("potrace 1.16.0") == "1.16.0"

    def test_parses_major_minor_only(self) -> None:
        assert _parse_version("Inkscape 1.2") == "1.2.0"

    def test_extracts_from_surrounding_text(self) -> None:
        assert _parse_version("some tool v3.14.159 (build 42)") == "3.14.159"

    def test_returns_none_for_no_version(self) -> None:
        assert _parse_version("no version here") is None

    def test_returns_none_for_empty_string(self) -> None:
        assert _parse_version("") is None


# ===========================================================================
# _version_meets_minimum helper
# ===========================================================================


@pytest.mark.unit
class TestVersionMeetsMinimum:
    def test_equal_versions_pass(self) -> None:
        assert _version_meets_minimum("1.16.0", "1.16.0") is True

    def test_greater_patch_passes(self) -> None:
        assert _version_meets_minimum("1.16.3", "1.16.0") is True

    def test_greater_minor_passes(self) -> None:
        assert _version_meets_minimum("1.17.0", "1.16.0") is True

    def test_lower_version_fails(self) -> None:
        assert _version_meets_minimum("1.15.9", "1.16.0") is False

    def test_lower_minor_fails(self) -> None:
        assert _version_meets_minimum("0.99.0", "1.0.0") is False


# ===========================================================================
# CheckResult
# ===========================================================================


@pytest.mark.unit
class TestCheckResult:
    def test_passed_when_ok(self) -> None:
        r = CheckResult(
            name="X", status=CheckStatus.OK, is_critical=True, message="ok"
        )
        assert r.passed is True
        assert r.failed is False

    def test_failed_when_not_ok(self) -> None:
        r = CheckResult(
            name="X",
            status=CheckStatus.MISSING,
            is_critical=True,
            message="missing",
        )
        assert r.passed is False
        assert r.failed is True

    def test_is_immutable(self) -> None:
        r = CheckResult(
            name="X", status=CheckStatus.OK, is_critical=True, message="ok"
        )
        with pytest.raises((AttributeError, TypeError)):
            r.name = "Y"  # type: ignore[misc]


# ===========================================================================
# ValidationReport
# ===========================================================================


def _ok(name: str, critical: bool = True) -> CheckResult:
    return CheckResult(name=name, status=CheckStatus.OK, is_critical=critical, message="ok")


def _fail(name: str, status: CheckStatus = CheckStatus.MISSING, critical: bool = True) -> CheckResult:
    return CheckResult(name=name, status=status, is_critical=critical, message="fail")


@pytest.fixture
def all_ok_report() -> ValidationReport:
    return ValidationReport(
        python_check=_ok("Python"),
        potrace_check=_ok("Potrace"),
        inkscape_check=_ok("Inkscape"),
        write_permissions_check=_ok("Write Permissions"),
        disk_space_check=_ok("Disk Space", critical=False),
    )


@pytest.fixture
def potrace_missing_report() -> ValidationReport:
    return ValidationReport(
        python_check=_ok("Python"),
        potrace_check=_fail("Potrace"),
        inkscape_check=_ok("Inkscape"),
        write_permissions_check=_ok("Write Permissions"),
        disk_space_check=_ok("Disk Space", critical=False),
    )


@pytest.fixture
def disk_warn_report() -> ValidationReport:
    return ValidationReport(
        python_check=_ok("Python"),
        potrace_check=_ok("Potrace"),
        inkscape_check=_ok("Inkscape"),
        write_permissions_check=_ok("Write Permissions"),
        disk_space_check=_fail(
            "Disk Space",
            status=CheckStatus.INSUFFICIENT_DISK,
            critical=False,
        ),
    )


@pytest.mark.unit
class TestValidationReport:
    def test_is_ready_when_all_critical_pass(self, all_ok_report: ValidationReport) -> None:
        assert all_ok_report.is_ready is True

    def test_not_ready_when_critical_fails(
        self, potrace_missing_report: ValidationReport
    ) -> None:
        assert potrace_missing_report.is_ready is False

    def test_is_ready_when_only_advisory_fails(
        self, disk_warn_report: ValidationReport
    ) -> None:
        """Low disk space is non-critical — app should still be ready."""
        assert disk_warn_report.is_ready is True

    def test_all_checks_returns_five_items(self, all_ok_report: ValidationReport) -> None:
        assert len(all_ok_report.all_checks) == 5

    def test_critical_checks_excludes_disk_space(self, all_ok_report: ValidationReport) -> None:
        critical_names = {c.name for c in all_ok_report.critical_checks}
        assert "Disk Space" not in critical_names

    def test_warnings_contains_advisory_failures(
        self, disk_warn_report: ValidationReport
    ) -> None:
        assert len(disk_warn_report.warnings) == 1
        assert disk_warn_report.warnings[0].name == "Disk Space"

    def test_failed_checks_returns_only_failures(
        self, potrace_missing_report: ValidationReport
    ) -> None:
        failed = potrace_missing_report.failed_checks
        assert len(failed) == 1
        assert failed[0].name == "Potrace"

    def test_summary_contains_all_check_names(
        self, all_ok_report: ValidationReport
    ) -> None:
        s = all_ok_report.summary()
        for check in all_ok_report.all_checks:
            assert check.name in s

    def test_summary_contains_ready_when_all_pass(
        self, all_ok_report: ValidationReport
    ) -> None:
        assert "READY" in all_ok_report.summary()

    def test_summary_contains_not_ready_when_critical_fails(
        self, potrace_missing_report: ValidationReport
    ) -> None:
        assert "NOT READY" in potrace_missing_report.summary()

    def test_report_is_immutable(self, all_ok_report: ValidationReport) -> None:
        with pytest.raises((AttributeError, TypeError)):
            all_ok_report.python_check = _fail("Python")  # type: ignore[misc]


# ===========================================================================
# DependencyChecker — _check_python
# ===========================================================================


@pytest.mark.unit
class TestCheckPython:
    def test_current_python_passes(self) -> None:
        checker = DependencyChecker()
        result = checker._check_python()  # noqa: SLF001
        # We're running on Python 3.12+ (project requirement)
        assert result.passed

    def test_old_python_fails(self) -> None:
        checker = DependencyChecker()
        mock_vi = MagicMock()
        mock_vi.major = 3
        mock_vi.minor = 11
        mock_vi.micro = 0
        with patch.object(sys, "version_info", mock_vi):
            result = checker._check_python()  # noqa: SLF001
        assert result.status == CheckStatus.VERSION_TOO_OLD
        assert result.is_critical is True
        assert result.download_url != ""

    def test_result_contains_detected_version(self) -> None:
        checker = DependencyChecker()
        result = checker._check_python()  # noqa: SLF001
        assert result.detected_version is not None
        assert result.minimum_version == "3.12.0"


# ===========================================================================
# DependencyChecker — _check_binary (Potrace proxy)
# ===========================================================================


@pytest.mark.unit
class TestCheckPotrace:
    @patch("vector_tracer_pro.core.dependency_checker.shutil.which", return_value=None)
    def test_missing_binary_returns_missing_status(self, _: MagicMock) -> None:
        checker = DependencyChecker()
        result = checker._check_potrace()  # noqa: SLF001
        assert result.status == CheckStatus.MISSING
        assert result.is_critical is True
        assert result.download_url != ""

    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.which",
        return_value="/usr/bin/potrace",
    )
    @patch(
        "vector_tracer_pro.core.dependency_checker.subprocess.run",
        return_value=MagicMock(stdout="potrace 1.16\n", stderr="", returncode=0),
    )
    def test_valid_version_returns_ok(self, _run: MagicMock, _which: MagicMock) -> None:
        checker = DependencyChecker()
        result = checker._check_potrace()  # noqa: SLF001
        assert result.passed
        assert result.detected_version == "1.16.0"
        assert result.detected_path == "/usr/bin/potrace"

    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.which",
        return_value="/usr/bin/potrace",
    )
    @patch(
        "vector_tracer_pro.core.dependency_checker.subprocess.run",
        return_value=MagicMock(stdout="potrace 1.14\n", stderr="", returncode=0),
    )
    def test_old_version_returns_version_too_old(
        self, _run: MagicMock, _which: MagicMock
    ) -> None:
        checker = DependencyChecker()
        result = checker._check_potrace()  # noqa: SLF001
        assert result.status == CheckStatus.VERSION_TOO_OLD

    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.which",
        return_value="/usr/bin/potrace",
    )
    @patch(
        "vector_tracer_pro.core.dependency_checker.subprocess.run",
        return_value=MagicMock(stdout="some tool\n", stderr="", returncode=0),
    )
    def test_unparseable_version_returns_error(
        self, _run: MagicMock, _which: MagicMock
    ) -> None:
        checker = DependencyChecker()
        result = checker._check_potrace()  # noqa: SLF001
        assert result.status == CheckStatus.ERROR

    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.which",
        return_value="/usr/bin/potrace",
    )
    @patch(
        "vector_tracer_pro.core.dependency_checker.subprocess.run",
        side_effect=__import__("subprocess").TimeoutExpired(cmd="potrace", timeout=10),
    )
    def test_timeout_returns_error(self, _run: MagicMock, _which: MagicMock) -> None:
        checker = DependencyChecker()
        result = checker._check_potrace()  # noqa: SLF001
        assert result.status == CheckStatus.ERROR
        assert "timed out" in result.message.lower()


# ===========================================================================
# DependencyChecker — _check_inkscape (headless probe)
# ===========================================================================


@pytest.mark.unit
class TestCheckInkscape:
    @patch("vector_tracer_pro.core.dependency_checker.shutil.which", return_value=None)
    def test_inkscape_missing_returns_missing(self, _: MagicMock) -> None:
        checker = DependencyChecker()
        result = checker._check_inkscape()  # noqa: SLF001
        assert result.status == CheckStatus.MISSING

    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.which",
        return_value="/usr/bin/inkscape",
    )
    @patch(
        "vector_tracer_pro.core.dependency_checker.subprocess.run",
        side_effect=[
            # First call: inkscape --version
            MagicMock(stdout="Inkscape 1.4.2\n", stderr="", returncode=0),
            # Second call: headless probe
            MagicMock(stdout="", stderr="", returncode=0),
        ],
    )
    def test_valid_inkscape_returns_ok(self, _run: MagicMock, _which: MagicMock) -> None:
        checker = DependencyChecker()
        result = checker._check_inkscape()  # noqa: SLF001
        assert result.passed
        assert result.detected_version == "1.4.2"

    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.which",
        return_value="/usr/bin/inkscape",
    )
    @patch(
        "vector_tracer_pro.core.dependency_checker.subprocess.run",
        side_effect=[
            MagicMock(stdout="Inkscape 1.4.2\n", stderr="", returncode=0),
            # Headless probe returns "unrecognized option"
            MagicMock(
                stdout="", stderr="unrecognized option: --actions", returncode=1
            ),
        ],
    )
    def test_old_headless_api_returns_version_too_old(
        self, _run: MagicMock, _which: MagicMock
    ) -> None:
        checker = DependencyChecker()
        result = checker._check_inkscape()  # noqa: SLF001
        assert result.status == CheckStatus.VERSION_TOO_OLD


# ===========================================================================
# DependencyChecker — _check_write_permissions
# ===========================================================================


@pytest.mark.unit
class TestCheckWritePermissions:
    def test_writable_paths_return_ok(self, tmp_path: Path) -> None:
        checker = DependencyChecker(write_check_paths=[tmp_path])
        result = checker._check_write_permissions()  # noqa: SLF001
        assert result.passed

    def test_no_paths_configured_returns_ok(self) -> None:
        """Empty path list should pass (no-op)."""
        checker = DependencyChecker(write_check_paths=[])
        result = checker._check_write_permissions()  # noqa: SLF001
        assert result.passed

    def test_creates_missing_directory(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "new_subdir"
        assert not new_dir.exists()
        checker = DependencyChecker(write_check_paths=[new_dir])
        result = checker._check_write_permissions()  # noqa: SLF001
        assert result.passed
        assert new_dir.is_dir()

    @patch("pathlib.Path.write_bytes", side_effect=OSError("Permission denied"))
    def test_non_writable_path_returns_permission_denied(
        self, _: MagicMock, tmp_path: Path
    ) -> None:
        checker = DependencyChecker(write_check_paths=[tmp_path])
        result = checker._check_write_permissions()  # noqa: SLF001
        assert result.status == CheckStatus.PERMISSION_DENIED
        assert result.is_critical is True


# ===========================================================================
# DependencyChecker — _check_disk_space
# ===========================================================================


@pytest.mark.unit
class TestCheckDiskSpace:
    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.disk_usage",
        return_value=MagicMock(free=2 * 1024 ** 3, total=10 * 1024 ** 3),
    )
    def test_sufficient_disk_returns_ok(self, _: MagicMock) -> None:
        checker = DependencyChecker(min_disk_space_mb=500)
        result = checker._check_disk_space()  # noqa: SLF001
        assert result.passed
        assert result.is_critical is False  # advisory

    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.disk_usage",
        return_value=MagicMock(free=100 * 1024 ** 2, total=10 * 1024 ** 3),
    )
    def test_low_disk_returns_insufficient(self, _: MagicMock) -> None:
        checker = DependencyChecker(min_disk_space_mb=500)
        result = checker._check_disk_space()  # noqa: SLF001
        assert result.status == CheckStatus.INSUFFICIENT_DISK
        assert result.is_critical is False  # still advisory

    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.disk_usage",
        side_effect=OSError("disk not found"),
    )
    def test_os_error_returns_error_status(self, _: MagicMock) -> None:
        checker = DependencyChecker()
        result = checker._check_disk_space()  # noqa: SLF001
        assert result.status == CheckStatus.ERROR


# ===========================================================================
# DependencyChecker — check_all integration (mocked)
# ===========================================================================


@pytest.mark.unit
class TestCheckAll:
    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.which",
        side_effect=lambda x: f"/usr/bin/{x}",
    )
    @patch(
        "vector_tracer_pro.core.dependency_checker.subprocess.run",
        return_value=MagicMock(
            stdout="tool 99.0.0\n", stderr="", returncode=0
        ),
    )
    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.disk_usage",
        return_value=MagicMock(free=2 * 1024 ** 3, total=10 * 1024 ** 3),
    )
    def test_check_all_returns_validation_report(
        self,
        _disk: MagicMock,
        _run: MagicMock,
        _which: MagicMock,
        tmp_path: Path,
    ) -> None:
        checker = DependencyChecker(write_check_paths=[tmp_path])
        report = checker.check_all()
        assert isinstance(report, ValidationReport)
        assert len(report.all_checks) == 6

    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.which",
        return_value=None,
    )
    @patch(
        "vector_tracer_pro.core.dependency_checker.shutil.disk_usage",
        return_value=MagicMock(free=2 * 1024 ** 3, total=10 * 1024 ** 3),
    )
    def test_check_all_not_ready_when_binaries_missing(
        self, _disk: MagicMock, _which: MagicMock, tmp_path: Path
    ) -> None:
        checker = DependencyChecker(write_check_paths=[tmp_path])
        report = checker.check_all()
        assert report.is_ready is False


# ===========================================================================
# DependencyChecker — from_path_manager
# ===========================================================================


@pytest.mark.unit
class TestFromPathManager:
    def test_from_path_manager_creates_checker(self, tmp_path: Path) -> None:
        from vector_tracer_pro.core.path_manager import PathManager

        pm = PathManager(output_root=tmp_path / "out", temp_root=tmp_path / "tmp")
        checker = DependencyChecker.from_path_manager(pm)
        assert isinstance(checker, DependencyChecker)
        assert len(checker._write_check_paths) > 0  # noqa: SLF001
