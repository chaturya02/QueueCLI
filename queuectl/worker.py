"""Worker implementation for job processing"""

import subprocess
import signal
import time
import os
import sys
from datetime import datetime, timedelta
from typing import Optional
import uuid
import threading

from .models import Job, JobState
from .storage import JobStore
from .config import ConfigManager


class Worker:
    """Background worker for processing jobs"""

    def __init__(
        self,
        worker_id: Optional[str] = None,
        db_path: str = "queuectl.db",
        config_manager: Optional[ConfigManager] = None
    ):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.db_path = db_path
        self.config = config_manager or ConfigManager()
        self.store = JobStore(db_path)
        self.running = False
        self.current_job: Optional[Job] = None
        self._shutdown = False
        self._lock = threading.Lock()

    def start(self):
        """Start the worker"""
        self.running = True
        self._shutdown = False

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        print(f"[{self.worker_id}] Worker started")

        try:
            while self.running and not self._shutdown:
                self._process_next_job()
                time.sleep(1)  # Poll interval
        finally:
            self._cleanup()

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n[{self.worker_id}] Received shutdown signal, finishing current job...")
        self._shutdown = True

    def _process_next_job(self):
        """Process the next available job"""
        try:
            # Acquire next job
            job = self.store.acquire_job(self.worker_id)

            if not job:
                return  # No jobs available

            with self._lock:
                self.current_job = job

            print(f"[{self.worker_id}] Processing job {job.id}: {job.command}")

            # Execute the job
            success, error_message = self._execute_job(job)

            if success:
                self._mark_completed(job)
            else:
                self._handle_failure(job, error_message)

            with self._lock:
                self.current_job = None

        except Exception as e:
            print(f"[{self.worker_id}] Error processing job: {e}")
            if self.current_job:
                self._handle_failure(self.current_job, str(e))
                with self._lock:
                    self.current_job = None

    def _execute_job(self, job: Job) -> tuple[bool, Optional[str]]:
        """Execute job command"""
        try:
            # Determine shell based on OS
            if os.name == 'nt':  # Windows
                shell = True
            else:  # Unix-like
                shell = True

            result = subprocess.run(
                job.command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                return True, None
            else:
                error_msg = f"Exit code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.strip()}"
                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "Command timed out after 5 minutes"
        except FileNotFoundError:
            return False, "Command not found"
        except Exception as e:
            return False, str(e)

    def _mark_completed(self, job: Job):
        """Mark job as completed"""
        job.state = JobState.COMPLETED
        job.updated_at = datetime.utcnow()
        self.store.update_job(job)
        print(f"[{self.worker_id}] Job {job.id} completed successfully")

    def _handle_failure(self, job: Job, error_message: str):
        """Handle job failure with retry logic"""
        job.attempts += 1
        job.error_message = error_message
        job.updated_at = datetime.utcnow()

        max_retries = job.max_retries

        if job.attempts >= max_retries:
            # Move to DLQ
            job.state = JobState.DEAD
            job.next_retry_at = None
            self.store.update_job(job)
            print(f"[{self.worker_id}] Job {job.id} failed permanently, moved to DLQ")
        else:
            # Schedule retry with exponential backoff
            backoff_base = self.config.get("backoff_base", 2)
            delay_seconds = backoff_base ** job.attempts
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
            job.state = JobState.FAILED

            self.store.update_job(job)
            print(f"[{self.worker_id}] Job {job.id} failed (attempt {job.attempts}/{max_retries}), "
                  f"retrying in {delay_seconds}s. Error: {error_message}")

    def _cleanup(self):
        """Cleanup on worker shutdown"""
        # Release any locks held by this worker
        self.store.clear_locks(self.worker_id)
        self.store.close()
        print(f"[{self.worker_id}] Worker stopped")

    def stop(self):
        """Stop the worker"""
        self.running = False


def run_worker(worker_id: Optional[str] = None, db_path: str = "queuectl.db"):
    """Run a worker (entry point for multiprocessing)"""
    config = ConfigManager()
    if db_path == "queuectl.db":
        db_path = config.get("db_path", "queuectl.db")

    worker = Worker(worker_id=worker_id, db_path=db_path, config_manager=config)
    worker.start()
