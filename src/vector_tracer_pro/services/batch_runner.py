"""
vector_tracer_pro.services.batch_runner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Runs vectorisation pipeline jobs concurrently using thread pool execution.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from vector_tracer_pro.services.preset_manager import TracingPreset


@dataclass
class BatchJob:
    """Represents a single job in a batch run."""

    job_id: str
    input_path: Path
    output_dir: Path
    preset: TracingPreset
    status: str = "pending"  # pending | running | done | failed
    error: str | None = None


@dataclass
class BatchProgress:
    """Progress update for an active batch job."""

    job_id: str
    step: str
    percent: int


class BatchRunner:
    """Manages concurrent pipeline runs using a thread pool executor."""

    def __init__(self) -> None:
        """Initialize BatchRunner."""
        self._lock = threading.Lock()
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._futures: list[tuple[concurrent.futures.Future, BatchJob]] = []
        self._cancelled = False

    def submit(
        self,
        jobs: list[BatchJob],
        on_job_progress: Callable[[BatchProgress], None] | None = None,
        on_job_done: Callable[[BatchJob], None] | None = None,
        max_workers: int = 2,
    ) -> None:
        """Submit a list of BatchJobs for concurrent execution.

        Parameters
        ----------
        jobs:
            The list of BatchJob instances to run.
        on_job_progress:
            Callback invoked for individual job progress updates.
        on_job_done:
            Callback invoked when a job completes or fails.
        max_workers:
            Maximum number of concurrent execution threads.
        """
        with self._lock:
            self._cancelled = False
            self._on_job_done = on_job_done
            self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
            self._futures = []

            for job in jobs:
                job.status = "pending"
                job.error = None
                future = self._executor.submit(
                    self._run_job,
                    job,
                    on_job_progress,
                    on_job_done,
                )
                self._futures.append((future, job))

    def _run_job(
        self,
        job: BatchJob,
        on_job_progress: Callable[[BatchProgress], None] | None = None,
        on_job_done: Callable[[BatchJob], None] | None = None,
    ) -> None:
        """Execute a single BatchJob in a worker thread."""
        from vector_tracer_pro.core.image.preprocessor import PreprocessConfig
        from vector_tracer_pro.core.marketplace_validator import MarketplacePreset
        from vector_tracer_pro.core.pipeline import Pipeline
        from vector_tracer_pro.core.trace_strategy import TraceParams

        pipeline = Pipeline()
        preset = job.preset
        p_cfg = PreprocessConfig(**preset.preprocess_config) if preset.preprocess_config else None
        t_params = TraceParams(**preset.trace_params) if preset.trace_params else None

        def on_pipeline_progress(step: str, percent: int) -> None:
            if self._cancelled:
                raise RuntimeError("Cancelled")
            if on_job_progress:
                on_job_progress(BatchProgress(job_id=job.job_id, step=step, percent=percent))

        try:
            if self._cancelled:
                raise RuntimeError("Cancelled")

            job.status = "running"

            pipeline.run(
                input_path=job.input_path,
                output_dir=job.output_dir,
                preset=MarketplacePreset(preset.marketplace),
                preprocess_config=p_cfg,
                trace_params=t_params,
                on_progress=on_pipeline_progress,
            )

            if self._cancelled:
                raise RuntimeError("Cancelled")

            job.status = "done"
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
        finally:
            if on_job_done:
                on_job_done(job)

    def cancel_all(self) -> None:
        """Cancel all pending and running batch jobs."""
        with self._lock:
            self._cancelled = True
            for future, job in self._futures:
                if not future.done():
                    # Attempt to cancel if it has not started
                    cancelled = future.cancel()
                    if cancelled:
                        job.status = "failed"
                        job.error = "Cancelled"
                        if getattr(self, "_on_job_done", None):
                            with contextlib.suppress(Exception):
                                self._on_job_done(job)
            if self._executor:
                self._executor.shutdown(wait=False, cancel_futures=True)
