"""
tests.unit.services.test_batch_runner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for BatchRunner.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from vector_tracer_pro.services.batch_runner import BatchJob, BatchRunner
from vector_tracer_pro.services.preset_manager import TracingPreset


@pytest.mark.unit
class TestBatchRunner:
    @patch("vector_tracer_pro.core.pipeline.Pipeline")
    def test_submit_runs_jobs_and_calls_callbacks(self, mock_pipeline_cls, tmp_path) -> None:
        mock_pipeline = mock_pipeline_cls.return_value

        # Define mock execution that invokes progress callback
        def mock_run(
            input_path,
            output_dir,
            preset,
            preprocess_config=None,
            trace_params=None,
            on_progress=None,
        ):
            if on_progress:
                on_progress("loading", 10)
                on_progress("done", 100)

        mock_pipeline.run.side_effect = mock_run

        runner = BatchRunner()
        preset = TracingPreset("test", "freepik", [], {}, {})

        job1 = BatchJob("job_1", Path("in1.png"), tmp_path, preset)
        job2 = BatchJob("job_2", Path("in2.png"), tmp_path, preset)

        progress_updates = []
        completed_jobs = []

        # Define callbacks
        def on_progress(p):
            progress_updates.append(p)

        def on_done(j):
            completed_jobs.append(j)

        # Run
        runner.submit([job1, job2], on_job_progress=on_progress, on_job_done=on_done)

        # Wait for threads to finish (max 2.5 seconds)
        for _ in range(50):
            if len(completed_jobs) == 2:
                break
            time.sleep(0.05)

        assert len(completed_jobs) == 2
        assert job1.status == "done"
        assert job2.status == "done"
        assert job1.error is None
        assert job2.error is None

        # Verify progress callback was called
        assert len(progress_updates) == 4
        assert any(
            p.job_id == "job_1" and p.step == "loading" and p.percent == 10
            for p in progress_updates
        )
        assert any(
            p.job_id == "job_2" and p.step == "done" and p.percent == 100 for p in progress_updates
        )

    @patch("vector_tracer_pro.core.pipeline.Pipeline")
    def test_job_failure_handling(self, mock_pipeline_cls, tmp_path) -> None:
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.run.side_effect = ValueError("Processing failed")

        runner = BatchRunner()
        preset = TracingPreset("test", "freepik", [], {}, {})
        job = BatchJob("job_1", Path("in.png"), tmp_path, preset)

        completed = []
        runner.submit([job], on_job_done=completed.append)

        # Wait
        for _ in range(50):
            if completed:
                break
            time.sleep(0.05)

        assert len(completed) == 1
        assert job.status == "failed"
        assert "Processing failed" in job.error

    @patch("vector_tracer_pro.core.pipeline.Pipeline")
    def test_cancel_all(self, mock_pipeline_cls, tmp_path) -> None:
        mock_pipeline = mock_pipeline_cls.return_value

        # Introduce a delay in mock run to test cancellation
        def mock_run(*args, **kwargs):
            time.sleep(0.2)
            if kwargs.get("on_progress"):
                kwargs["on_progress"]("loading", 10)

        mock_pipeline.run.side_effect = mock_run

        runner = BatchRunner()
        preset = TracingPreset("test", "freepik", [], {}, {})

        job1 = BatchJob("job_1", Path("in1.png"), tmp_path, preset)
        job2 = BatchJob("job_2", Path("in2.png"), tmp_path, preset)
        job3 = BatchJob("job_3", Path("in3.png"), tmp_path, preset)

        completed = []
        runner.submit([job1, job2, job3], on_job_done=completed.append, max_workers=1)

        # Sleep briefly to ensure the first job is running, but the rest are pending
        time.sleep(0.05)

        # Cancel all
        runner.cancel_all()

        # Wait for executor to clean up
        for _ in range(50):
            if len(completed) == 3:
                break
            time.sleep(0.05)

        assert len(completed) == 3
        # All jobs should have failed
        assert job1.status == "failed"
        assert job2.status == "failed"
        assert job3.status == "failed"
