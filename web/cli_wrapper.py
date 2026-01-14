#!/usr/bin/env python3
"""
AI Factory - Generic CLI Tool Wrapper
Provides web interface for testing CLI applications
"""
from flask import Flask, render_template_string, request, jsonify
import subprocess
import os
import sys
import glob

app = Flask(__name__)

# Project directory will be set via command line
PROJECT_DIR = None
PROJECT_NAME = None

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>{{ project_name }} - CLI Tester</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            max-width: 900px; 
            margin: 0 auto; 
            padding: 40px 20px;
            background: #f5f7fa;
        }
        h1 { 
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .command-box { 
            background: #ecf0f1; 
            padding: 25px; 
            border-radius: 8px; 
            margin: 20px 0;
        }
        input { 
            padding: 12px 15px; 
            width: calc(100% - 120px);
            font-size: 16px;
            border: 2px solid #bdc3c7;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
        }
        input:focus {
            outline: none;
            border-color: #3498db;
        }
        button { 
            padding: 12px 25px; 
            background: #3498db; 
            color: white; 
            border: none; 
            cursor: pointer; 
            font-size: 16px;
            border-radius: 6px;
            margin-left: 10px;
            transition: background 0.3s;
        }
        button:hover { background: #2980b9; }
        button:active { transform: scale(0.98); }
        .output { 
            background: #1e1e1e; 
            color: #d4d4d4; 
            padding: 20px; 
            border-radius: 8px; 
            margin: 20px 0; 
            font-family: 'Courier New', monospace;
            white-space: pre-wrap;
            min-height: 100px;
            font-size: 14px;
            line-height: 1.5;
        }
        .examples { 
            background: #e8f4f8; 
            padding: 20px; 
            border-radius: 8px; 
            margin: 20px 0;
            border-left: 4px solid #3498db;
        }
        .examples h3 {
            margin-top: 0;
            color: #2c3e50;
        }
        .examples code { 
            background: white; 
            padding: 4px 8px; 
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            color: #e74c3c;
        }
        .info {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .success { color: #27ae60; }
        .error { color: #e74c3c; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 {{ project_name }} - CLI Tester</h1>
        
        <div class="info">
            <strong>ℹ️ Info:</strong> This is a web interface for testing CLI application.<br>
            <strong>Project:</strong> {{ project_name }}<br>
            <strong>Main Script:</strong> <code>{{ main_script }}</code>
        </div>
        
        <div class="examples">
            <h3>📋 Available Commands</h3>
            <div id="commands-list">Loading commands...</div>
        </div>
        
        <div class="command-box">
            <form id="cmdForm">
                <input type="text" id="cmdInput" name="cmd" placeholder="Enter command and arguments..." autofocus>
                <button type="submit">▶ Run</button>
            </form>
        </div>
        
        <div class="output" id="output">Ready to test. Enter a command above and press Run.</div>
    </div>
    
    <script>
        // Load available commands
        fetch(window.location.pathname + '/api/commands')
            .then(r => r.json())
            .then(data => {
                const cmdList = document.getElementById('commands-list');
                if (data.commands && data.commands.length > 0) {
                    cmdList.innerHTML = data.commands.map(cmd => 
                        `<div style="margin: 8px 0;"><code>${cmd}</code></div>`
                    ).join('');
                } else {
                    cmdList.innerHTML = '<code>No commands detected. Enter any command to test.</code>';
                }
            });
        
        // Command form submission
        document.getElementById('cmdForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const cmd = document.getElementById('cmdInput').value;
            const output = document.getElementById('output');
            output.textContent = '⏳ Running command...';
            
            try {
                const response = await fetch(window.location.pathname + '/api/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({cmd: cmd})
                });
                
                const data = await response.json();
                
                if (data.error) {
                    output.innerHTML = `<span class="error">❌ Error:</span>\\n${data.error}`;
                } else {
                    const statusIcon = data.returncode === 0 ? '✅' : '⚠️';
                    output.innerHTML = `${statusIcon} Exit code: ${data.returncode}\\n\\n${data.output}`;
                }
            } catch (error) {
                output.innerHTML = `<span class="error">❌ Request failed:</span>\\n${error.message}`;
            }
        });
        
        // Enter key focuses input
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.target !== document.getElementById('cmdInput')) {
                document.getElementById('cmdInput').focus();
            }
        });
    </script>
</body>
</html>
'''

def find_main_script(project_dir):
    """Find main Python script in project"""
    # Common patterns for main scripts
    patterns = [
        'src/main.py',
        'src/app.py', 
        'src/*.py',
        'main.py',
        '*.py'
    ]
    
    for pattern in patterns:
        matches = glob.glob(os.path.join(project_dir, pattern))
        if matches:
            # Return first match relative to project dir
            return os.path.relpath(matches[0], project_dir)
    
    return None

def detect_commands(project_dir, main_script):
    """Try to detect available commands from script"""
    try:
        script_path = os.path.join(project_dir, main_script)
        
        # Try running with --help
        result = subprocess.run(
            ['python3', script_path, '--help'],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=project_dir
        )
        
        # Parse help output for commands
        commands = []
        if result.returncode == 0 and result.stdout:
            # Simple heuristic: lines that look like commands
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line and not line.startswith('-') and len(line.split()) <= 3:
                    commands.append(line)
        
        return commands[:10]  # Max 10 commands
        
    except:
        return []

@app.route('/')
def index():
    """Render CLI tester interface"""
    main_script = find_main_script(PROJECT_DIR)
    
    if not main_script:
        return "Error: No Python script found in project", 500
    
    return render_template_string(
        HTML_TEMPLATE,
        project_name=PROJECT_NAME,
        main_script=main_script
    )

@app.route('/api/commands')
def get_commands():
    """Get available commands"""
    main_script = find_main_script(PROJECT_DIR)
    
    if not main_script:
        return jsonify({'commands': []})
    
    commands = detect_commands(PROJECT_DIR, main_script)
    return jsonify({'commands': commands})

@app.route('/api/run', methods=['POST'])
def run_command():
    """Execute CLI command"""
    try:
        data = request.get_json()
        cmd = data.get('cmd', '').strip()
        
        if not cmd:
            return jsonify({'error': 'No command provided'}), 400
        
        # Find main script
        main_script = find_main_script(PROJECT_DIR)
        if not main_script:
            return jsonify({'error': 'No main script found'}), 500
        
        script_path = os.path.join(PROJECT_DIR, main_script)
        
        # Parse command arguments
        args = cmd.split()
        
        # Run script with arguments
        result = subprocess.run(
            ['python3', script_path] + args,
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=10
        )
        
        # Combine stdout and stderr
        output = result.stdout
        if result.stderr:
            output += '\n--- stderr ---\n' + result.stderr
        
        return jsonify({
            'output': output.strip() if output.strip() else '(no output)',
            'returncode': result.returncode
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Command timeout (10s)'}), 500
    except Exception as e:
        return jsonify({'error': f'Execution error: {str(e)}'}), 500

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 cli_wrapper.py <project_dir> <port>")
        sys.exit(1)
    
    PROJECT_DIR = sys.argv[1]
    PORT = int(sys.argv[2])
    PROJECT_NAME = os.path.basename(PROJECT_DIR)
    
    if not os.path.isdir(PROJECT_DIR):
        print(f"Error: Project directory not found: {PROJECT_DIR}")
        sys.exit(1)
    
    print(f"Starting CLI wrapper for {PROJECT_NAME} on port {PORT}")
    print(f"Project directory: {PROJECT_DIR}")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
