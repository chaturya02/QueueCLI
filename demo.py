#!/usr/bin/env python3
"""
Demo script for QueueCTL
Demonstrates various features of the job queue system
"""

import subprocess
import time
import json

def run_cmd(cmd):
    """Run a command and print output"""
    print(f"\n$ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    time.sleep(1)

def demo():
    """Run QueueCTL demo"""
    
    print("="*60)
    print("QueueCTL Demo")
    print("="*60)
    
    # Clean up
    print("\n[1] Cleaning up old data...")
    subprocess.run("del queuectl.db queuectl_config.json", shell=True, capture_output=True)
    
    # Show initial status
    print("\n[2] Initial Status")
    run_cmd("python -m queuectl.cli status")
    
    # Configure system
    print("\n[3] Configure System")
    run_cmd("python -m queuectl.cli config set max-retries 3")
    run_cmd("python -m queuectl.cli config set backoff-base 2")
    run_cmd("python -m queuectl.cli config show")
    
    # Enqueue jobs
    print("\n[4] Enqueue Jobs")
    run_cmd('python -m queuectl.cli enqueue "echo Hello from Job 1"')
    run_cmd('python -m queuectl.cli enqueue "echo Hello from Job 2"')
    run_cmd('python -m queuectl.cli enqueue "timeout /t 2 >nul & echo Delayed job completed"')
    
    # Enqueue with JSON
    job_spec = {
        "id": "custom-job-1",
        "command": "echo Custom JSON Job",
        "max_retries": 5
    }
    json_str = json.dumps(job_spec).replace('"', '\\"')
    run_cmd(f'python -m queuectl.cli enqueue "{json_str}"')
    
    # Show queue status
    print("\n[5] Queue Status")
    run_cmd("python -m queuectl.cli status")
    run_cmd("python -m queuectl.cli list --state pending")
    
    # Enqueue a failing job
    print("\n[6] Enqueue Failing Job")
    failing_job = {
        "id": "failing-job",
        "command": "exit 1",
        "max_retries": 2
    }
    json_str = json.dumps(failing_job).replace('"', '\\"')
    run_cmd(f'python -m queuectl.cli enqueue "{json_str}"')
    
    # Show all jobs
    print("\n[7] List All Jobs")
    run_cmd("python -m queuectl.cli list")
    
    print("\n[8] Ready to Process Jobs!")
    print("\nTo start workers, run in a separate terminal:")
    print("  python -m queuectl.cli worker start --count 2")
    print("\nOr run:")
    print("  queuectl worker start --count 2")
    print("\n(Press Ctrl+C to stop workers)")
    
    print("\n[9] After workers finish, check results:")
    print("  python -m queuectl.cli status")
    print("  python -m queuectl.cli list --state completed")
    print("  python -m queuectl.cli list --state dead")
    print("  python -m queuectl.cli dlq list")
    
    print("\n" + "="*60)
    print("Demo setup complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    demo()
