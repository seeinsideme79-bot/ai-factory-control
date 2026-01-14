#!/bin/bash
# AI Factory - Project Deployment Script
# Deploys a project for testing in human validation phase

set -e

PROJECT_NAME=$1
PORT=$2
STARTUP_WAIT=${3:-2}  # Default 2 seconds if not provided

if [ -z "$PROJECT_NAME" ] || [ -z "$PORT" ]; then
    echo "Usage: $0 <project_name> <port> [startup_wait_seconds]"
    exit 1
fi

PROJECT_DIR="$HOME/projects/$PROJECT_NAME"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Project directory not found: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

echo "Deploying $PROJECT_NAME on port $PORT..."

# Detect project type and deploy accordingly
if [ -f "requirements.txt" ]; then
    # Python/Flask project
    echo "Detected Python project (Flask)"
    
    # Install dependencies (if not already)
    pip3 install -r requirements.txt --break-system-packages --quiet 2>/dev/null || true
    
    # Find main app file
    if [ -f "src/app.py" ]; then
        MAIN_FILE="src/app.py"
    elif [ -f "app.py" ]; then
        MAIN_FILE="app.py"
    else
        echo "Error: No app.py found"
        exit 1
    fi
    
    # Start Flask app
    export FLASK_APP=$MAIN_FILE
    export FLASK_ENV=production
    nohup python3 -m flask run --host=127.0.0.1 --port=$PORT > /tmp/$PROJECT_NAME.log 2>&1 &
    PID=$!
    
elif [ -f "package.json" ]; then
    # Node.js project
    echo "Detected Node.js project"
    
    npm install --silent 2>/dev/null || true
    nohup npm start -- --port $PORT > /tmp/$PROJECT_NAME.log 2>&1 &
    PID=$!
    
elif [ -f "index.html" ]; then
    # Static HTML
    echo "Detected static HTML project"
    
    # Simple Python HTTP server
    cd "$PROJECT_DIR"
    nohup python3 -m http.server $PORT > /tmp/$PROJECT_NAME.log 2>&1 &
    PID=$!
    
elif [ -f "src/main.py" ] || [ -f "src/counter.py" ] || [ -d "src" ] && [ -n "$(find src -maxdepth 1 -name '*.py' -type f)" ]; then
    # CLI Tool - use generic wrapper
    echo "Detected CLI tool project"
    
    CLI_WRAPPER="$HOME/projects/ai-factory-control/web/cli_wrapper.py"
    if [ ! -f "$CLI_WRAPPER" ]; then
        echo "Error: CLI wrapper not found: $CLI_WRAPPER"
        exit 1
    fi
    
    nohup python3 $CLI_WRAPPER "$PROJECT_DIR" $PORT > /tmp/$PROJECT_NAME.log 2>&1 &
    PID=$!
    
else
    echo "Error: Unknown project type"
    exit 1
fi

# Save PID
echo $PID > /tmp/$PROJECT_NAME.pid

# Wait for startup (configurable)
sleep $STARTUP_WAIT

# Check if process is running
if ps -p $PID > /dev/null; then
    echo "SUCCESS: Deployed on port $PORT (PID: $PID)"
    exit 0
else
    echo "ERROR: Deployment failed"
    cat /tmp/$PROJECT_NAME.log
    exit 1
fi
