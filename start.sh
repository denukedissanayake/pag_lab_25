#!/bin/bash
# Anomaly Detection Service Startup Script

echo "🚀 Starting Anomaly Detection Service..."
echo "📁 Working directory: $(pwd)"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "🐍 Activating virtual environment..."
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "⚠️  Virtual environment not found. Creating with 'python3 -m venv .venv'"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
fi

# Start the application
echo "🌟 Starting FastAPI application..."
python main.py
