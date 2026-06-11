"""
tests.unit.core.test_path_manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for :mod:`vector_tracer_pro.core.path_manager`.

All tests use a tmp_path fixture for ``output_root`` and ``temp_root``
so that no writes touch real user-profile directories.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from vector_tracer_pro.core.path_manager import PathManager


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def pm(tmp_path: Path) -> PathManager:
    """PathManager with both roots inside the test's tmp directory."""
    return PathManager(
        output_root=tmp_path / "Output",
        temp_root=tmp_path / "Temp",
    )


# ===========================================================================
# Construction
# ===========================================================================


@pytest.mark.unit
class TestPathManagerConstruction:
    def test_default_construction_does_not_raise(self) -> None:
        """PathManager() with no args should succeed (no IO at __init__)."""
        pm = PathManager()
        assert pm is not None

    def test_custom_output_root_is_stored(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom_output"
        pm = PathManager(output_root=custom)
        assert pm.get_output_root() == custom

    def test_custom_temp_root_is_stored(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom_temp"
        pm = PathManager(temp_root=custom)
        assert pm._temp_root == custom  # noqa: SLF001

    def test_session_id_exists(self) -> None:
        pm = PathManager()
        assert pm.session_id.startswith("session_")
        assert len(pm.session_id) > 12

    def test_session_isolation(self) -> None:
        pm1 = PathManager()
        pm2 = PathManager()
        assert pm1.session_id != pm2.session_id
        assert pm1.get_temp_dir() != pm2.get_temp_dir()


# ===========================================================================
# Directory accessors — existence
# ===========================================================================


@pytest.mark.unit
class TestDirectoryAccessors:
    def test_get_input_dir_returns_path(self, pm: PathManager) -> None:
        d = pm.get_input_dir()
        assert isinstance(d, Path)

    def test_get_input_dir_creates_directory(self, pm: PathManager) -> None:
        d = pm.get_input_dir()
        assert d.is_dir()

    def test_get_output_svg_dir_under_output_root(self, pm: PathManager, tmp_path: Path) -> None:
        d = pm.get_output_svg_dir()
        assert d.is_dir()
        assert str(tmp_path / "Output") in str(d)

    def test_get_output_svg_dir_name_is_svg(self, pm: PathManager) -> None:
        d = pm.get_output_svg_dir()
        assert d.name == "SVG"

    def test_get_output_preview_dir_name_is_previews(self, pm: PathManager) -> None:
        d = pm.get_output_preview_dir()
        assert d.name == "Previews"

    def test_get_temp_dir_under_temp_root(self, pm: PathManager, tmp_path: Path) -> None:
        d = pm.get_temp_dir()
        assert d.is_dir()
        assert str(tmp_path / "Temp") in str(d)

    def test_get_logs_dir_exists_after_call(self, pm: PathManager) -> None:
        d = pm.get_logs_dir()
        assert d.is_dir()

    def test_get_config_dir_exists_after_call(self, pm: PathManager) -> None:
        d = pm.get_config_dir()
        assert d.is_dir()

    def test_get_user_presets_dir_is_child_of_config(self, pm: PathManager) -> None:
        presets = pm.get_user_presets_dir()
        config = pm.get_config_dir()
        assert presets.parent == config

    def test_all_accessors_return_directories(self, pm: PathManager) -> None:
        dirs = [
            pm.get_input_dir(),
            pm.get_output_svg_dir(),
            pm.get_output_preview_dir(),
            pm.get_temp_dir(),
            pm.get_logs_dir(),
            pm.get_config_dir(),
            pm.get_user_presets_dir(),
        ]
        for d in dirs:
            assert d.is_dir(), f"{d} was not created"


# ===========================================================================
# ensure_all_dirs
# ===========================================================================


@pytest.mark.unit
class TestEnsureAllDirs:
    def test_ensure_all_dirs_creates_everything(self, pm: PathManager) -> None:
        pm.ensure_all_dirs()
        assert pm.get_output_svg_dir().is_dir()
        assert pm.get_output_preview_dir().is_dir()
        assert pm.get_temp_dir().is_dir()
        assert pm.get_logs_dir().is_dir()
        assert pm.get_config_dir().is_dir()
        assert pm.get_user_presets_dir().is_dir()

    def test_ensure_all_dirs_is_idempotent(self, pm: PathManager) -> None:
        pm.ensure_all_dirs()
        pm.ensure_all_dirs()  # should not raise


# ===========================================================================
# set_output_root
# ===========================================================================


@pytest.mark.unit
class TestSetOutputRoot:
    def test_set_output_root_changes_svg_dir(
        self, pm: PathManager, tmp_path: Path
    ) -> None:
        new_root = tmp_path / "new_output"
        pm.set_output_root(new_root)
        svg_dir = pm.get_output_svg_dir()
        assert str(new_root) in str(svg_dir)
        assert svg_dir.is_dir()

    def test_set_output_root_changes_preview_dir(
        self, pm: PathManager, tmp_path: Path
    ) -> None:
        new_root = tmp_path / "another_output"
        pm.set_output_root(new_root)
        preview_dir = pm.get_output_preview_dir()
        assert str(new_root) in str(preview_dir)

    def test_get_output_root_reflects_new_root(
        self, pm: PathManager, tmp_path: Path
    ) -> None:
        new_root = tmp_path / "updated"
        pm.set_output_root(new_root)
        assert pm.get_output_root() == new_root


# ===========================================================================
# Path derivation helpers
# ===========================================================================


@pytest.mark.unit
class TestPathDerivation:
    def test_svg_path_for_changes_extension_to_svg(self, pm: PathManager) -> None:
        p = pm.svg_path_for(Path("photo.jpg"))
        assert p.suffix == ".svg"
        assert p.stem == "photo"

    def test_svg_path_for_is_inside_svg_dir(self, pm: PathManager) -> None:
        p = pm.svg_path_for(Path("artwork.png"))
        assert p.parent == pm.get_output_svg_dir()

    def test_preview_path_for_changes_extension_to_jpg(self, pm: PathManager) -> None:
        p = pm.preview_path_for(Path("logo.png"))
        assert p.suffix == ".jpg"
        assert p.stem == "logo"

    def test_preview_path_for_is_inside_preview_dir(self, pm: PathManager) -> None:
        p = pm.preview_path_for(Path("icon.png"))
        assert p.parent == pm.get_output_preview_dir()

    def test_temp_path_for_default_suffix_is_bmp(self, pm: PathManager) -> None:
        p = pm.temp_path_for(Path("image.jpg"))
        assert p.suffix == ".bmp"

    def test_temp_path_for_custom_suffix_pbm(self, pm: PathManager) -> None:
        p = pm.temp_path_for(Path("image.jpg"), suffix=".pbm")
        assert p.suffix == ".pbm"

    def test_temp_path_for_is_inside_temp_dir(self, pm: PathManager) -> None:
        p = pm.temp_path_for(Path("scan.png"))
        assert p.parent == pm.get_temp_dir()

    def test_svg_path_stem_preserved_for_nested_input(self, pm: PathManager) -> None:
        """Deep input path — only the filename stem should be used."""
        p = pm.svg_path_for(Path("some/deep/folder/bird.jpg"))
        assert p.stem == "bird"
        assert p.parent == pm.get_output_svg_dir()

    def test_temp_path_for_collision_prevention(self, pm: PathManager) -> None:
        """Calling temp_path_for twice with same name must return different paths."""
        p1 = pm.temp_path_for(Path("image.jpg"))
        p2 = pm.temp_path_for(Path("image.jpg"))
        assert p1 != p2


# ===========================================================================
# Cleanup API
# ===========================================================================


@pytest.mark.unit
class TestCleanupAPI:
    def test_cleanup_temp_file_removes_file(self, pm: PathManager) -> None:
        p = pm.temp_path_for(Path("test.jpg"))
        p.write_bytes(b"data")
        assert p.is_file()
        assert pm.cleanup_temp_file(p) is True
        assert not p.exists()

    def test_cleanup_temp_file_missing_returns_false(self, pm: PathManager) -> None:
        p = pm.temp_path_for(Path("nonexistent.jpg"))
        assert pm.cleanup_temp_file(p) is False

    def test_cleanup_all_temp_files(self, pm: PathManager) -> None:
        p1 = pm.temp_path_for(Path("1.jpg"))
        p2 = pm.temp_path_for(Path("2.jpg"))
        p1.write_bytes(b"data1")
        p2.write_bytes(b"data2")
        
        temp_dir = pm.get_temp_dir()
        assert p1.is_file()
        assert p2.is_file()
        assert temp_dir.is_dir()
        
        deleted_count = pm.cleanup_all_temp_files()
        assert deleted_count == 2
        assert not p1.exists()
        assert not p2.exists()
        assert not temp_dir.exists()

    def test_cleanup_orphaned_sessions(self, pm: PathManager) -> None:
        # Create an orphaned session folder in the same temp root
        orphaned_dir = pm._temp_root / "session_999999999999"
        orphaned_dir.mkdir(parents=True, exist_ok=True)
        orphaned_file = orphaned_dir / "old_temp.bmp"
        orphaned_file.write_bytes(b"old")
        
        assert orphaned_dir.is_dir()
        assert orphaned_file.is_file()
        
        # Run cleanup
        orphaned_deleted = pm.cleanup_orphaned_sessions()
        assert orphaned_deleted == 1
        assert not orphaned_dir.exists()
        assert not orphaned_file.exists()
        
        # Current session should remain untouched
        assert pm.get_temp_dir().is_dir()


# ===========================================================================
# Thread safety
# ===========================================================================


@pytest.mark.unit
class TestThreadSafety:
    def test_concurrent_ensure_all_dirs_does_not_raise(
        self, pm: PathManager
    ) -> None:
        """Multiple threads calling ensure_all_dirs concurrently must not crash."""
        errors: list[Exception] = []

        def worker() -> None:
            try:
                pm.ensure_all_dirs()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_set_output_root_and_read_does_not_raise(
        self, pm: PathManager, tmp_path: Path
    ) -> None:
        """set_output_root and get_output_svg_dir may be called concurrently."""
        errors: list[Exception] = []

        def setter() -> None:
            for i in range(50):
                try:
                    pm.set_output_root(tmp_path / f"root_{i}")
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

        def reader() -> None:
            for _ in range(50):
                try:
                    pm.get_output_root()
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

        threads = [
            threading.Thread(target=setter),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
