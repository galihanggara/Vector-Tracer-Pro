"""
vector_tracer_pro.core.dependency_checker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Runtime verification of all external dependencies and system requirements.

Checks performed
----------------
1. **Python version** — must be >= 3.12 (critical)
2. **Potrace** — must be on PATH, version >= 1.16 (critical)
3. **Inkscape** — must be on PATH, version >= 1.0, ``--actions`` flag
   must be supported for headless multi-colour tracing (critical)
4. **Write permissions** — application output, temp, config, and log
   directories must be writable (critical)
5. **Disk space** — at least ``min_disk_space_mb`` free on the output
   drive (non-critical — advisory warning only)

All results are returned as immutable :class:`CheckResult` and
:class:`ValidationReport` dataclasses, making them safe to pass between
threads and inspect from the UI.

Usage
-----
::

    from vector_tracer_pro.core.dependency_checker import DependencyChecker
    from vector_tracer_pro.core.path_manager import PathManager

    pm = PathManager()
    checker = DependencyChecker.from_path_manager(pm)
    report = checker.check_all()

    if not report.is_ready:
        for check in report.failed_checks:
            print(check.message)
            if check.download_url:
                print(f"  Download: {check.download_url}")
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Sequence

from vector_tracer_pro.config.defaults import (
    INKSCAPE_EXECUTABLE,
    INKSCAPE_MINIMUM_VERSION,
    POTRACE_EXECUTABLE,
    POTRACE_MINIMUM_VERSION,
)

logger = logging.getLogger(__name__)

# Minimum Python version as a (major, minor) tuple
_MIN_PYTHON: tuple[int, int] = (3, 12)

# Minimum free disk space recommended for safe operation (MB)
_DEFAULT_MIN_DISK_MB: float = 500.0

# Download URLs shown to users in error messages
_POTRACE_DOWNLOAD_URL: str = "http://potrace.sourceforge.net/#downloading"
_INKSCAPE_DOWNLOAD_URL: str = "https://inkscape.org/release/"
_PYTHON_DOWNLOAD_URL: str = "https://www.python.org/downloads/"

# Regex that extracts the first X.Y or X.Y.Z version string from any text
_VERSION_RE: re.Pattern[str] = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


# ===========================================================================
# Result types
# ===========================================================================


class CheckStatus(Enum):
    """Outcome of a single dependency check."""

    OK = auto()
    MISSING = auto()
    VERSION_TOO_OLD = auto()
    PERMISSION_DENIED = auto()
    INSUFFICIENT_DISK = auto()
    ERROR = auto()


@dataclass(frozen=True)
class CheckResult:
    """Immutable result of one dependency check.

    Attributes
    ----------
    name:
        Human-readable name of the check (e.g. ``"Inkscape"``).
    status:
        Outcome of the check.
    is_critical:
        If ``True``, a failing check blocks the application from running.
        If ``False``, the check is advisory (generates a warning).
    message:
        One-line human-readable summary suitable for display in the UI.
    detected_version:
        Version string found for the binary, or ``None`` if not applicable.
    minimum_version:
        Minimum required version string, or ``None`` if not applicable.
    detected_path:
        Full filesystem path of the binary as resolved by ``shutil.which``,
        or ``None`` if the binary was not found.
    download_url:
        URL where the user can obtain the required software.
    details:
        Optional multi-line diagnostic details (e.g. raw subprocess output).
    """

    name: str
    status: CheckStatus
    is_critical: bool
    message: str
    detected_version: str | None = None
    minimum_version: str | None = None
    detected_path: str | None = None
    download_url: str = ""
    details: str = ""

    @property
    def passed(self) -> bool:
        """``True`` if this check succeeded."""
        return self.status is CheckStatus.OK

    @property
    def failed(self) -> bool:
        """``True`` if this check did not succeed."""
        return not self.passed


@dataclass(frozen=True)
class ValidationReport:
    """Aggregated result of all dependency checks.

    Attributes
    ----------
    python_check:
        Result of the Python version check.
    potrace_check:
        Result of the Potrace binary check.
    inkscape_check:
        Result of the Inkscape binary check.
    write_permissions_check:
        Result of the filesystem write-permission check.
    disk_space_check:
        Result of the available disk-space check (advisory).
    """

    python_check: CheckResult
    potrace_check: CheckResult
    inkscape_check: CheckResult
    write_permissions_check: CheckResult
    disk_space_check: CheckResult

    # ------------------------------------------------------------------
    # Computed views
    # ------------------------------------------------------------------

    @property
    def all_checks(self) -> list[CheckResult]:
        """All checks in deterministic order."""
        return [
            self.python_check,
            self.potrace_check,
            self.inkscape_check,
            self.write_permissions_check,
            self.disk_space_check,
        ]

    @property
    def critical_checks(self) -> list[CheckResult]:
        """Only the checks that are marked as critical."""
        return [c for c in self.all_checks if c.is_critical]

    @property
    def failed_checks(self) -> list[CheckResult]:
        """All checks that did not pass (critical and advisory)."""
        return [c for c in self.all_checks if c.failed]

    @property
    def warnings(self) -> list[CheckResult]:
        """Non-critical checks that failed (advisory only)."""
        return [c for c in self.all_checks if c.failed and not c.is_critical]

    @property
    def is_ready(self) -> bool:
        """``True`` if and only if every *critical* check passed.

        Non-critical (advisory) failures do not block readiness.
        """
        return all(c.passed for c in self.critical_checks)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a multi-line human-readable summary of all checks.

        Suitable for logging or display in the UI's dependency-check
        dialog.

        Returns
        -------
        str
            Formatted report text.
        """
        sep = "=" * 48
        lines: list[str] = [
            "",
            "  Vector Tracer Pro — Dependency Validation",
            f"  {sep}",
        ]
        for check in self.all_checks:
            tag = "OK" if check.passed else check.status.name.replace("_", " ")
            advisory = " [advisory]" if not check.is_critical else ""
            lines.append(f"  {check.name:<28} {tag}{advisory}")
            if not check.passed:
                lines.append(f"    → {check.message}")
                if check.download_url:
                    lines.append(f"    → Download: {check.download_url}")
        lines.append(f"  {sep}")
        status_word = "READY" if self.is_ready else "NOT READY"
        lines.append(f"  Application status: {status_word}")
        lines.append("")
        return "\n".join(lines)


# ===========================================================================
# Helper functions (module-private)
# ===========================================================================


def _parse_version(text: str) -> str | None:
    """Extract the first semantic version string from *text*.

    Parameters
    ----------
    text:
        Raw text output from a binary's ``--version`` flag.

    Returns
    -------
    str | None
        A normalised ``"MAJOR.MINOR.PATCH"`` string, or ``None`` if no
        version number could be found.
    """
    match = _VERSION_RE.search(text)
    if match is None:
        return None
    major, minor, patch = match.groups()
    return f"{major}.{minor}.{patch or '0'}"


def _version_tuple(version_str: str) -> tuple[int, ...]:
    """Convert a ``"X.Y.Z"`` string to a comparable integer tuple."""
    return tuple(int(part) for part in version_str.split("."))


def _version_meets_minimum(detected: str, minimum: str) -> bool:
    """Return ``True`` if *detected* >= *minimum* (semantic comparison)."""
    return _version_tuple(detected) >= _version_tuple(minimum)


# ===========================================================================
# Checker
# ===========================================================================


class DependencyChecker:
    """Validates all external dependencies required by Vector Tracer Pro.

    Parameters
    ----------
    potrace_executable:
        Name or path of the Potrace binary.  Defaults to ``"potrace"``
        (resolved via ``shutil.which`` / PATH).
    inkscape_executable:
        Name or path of the Inkscape binary.  Defaults to ``"inkscape"``.
    write_check_paths:
        Directories that must be writable.  If ``None``, a default set of
        application-critical directories is used.
    min_disk_space_mb:
        Minimum free disk space in megabytes (advisory, non-critical).
        Defaults to 500 MB.

    Examples
    --------
    >>> checker = DependencyChecker()
    >>> report = checker.check_all()
    >>> print(report.summary())
    """

    def __init__(
        self,
        *,
        potrace_executable: str = POTRACE_EXECUTABLE,
        inkscape_executable: str = INKSCAPE_EXECUTABLE,
        write_check_paths: Sequence[Path] | None = None,
        min_disk_space_mb: float = _DEFAULT_MIN_DISK_MB,
    ) -> None:
        self._potrace_exe: str = potrace_executable
        self._inkscape_exe: str = inkscape_executable
        self._write_check_paths: Sequence[Path] = write_check_paths or []
        self._min_disk_space_mb: float = min_disk_space_mb

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_path_manager(cls, path_manager: object) -> "DependencyChecker":
        """Create a checker pre-configured with paths from a PathManager.

        Parameters
        ----------
        path_manager:
            An instance of :class:`~vector_tracer_pro.core.path_manager.PathManager`.

        Returns
        -------
        DependencyChecker
            Configured checker that verifies write access to all standard
            application directories.
        """
        # Import here to avoid circular import at module level
        from vector_tracer_pro.core.path_manager import PathManager  # noqa: PLC0415

        pm: PathManager = path_manager  # type: ignore[assignment]
        paths: list[Path] = [
            pm._output_root,   # noqa: SLF001
            pm._temp_root,     # noqa: SLF001
            pm._config_dir,    # noqa: SLF001
            pm._log_dir,       # noqa: SLF001
        ]
        return cls(write_check_paths=paths)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_all(self) -> ValidationReport:
        """Run all dependency checks and return an aggregated report.

        All checks are run unconditionally so the UI can display a complete
        picture even when multiple dependencies are missing.

        Returns
        -------
        ValidationReport
            Frozen dataclass with one :class:`CheckResult` per check.
        """
        logger.info("Running dependency validation...")
        report = ValidationReport(
            python_check=self._check_python(),
            potrace_check=self._check_potrace(),
            inkscape_check=self._check_inkscape(),
            write_permissions_check=self._check_write_permissions(),
            disk_space_check=self._check_disk_space(),
        )
        logger.info(report.summary())
        return report

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_python(self) -> CheckResult:
        """Verify the running Python version meets the minimum requirement."""
        vi = sys.version_info
        major, minor, micro = vi.major, vi.minor, vi.micro
        detected = f"{major}.{minor}.{micro}"
        minimum = f"{_MIN_PYTHON[0]}.{_MIN_PYTHON[1]}.0"

        if (major, minor) >= _MIN_PYTHON:
            return CheckResult(
                name="Python",
                status=CheckStatus.OK,
                is_critical=True,
                message=f"Python {detected} — OK.",
                detected_version=detected,
                minimum_version=minimum,
            )

        return CheckResult(
            name="Python",
            status=CheckStatus.VERSION_TOO_OLD,
            is_critical=True,
            message=(
                f"Python {detected} detected; "
                f"{_MIN_PYTHON[0]}.{_MIN_PYTHON[1]}+ required."
            ),
            detected_version=detected,
            minimum_version=minimum,
            download_url=_PYTHON_DOWNLOAD_URL,
        )

    def _check_potrace(self) -> CheckResult:
        """Verify Potrace is installed and meets the minimum version."""
        return self._check_binary(
            name="Potrace",
            executable=self._potrace_exe,
            minimum_version=POTRACE_MINIMUM_VERSION,
            download_url=_POTRACE_DOWNLOAD_URL,
            version_args=["--version"],
        )

    def _check_inkscape(self) -> CheckResult:
        """Verify Inkscape is installed, meets version, and supports headless.

        In addition to the version check performed by :meth:`_check_binary`,
        this method verifies that Inkscape's ``--actions`` flag is recognised,
        which is required for headless multi-colour tracing (Inkscape 1.x+).
        """
        binary_result = self._check_binary(
            name="Inkscape",
            executable=self._inkscape_exe,
            minimum_version=INKSCAPE_MINIMUM_VERSION,
            download_url=_INKSCAPE_DOWNLOAD_URL,
            version_args=["--version"],
        )

        if not binary_result.passed:
            return binary_result

        # Additional: verify --actions headless flag
        headless_result = self._check_inkscape_headless()
        if not headless_result.passed:
            return headless_result

        return binary_result

    def _check_inkscape_headless(self) -> CheckResult:
        """Probe Inkscape's ``--actions`` flag for headless CLI support."""
        try:
            result = subprocess.run(
                [self._inkscape_exe, "--actions=quit"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            combined = (result.stdout + result.stderr).lower()
            # Inkscape 1.x exits cleanly; 0.9x prints "unrecognized option"
            if "unrecognized" in combined or "invalid" in combined:
                return CheckResult(
                    name="Inkscape (headless)",
                    status=CheckStatus.VERSION_TOO_OLD,
                    is_critical=True,
                    message=(
                        "Inkscape --actions flag not supported. "
                        "Inkscape >= 1.0 required for multi-colour tracing."
                    ),
                    download_url=_INKSCAPE_DOWNLOAD_URL,
                    details=combined[:300],
                )
        except subprocess.TimeoutExpired:
            return CheckResult(
                name="Inkscape (headless)",
                status=CheckStatus.ERROR,
                is_critical=True,
                message="Inkscape headless probe timed out.",
            )
        except OSError as exc:
            return CheckResult(
                name="Inkscape (headless)",
                status=CheckStatus.ERROR,
                is_critical=True,
                message=f"Inkscape headless probe failed: {exc}",
            )

        return CheckResult(
            name="Inkscape (headless)",
            status=CheckStatus.OK,
            is_critical=True,
            message="Inkscape --actions flag is supported.",
        )

    def _check_write_permissions(self) -> CheckResult:
        """Verify write access to all required application directories."""
        if not self._write_check_paths:
            return CheckResult(
                name="Write Permissions",
                status=CheckStatus.OK,
                is_critical=True,
                message="No paths configured for permission check — skipped.",
            )

        failed: list[str] = []
        for path in self._write_check_paths:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError:
                failed.append(str(path))
                continue
            if not os.access(path, os.W_OK):
                failed.append(str(path))

        if failed:
            return CheckResult(
                name="Write Permissions",
                status=CheckStatus.PERMISSION_DENIED,
                is_critical=True,
                message=f"No write access to {len(failed)} director(y/ies).",
                details="\n".join(failed),
            )

        return CheckResult(
            name="Write Permissions",
            status=CheckStatus.OK,
            is_critical=True,
            message=(
                f"Write access confirmed for {len(self._write_check_paths)} "
                "director(y/ies)."
            ),
        )

    def _check_disk_space(self) -> CheckResult:
        """Check available disk space on the home / output drive.

        This check is **non-critical** (advisory only).  A warning is emitted
        if free space drops below :attr:`_min_disk_space_mb`, but the
        application will still be marked as ready.
        """
        # Use the user's home directory as the reference drive
        check_path = Path.home()
        try:
            usage = shutil.disk_usage(check_path)
        except OSError as exc:
            return CheckResult(
                name="Disk Space",
                status=CheckStatus.ERROR,
                is_critical=False,
                message=f"Could not query disk usage: {exc}",
            )

        free_mb = usage.free / (1024 * 1024)
        total_mb = usage.total / (1024 * 1024)

        if free_mb < self._min_disk_space_mb:
            return CheckResult(
                name="Disk Space",
                status=CheckStatus.INSUFFICIENT_DISK,
                is_critical=False,  # advisory only
                message=(
                    f"Only {free_mb:,.0f} MB free on {check_path.anchor}; "
                    f"{self._min_disk_space_mb:,.0f} MB recommended."
                ),
                details=(
                    f"Drive: {check_path.anchor}  "
                    f"Free: {free_mb:,.0f} MB / Total: {total_mb:,.0f} MB"
                ),
            )

        return CheckResult(
            name="Disk Space",
            status=CheckStatus.OK,
            is_critical=False,
            message=(
                f"{free_mb:,.0f} MB free on {check_path.anchor} "
                f"(>= {self._min_disk_space_mb:,.0f} MB recommended)."
            ),
        )

    # ------------------------------------------------------------------
    # Private binary-check helper
    # ------------------------------------------------------------------

    def _check_binary(
        self,
        *,
        name: str,
        executable: str,
        minimum_version: str,
        download_url: str,
        version_args: list[str],
    ) -> CheckResult:
        """Generic binary existence + version check.

        Parameters
        ----------
        name:
            Human-readable name for the binary (used in ``CheckResult.name``).
        executable:
            Binary name or path to look up via ``shutil.which``.
        minimum_version:
            Minimum acceptable version string (``"X.Y.Z"``).
        download_url:
            URL shown to the user if the binary is missing or outdated.
        version_args:
            Command-line arguments to pass for version output (e.g.
            ``["--version"]``).

        Returns
        -------
        CheckResult
        """
        # 1. Existence check
        resolved_path = shutil.which(executable)
        if resolved_path is None:
            return CheckResult(
                name=name,
                status=CheckStatus.MISSING,
                is_critical=True,
                message=f"{name} not found on PATH.",
                minimum_version=minimum_version,
                download_url=download_url,
            )

        # 2. Version check
        try:
            proc = subprocess.run(
                [executable, *version_args],
                capture_output=True,
                text=True,
                timeout=10,
            )
            raw_output = proc.stdout + proc.stderr
        except subprocess.TimeoutExpired:
            return CheckResult(
                name=name,
                status=CheckStatus.ERROR,
                is_critical=True,
                message=f"{name} version check timed out (> 10 s).",
                detected_path=resolved_path,
                download_url=download_url,
            )
        except OSError as exc:
            return CheckResult(
                name=name,
                status=CheckStatus.ERROR,
                is_critical=True,
                message=f"Failed to run {name}: {exc}",
                detected_path=resolved_path,
                download_url=download_url,
            )

        # 3. Parse version
        detected_version = _parse_version(raw_output)
        if detected_version is None:
            return CheckResult(
                name=name,
                status=CheckStatus.ERROR,
                is_critical=True,
                message=f"Could not parse {name} version from output.",
                detected_path=resolved_path,
                download_url=download_url,
                details=raw_output[:500],
            )

        # 4. Version comparison
        if not _version_meets_minimum(detected_version, minimum_version):
            return CheckResult(
                name=name,
                status=CheckStatus.VERSION_TOO_OLD,
                is_critical=True,
                message=(
                    f"{name} v{detected_version} found; "
                    f"v{minimum_version}+ required."
                ),
                detected_version=detected_version,
                minimum_version=minimum_version,
                detected_path=resolved_path,
                download_url=download_url,
            )

        return CheckResult(
            name=name,
            status=CheckStatus.OK,
            is_critical=True,
            message=f"{name} v{detected_version} — OK. ({resolved_path})",
            detected_version=detected_version,
            minimum_version=minimum_version,
            detected_path=resolved_path,
        )
