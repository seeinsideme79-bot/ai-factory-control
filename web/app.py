#!/usr/bin/env python3
"""
AI Factory Manager - Web UI
Flask application for managing AI Factory projects
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import yaml
import os
import subprocess
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Paths
PROJECTS_DIR = os.path.expanduser('~/projects')
CONTROL_DIR = os.path.join(PROJECTS_DIR, 'ai-factory-control')
REGISTRY_FILE = os.path.join(CONTROL_DIR, 'registry', 'projects.yaml')
ORCHESTRATOR_SCRIPT = os.path.join(CONTROL_DIR, 'orchestrator', 'orchestrator.py')

# Simple auth - tek kullanıcı
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'aifactory2026')


def login_required(f):
    """Login kontrolü için decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def load_registry():
    """Registry dosyasını yükle"""
    try:
        with open(REGISTRY_FILE, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('projects', []) if data else []
    except Exception as e:
        print(f"Error loading registry: {e}")
        return []


def load_project_state(project_id):
    """Proje state dosyasını yükle"""
    try:
        state_file = os.path.join(PROJECTS_DIR, project_id, 'state', 'state.yaml')
        with open(state_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading state for {project_id}: {e}")
        return None


def get_system_resources():
    """Sistem kaynak kullanımını al"""
    try:
        # RAM kullanımı
        mem_info = subprocess.check_output(['free', '-m'], text=True)
        lines = mem_info.split('\n')
        mem_line = lines[1].split()
        total_ram = int(mem_line[1])
        used_ram = int(mem_line[2])
        
        # Proje deployment durumları (TODO: gerçek deployment sistemi)
        service_count = 0
        ondemand_count = 0
        
        return {
            'ram_total': total_ram,
            'ram_used': used_ram,
            'ram_percent': int((used_ram / total_ram) * 100),
            'service_count': service_count,
            'service_max': 1,
            'ondemand_count': ondemand_count,
            'ondemand_max': 2
        }
    except Exception as e:
        print(f"Error getting system resources: {e}")
        return {
            'ram_total': 1024,
            'ram_used': 0,
            'ram_percent': 0,
            'service_count': 0,
            'service_max': 1,
            'ondemand_count': 0,
            'ondemand_max': 2
        }


@app.route('/')
@login_required
def index():
    """Ana dashboard"""
    projects = load_registry()
    
    # Her proje için state bilgisini yükle
    for project in projects:
        state = load_project_state(project['id'])
        if state:
            project['state'] = state
    
    resources = get_system_resources()
    
    return render_template('dashboard.html', 
                         projects=projects, 
                         resources=resources,
                         now=datetime.now())


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login sayfası"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('Başarıyla giriş yaptınız!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Hatalı şifre!', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout"""
    session.pop('logged_in', None)
    flash('Çıkış yaptınız.', 'info')
    return redirect(url_for('login'))


@app.route('/project/<project_id>')
@login_required
def project_detail(project_id):
    """Proje detay sayfası"""
    state = load_project_state(project_id)
    
    if not state:
        flash(f'Proje bulunamadı: {project_id}', 'error')
        return redirect(url_for('index'))
    
    return render_template('project_detail.html', 
                         project_id=project_id, 
                         state=state)


@app.route('/api/run-agent', methods=['POST'])
@login_required
def run_agent():
    """Agent çalıştır (API endpoint)"""
    try:
        data = request.json
        project_id = data.get('project_id')
        agent = data.get('agent')
        
        if not project_id or not agent:
            return jsonify({'error': 'project_id ve agent gerekli'}), 400
        
        # Orchestrator'ı çalıştır
        cmd = ['python3', ORCHESTRATOR_SCRIPT, project_id, agent]
        result = subprocess.run(cmd, 
                              capture_output=True, 
                              text=True, 
                              timeout=300)  # 5 dakika timeout
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'output': result.stdout
            })
        else:
            return jsonify({
                'success': False,
                'error': result.stderr
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Agent timeout (5dk)'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
