"""CLI interface for queuectl"""

import click
import json
import uuid
import multiprocessing
import os
import signal
import time
from datetime import datetime
from tabulate import tabulate
from typing import Optional

from .models import Job, JobState
from .storage import JobStore
from .config import ConfigManager
from .worker import run_worker


# Global process manager for workers
worker_processes = []


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """QueueCTL - A CLI-based background job queue system"""
    pass


@cli.command()
@click.argument("job_spec")
def enqueue(job_spec: str):
    """
    Enqueue a new job.
    
    JOB_SPEC can be a JSON string or a simple command.
    
    Examples:
        queuectl enqueue '{"id":"job1","command":"echo hello"}'
        queuectl enqueue "echo 'Hello World'"
    """
    config = ConfigManager()
    store = JobStore(config.get("db_path"))

    try:
        # Try to parse as JSON first
        try:
            job_data = json.loads(job_spec)
            
            # Validate required fields
            if "command" not in job_data:
                click.echo("Error: 'command' field is required in job specification", err=True)
                return
            
            # Generate ID if not provided
            if "id" not in job_data:
                job_data["id"] = f"job-{uuid.uuid4().hex[:8]}"
            
            # Apply defaults
            if "max_retries" not in job_data:
                job_data["max_retries"] = config.get("max_retries", 3)
            
            job = Job.from_dict(job_data)
            
        except json.JSONDecodeError:
            # Treat as simple command
            job = Job(
                id=f"job-{uuid.uuid4().hex[:8]}",
                command=job_spec,
                max_retries=config.get("max_retries", 3)
            )

        # Enqueue the job
        if store.enqueue(job):
            click.echo(f"[OK] Job enqueued successfully: {job.id}")
            click.echo(f"  Command: {job.command}")
            click.echo(f"  Max retries: {job.max_retries}")
        else:
            click.echo(f"Error: Job with ID '{job.id}' already exists", err=True)

    except Exception as e:
        click.echo(f"Error enqueueing job: {e}", err=True)
    finally:
        store.close()


@cli.group()
def worker():
    """Manage workers"""
    pass


@worker.command()
@click.option("--count", "-c", default=1, help="Number of workers to start")
@click.option("--daemon", "-d", is_flag=True, help="Run workers in background")
def start(count: int, daemon: bool):
    """Start worker processes"""
    config = ConfigManager()
    db_path = config.get("db_path")

    if daemon:
        click.echo("Error: Daemon mode not yet implemented. Run workers in foreground.", err=True)
        click.echo("Tip: Use a process manager like systemd or supervisord for production.")
        return

    click.echo(f"Starting {count} worker(s)...")

    global worker_processes
    
    # Create worker processes
    for i in range(count):
        worker_id = f"worker-{i+1}"
        process = multiprocessing.Process(
            target=run_worker,
            args=(worker_id, db_path),
            name=worker_id
        )
        process.start()
        worker_processes.append(process)
        click.echo(f"  [OK] Started {worker_id} (PID: {process.pid})")

    # Register cleanup handler
    def cleanup(signum, frame):
        click.echo("\nShutting down workers...")
        for p in worker_processes:
            if p.is_alive():
                p.terminate()
        for p in worker_processes:
            p.join(timeout=5)
        click.echo("All workers stopped")
        exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    click.echo(f"\nWorkers running. Press Ctrl+C to stop.")

    # Wait for workers
    try:
        for process in worker_processes:
            process.join()
    except KeyboardInterrupt:
        cleanup(None, None)


@worker.command()
def stop():
    """Stop all running workers"""
    # This is a simplified version - in production, you'd track PIDs
    click.echo("Sending stop signal to workers...")
    
    # Attempt to find and stop worker processes
    # This is OS-specific and simplified
    if os.name == 'nt':
        click.echo("Please stop workers manually with Ctrl+C or Task Manager")
    else:
        click.echo("Please stop workers manually with Ctrl+C or kill command")


@cli.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed status")
def status(verbose: bool):
    """Show queue status and statistics"""
    config = ConfigManager()
    store = JobStore(config.get("db_path"))

    try:
        stats = store.get_stats()
        
        click.echo("\n=== QueueCTL Status ===\n")
        
        # Job statistics
        click.echo("Job Statistics:")
        table_data = []
        for state in JobState:
            count = stats.get(state.value, 0)
            table_data.append([state.value.upper(), count])
        
        click.echo(tabulate(table_data, headers=["State", "Count"], tablefmt="simple"))
        
        # Configuration
        if verbose:
            click.echo("\nConfiguration:")
            cfg = config.get_all()
            cfg_data = [[k, v] for k, v in cfg.items()]
            click.echo(tabulate(cfg_data, headers=["Setting", "Value"], tablefmt="simple"))
        
        click.echo()

    except Exception as e:
        click.echo(f"Error retrieving status: {e}", err=True)
    finally:
        store.close()


@cli.command()
@click.option("--state", "-s", type=click.Choice([s.value for s in JobState]), help="Filter by state")
@click.option("--limit", "-l", type=int, help="Limit number of results")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed job information")
def list(state: Optional[str], limit: Optional[int], verbose: bool):
    """List jobs"""
    config = ConfigManager()
    store = JobStore(config.get("db_path"))

    try:
        job_state = JobState(state) if state else None
        jobs = store.list_jobs(state=job_state, limit=limit)

        if not jobs:
            click.echo("No jobs found")
            return

        # Prepare table data
        if verbose:
            headers = ["ID", "Command", "State", "Attempts", "Max Retries", "Created At", "Error"]
            table_data = []
            for job in jobs:
                table_data.append([
                    job.id,
                    job.command[:50] + "..." if len(job.command) > 50 else job.command,
                    job.state.value,
                    job.attempts,
                    job.max_retries,
                    job.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    (job.error_message[:30] + "...") if job.error_message and len(job.error_message) > 30 else (job.error_message or "")
                ])
        else:
            headers = ["ID", "Command", "State", "Attempts"]
            table_data = []
            for job in jobs:
                table_data.append([
                    job.id,
                    job.command[:60] + "..." if len(job.command) > 60 else job.command,
                    job.state.value,
                    f"{job.attempts}/{job.max_retries}"
                ])

        click.echo(f"\nFound {len(jobs)} job(s):\n")
        click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
        click.echo()

    except Exception as e:
        click.echo(f"Error listing jobs: {e}", err=True)
    finally:
        store.close()


@cli.group()
def dlq():
    """Manage Dead Letter Queue"""
    pass


@dlq.command(name="list")
@click.option("--limit", "-l", type=int, help="Limit number of results")
def dlq_list(limit: Optional[int]):
    """List jobs in Dead Letter Queue"""
    config = ConfigManager()
    store = JobStore(config.get("db_path"))

    try:
        jobs = store.list_jobs(state=JobState.DEAD, limit=limit)

        if not jobs:
            click.echo("No jobs in Dead Letter Queue")
            return

        headers = ["ID", "Command", "Attempts", "Error", "Updated At"]
        table_data = []
        for job in jobs:
            table_data.append([
                job.id,
                job.command[:50] + "..." if len(job.command) > 50 else job.command,
                job.attempts,
                (job.error_message[:40] + "...") if job.error_message and len(job.error_message) > 40 else (job.error_message or ""),
                job.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            ])

        click.echo(f"\nDead Letter Queue ({len(jobs)} job(s)):\n")
        click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))
        click.echo()

    except Exception as e:
        click.echo(f"Error listing DLQ: {e}", err=True)
    finally:
        store.close()


@dlq.command()
@click.argument("job_id")
def retry(job_id: str):
    """Retry a job from Dead Letter Queue"""
    config = ConfigManager()
    store = JobStore(config.get("db_path"))

    try:
        job = store.get_job(job_id)

        if not job:
            click.echo(f"Error: Job '{job_id}' not found", err=True)
            return

        if job.state != JobState.DEAD:
            click.echo(f"Error: Job '{job_id}' is not in Dead Letter Queue (state: {job.state.value})", err=True)
            return

        # Reset job for retry
        job.state = JobState.PENDING
        job.attempts = 0
        job.error_message = None
        job.next_retry_at = None

        if store.update_job(job):
            click.echo(f"[OK] Job '{job_id}' has been requeued for retry")
        else:
            click.echo(f"Error: Failed to update job '{job_id}'", err=True)

    except Exception as e:
        click.echo(f"Error retrying job: {e}", err=True)
    finally:
        store.close()


@dlq.command()
@click.confirmation_option(prompt="Are you sure you want to clear the entire Dead Letter Queue?")
def clear():
    """Clear all jobs from Dead Letter Queue"""
    config = ConfigManager()
    store = JobStore(config.get("db_path"))

    try:
        jobs = store.list_jobs(state=JobState.DEAD)
        count = 0

        for job in jobs:
            if store.delete_job(job.id):
                count += 1

        click.echo(f"[OK] Cleared {count} job(s) from Dead Letter Queue")

    except Exception as e:
        click.echo(f"Error clearing DLQ: {e}", err=True)
    finally:
        store.close()


@cli.group()
def config():
    """Manage configuration"""
    pass


@config.command(name="show")
def config_show():
    """Show current configuration"""
    config_mgr = ConfigManager()
    cfg = config_mgr.get_all()

    click.echo("\n=== Configuration ===\n")
    table_data = [[k, v] for k, v in cfg.items()]
    click.echo(tabulate(table_data, headers=["Setting", "Value"], tablefmt="simple"))
    click.echo()


@config.command(name="set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """Set a configuration value"""
    config_mgr = ConfigManager()

    # Type conversion for known numeric settings
    if key in ["max_retries", "backoff_base"]:
        try:
            value = int(value)
        except ValueError:
            click.echo(f"Error: '{key}' must be an integer", err=True)
            return

    config_mgr.set(key, value)
    click.echo(f"[OK] Configuration updated: {key} = {value}")


@config.command(name="reset")
@click.confirmation_option(prompt="Are you sure you want to reset configuration to defaults?")
def config_reset():
    """Reset configuration to defaults"""
    config_mgr = ConfigManager()
    config_mgr.reset()
    click.echo("[OK] Configuration reset to defaults")


if __name__ == "__main__":
    cli()
