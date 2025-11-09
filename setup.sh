#!/bin/bash
# QueueCTL Setup Script for Unix/Linux/macOS

set -e

echo "============================================"
echo "QueueCTL Setup Script"
echo "============================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo "[1/5] Python found"
python3 --version

echo
echo "[2/5] Creating virtual environment..."
python3 -m venv venv

echo
echo "[3/5] Activating virtual environment..."
source venv/bin/activate

echo
echo "[4/5] Installing dependencies..."
pip install -r requirements.txt

echo
echo "[5/5] Installing QueueCTL..."
pip install -e .

echo
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo
echo "To get started:"
echo "  1. Activate the virtual environment:"
echo "     source venv/bin/activate"
echo
echo "  2. Run the demo:"
echo "     python demo.py"
echo
echo "  3. Or start using QueueCTL:"
echo "     queuectl --help"
echo
echo "See QUICKSTART.md for more information."
echo
