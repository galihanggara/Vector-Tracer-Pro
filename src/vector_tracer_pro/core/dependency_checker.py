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
4. **VTracer** — optional colour-vectoriser; advisory if absent (non-critical)
5. **Write permissions** — application output, temp, config, and log
   directories must be writable, verified by an **actual probe-file write**
   rather than ``os.access()`` (critical)
6. **Disk space** — at least ``min_disk_space_mb`` free on the **output
   drive** (defaults to the drive reported by PathManager; non-critical)

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
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
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

# VTracer — optional vectoriser
_VTRACER_EXECUTABLE: str = "vtracer"
_VTRACER_MINIMUM_VERSION: str = "0.6.0"
_VTRACER_DOWNLOAD_URL: str = "https://github.com/visioncortex/vtracer/releases"

# Download URLs shown to users in error messages
_POTRACE_DOWNLOAD_URL: str = "http://potrace.sourceforge.net/#downloading"
_INKSCAPE_DOWNLOAD_URL: str = "https://inkscape.org/release/"
_PYTHON_DOWNLOAD_URL: str = "https://www.python.org/downloads/"

# Regex that extracts the first X.Y or X.Y.Z version string from any text
_VERSION_RE: re.Pattern[str] = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")

# Probe filename prefix written during the write-permission check
_PROBE_PREFIX: str = ".vtp_write_probe_"


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
    vtracer_check:
        Result of the VTracer binary check (optional, non-critical).
        ``None`` if the check was not performed.
    write_permissions_check:
        Result of the filesystem write-permission check (probe-file write).
    disk_space_check:
        Result of the available disk-space check on the output drive (advisory).
    """

    python_check: CheckResult
    potrace_check: CheckResult
    inkscape_check: CheckResult
    write_permissions_check: CheckResult
    disk_space_check: CheckResult
    vtracer_check: CheckResult | None = None  # optional — None if not performed

    # ------------------------------------------------------------------
    # Computed views
    # ------------------------------------------------------------------

    @property
    def all_checks(self) -> list[CheckResult]:
        """All performed checks in deterministic order."""
        checks = [
            self.python_check,
            self.potrace_check,
            self.inkscape_check,
            self.write_permissions_check,
            self.disk_space_check,
        ]
        if self.vtracer_check is not None:
            checks.append(self.vtracer_check)
        return checks

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

        Returns
        -------
        str
            Formatted report text suitable for logging or UI display.
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
        Name or path of the Potrace binary.
    inkscape_executable:
        Name or path of the Inkscape binary.
    vtracer_executable:
        Name or path of the VTracer binary.  VTracer is optional; its
        absence generates an advisory warning, not a blocking error.
    write_check_paths:
        Directories that must be writable.  Write access is verified by
        creating and immediately deleting a small probe file (not by
        ``os.access()`` which can be incorrect on Windows with ACLs).
    min_disk_space_mb:
        Minimum free disk space in megabytes (advisory, non-critical).
    disk_check_path:
        Path used to determine which drive to check for free space.
        Typically the output root so the check reflects the actual
        destination drive (not necessarily the system drive).
        Defaults to ``Path.home()`` if ``None``.

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
        vtracer_executable: str = _VTRACER_EXECUTABLE,
        write_check_paths: Sequence[Path] | None = None,
        min_disk_space_mb: float = _DEFAULT_MIN_DISK_MB,
        disk_check_path: Path | None = None,
    ) -> None:
        self._potrace_exe: str = potrace_executable
        self._inkscape_exe: str = inkscape_executable
        self._vtracer_exe: str = vtracer_executable
        self._write_check_paths: Sequence[Path] = write_check_paths or []
        self._min_disk_space_mb: float = min_disk_space_mb
        self._disk_check_path: Path = disk_check_path or Path.home()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_path_manager(cls, path_manager: object) -> "DependencyChecker":
        """Create a checker pre-configured with paths from a PathManager.

        Uses only the public API of :class:`PathManager` — no private
        attribute access (``_output_root``, ``_config_dir``, etc.).

        Parameters
        ----------
        path_manager:
            An instance of :class:`~vector_tracer_pro.core.path_manager.PathManager`.

        Returns
        -------
        DependencyChecker
            Checker configured to verify write access to all standard
            application directories and disk space on the output drive.
        """
        from vector_tracer_pro.core.path_manager import PathManager  # noqa: PLC0415

        pm: PathManager = path_manager  # type: ignore[assignment]

        # Use public API — no access to private attributes
        write_paths: list[Path] = [
            pm.get_output_root(),   # public method
            pm.temp_root,           # public property
            pm.config_dir_path,     # public property
            pm.log_dir_path,        # public property
        ]
        return cls(
            write_check_paths=write_paths,
            disk_check_path=pm.get_output_root(),  # check the output drive
        )

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
            vtracer_check=self._check_vtracer(),
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
            is_critical=True,
        )

    def _check_inkscape(self) -> CheckResult:
        """Verify Inkscape is installed, meets version, and supports headless.

        In addition to the version check, verifies that ``--actions`` is
        recognised (Inkscape 1.x headless API required for multi-colour
        tracing).
        """
        binary_result = self._check_binary(
            name="Inkscape",
            executable=self._inkscape_exe,
            minimum_version=INKSCAPE_MINIMUM_VERSION,
            download_url=_INKSCAPE_DOWNLOAD_URL,
            version_args=["--version"],
            is_critical=True,
        )

        if not binary_result.passed:
            return binary_result

        return self._check_inkscape_headless(
            detected_version=binary_result.detected_version,
            detected_path=binary_result.detected_path,
        )

    def _check_inkscape_headless(
        self,
        detected_version: str | None = None,
        detected_path: str | None = None,
    ) -> CheckResult:
        """Probe Inkscape's ``--actions`` flag for headless CLI support."""
        try:
            result = subprocess.run(
                [self._inkscape_exe, "--actions=quit"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            combined = (result.stdout + result.stderr).lower()
            if "unrecognized" in combined or "invalid" in combined:
                return CheckResult(
                    name="Inkscape",
                    status=CheckStatus.VERSION_TOO_OLD,
                    is_critical=True,
                    message=(
                        "Inkscape --actions flag not supported. "
                        "Inkscape >= 1.0 required for multi-colour tracing."
                    ),
                    detected_version=detected_version,
                    detected_path=detected_path,
                    download_url=_INKSCAPE_DOWNLOAD_URL,
                    details=combined[:300],
                )
            if result.returncode != 0:
                return CheckResult(
                    name="Inkscape",
                    status=CheckStatus.ERROR,
                    is_critical=True,
                    message=f"Inkscape headless probe failed with exit code {result.returncode}.",
                    detected_version=detected_version,
                    detected_path=detected_path,
                    details=combined[:300],
                )
        except subprocess.TimeoutExpired:
            return CheckResult(
                name="Inkscape",
                status=CheckStatus.ERROR,
                is_critical=True,
                message="Inkscape headless probe timed out.",
                detected_version=detected_version,
                detected_path=detected_path,
            )
        except OSError as exc:
            return CheckResult(
                name="Inkscape",
                status=CheckStatus.ERROR,
                is_critical=True,
                message=f"Inkscape headless probe failed: {exc}",
                detected_version=detected_version,
                detected_path=detected_path,
            )

        return CheckResult(
            name="Inkscape",
            status=CheckStatus.OK,
            is_critical=True,
            message="Inkscape headless --actions flag is supported.",
            detected_version=detected_version,
            detected_path=detected_path,
        )

    def _check_vtracer(self) -> CheckResult:
        """Check for VTracer — optional colour vectoriser (non-critical).

        VTracer is an alternative to Inkscape for colour tracing.  Its
        absence generates an advisory warning but does not block the
        application from running.
        """
        return self._check_binary(
            name="VTracer",
            executable=self._vtracer_exe,
            minimum_version=_VTRACER_MINIMUM_VERSION,
            download_url=_VTRACER_DOWNLOAD_URL,
            version_args=["--version"],
            is_critical=False,  # advisory — app works without VTracer
        )

    def _check_write_permissions(self) -> CheckResult:
        """Verify write access to all required application directories.

        Uses an **actual probe-file write** (create + delete a small file)
        rather than ``os.access()`` which can be unreliable on Windows with
        Access Control Lists (ACLs).
        """
        if not self._write_check_paths:
            return CheckResult(
                name="Write Permissions",
                status=CheckStatus.OK,
                is_critical=True,
                message="No paths configured for permission check — skipped.",
            )

        failed: list[str] = []
        for path in self._write_check_paths:
            # Step 1: create directory
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError:
                failed.append(str(path))
                continue

            # Step 2: attempt actual file write + delete
            probe = path / f"{_PROBE_PREFIX}{uuid.uuid4().hex[:8]}"
            try:
                probe.write_bytes(b"vtp")
                probe.unlink()
            except OSError:
                failed.append(str(path))

        if failed:
            return CheckResult(
                name="Write Permissions",
                status=CheckStatus.PERMISSION_DENIED,
                is_critical=True,
                message=f"Cannot write to {len(failed)} director(y/ies).",
                details="\n".join(failed),
            )

        return CheckResult(
            name="Write Permissions",
            status=CheckStatus.OK,
            is_critical=True,
            message=(
                f"Write access confirmed for {len(self._write_check_paths)} "
                "director(y/ies) (probe write verified)."
            ),
        )

    def _check_disk_space(self) -> CheckResult:
        """Check available disk space on the **output drive**.

        The check uses :attr:`_disk_check_path` (typically the output root)
        so that the reported free space reflects the actual destination
        drive rather than always checking the system drive.

        This check is **non-critical** (advisory only).
        """
        check_path = self._disk_check_path
        try:
            usage = shutil.disk_usage(check_path)
        except OSError as exc:
            return CheckResult(
                name="Disk Space",
                status=CheckStatus.ERROR,
                is_critical=False,
                message=f"Could not query disk usage for {check_path}: {exc}",
            )

        free_mb = usage.free / (1024 * 1024)
        total_mb = usage.total / (1024 * 1024)
        drive = Path(check_path.anchor) if check_path.anchor else check_path

        if free_mb < self._min_disk_space_mb:
            return CheckResult(
                name="Disk Space",
                status=CheckStatus.INSUFFICIENT_DISK,
                is_critical=False,
                message=(
                    f"Only {free_mb:,.0f} MB free on {drive}; "
                    f"{self._min_disk_space_mb:,.0f} MB recommended."
                ),
                details=(
                    f"Drive: {drive}  "
                    f"Free: {free_mb:,.0f} MB / Total: {total_mb:,.0f} MB"
                ),
            )

        return CheckResult(
            name="Disk Space",
            status=CheckStatus.OK,
            is_critical=False,
            message=(
                f"{free_mb:,.0f} MB free on {drive} "
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
        minimum_version: str | None,
        download_url: str,
        version_args: list[str],
        is_critical: bool = True,
    ) -> CheckResult:
        """Generic binary existence + version check.

        Parameters
        ----------
        name:
            Human-readable name (used in ``CheckResult.name``).
        executable:
            Binary name or path to look up via ``shutil.which``.
        minimum_version:
            Minimum acceptable version string ``"X.Y.Z"``.
            ``None`` means any detected version is accepted.
        download_url:
            URL shown to the user if the binary is missing or outdated.
        version_args:
            Command-line arguments to pass for version output.
        is_critical:
            Whether a failing check blocks the application.
            ``False`` produces an advisory warning only.

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
                is_critical=is_critical,
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
            if proc.returncode != 0:
                return CheckResult(
                    name=name,
                    status=CheckStatus.ERROR,
                    is_critical=is_critical,
                    message=f"{name} version check failed with exit code {proc.returncode}.",
                    detected_path=resolved_path,
                    download_url=download_url,
                    details=(proc.stdout + proc.stderr)[:500],
                )
            raw_output = proc.stdout + proc.stderr
        except subprocess.TimeoutExpired:
            return CheckResult(
                name=name,
                status=CheckStatus.ERROR,
                is_critical=is_critical,
                message=f"{name} version check timed out (> 10 s).",
                detected_path=resolved_path,
                download_url=download_url,
            )
        except OSError as exc:
            return CheckResult(
                name=name,
                status=CheckStatus.ERROR,
                is_critical=is_critical,
                message=f"Failed to run {name}: {exc}",
                detected_path=resolved_path,
                download_url=download_url,
            )

        # 3. Parse version
        detected_version = _parse_version(raw_output)
        if detected_version is None:
            # Cannot parse version — treat as an error only if min version required
            if minimum_version is not None:
                return CheckResult(
                    name=name,
                    status=CheckStatus.ERROR,
                    is_critical=is_critical,
                    message=f"Could not parse {name} version from output.",
                    detected_path=resolved_path,
                    download_url=download_url,
                    details=raw_output[:500],
                )
            # No version requirement — found is enough
            return CheckResult(
                name=name,
                status=CheckStatus.OK,
                is_critical=is_critical,
                message=f"{name} found (version unknown). ({resolved_path})",
                detected_path=resolved_path,
            )

        # 4. Version comparison
        if minimum_version is not None and not _version_meets_minimum(
            detected_version, minimum_version
        ):
            return CheckResult(
                name=name,
                status=CheckStatus.VERSION_TOO_OLD,
                is_critical=is_critical,
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
            is_critical=is_critical,
            message=f"{name} v{detected_version} — OK. ({resolved_path})",
            detected_version=detected_version,
            minimum_version=minimum_version,
            detected_path=resolved_path,
        )
