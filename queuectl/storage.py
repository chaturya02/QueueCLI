"""Job storage with SQLite backend"""

import sqlite3
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
import os

from .models import Job, JobState


class JobStore:
    """Persistent job storage with SQLite"""

    def __init__(self, db_path: str = "queuectl.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        """Initialize database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                next_retry_at TEXT,
                error_message TEXT,
                locked_by TEXT,
                locked_at TEXT
            )
        """)

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_state 
            ON jobs(state)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_next_retry 
            ON jobs(next_retry_at)
        """)

        conn.commit()

    def enqueue(self, job: Job) -> bool:
        """Add a new job to the queue"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO jobs (
                    id, command, state, attempts, max_retries,
                    created_at, updated_at, next_retry_at, error_message,
                    locked_by, locked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.id,
                job.command,
                job.state.value,
                job.attempts,
                job.max_retries,
                job.created_at.isoformat(),
                job.updated_at.isoformat(),
                job.next_retry_at.isoformat() if job.next_retry_at else None,
                job.error_message,
                None,  # locked_by
                None,  # locked_at
            ))

            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Job with this ID already exists

    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_job(row)
        return None

    def acquire_job(self, worker_id: str) -> Optional[Job]:
        """Acquire next available job for processing (with locking)"""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            now = datetime.utcnow().isoformat()

            # Find next job: pending or failed with retry time passed
            cursor.execute("""
                SELECT * FROM jobs
                WHERE (
                    (state = ? AND (locked_by IS NULL OR locked_at < datetime('now', '-5 minutes')))
                    OR
                    (state = ? AND next_retry_at <= ? AND (locked_by IS NULL OR locked_at < datetime('now', '-5 minutes')))
                )
                ORDER BY created_at ASC
                LIMIT 1
            """, (JobState.PENDING.value, JobState.FAILED.value, now))

            row = cursor.fetchone()

            if not row:
                return None

            job_id = row["id"]

            # Lock the job
            cursor.execute("""
                UPDATE jobs
                SET locked_by = ?, locked_at = ?, state = ?
                WHERE id = ?
            """, (worker_id, now, JobState.PROCESSING.value, job_id))

            conn.commit()

            # Fetch the locked job
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()

            return self._row_to_job(row)

    def update_job(self, job: Job) -> bool:
        """Update an existing job"""
        conn = self._get_connection()
        cursor = conn.cursor()

        job.updated_at = datetime.utcnow()

        cursor.execute("""
            UPDATE jobs
            SET command = ?, state = ?, attempts = ?, max_retries = ?,
                updated_at = ?, next_retry_at = ?, error_message = ?,
                locked_by = NULL, locked_at = NULL
            WHERE id = ?
        """, (
            job.command,
            job.state.value,
            job.attempts,
            job.max_retries,
            job.updated_at.isoformat(),
            job.next_retry_at.isoformat() if job.next_retry_at else None,
            job.error_message,
            job.id,
        ))

        conn.commit()
        return cursor.rowcount > 0

    def list_jobs(
        self,
        state: Optional[JobState] = None,
        limit: Optional[int] = None
    ) -> List[Job]:
        """List jobs, optionally filtered by state"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if state:
            query = "SELECT * FROM jobs WHERE state = ? ORDER BY created_at DESC"
            params = (state.value,)
        else:
            query = "SELECT * FROM jobs ORDER BY created_at DESC"
            params = ()

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_job(row) for row in rows]

    def get_stats(self) -> Dict[str, int]:
        """Get job statistics by state"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT state, COUNT(*) as count
            FROM jobs
            GROUP BY state
        """)

        stats = {}
        for row in cursor.fetchall():
            stats[row["state"]] = row["count"]

        return stats

    def delete_job(self, job_id: str) -> bool:
        """Delete a job"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()

        return cursor.rowcount > 0

    def clear_locks(self, worker_id: Optional[str] = None):
        """Clear stale locks (jobs locked for more than 5 minutes)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if worker_id:
            cursor.execute("""
                UPDATE jobs
                SET locked_by = NULL, locked_at = NULL, state = ?
                WHERE locked_by = ? AND state = ?
            """, (JobState.PENDING.value, worker_id, JobState.PROCESSING.value))
        else:
            cursor.execute("""
                UPDATE jobs
                SET locked_by = NULL, locked_at = NULL, state = ?
                WHERE locked_at < datetime('now', '-5 minutes') AND state = ?
            """, (JobState.PENDING.value, JobState.PROCESSING.value))

        conn.commit()

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert database row to Job object"""
        return Job(
            id=row["id"],
            command=row["command"],
            state=JobState(row["state"]),
            attempts=row["attempts"],
            max_retries=row["max_retries"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            next_retry_at=datetime.fromisoformat(row["next_retry_at"]) if row["next_retry_at"] else None,
            error_message=row["error_message"],
        )

    def close(self):
        """Close database connection"""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn
