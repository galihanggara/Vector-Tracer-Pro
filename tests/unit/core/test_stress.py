"""
tests.unit.core.test_stress
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Stress and concurrency tests for PathManager and batch pipeline simulation.
"""

from __future__ import annotations

import concurrent.futures
import queue
from pathlib import Path

import pytest

from vector_tracer_pro.core.marketplace_validator import MarketplaceValidator
from vector_tracer_pro.core.path_manager import PathManager


@pytest.mark.unit
class TestMultiThreadStress:
    def test_concurrent_temp_file_operations(self, tmp_path: Path) -> None:
        """Stress test PathManager under high concurrent file creation and deletion."""
        pm = PathManager(
            output_root=tmp_path / "Output",
            temp_root=tmp_path / "Temp",
        )
        pm.ensure_all_dirs()

        num_threads = 50
        ops_per_thread = 20
        created_paths: queue.Queue[Path] = queue.Queue()
        errors: list[Exception] = []

        def worker(thread_idx: int) -> None:
            try:
                for i in range(ops_per_thread):
                    # Derive unique path
                    p = pm.temp_path_for(Path(f"thread_{thread_idx}_file_{i}.png"), suffix=".bmp")
                    # Write file
                    p.write_bytes(f"thread_{thread_idx}_op_{i}_data".encode())
                    assert p.is_file()
                    created_paths.put(p)
            except Exception as exc:
                errors.append(exc)

        # Launch concurrent threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, idx) for idx in range(num_threads)]
            concurrent.futures.wait(futures)

        assert not errors, f"Errors occurred during file creation: {errors}"
        assert created_paths.qsize() == (num_threads * ops_per_thread)

        # Concurrently delete all files
        def cleanup_worker() -> None:
            try:
                while True:
                    try:
                        p = created_paths.get_nowait()
                        # Verify we can delete it
                        deleted = pm.cleanup_temp_file(p)
                        assert deleted is True
                        assert not p.exists()
                    except queue.Empty:
                        break
            except Exception as exc:
                errors.append(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(cleanup_worker) for _ in range(num_threads)]
            concurrent.futures.wait(futures)

        assert not errors, f"Errors occurred during cleanup: {errors}"

    def test_simulated_batch_pipeline_stress(self, tmp_path: Path) -> None:
        """Stress test simulating a concurrent batch processing pipeline.

        Each thread behaves like a pipeline job:
          1. Resolves path using PathManager
          2. Generates temporary file
          3. Validates fake SVG output
          4. Performs cleanup
        """
        pm = PathManager(
            output_root=tmp_path / "Output",
            temp_root=tmp_path / "Temp",
        )
        pm.ensure_all_dirs()
        validator = MarketplaceValidator()

        num_jobs = 40
        max_workers = 10
        errors: list[Exception] = []

        def run_pipeline_job(job_id: int) -> None:
            try:
                # 1. Staging input
                temp_input = pm.temp_path_for(Path(f"image_{job_id}.png"), suffix=".bmp")
                temp_input.write_bytes(b"mock_raw_pixels")

                # 2. Simulate processing & writing output SVG
                svg_output = pm.svg_path_for(Path(f"vector_{job_id}.png"))
                svg_output.parent.mkdir(parents=True, exist_ok=True)
                svg_output.write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
                    '  <path d="M 0 0 Z" fill="#ffffff" />'
                    "</svg>"
                )

                # 3. Validate output
                result = validator.validate_svg(svg_output, "adobe_stock")
                assert result.is_compliant is True

                # 4. Clean up job-specific input
                deleted = pm.cleanup_temp_file(temp_input)
                assert deleted is True

            except Exception as exc:
                errors.append(exc)

        # Run concurrent pipeline jobs
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_pipeline_job, idx) for idx in range(num_jobs)]
            concurrent.futures.wait(futures)

        assert not errors, f"Errors occurred during batch pipeline simulation: {errors}"

        # Delete remaining outputs and clean up session directory
        assert pm.cleanup_all_temp_files() == 0  # Job files already deleted
        assert not (
            pm.temp_root / pm.session_id
        ).exists()  # Session directory itself should be deleted
