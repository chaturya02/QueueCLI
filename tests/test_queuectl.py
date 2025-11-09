"""Test suite for QueueCTL"""

import unittest
import os
import tempfile
import shutil
from datetime import datetime, timedelta

from queuectl.models import Job, JobState
from queuectl.storage import JobStore
from queuectl.config import ConfigManager


class TestJobModel(unittest.TestCase):
    """Test Job model"""

    def test_job_creation(self):
        """Test creating a job"""
        job = Job(
            id="test-job",
            command="echo 'test'",
            max_retries=3
        )
        
        self.assertEqual(job.id, "test-job")
        self.assertEqual(job.command, "echo 'test'")
        self.assertEqual(job.state, JobState.PENDING)
        self.assertEqual(job.attempts, 0)
        self.assertEqual(job.max_retries, 3)

    def test_job_to_dict(self):
        """Test job serialization to dict"""
        job = Job(id="test", command="echo test")
        data = job.to_dict()
        
        self.assertEqual(data["id"], "test")
        self.assertEqual(data["command"], "echo test")
        self.assertEqual(data["state"], "pending")

    def test_job_from_dict(self):
        """Test job deserialization from dict"""
        data = {
            "id": "test",
            "command": "echo test",
            "state": "pending",
            "attempts": 0,
            "max_retries": 3,
        }
        
        job = Job.from_dict(data)
        self.assertEqual(job.id, "test")
        self.assertEqual(job.command, "echo test")
        self.assertEqual(job.state, JobState.PENDING)


class TestJobStore(unittest.TestCase):
    """Test JobStore"""

    def setUp(self):
        """Set up test database"""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test.db")
        self.store = JobStore(self.db_path)

    def tearDown(self):
        """Clean up test database"""
        self.store.close()
        shutil.rmtree(self.test_dir)

    def test_enqueue_job(self):
        """Test enqueueing a job"""
        job = Job(id="test-1", command="echo test")
        result = self.store.enqueue(job)
        
        self.assertTrue(result)
        
        # Verify job was stored
        retrieved = self.store.get_job("test-1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "test-1")

    def test_duplicate_job_id(self):
        """Test that duplicate job IDs are rejected"""
        job1 = Job(id="duplicate", command="echo 1")
        job2 = Job(id="duplicate", command="echo 2")
        
        self.assertTrue(self.store.enqueue(job1))
        self.assertFalse(self.store.enqueue(job2))

    def test_acquire_job(self):
        """Test acquiring a job for processing"""
        job = Job(id="test-acquire", command="echo test")
        self.store.enqueue(job)
        
        acquired = self.store.acquire_job("worker-1")
        
        self.assertIsNotNone(acquired)
        self.assertEqual(acquired.id, "test-acquire")
        self.assertEqual(acquired.state, JobState.PROCESSING)

    def test_job_locking(self):
        """Test that acquired jobs are locked"""
        job = Job(id="test-lock", command="echo test")
        self.store.enqueue(job)
        
        # Worker 1 acquires job
        acquired1 = self.store.acquire_job("worker-1")
        self.assertIsNotNone(acquired1)
        
        # Worker 2 should not be able to acquire the same job
        acquired2 = self.store.acquire_job("worker-2")
        self.assertIsNone(acquired2)

    def test_update_job(self):
        """Test updating a job"""
        job = Job(id="test-update", command="echo test")
        self.store.enqueue(job)
        
        job.state = JobState.COMPLETED
        job.attempts = 1
        
        result = self.store.update_job(job)
        self.assertTrue(result)
        
        retrieved = self.store.get_job("test-update")
        self.assertEqual(retrieved.state, JobState.COMPLETED)
        self.assertEqual(retrieved.attempts, 1)

    def test_list_jobs_by_state(self):
        """Test listing jobs filtered by state"""
        self.store.enqueue(Job(id="pending-1", command="echo 1"))
        self.store.enqueue(Job(id="pending-2", command="echo 2"))
        
        job3 = Job(id="completed-1", command="echo 3")
        job3.state = JobState.COMPLETED
        self.store.enqueue(job3)
        
        pending = self.store.list_jobs(state=JobState.PENDING)
        self.assertEqual(len(pending), 2)
        
        completed = self.store.list_jobs(state=JobState.COMPLETED)
        self.assertEqual(len(completed), 1)

    def test_get_stats(self):
        """Test getting job statistics"""
        self.store.enqueue(Job(id="p1", command="echo 1"))
        self.store.enqueue(Job(id="p2", command="echo 2"))
        
        job3 = Job(id="c1", command="echo 3")
        job3.state = JobState.COMPLETED
        self.store.enqueue(job3)
        
        stats = self.store.get_stats()
        
        self.assertEqual(stats.get("pending", 0), 2)
        self.assertEqual(stats.get("completed", 0), 1)


class TestConfigManager(unittest.TestCase):
    """Test ConfigManager"""

    def setUp(self):
        """Set up test config"""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, "test_config.json")
        self.config = ConfigManager(self.config_path)

    def tearDown(self):
        """Clean up test config"""
        shutil.rmtree(self.test_dir)

    def test_default_config(self):
        """Test default configuration values"""
        self.assertEqual(self.config.get("max_retries"), 3)
        self.assertEqual(self.config.get("backoff_base"), 2)

    def test_set_config(self):
        """Test setting configuration values"""
        self.config.set("max_retries", 5)
        self.assertEqual(self.config.get("max_retries"), 5)

    def test_config_persistence(self):
        """Test that configuration persists"""
        self.config.set("max_retries", 7)
        
        # Create new config manager with same path
        config2 = ConfigManager(self.config_path)
        self.assertEqual(config2.get("max_retries"), 7)

    def test_reset_config(self):
        """Test resetting configuration"""
        self.config.set("max_retries", 10)
        self.config.reset()
        self.assertEqual(self.config.get("max_retries"), 3)


if __name__ == "__main__":
    unittest.main()
