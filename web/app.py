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
import glob
import json

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


@app.route('/new-project', methods=['GET', 'POST'])
@login_required
def new_project():
    """Yeni proje oluştur"""
    if request.method == 'GET':
        return render_template('new_project.html')

    # POST - Form submission
    try:
        project_name = request.form.get('project_name', '').strip()
        vision = request.form.get('vision', '').strip()
        llm_profile = request.form.get('llm_profile', '').strip()
        auto_run_prp = request.form.get('auto_run_prp') == 'on'

        # Validation
        if not project_name or not vision:
            flash('Proje adı ve vizyon zorunludur!', 'error')
            return redirect(url_for('new_project'))

        # new-project.sh script'ini çalıştır
        script_path = os.path.join(CONTROL_DIR, 'scripts', 'new-project.sh')
        cmd = [script_path, project_name, vision]

        result = subprocess.run(cmd,
                              capture_output=True,
                              text=True,
                              timeout=60,
                              cwd=os.path.join(CONTROL_DIR, 'scripts'))

        if result.returncode != 0:
            flash(f'Proje oluşturma hatası: {result.stderr}', 'error')
            return redirect(url_for('new_project'))

        flash(f'Proje başarıyla oluşturuldu: product-{project_name}', 'success')

        # Auto run PRP agent
        if auto_run_prp:
            try:
                project_id = f'product-{project_name}'
                orchestrator_cmd = ['python3', ORCHESTRATOR_SCRIPT, project_id, 'prp']
                subprocess.Popen(orchestrator_cmd,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
                flash('PRP Agent arka planda çalıştırılıyor...', 'info')
            except Exception as e:
                flash(f'PRP Agent başlatma hatası: {str(e)}', 'error')

        return redirect(url_for('index'))

    except subprocess.TimeoutExpired:
        flash('Proje oluşturma zaman aşımına uğradı!', 'error')
        return redirect(url_for('new_project'))
    except Exception as e:
        flash(f'Hata: {str(e)}', 'error')
        return redirect(url_for('new_project'))


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


@app.route('/project/<project_id>/validation-history')
@login_required
def validation_history(project_id):
    """Validation history sayfası"""
    state = load_project_state(project_id)

    if not state:
        flash(f'Proje bulunamadı: {project_id}', 'error')
        return redirect(url_for('index'))

    return render_template('validation_history.html',
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


@app.route('/project/<project_id>/validation')
@login_required
def human_validation(project_id):
    """Human validation sayfası"""
    state = load_project_state(project_id)

    if not state:
        flash(f'Proje bulunamadı: {project_id}', 'error')
        return redirect(url_for('index'))

    if state['phase'] != 'human_validation':
        flash('Proje human_validation fazında değil!', 'error')
        return redirect(url_for('project_detail', project_id=project_id))

    # Load test results
    test_results = []
    test_summary = {'total': 0, 'passed': 0, 'failed': 0, 'pass_rate': 0.0}
    try:
        results_file = os.path.join(PROJECTS_DIR, project_id, 'reports', 'test_results.md')
        with open(results_file, 'r') as f:
            content = f.read()
            # Parse results (simple parsing)
            if '✅ PASS' in content:
                test_results.append({
                    'name': 'Syntax Check',
                    'file': 'src/counter.py',
                    'passed': True,
                    'status': 'PASS'
                })
            # Parse summary
            for line in content.split('\n'):
                if 'Total:' in line:
                    test_summary['total'] = int(line.split(':')[1].strip())
                elif 'Passed:' in line:
                    test_summary['passed'] = int(line.split(':')[1].strip())
                elif 'Failed:' in line:
                    test_summary['failed'] = int(line.split(':')[1].strip())
                elif 'Pass Rate:' in line:
                    test_summary['pass_rate'] = float(line.split(':')[1].strip().replace('%', ''))
    except Exception as e:
        print(f"Error loading test results: {e}")

    # Load test specs
    test_specs = []
    try:
        specs_file = os.path.join(PROJECTS_DIR, project_id, 'tests', 'test_specs.md')
        with open(specs_file, 'r') as f:
            content = f.read()
            # Simple parsing
            current_spec = {}
            for line in content.split('\n'):
                if line.startswith('### Test '):
                    if current_spec:
                        test_specs.append(current_spec)
                    current_spec = {'title': line.replace('### ', '').strip()}
                elif line.startswith('- Input:'):
                    current_spec['input'] = line.replace('- Input:', '').strip()
                elif line.startswith('- Expected:'):
                    current_spec['expected'] = line.replace('- Expected:', '').strip()
                elif line.startswith('- Command:'):
                    current_spec['command'] = line.replace('- Command:', '').strip().strip('`')
            if current_spec:
                test_specs.append(current_spec)
    except Exception as e:
        print(f"Error loading test specs: {e}")

    return render_template('human_validation.html',
                         project={'meta': state['meta']},
                         project_id=project_id,
                         state=state,
                         test_results=test_results,
                         manual_tests=test_specs)


@app.route('/api/validation-history/<project_id>')
@login_required
def get_validation_history(project_id):
    """Validation history listesi (API endpoint)"""
    try:
        history_dir = os.path.join(PROJECTS_DIR, project_id, 'reports', 'validation_history')
        
        # Klasör yoksa boş liste döndür
        if not os.path.exists(history_dir):
            return jsonify({'history': []})
        
        # Tüm validation dosyalarını bul
        history_files = sorted(glob.glob(os.path.join(history_dir, 'validation_*.md')), reverse=True)
        
        history = []
        for filepath in history_files:
            filename = os.path.basename(filepath)
            
            # Dosyayı oku
            with open(filepath, 'r') as f:
                content = f.read()
            
            # Parse date and decision
            date = None
            decision = None
            
            for line in content.split('\n'):
                if line.startswith('**Date:**'):
                    date = line.replace('**Date:**', '').strip()
                elif line.startswith('**Decision:**'):
                    decision = line.replace('**Decision:**', '').strip().upper()
            
            history.append({
                'filename': filename,
                'date': date or 'Unknown',
                'decision': decision or 'UNKNOWN',
                'content': content
            })
        
        return jsonify({'history': history})
    
    except Exception as e:
        print(f"Error loading validation history: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/custom-scenarios/<project_id>', methods=['GET', 'POST', 'DELETE'])
@login_required
def custom_scenarios(project_id):
    """Custom scenarios API endpoint"""
    scenarios_file = os.path.join(PROJECTS_DIR, project_id, 'tests', 'custom_scenarios.json')
    
    if request.method == 'GET':
        # Load existing scenarios
        try:
            if os.path.exists(scenarios_file):
                with open(scenarios_file, 'r') as f:
                    scenarios = json.load(f)
                return jsonify({'scenarios': scenarios})
            else:
                return jsonify({'scenarios': []})
        except Exception as e:
            print(f"Error loading custom scenarios: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        # Add new scenario
        try:
            data = request.json
            title = data.get('title', '').strip()
            input_val = data.get('input', '').strip()
            expected = data.get('expected', '').strip()
            description = data.get('description', '').strip()
            
            if not title:
                return jsonify({'error': 'Title is required'}), 400
            
            # Load existing scenarios
            scenarios = []
            if os.path.exists(scenarios_file):
                with open(scenarios_file, 'r') as f:
                    scenarios = json.load(f)
            
            # Generate new ID
            new_id = max([s.get('id', 0) for s in scenarios], default=0) + 1
            
            # Add new scenario
            new_scenario = {
                'id': new_id,
                'title': title,
                'input': input_val,
                'expected': expected,
                'description': description,
                'created_at': datetime.now().isoformat()
            }
            scenarios.append(new_scenario)
            
            # Save to file
            os.makedirs(os.path.dirname(scenarios_file), exist_ok=True)
            with open(scenarios_file, 'w') as f:
                json.dump(scenarios, f, indent=2)
            
            return jsonify({'success': True, 'scenario': new_scenario})
        
        except Exception as e:
            print(f"Error saving custom scenario: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'DELETE':
        # Delete scenario
        try:
            data = request.json
            scenario_id = data.get('id')
            
            if not scenario_id:
                return jsonify({'error': 'ID is required'}), 400
            
            # Load existing scenarios
            if not os.path.exists(scenarios_file):
                return jsonify({'error': 'No scenarios found'}), 404
            
            with open(scenarios_file, 'r') as f:
                scenarios = json.load(f)
            
            # Remove scenario
            scenarios = [s for s in scenarios if s.get('id') != scenario_id]
            
            # Save to file
            with open(scenarios_file, 'w') as f:
                json.dump(scenarios, f, indent=2)
            
            return jsonify({'success': True})
        
        except Exception as e:
            print(f"Error deleting custom scenario: {e}")
            return jsonify({'error': str(e)}), 500


@app.route('/api/analyze-rejection/<project_id>', methods=['POST'])
@login_required
def analyze_rejection(project_id):
    """LLM ile rejection feedback analizi"""
    print(f"=== FUNCTION CALLED: project_id={project_id} ===", flush=True)
    
    try:
        print("=== INSIDE TRY BLOCK ===", flush=True)
        import requests
        import re
        print("=== IMPORTS OK ===", flush=True)
        
        data = request.json
        print(f"=== DATA: {data} ===", flush=True)

        feedback = data.get('feedback', '')
        test_results = data.get('test_results', {})
        
        # Failed testleri topla
        failed_tests = []
        for test_id, test_data in test_results.items():
            if test_data.get('result') == 'fail':
                failed_tests.append({
                    'title': test_data.get('title', ''),
                    'input': test_data.get('input', ''),
                    'expected': test_data.get('expected', '')
                })
        
        if not failed_tests:
            return jsonify({
                'success': True,
                'analysis': {
                    'recommendation': 'code',
                    'reasoning': 'No failed tests detected',
                    'test_analysis': []
                }
            })
        
        # LLM prompt
        failed_summary = chr(10).join([f"- {t['title']}" for t in failed_tests])
        llm_prompt = f"""Analyze validation feedback and failed tests to determine if issues are:
- PRP (requirements): Missing features, wrong specs, requirement gaps
- CODE (implementation): Bugs, incorrect implementation of existing requirements

CRITICAL: If ANY test requires PRP change, recommend "prp". Only "code" if ALL are implementation bugs.

Feedback: {feedback if feedback else "No feedback provided"}
Failed Tests:
{failed_summary}

Return ONLY valid JSON:
{{"recommendation": "prp" or "code", "reasoning": "Brief explanation", "test_analysis": [{{"test": "Test name", "category": "prp|code|both", "reason": "Why"}}]}}"""

        # LLM API call
        api_key = os.environ.get('OPENROUTER_API_KEY')
        print(f"=== API KEY EXISTS: {bool(api_key)} ===", flush=True)
        
        if not api_key:
            return jsonify({'error': 'OpenRouter API key not configured'}), 500
        
        print("=== CALLING LLM API ===", flush=True)
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'google/gemma-3-27b-it:free',
                'messages': [{'role': 'user', 'content': llm_prompt}],
                'max_tokens': 2000,
                'temperature': 0.3
            },
            timeout=30
        )
        
        print(f"=== API RESPONSE STATUS: {response.status_code} ===", flush=True)
        print(f"=== API RESPONSE: {response.text[:200]} ===", flush=True)

        if response.status_code != 200:
            return jsonify({'error': f'LLM API error: {response.status_code}'}), 500
        
        content = response.json()['choices'][0]['message']['content']
        print(f"=== LLM CONTENT: {content} ===", flush=True)
        content = re.sub(r'```json\s*|\s*```', '', content).strip()
        print(f"=== CLEANED CONTENT: {content} ===", flush=True)

        analysis = json.loads(content)
        
        return jsonify({'success': True, 'analysis': analysis})
    
    except Exception as e:
        print(f"=== ERROR: {e} ===")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/human-validation', methods=['POST'])
@login_required
def submit_human_validation():
    """Human validation submit (API endpoint)"""
    try:
        data = request.json
        project_id = data.get('project_id')
        decision = data.get('decision')  # 'approve' or 'reject'
        target_phase = data.get('target_phase')  # 'prp' or 'development'
        ai_analysis = data.get('ai_analysis', {})
        test_results = data.get('test_results', {})
        feedback = data.get('feedback', '')

        if not project_id or not decision:
            return jsonify({'error': 'project_id ve decision gerekli'}), 400

        # Create validation history directory
        history_dir = os.path.join(PROJECTS_DIR, project_id, 'reports', 'validation_history')
        os.makedirs(history_dir, exist_ok=True)

        # Generate history filename
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        history_file = os.path.join(history_dir, f'validation_{timestamp}.md')

        # Create validation report
        with open(history_file, 'w') as f:
            f.write("# Human Validation Report\n\n")
            f.write(f"**Date:** {datetime.now().isoformat()}\n")
            f.write(f"**Decision:** {decision.upper()}\n\n")
            
            f.write("## Manual Test Results\n\n")
            
            passed = 0
            failed = 0
            skipped = 0
            
            for test_id, test_data in test_results.items():
                title = test_data.get('title', 'Unknown Test')
                result = test_data.get('result', 'skip')
                desc = test_data.get('description', '')
                
                if result == 'pass':
                    f.write(f"### ✅ {title}\n")
                    passed += 1
                elif result == 'fail':
                    f.write(f"### ❌ {title}\n")
                    failed += 1
                else:
                    f.write(f"### ⏭️ {title}\n")
                    skipped += 1
                
                f.write(f"- Result: **{result.upper()}**\n")
                if desc:
                    f.write(f"- Description: {desc}\n")
                f.write("\n")
            
            f.write(f"**Summary:** {passed} passed, {failed} failed, {skipped} skipped\n\n")
            
            # AI Analysis section
            if ai_analysis:
                f.write("## AI Analysis\n\n")
                f.write(f"**Recommendation:** {ai_analysis.get('recommendation', 'N/A').upper()}\n")
                f.write(f"**Reasoning:** {ai_analysis.get('reasoning', 'N/A')}\n\n")
                
                test_analysis_list = ai_analysis.get('test_analysis', [])
                if test_analysis_list:
                    f.write("### Test Breakdown\n\n")
                    for test in test_analysis_list:
                        category = test.get('category', 'unknown').upper()
                        f.write(f"- **{test.get('test', 'Unknown')}:** {category}\n")
                        f.write(f"  - {test.get('reason', 'N/A')}\n")
                    f.write("\n")
                
                if target_phase:
                    f.write(f"**Final Decision:** Next phase = {target_phase}\n\n")
            
            if feedback:
                f.write("## Feedback\n\n")
                f.write(feedback + "\n\n")

        # Update state based on decision
        script_path = os.path.join(CONTROL_DIR, 'scripts', 'update-state.sh')

        if decision == 'approve':
            new_phase = 'release'
        else:  # reject
            new_phase = target_phase if target_phase else 'development'

        cmd = [script_path, project_id, 'phase', new_phase]
        result = subprocess.run(cmd,
                              capture_output=True,
                              text=True,
                              timeout=30,
                              cwd=os.path.join(CONTROL_DIR, 'scripts'))

        if result.returncode != 0:
            return jsonify({
                'success': False,
                'error': f'State update failed: {result.stderr}'
            }), 500

        # Save feedback to main feedback file
        if feedback:
            feedback_file = os.path.join(PROJECTS_DIR, project_id, 'reports', 'human_feedback.md')
            with open(feedback_file, 'a') as f:
                f.write(f"\n---\n\n# Feedback - {timestamp}\n\n")
                f.write(f"**Decision:** {decision}\n\n")
                f.write(feedback + "\n")

        return jsonify({'success': True})

    except Exception as e:
        print(f"Error submitting validation: {e}")
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
