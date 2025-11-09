# QueueCLI - CLI Background Job Queue System
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
A production-grade CLI-based background job queue system with worker processes, automatic retries using exponential backoff, and a Dead Letter Queue (DLQ).
## Features
- Job queue management via CLI
- Multiple worker processes for parallel execution  
- Automatic retry with exponential backoff
- Dead Letter Queue for permanently failed jobs
- Persistent SQLite storage (survives restarts)
- Job locking prevents duplicate processing
- Graceful worker shutdown
- Runtime configuration management
## Quick Start
### Installation
```bash
# Clone repository
git clone https://github.com/yourusername/QueueCLI.git
cd QueueCLI
# Install dependencies
pip install -r requirements.txt
# Install QueueCLI
pip install -e .
# Verify
queuectl --version
```
**Windows:** Run ```.\setup.bat``` for automated setup.
### Basic Usage
```bash
# Enqueue a job
queuectl enqueue "echo Hello QueueCLI"
# Start workers (in new terminal)
queuectl worker start --count 2
# Check status
queuectl status
# List jobs
queuectl list --state completed
```
## CLI Commands
| Command | Description |
|---------|-------------|
| ```queuectl enqueue "cmd"``` | Add job to queue |
| ```queuectl enqueue '{\"id\":\"job1\",\"command\":\"echo test\",\"max_retries\":5}'``` | Enqueue with JSON |
| ```queuectl worker start --count N``` | Start N workers |
| ```queuectl status``` | Show queue statistics |
| ```queuectl list --state <state>``` | List jobs by state |
| ```queuectl dlq list``` | View Dead Letter Queue |
| ```queuectl dlq retry <job-id>``` | Retry failed job |
| ```queuectl config set <key> <value>``` | Update config |
**States:** pending, processing, completed, failed, dead
**Windows PowerShell JSON:** Use single quotes: ```queuectl enqueue '{\"id\":\"job1\",\"command\":\"echo test\"}'```
## Configuration
```bash
# Set max retries (default: 3)
queuectl config set max-retries 5
# Set backoff base (default: 2, delay = base^attempts)
queuectl config set backoff-base 2
# View settings
queuectl config show
```
**Exponential Backoff** (base=2): 2s → 4s → 8s → 16s...
## Job Lifecycle
```
PENDING → PROCESSING → COMPLETED (success)
                    ↓
                  FAILED → retry → ... → DEAD (max retries exceeded)
```
## Architecture
```
CLI Layer (cli.py)
    ↓
Business Logic (worker.py, models.py, config.py)
    ↓
Persistence Layer (storage.py with SQLite)
```
**Concurrency:** Multi-process workers with optimistic locking prevent duplicate job processing.
**Database Schema:**
```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TEXT,
    updated_at TEXT,
    next_retry_at TEXT,
    error_message TEXT,
    locked_by TEXT,
    locked_at TEXT
);
```
## Examples
### Batch Processing
```bash
# Enqueue multiple jobs
for i in {1..10}; do queuectl enqueue "python process.py item"; done
# Process with 4 workers
queuectl worker start --count 4
```
### Handle Failures
```bash
# Enqueue job with retries
queuectl enqueue '{\"id\":\"api-call\",\"command\":\"python api.py\",\"max_retries\":5}'
# Check failures
queuectl dlq list
# Retry specific job
queuectl dlq retry api-call
```
### Windows
```powershell
queuectl enqueue "timeout /t 5 /nobreak"
queuectl enqueue "python script.py"
```
## Testing
```bash
# Unit tests
python -m pytest tests/
# Validation script
python validate.py
# Demo
python demo.py
# Then: queuectl worker start --count 2
```
## Project Structure
```
QueueCTL/
├── queuectl/
│   ├── cli.py          # CLI interface
│   ├── models.py       # Job models
│   ├── storage.py      # SQLite persistence
│   ├── worker.py       # Worker implementation
│   └── config.py       # Configuration
├── tests/
├── requirements.txt
├── setup.py
└── README.md
```
## Design Decisions
**SQLite vs Redis:** SQLite for zero-config, file-based persistence. Good for single-machine use.
**Multiprocessing:** True parallelism (no GIL), fault isolation, easier shutdown vs threads.
**Exponential Backoff:** Simple ```delay = base^attempts``` balances quick retries with backing off.
**Job Locking:** 5-minute lock expiration handles crashed workers automatically.
 
## Troubleshooting
| Problem | Solution |
|---------|----------|
| "queuectl not found" | Activate venv: ```.\venv\Scripts\Activate.ps1``` (Win) or ```source venv/bin/activate``` (Unix) |
| Workers not processing | Check: ```queuectl status``` and verify workers running |
| JSON parsing error | Windows: Use single quotes around JSON |
| Unicode errors | Fixed! Uses [OK] instead of special chars |
## Future Enhancements
- Job priority queues
- Scheduled/delayed jobs  
- Job output logging
- Web dashboard
- PostgreSQL support

