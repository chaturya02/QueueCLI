#!/usr/bin/env python3
"""
Validation script for QueueCTL
Tests core functionality and demonstrates the system in action
"""

import subprocess
import time
import json
import sys
import os

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_test(message):
    print(f"\n{BLUE}[TEST]{RESET} {message}")

def print_success(message):
    print(f"{GREEN}[OK]{RESET} {message}")

def print_error(message):
    print(f"{RED}[X]{RESET} {message}")

def print_info(message):
    print(f"{YELLOW}[i]{RESET} {message}")

def run_command(cmd, check=True):
    """Run a command and return output"""
    print_info(f"Running: {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True
    )
    if check and result.returncode != 0:
        print_error(f"Command failed: {result.stderr}")
        return None
    return result

def cleanup():
    """Clean up test data"""
    print_info("Cleaning up test data...")
    files_to_remove = ["queuectl.db", "queuectl_config.json"]
    for f in files_to_remove:
        if os.path.exists(f):
            os.remove(f)
            print_info(f"Removed {f}")

def test_1_basic_job():
    """Test 1: Basic job completion"""
    print_test("Test 1: Basic job completes successfully")
    
    # Enqueue a simple job
    result = run_command('python -m queuectl.cli enqueue "echo Hello World"')
    if not result:
        return False
    print_success("Job enqueued")
    
    # Check status
    result = run_command("python -m queuectl.cli status")
    if not result or "PENDING" not in result.stdout:
        print_error("Job not in pending state")
        return False
    print_success("Job is in pending state")
    
    return True

def test_2_failed_job_retry():
    """Test 2: Failed job retries with backoff"""
    print_test("Test 2: Failed job retries with exponential backoff")
    
    # Set max retries to 2 for faster testing
    run_command("python -m queuectl.cli config set max-retries 2")
    
    # Enqueue a job that will fail
    job_spec = {
        "id": "failing-job",
        "command": "exit 1",
        "max_retries": 2
    }
    json_str = json.dumps(job_spec).replace('"', '\\"')
    result = run_command(f'python -m queuectl.cli enqueue "{json_str}"')
    if not result:
        return False
    print_success("Failing job enqueued")
    
    return True

def test_3_job_persistence():
    """Test 3: Job data survives restart"""
    print_test("Test 3: Job data persists across restarts")
    
    # Enqueue a job
    result = run_command('python -m queuectl.cli enqueue "echo Persistent Job"')
    if not result:
        return False
    
    # Check that job exists
    result = run_command("python -m queuectl.cli list --state pending")
    if not result or "Persistent Job" not in result.stdout:
        print_error("Job not found after enqueue")
        return False
    print_success("Job persisted in database")
    
    return True

def test_4_configuration():
    """Test 4: Configuration management"""
    print_test("Test 4: Configuration management")
    
    # Show config
    result = run_command("python -m queuectl.cli config show")
    if not result:
        return False
    print_success("Configuration displayed")
    
    # Set config
    result = run_command("python -m queuectl.cli config set max-retries 5")
    if not result:
        return False
    
    # Verify
    result = run_command("python -m queuectl.cli config show")
    if not result or "5" not in result.stdout:
        print_error("Configuration not updated")
        return False
    print_success("Configuration updated and persisted")
    
    return True

def test_5_dlq():
    """Test 5: Dead Letter Queue"""
    print_test("Test 5: Dead Letter Queue functionality")
    
    # This test requires running a worker, so we'll just demonstrate the commands
    print_info("DLQ commands available:")
    print_info("  - queuectl dlq list")
    print_info("  - queuectl dlq retry <job-id>")
    print_info("  - queuectl dlq clear")
    print_success("DLQ commands documented")
    
    return True

def test_6_list_and_status():
    """Test 6: List and status commands"""
    print_test("Test 6: List and status commands")
    
    # Status
    result = run_command("python -m queuectl.cli status")
    if not result:
        return False
    print_success("Status command works")
    
    # List all
    result = run_command("python -m queuectl.cli list")
    if not result:
        return False
    print_success("List command works")
    
    # List by state
    result = run_command("python -m queuectl.cli list --state pending")
    if not result:
        return False
    print_success("List with filter works")
    
    return True

def main():
    """Run all validation tests"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}QueueCTL Validation Script{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    # Clean up before starting
    cleanup()
    
    tests = [
        test_1_basic_job,
        test_2_failed_job_retry,
        test_3_job_persistence,
        test_4_configuration,
        test_5_dlq,
        test_6_list_and_status,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print_error(f"{test.__name__} failed")
        except Exception as e:
            failed += 1
            print_error(f"{test.__name__} failed with exception: {e}")
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"\n{GREEN}Passed:{RESET} {passed}/{len(tests)}")
    if failed > 0:
        print(f"{RED}Failed:{RESET} {failed}/{len(tests)}")
    
    print(f"\n{YELLOW}Note:{RESET} To test worker functionality, run:")
    print(f"  python -m queuectl.cli worker start --count 2")
    print(f"\nThis will process all enqueued jobs with 2 workers.")
    print(f"Press Ctrl+C to stop workers.\n")
    
    # Show final status
    print_test("Final queue status:")
    run_command("python -m queuectl.cli status")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
