#!/usr/bin/env python3
"""
AI Factory Manager - Web UI
Flask application for managing AI Factory projects
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
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

# API Secret for GitHub sync
API_SECRET = "ai-factory-secret-2026-xK9mP2nQ"


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

def save_project_state(project_id, state):
    """Save project state"""
    state_file = os.path.join(PROJECTS_DIR, project_id, 'state', 'state.yaml')
    try:
        with open(state_file, 'w') as f:
            yaml.dump(state, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        print(f"Error saving state for {project_id}: {e}", flush=True)
        return False

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


def load_rejection_analyzer_prompt():
    """Rejection analyzer prompt'unu dosyadan yükle"""
    prompt_file = os.path.join(CONTROL_DIR, 'agents', 'templates', 'rejection_analyzer.md')
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error loading rejection analyzer prompt: {e}")
        # Fallback prompt
        return """Analyze validation feedback and determine if issues are PRP or CODE.
Return JSON: {"recommendation": "prp|code", "reasoning": "...", "test_analysis": [...]}"""


def load_llm_profile(profile_name='gemma-free'):
    """LLM profile'ı yükle"""
    profiles_file = os.path.join(CONTROL_DIR, 'config', 'llm.profiles.yaml')
    try:
        with open(profiles_file, 'r') as f:
            profiles_data = yaml.safe_load(f)
            profile = profiles_data['profiles'].get(profile_name)
            if not profile:
                profile_name = profiles_data.get('default_profile', 'gemma-free')
                profile = profiles_data['profiles'].get(profile_name)
            return profile
    except Exception as e:
        print(f"Error loading LLM profile: {e}")
        # Fallback
        return {
            'provider': 'openrouter',
            'model': 'google/gemma-3-27b-it:free',
            'max_tokens': 2000,
            'temperature': 0.3
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

@app.route('/api/get-profiles', methods=['GET'])
@login_required
def get_profiles():
    """LLM profiles listesi (API endpoint)"""
    try:
        profiles_file = os.path.join(CONTROL_DIR, 'config', 'llm.profiles.yaml')
        
        with open(profiles_file, 'r') as f:
            profiles_data = yaml.safe_load(f)
        
        profiles = profiles_data.get('profiles', {})
        default_profile = profiles_data.get('default_profile', 'gemma-free')
        
        # Simplified profile list for UI
        profile_list = []
        for name, config in profiles.items():
            profile_list.append({
                'name': name,
                'model': config.get('model', 'Unknown'),
                'description': config.get('description', ''),
                'is_default': (name == default_profile)
            })
        
        return jsonify({
            'success': True,
            'profiles': profile_list,
            'default_profile': default_profile
        })
    
    except Exception as e:
        print(f"Error loading profiles: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/run-agent', methods=['POST'])
@login_required

def run_agent():
    """Agent çalıştır (API endpoint)"""
    try:
        data = request.json
        project_id = data.get('project_id')
        agent = data.get('agent')
        model_override = data.get('model_override')

        if not project_id or not agent:
            return jsonify({'error': 'project_id ve agent gerekli'}), 400

        # Orchestrator'ı çalıştır
        cmd = ['python3', ORCHESTRATOR_SCRIPT, project_id, agent]
        if model_override:
            cmd.extend(['--model', model_override])
        
        result = subprocess.run(cmd,
                              capture_output=True,
                              text=True,
                              timeout=300)

        if result.returncode == 0:
            # Başarılı - stdout'u döndür
            return jsonify({
                'success': True,
                'output': result.stdout
            })
        else:
            # Hata - stderr'ı parse et ve anlamlı mesaj döndür
            error_msg = parse_orchestrator_error(result.stderr, result.stdout)
            return jsonify({
                'success': False,
                'error': error_msg,
                'raw_stderr': result.stderr[:500]  # Debug için ilk 500 char
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Agent timeout (5 dakika)'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def parse_orchestrator_error(stderr, stdout):
    """Orchestrator hata mesajını parse et ve kullanıcı dostu hale getir"""
    import re
    
    # Emoji'leri temizle
    clean_text = re.sub(r'[🔧📋🤖🔧🌐📊📝⚡🔍🚀✅❌📛]', '', stderr + stdout)
    
    # Yaygın hata pattern'leri
    if 'API error 402' in clean_text:
        return '💳 Kredi yetersiz: OpenRouter hesabınızda yeterli kredi yok. https://openrouter.ai/settings/credits adresinden kredi ekleyin.'
    
    if 'API error 400' in clean_text and 'not a valid model ID' in clean_text:
        # Model ID'yi çıkar
        model_match = re.search(r'([\w\/-]+)\s+is not a valid model ID', clean_text)
        if model_match:
            invalid_model = model_match.group(1)
            return f'❌ Geçersiz model: "{invalid_model}" OpenRouter\'da bulunamadı. Lütfen farklı bir model seçin.'
        return '❌ Geçersiz model ID. Lütfen farklı bir model seçin.'
    
    if 'API error 401' in clean_text:
        return '🔑 API key hatası: OpenRouter API key\'iniz geçersiz veya eksik.'
    
    if 'API error 429' in clean_text:
        return '⏳ Rate limit: Çok fazla istek gönderildi. Lütfen birkaç dakika bekleyin.'
    
    if 'API error' in clean_text:
        # Genel API hatası - mesajı çıkar
        error_match = re.search(r'API error \d+: (.+?)(?:\n|$)', clean_text)
        if error_match:
            return f'🌐 API Hatası: {error_match.group(1)[:200]}'
    
    if 'LLM call failed' in clean_text:
        return '❌ LLM çağrısı başarısız oldu. Lütfen model seçiminizi kontrol edin veya tekrar deneyin.'
    
    if 'agent_error' in clean_text:
        return '⚠️ Agent hatası: Agent çalışırken bir hata oluştu. Logları kontrol edin.'
    
    # Hiçbir pattern eşleşmezse, temizlenmiş mesajın ilk 300 karakterini döndür
    return clean_text.strip()[:300] or 'Bilinmeyen hata oluştu'


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
    try:
        import requests
        import re
        
        data = request.json
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
        
        # Load prompt template from file
        prompt_template = load_rejection_analyzer_prompt()
        
        # Prepare data for prompt
        failed_summary = chr(10).join([f"- {t['title']}" for t in failed_tests])
        
        # Replace placeholders in template (simple replacement)
        llm_prompt = prompt_template
        # Extract just the task portion for the LLM (skip the markdown header)
        if '## Task' in llm_prompt:
            llm_prompt = llm_prompt.split('## Task', 1)[1]
        
        # Build actual prompt
        llm_prompt = f"""Analyze validation feedback and failed tests to determine if issues are PRP or CODE.

Feedback: {feedback if feedback else 'No feedback provided'}

Failed Tests:
{failed_summary}

Return ONLY valid JSON:
{{"recommendation": "prp|code", "reasoning": "Brief explanation", "test_analysis": [{{"test": "Test name", "category": "prp|code", "reason": "Why"}}]}}"""
        
        # Load LLM config from profile - use rejection_analyzer from state
        try:
            state = load_project_state(project_id)
            profile_name = state.get('agent_models', {}).get('rejection_analyzer', 'gemma-free')
            llm_config = load_llm_profile(profile_name)
        except Exception as e:
           print(f"Warning: Could not load state for rejection analyzer, using default: {e}")
           llm_config = load_llm_profile('gemma-free')
        
        # LLM API call
        api_key = os.environ.get('OPENROUTER_API_KEY')
        
        if not api_key:
            return jsonify({'error': 'OpenRouter API key not configured'}), 500
        
        # Get provider settings
        provider = llm_config.get('provider', 'openrouter')
        if provider == 'openrouter':
            api_url = 'https://openrouter.ai/api/v1/chat/completions'
        else:
            return jsonify({'error': f'Unsupported provider: {provider}'}), 500
        
        response = requests.post(
            api_url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': llm_config.get('model', 'google/gemma-3-27b-it:free'),
                'messages': [{'role': 'user', 'content': llm_prompt}],
                'max_tokens': llm_config.get('max_tokens', 2000),
                'temperature': llm_config.get('temperature', 0.3)
            },
            timeout=30
        )

        # DEBUG - Response kontrolü
        print(f"DEBUG - Response status: {response.status_code}")
        print(f"DEBUG - Response text (first 200 chars): {response.text[:200]}")

        if response.status_code != 200:
            print(f"ERROR - API returned {response.status_code}: {response.text[:500]}")
            return jsonify({'error': f'LLM API error: {response.status_code}'}), 500

        # Parse response
        response_json = response.json()
        print(f"DEBUG - Full response keys: {response_json.keys()}")

        # OpenRouter format: choices[0].message.content
        if 'choices' in response_json:
            content = response_json['choices'][0]['message']['content']
        else:
            print(f"ERROR - Unexpected response format: {response_json}")
            return jsonify({'error': 'Unexpected API response format'}), 500

        print(f"DEBUG - LLM content (first 200 chars): {content[:200]}")

        content = re.sub(r'^```json\s*|\s*```$', '', content, flags=re.MULTILINE).strip()

        # Clean markdown code fences
        import re
        content = re.sub(r'^```json\s*|\s*```$', '', content, flags=re.MULTILINE).strip()

        analysis = json.loads(content)
        
        return jsonify({'success': True, 'analysis': analysis})
    
    except Exception as e:
        print(f"Error in rejection analysis: {e}")
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


# ===== GitHub Sync API =====

def require_api_key(f):
    """API key authentication decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != API_SECRET:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/api/save-agent-models/<project_id>', methods=['POST'])
@login_required
def save_agent_models(project_id):
    """Save agent model selections to state"""
    try:
        data = request.json
        agent_models = data.get('agent_models', {})
        
        # Validate project exists
        projects = load_registry()
        project = next((p for p in projects if p['id'] == project_id), None)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        # Load current state
        project_path = os.path.join(PROJECTS_DIR, project_id)
        state_file = os.path.join(project_path, 'state', 'state.yaml')
        
        with open(state_file, 'r') as f:
            state = yaml.safe_load(f)
        
        # Update agent_models
        if 'agent_models' not in state:
            state['agent_models'] = {}
        
        state['agent_models'].update(agent_models)
        
        # Save state
        with open(state_file, 'w') as f:
            yaml.dump(state, f, default_flow_style=False, sort_keys=False)
        
        return jsonify({
            'success': True,
            'message': 'Agent models saved successfully',
            'agent_models': state['agent_models']
        })
        
    except Exception as e:
        print(f"Error saving agent models: {e}", flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/github-sync', methods=['POST'])
@require_api_key
def github_sync():
    """
    GitHub dosya senkronizasyonu
    Actions: read, write, commit
    """
    try:
        data = request.json
        action = data.get('action')
        
        if action == 'read':
            # Dosya oku
            file_path = data.get('file_path')
            if not file_path:
                return jsonify({'error': 'file_path required'}), 400
            
            # Path validation - sadece proje klasörü içinde
            if '..' in file_path or file_path.startswith('/'):
                return jsonify({'error': 'Invalid file path'}), 400
            
            full_path = os.path.join(CONTROL_DIR, file_path)
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                return jsonify({
                    'success': True,
                    'file_path': file_path,
                    'content': content,
                    'size': len(content)
                })
            except FileNotFoundError:
                return jsonify({'error': f'File not found: {file_path}'}), 404
            except Exception as e:
                return jsonify({'error': f'Read error: {str(e)}'}), 500
        
        elif action == 'write':
            # Dosya yaz
            file_path = data.get('file_path')
            content = data.get('content')
            
            if not file_path or content is None:
                return jsonify({'error': 'file_path and content required'}), 400
            
            # Path validation
            if '..' in file_path or file_path.startswith('/'):
                return jsonify({'error': 'Invalid file path'}), 400
            
            full_path = os.path.join(CONTROL_DIR, file_path)
            
            # Dizin yoksa oluştur
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            try:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                return jsonify({
                    'success': True,
                    'message': f'File {file_path} updated',
                    'size': len(content)
                })
            except Exception as e:
                return jsonify({'error': f'Write error: {str(e)}'}), 500
        
        elif action == 'commit':
            # Git commit + push
            message = data.get('message', 'Auto-commit from Claude')
            
            try:
                # Git add
                result = subprocess.run(
                    ['git', 'add', '-A'], 
                    cwd=CONTROL_DIR, 
                    capture_output=True, 
                    text=True,
                    check=True
                )
                
                # Git commit
                result = subprocess.run(
                    ['git', 'commit', '-m', message], 
                    cwd=CONTROL_DIR, 
                    capture_output=True, 
                    text=True,
                    check=True
                )
                
                # Git push
                result = subprocess.run(
                    ['git', 'push'], 
                    cwd=CONTROL_DIR, 
                    capture_output=True, 
                    text=True,
                    check=True
                )
                
                return jsonify({
                    'success': True,
                    'message': 'Committed and pushed to GitHub',
                    'commit_message': message
                })
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if e.stderr else str(e)
                return jsonify({
                    'success': False,
                    'error': f'Git error: {error_msg}'
                }), 500
        
        else:
            return jsonify({'error': f'Unknown action: {action}'}), 400
    
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

# AI Factory - Deployment Settings API
# Add these to app.py

import yaml
import os
from datetime import datetime

DEPLOYMENT_CONFIG_PATH = os.path.expanduser("~/projects/ai-factory-control/config/deployment.yaml")

def load_deployment_config():
    """Load deployment configuration"""
    try:
        with open(DEPLOYMENT_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('deployment', {})
    except FileNotFoundError:
        # Return defaults if file doesn't exist
        return {
            'port_range': {'start': 5001, 'end': 5010},
            'max_concurrent_deployments': 10,
            'auto_stop': {'enabled': True, 'idle_timeout_minutes': 30},
            'startup': {'wait_seconds': 2, 'health_check_retries': 3},
            'proxy': {'timeout_seconds': 30, 'max_request_size_mb': 10},
            'logs': {'directory': '/tmp', 'keep_days': 7, 'max_size_mb': 50},
            'defaults': {'type': 'web_app', 'auto_detect_type': True}
        }
    except Exception as e:
        print(f"Error loading deployment config: {e}", flush=True)
        return {}

def save_deployment_config(config):
    """Save deployment configuration"""
    try:
        # Read existing file to preserve structure
        full_config = {'deployment': config}
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(DEPLOYMENT_CONFIG_PATH), exist_ok=True)
        
        # Write with comments
        with open(DEPLOYMENT_CONFIG_PATH, 'w') as f:
            f.write("# AI Factory - Deployment Settings\n")
            f.write(f"# Last updated: {datetime.now().isoformat()}\n\n")
            yaml.dump(full_config, f, default_flow_style=False, sort_keys=False)
        
        return True
    except Exception as e:
        print(f"Error saving deployment config: {e}", flush=True)
        return False

# Update settings route to include deployment config
@app.route('/settings')
def settings():
    if not session.get('logged_in'):
       return redirect(url_for('login'))
    
    # Load LLM profiles
    profiles_path = os.path.expanduser("~/projects/ai-factory-control/config/llm.profiles.yaml")
    try:
        with open(profiles_path, 'r') as f:
            profiles_config = yaml.safe_load(f)
    except:
        profiles_config = {'profiles': {}, 'default_profile': 'gemma-free'}
    
    # Load deployment config
    deployment_config = load_deployment_config()
    
    return render_template('settings.html', 
                         profiles=profiles_config.get('profiles', {}),
                         default_profile=profiles_config.get('default_profile', 'gemma-free'),
                         deployment_config=deployment_config)

@app.route('/api/save-deployment-settings', methods=['POST'])
def save_deployment_settings():
    """Save deployment settings"""
    try:
        data = request.get_json()
        
        # Validation
        if data['port_range']['start'] >= data['port_range']['end']:
            return jsonify({'success': False, 'error': 'Invalid port range'}), 400
        
        if data['max_concurrent_deployments'] < 1 or data['max_concurrent_deployments'] > 20:
            return jsonify({'success': False, 'error': 'Max concurrent must be 1-20'}), 400
        
        if data['auto_stop']['idle_timeout_minutes'] < 5 or data['auto_stop']['idle_timeout_minutes'] > 240:
            return jsonify({'success': False, 'error': 'Idle timeout must be 5-240 minutes'}), 400
        
        # Add defaults if not present
        if 'defaults' not in data:
            data['defaults'] = {'type': 'web_app', 'auto_detect_type': True}
        
        # Save
        success = save_deployment_config(data)
        
        if success:
            # Reload port range in memory
            global AVAILABLE_PORTS
            AVAILABLE_PORTS = list(range(data['port_range']['start'], data['port_range']['end'] + 1))
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save config'}), 500
            
    except Exception as e:
        print(f"Save deployment settings error: {e}", flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reset-deployment-settings', methods=['POST'])
def reset_deployment_settings():
    """Reset deployment settings to defaults"""
    try:
        defaults = {
            'port_range': {'start': 5001, 'end': 5010},
            'max_concurrent_deployments': 10,
            'auto_stop': {'enabled': True, 'idle_timeout_minutes': 30},
            'startup': {'wait_seconds': 2, 'health_check_retries': 3},
            'proxy': {'timeout_seconds': 30, 'max_request_size_mb': 10},
            'logs': {'directory': '/tmp', 'keep_days': 7, 'max_size_mb': 50},
            'defaults': {'type': 'web_app', 'auto_detect_type': True}
        }
        
        success = save_deployment_config(defaults)
        
        if success:
            # Reload port range
            global AVAILABLE_PORTS
            AVAILABLE_PORTS = list(range(5001, 5011))
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to reset'}), 500
            
    except Exception as e:
        print(f"Reset deployment settings error: {e}", flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

# Update deployment functions to use config
def get_available_port():
    """Get next available port from config"""
    config = load_deployment_config()
    port_range = config.get('port_range', {'start': 5001, 'end': 5010})
    
    used_ports = set(deployed_projects.values())
    for port in range(port_range['start'], port_range['end'] + 1):
        if port not in used_ports:
            return port
    return None

# Initialize AVAILABLE_PORTS from config on startup
deployment_config = load_deployment_config()
AVAILABLE_PORTS = list(range(
    deployment_config.get('port_range', {}).get('start', 5001),
    deployment_config.get('port_range', {}).get('end', 5010) + 1
))
# AI Factory - Deployment API Endpoints
# Add these to app.py

import subprocess
import os
from datetime import datetime

# Port management (will be loaded from config)
AVAILABLE_PORTS = []  # Initialized on startup from config
deployed_projects = {}  # {project_id: port}

def get_available_port():
    """Get next available port from config"""
    config = load_deployment_config()
    port_range = config.get('port_range', {'start': 5001, 'end': 5010})
    
    used_ports = set(deployed_projects.values())
    for port in range(port_range['start'], port_range['end'] + 1):
        if port not in used_ports:
            return port
    return None

# Initialize AVAILABLE_PORTS from config on startup
try:
    deployment_config = load_deployment_config()
    AVAILABLE_PORTS = list(range(
        deployment_config.get('port_range', {}).get('start', 5001),
        deployment_config.get('port_range', {}).get('end', 5010) + 1
    ))
    print(f"Initialized deployment with port range: {deployment_config.get('port_range')}", flush=True)
except Exception as e:
    print(f"Error initializing deployment config: {e}", flush=True)
    AVAILABLE_PORTS = list(range(5001, 5011))

def load_deployments():
    """Load deployments from all project states"""
    global deployed_projects
    deployed_projects = {}
    projects_dir = os.path.expanduser("~/projects")
    
    for project_dir in os.listdir(projects_dir):
        if not project_dir.startswith("product-"):
            continue
        
        state_file = os.path.join(projects_dir, project_dir, "state", "state.yaml")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    state = yaml.safe_load(f)
                if state.get('deployment', {}).get('status') == 'deployed':
                    port = state['deployment'].get('port')
                    if port:
                        deployed_projects[project_dir] = port
            except:
                pass

# Load deployments on startup
load_deployments()

@app.route('/api/deployment-status/<project_id>', methods=['GET'])
def get_deployment_status(project_id):
    """Get current deployment status"""
    try:
        state = load_project_state(project_id)
        deployment = state.get('deployment', {})
        
        if deployment.get('status') == 'deployed':
            return jsonify({
                'success': True,
                'status': 'deployed',
                'url': deployment.get('url'),
                'port': deployment.get('port'),
                'started_at': deployment.get('started_at')
            })
        else:
            return jsonify({
                'success': True,
                'status': 'not_deployed'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deploy/<project_id>', methods=['POST'])
def deploy_project(project_id):
    """Deploy project for testing"""
    try:
        # Load config
        config = load_deployment_config()
        
        # Check if already deployed
        state = load_project_state(project_id)
        if state.get('deployment', {}).get('status') == 'deployed':
            return jsonify({'success': False, 'error': 'Already deployed'}), 400
        
        # Get available port
        port = get_available_port()
        if not port:
            max_concurrent = config.get('max_concurrent_deployments', 10)
            return jsonify({'success': False, 'error': f'No available ports (max {max_concurrent} deployments)'}), 503
        
        # Run deploy script
        script_path = os.path.expanduser("~/projects/ai-factory-control/scripts/deploy-project.sh")
        startup_wait = config.get('startup', {}).get('wait_seconds', 2)
        
        result = subprocess.run(
            [script_path, project_id, str(port), str(startup_wait)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'error': f'Deployment failed: {result.stderr}'
            }), 500
        
        # Extract PID from output
        pid = None
        for line in result.stdout.split('\n'):
            if 'PID:' in line:
                pid = line.split('PID:')[1].strip().rstrip(')')
        
        # Update state
        deployment = {
            'status': 'deployed',
            'type': 'web_app',  # TODO: Auto-detect
            'port': port,
            'url': f'/preview/{project_id}',
            'pid': pid,
            'started_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat()
        }
        
        state['deployment'] = deployment
        save_project_state(project_id, state)
        
        # Track deployment
        deployed_projects[project_id] = port
        
        return jsonify({
            'success': True,
            'url': f'/preview/{project_id}',
            'port': port,
            'pid': pid
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Deployment timeout (60s)'}), 500
    except Exception as e:
        print(f"Deploy error: {e}", flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stop-deployment/<project_id>', methods=['POST'])
def stop_deployment(project_id):
    """Stop project deployment"""
    try:
        state = load_project_state(project_id)
        deployment = state.get('deployment', {})
        
        if deployment.get('status') != 'deployed':
            return jsonify({'success': False, 'error': 'Not deployed'}), 400
        
        # Kill process
        pid = deployment.get('pid')
        if pid:
            try:
                subprocess.run(['kill', str(pid)], check=False)
            except:
                pass
        
        # Update state
        deployment['status'] = 'stopped'
        deployment['stopped_at'] = datetime.now().isoformat()
        state['deployment'] = deployment
        save_project_state(project_id, state)
        
        # Remove from tracking
        if project_id in deployed_projects:
            del deployed_projects[project_id]
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Stop error: {e}", flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/preview/<project_id>')
@app.route('/preview/<project_id>/<path:subpath>')
def preview_proxy(project_id, subpath=''):
    """Proxy requests to deployed project"""
    try:
        # Load config
        config = load_deployment_config()
        proxy_timeout = config.get('proxy', {}).get('timeout_seconds', 30)
        
        state = load_project_state(project_id)
        deployment = state.get('deployment', {})
        
        if deployment.get('status') != 'deployed':
            return "Project not deployed", 404
        
        port = deployment.get('port')
        if not port:
            return "Port not assigned", 500
        
        # Update last activity
        deployment['last_activity'] = datetime.now().isoformat()
        save_project_state(project_id, state)
        
        # Proxy to local port
        import requests
        target_url = f"http://127.0.0.1:{port}/{subpath}"
        
        # Forward request
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers={k: v for k, v in request.headers if k.lower() != 'host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=proxy_timeout
        )
        
        # Return response
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded_headers]
        
        return Response(resp.content, resp.status_code, headers)
        
    except requests.exceptions.ConnectionError:
        return "Service not running", 503
    except requests.exceptions.Timeout:
        return "Service timeout", 504
    except Exception as e:
        print(f"Proxy error: {e}", flush=True)
        return f"Proxy error: {str(e)}", 500

@app.route('/preview/<project_id>/api/<path:api_path>', methods=['GET', 'POST'])
def preview_api_proxy(project_id, api_path):
    """Proxy API calls from iframe to deployed project"""
    try:
        config = load_deployment_config()
        proxy_timeout = config.get('proxy', {}).get('timeout_seconds', 30)
        
        state = load_project_state(project_id)
        deployment = state.get('deployment', {})
        
        if deployment.get('status') != 'deployed':
            return jsonify({'error': 'Project not deployed'}), 404
        
        port = deployment.get('port')
        if not port:
            return jsonify({'error': 'Port not assigned'}), 500
        
        # Proxy to local port API
        import requests
        target_url = f"http://127.0.0.1:{port}/api/{api_path}"
        
        # Forward request
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers={k: v for k, v in request.headers if k.lower() not in ['host', 'content-length']},
            data=request.get_data(),
            json=request.get_json() if request.is_json else None,
            allow_redirects=False,
            timeout=proxy_timeout
        )
        
        # Return JSON response
        return Response(resp.content, resp.status_code, {'Content-Type': 'application/json'})
        
    except Exception as e:
        print(f"API Proxy error: {e}", flush=True)
        return jsonify({'error': str(e)}), 500


# ============================================
# PRP REVIEW WORKFLOW ROUTES
# ============================================
# Aşağıdaki kodları app.py dosyasına ekleyin
# "if __name__ == '__main__'" satırından ÖNCE

@app.route('/project/<project_id>/prp')
def prp_page(project_id):
    """PRP görüntüleme ve düzenleme sayfası"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # State'i yükle
    state = load_project_state(project_id)
    if not state:
        flash('Project not found', 'error')
        return redirect(url_for('dashboard'))
    
    # PRP dosyasını oku
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    prp_file = os.path.join(project_dir, 'prp', 'prp.md')
    
    prp_content = ""
    prp_version = state.get('version', {}).get('prp', '0.1')
    # Sadece 'prp' phase'de editable
    is_editable = state.get('phase') == 'prp'
    
    if os.path.exists(prp_file):
        with open(prp_file, 'r', encoding='utf-8') as f:
            prp_content = f.read()
    else:
        prp_content = "# Product Requirement Prompt\n\n*PRP not yet created*"
    
    return render_template('prp_editor.html',
                         project_id=project_id,
                         state=state,
                         prp_content=prp_content,
                         prp_version=prp_version,
                         is_editable=is_editable)


@app.route('/api/prp/<project_id>', methods=['GET'])
def get_prp_content(project_id):
    """PRP içeriğini JSON olarak döndür"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    prp_file = os.path.join(project_dir, 'prp', 'prp.md')
    
    if not os.path.exists(prp_file):
        return jsonify({
            'success': False,
            'error': 'PRP file not found'
        }), 404
    
    try:
        with open(prp_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        state = load_project_state(project_id)
        version = state.get('version', {}).get('prp', '0.1')
        
        return jsonify({
            'success': True,
            'content': content,
            'version': version
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/prp/<project_id>', methods=['POST'])
def save_prp_content(project_id):
    """PRP içeriğini kaydet"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    new_content = data.get('content', '')
    
    if not new_content.strip():
        return jsonify({
            'success': False,
            'error': 'Content cannot be empty'
        }), 400
    
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    prp_file = os.path.join(project_dir, 'prp', 'prp.md')
    
    try:
        
        # Yeni içeriği kaydet (backup YAPMA - sadece approve'da backup)
        with open(prp_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return jsonify({
            'success': True,
            'message': 'PRP saved successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/prp-history/<project_id>', methods=['GET'])
def get_prp_history(project_id):
    """PRP version history'sini döndür"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    history_file = os.path.join(project_dir, 'prp', 'prp_history.md')
    
    if not os.path.exists(history_file):
        return jsonify({
            'success': True,
            'history': [],
            'message': 'No history available'
        })
    
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history_content = f.read()
        
        # History'yi parse et
        versions = []
        current_version = None
        current_content = []
        
        for line in history_content.split('\n'):
            if line.startswith('## Version'):
                if current_version:
                    versions.append({
                        'version': current_version,
                        'content': '\n'.join(current_content)
                    })
                current_version = line.replace('## Version', '').strip()
                current_content = []
            else:
                current_content.append(line)
        
        # Son version'ı ekle
        if current_version:
            versions.append({
                'version': current_version,
                'content': '\n'.join(current_content)
            })
        
        return jsonify({
            'success': True,
            'history': versions
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/prp-approve/<project_id>', methods=['POST'])
def approve_prp(project_id):
    """PRP'yi onayla ve state'i güncelle"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    bump_version = data.get('bump_version', True)
    
    try:
        state = load_project_state(project_id)
        if not state:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        prp_file = os.path.join(project_dir, 'prp', 'prp.md')
        
        # Backup mevcut PRP (version bump'tan ÖNCE)
        if os.path.exists(prp_file):
            backup_prp_to_history(project_id, prp_file)
        
        # Version'ı güncelle
        old_version = state.get('version', {}).get('prp', '0.1')
        if bump_version:
            current_prp_version = old_version
            version_parts = current_prp_version.split('.')
            if len(version_parts) == 2:
                major, minor = version_parts
                new_version = f"{major}.{int(minor) + 1}"
            else:
                new_version = "1.0"
            
            if 'version' not in state:
                state['version'] = {}
            state['version']['prp'] = new_version
        
        # Phase güncelle (eğer 'prp' phase'indeyse)
        if state.get('phase') == 'prp':
            state['phase'] = 'development'
            state['next_action'] = {
                'agent': 'dev_agent',
                'action': 'Generate code based on PRP',
                'requires_human_approval': True
            }
        
        # Last event güncelle
        from datetime import datetime
        state['last_event'] = {
            'agent': 'human',
            'action': f"PRP v{state['version']['prp']} approved",
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'result': 'success',
            'model': 'N/A'
        }
        
        # State'i kaydet
        save_project_state(project_id, state)
        
        # Generate AI summary (non-blocking, best effort)
        try:
            generate_prp_summary(project_id, old_version, state['version']['prp'])
        except Exception as e:
            print(f"Warning: Could not generate AI summary: {e}", flush=True)
        
        return jsonify({
            'success': True,
            'message': 'PRP approved and state updated',
            'new_version': state['version']['prp'],
            'new_phase': state['phase']
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def generate_prp_summary(project_id, old_version, new_version):
    """Generate AI summary for PRP version changes"""
    import requests
    
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    history_file = os.path.join(project_dir, 'prp', 'prp_history.md')
    
    if not os.path.exists(history_file):
        return
    
    # Parse history to get versions
    versions = parse_prp_history(project_id)
    if len(versions) < 2:
        return  # No previous version to compare
    
    # Find old and new version content
    old_content = None
    new_content = None
    
    for v in versions:
        if v['version'] == old_version:
            old_content = v['content']
        if v['version'] == new_version:
            new_content = v['content']
    
    if not old_content or not new_content:
        return
    
    # Load LLM config
    state = load_project_state(project_id)
    model_name = state.get('agent_models', {}).get('prp_agent', 'gemma-free')
    
    profiles_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'llm.profiles.yaml')
    with open(profiles_path, 'r') as f:
        profiles_data = yaml.safe_load(f)
    
    profile = profiles_data['profiles'].get(model_name, profiles_data['profiles']['gemma-free'])
    
    # Generate summary prompt
    summary_prompt = f"""Compare these two PRP versions and summarize the key changes in 3-5 bullet points.

Previous Version (v{old_version}):
{old_content[:3000]}

Current Version (v{new_version}):
{new_content[:3000]}

Provide ONLY a bulleted list of key changes (no introduction, no conclusion). Focus on:
- New sections or features added
- Removed sections or features
- Significant content changes
- Scope or requirement modifications

Format: Use markdown bullet points (- or *)."""

    # Call LLM API
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    api_key = os.environ.get('OPENROUTER_API_KEY')
    
    response = requests.post(
        api_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": profile['model'],
            "messages": [
                {"role": "user", "content": summary_prompt}
            ],
            "max_tokens": 300,
            "temperature": 0.3
        },
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"LLM API error: {response.status_code}", flush=True)
        return
    
    result = response.json()
    summary = result['choices'][0]['message']['content'].strip()
    
    # Append summary to history file
    with open(history_file, 'r', encoding='utf-8') as f:
        history_content = f.read()
    
    # Insert summary after the version header
    version_header = f"## Version {new_version}"
    if version_header in history_content:
        parts = history_content.split(version_header, 1)
        if len(parts) == 2:
            # Find first newline after header
            header_and_date = parts[1].split('\n', 1)
            if len(header_and_date) == 2:
                summary_section = f"\n### 🤖 AI Change Summary\n\n{summary}\n"
                new_history = parts[0] + version_header + '\n' + header_and_date[0] + summary_section + '\n' + header_and_date[1]
                
                with open(history_file, 'w', encoding='utf-8') as f:
                    f.write(new_history)
                
                print(f"AI summary generated for PRP v{new_version}", flush=True)



def backup_prp_to_history(project_id, prp_file):
    """PRP'yi history dosyasına backup al"""
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    history_file = os.path.join(project_dir, 'prp', 'prp_history.md')
    
    # Mevcut state'i al
    state = load_project_state(project_id)
    current_version = state.get('version', {}).get('prp', '0.1')
    
    # Mevcut PRP'yi oku
    with open(prp_file, 'r', encoding='utf-8') as f:
        current_prp = f.read()
    
    # History dosyası yoksa oluştur
    if not os.path.exists(history_file):
        with open(history_file, 'w', encoding='utf-8') as f:
            f.write("# PRP Version History\n\n")
    
    # History'ye ekle
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    history_entry = f"\n\n## Version {current_version} - {timestamp}\n\n{current_prp}\n"
    
    with open(history_file, 'a', encoding='utf-8') as f:
        f.write(history_entry)


# PRP ROUTES END

# ============================================
# VISION MANAGEMENT ROUTES
# ============================================
# Vision Management Routes
# Add to app.py

@app.route('/api/save-vision/<project_id>', methods=['POST'])
def save_vision(project_id):
    """Save product vision to prp.md"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        vision = data.get('vision', '').strip()
        
        if not vision:
            return jsonify({'success': False, 'error': 'Vision cannot be empty'}), 400
        
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        prp_file = os.path.join(project_dir, 'prp', 'prp.md')
        
        # Write vision to prp.md
        with open(prp_file, 'w', encoding='utf-8') as f:
            f.write(f"# Product Vision\n\n{vision}\n")
        
        # Update state - add vision field
        state = load_project_state(project_id)
        if 'meta' not in state:
            state['meta'] = {}
        state['meta']['has_vision'] = True
        save_project_state(project_id, state)
        
        return jsonify({
            'success': True,
            'message': 'Vision saved successfully'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/get-vision/<project_id>')
def get_vision(project_id):
    """Get current vision from prp.md"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        prp_file = os.path.join(project_dir, 'prp', 'prp.md')
        
        if not os.path.exists(prp_file):
            return jsonify({'success': True, 'vision': ''})
        
        with open(prp_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract vision (simple: everything in prp.md if phase is 'idea')
        state = load_project_state(project_id)
        if state.get('phase') == 'idea':
            # Remove "# Product Vision" header if present
            vision = content.replace('# Product Vision', '').strip()
        else:
            vision = ''
        
        return jsonify({
            'success': True,
            'vision': vision
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================
# VISION MANAGEMENT ROUTES
# ============================================
# ============================================
# ============================================
# PRP VERSIONS LIST - BACKEND
# File: web/app.py
# ============================================
# Bu kodu app.py'nin PRP routes bölümüne ekleyin

@app.route('/project/<project_id>/prp/versions')
def prp_versions_list(project_id):
    """PRP version listesi sayfası"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    state = load_project_state(project_id)
    if not state:
        flash('Project not found', 'error')
        return redirect(url_for('dashboard'))
    
    # History dosyasını parse et
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    history_file = os.path.join(project_dir, 'prp', 'prp_history.md')
    
    versions = []
    if os.path.exists(history_file):
        versions = parse_prp_history(history_file, state)
    
    # Current PRP version'ı da ekle (en son)
    prp_file = os.path.join(project_dir, 'prp', 'prp.md')
    if os.path.exists(prp_file):
        with open(prp_file, 'r', encoding='utf-8') as f:
            current_content = f.read()
        
        current_version = {
            'version': state.get('version', {}).get('prp', '0.1'),
            'date': state.get('last_event', {}).get('timestamp', 'N/A'),
            'phase': state.get('phase', 'unknown'),
            'agent': state.get('last_event', {}).get('agent', 'unknown'),
            'model': state.get('last_event', {}).get('model', 'N/A'),
            'content': current_content,
            'is_current': True
        }
        versions.insert(0, current_version)  # En başa ekle
    
    return render_template('prp_versions.html',
                         project_id=project_id,
                         state=state,
                         versions=versions)


def parse_prp_history(history_file, state):
    """
    prp_history.md dosyasını parse et
    Return: List of version dictionaries
    """
    versions = []
    
    with open(history_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # "## Version" ile başlayan bölümleri bul
    import re
    pattern = r'^## Version ([\d.]+) - ([\d-]+ [\d:]+)'
    
    lines = content.split('\n')
    current_version = None
    current_content = []
    
    for line in lines:
        match = re.match(pattern, line)
        if match:
            # Önceki version'ı kaydet
            if current_version:
                versions.append({
                    'version': current_version['version'],
                    'date': current_version['date'],
                    'content': '\n'.join(current_content).strip(),
                    'is_current': False,
                    'phase': 'N/A',  # History'de phase yok, bilmiyoruz
                    'agent': 'prp_agent',  # Varsayılan
                    'model': 'N/A'  # History'de model yok
                })
                current_content = []
            
            # Yeni version başla
            current_version = {
                'version': match.group(1),
                'date': match.group(2)
            }
        else:
            # İçerik satırı
            if current_version:
                # Check for AI summary section
                if line.startswith('### 🤖 AI Change Summary'):
                    current_version['has_summary'] = True
                    current_version['summary'] = []
                elif 'has_summary' in current_version and line.strip() and not line.startswith('##'):
                # Collect summary lines until next section
                    if line.startswith('###') and '🤖' not in line:
                        current_version['has_summary'] = False  # End of summary
                    else:
                        current_version['summary'].append(line)
    
                    current_content.append(line)
    
    # Son version'ı ekle
    if current_version:
        versions.append({
            'version': current_version['version'],
            'date': current_version['date'],
            'content': '\n'.join(current_content).strip(),
            'is_current': False,
            'phase': 'N/A',
            'agent': 'prp_agent',
            'model': 'N/A',
            'summary': '\n'.join(current_version.get('summary', [])).strip() if 'summary' in current_version else None
        })
    
    # Duplicate'leri kaldır (aynı version + aynı tarih)
    seen = set()
    unique_versions = []
    for v in versions:
        key = f"{v['version']}-{v['date']}"
        if key not in seen:
            seen.add(key)
            unique_versions.append(v)
    
    # Tarihe göre sırala (yeniden eskiye)
    unique_versions.sort(key=lambda x: x['date'], reverse=True)
    
    return unique_versions


# ============================================
# Helper: Get version by number
# ============================================
@app.route('/project/<project_id>/prp/version/<version_number>')
def prp_version_detail(project_id, version_number):
    """Specific version detail sayfası"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    state = load_project_state(project_id)
    if not state:
        flash('Project not found', 'error')
        return redirect(url_for('dashboard'))
    
    # History'den version bul
    project_dir = os.path.join(PROJECTS_DIR, project_id)
    history_file = os.path.join(project_dir, 'prp', 'prp_history.md')
    
    versions = []
    if os.path.exists(history_file):
        versions = parse_prp_history(history_file, state)
    
    # Current version'ı da ekle
    prp_file = os.path.join(project_dir, 'prp', 'prp.md')
    current_prp_version = state.get('version', {}).get('prp', '0.1')
    
    if version_number == current_prp_version and os.path.exists(prp_file):
        with open(prp_file, 'r', encoding='utf-8') as f:
            current_content = f.read()
        
        selected_version = {
            'version': current_prp_version,
            'date': state.get('last_event', {}).get('timestamp', 'N/A'),
            'content': current_content,
            'is_current': True,
            'model': state.get('last_event', {}).get('model', 'N/A')
        }
    else:
        # History'den bul
        selected_version = next((v for v in versions if v['version'] == version_number), None)
    
    if not selected_version:
        flash(f'Version {version_number} not found', 'error')
        return redirect(url_for('prp_versions_list', project_id=project_id))
    
    # Önceki version'ı bul (diff için)
    all_versions = versions.copy()
    if selected_version.get('is_current'):
        all_versions.insert(0, selected_version)
    
    # Tarihe göre sırala
    all_versions.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    current_idx = next((i for i, v in enumerate(all_versions) if v['version'] == version_number), None)
    previous_version = all_versions[current_idx + 1] if current_idx is not None and current_idx + 1 < len(all_versions) else None
    
    return render_template('prp_version_detail.html',
                         project_id=project_id,
                         state=state,
                         version=selected_version,
                         previous_version=previous_version)


# ============================================
# PRP AUTO-UPDATE ENDPOINTS
# ============================================

@app.route('/api/parse-prp-suggestions/<project_id>', methods=['POST'])
def parse_prp_suggestions(project_id):
    """Extract PRP-specific issues from AI analysis"""
    try:
        data = request.get_json()
        ai_analysis = data.get('ai_analysis', {})
        
        if not ai_analysis or 'test_analysis' not in ai_analysis:
            return jsonify({'success': False, 'error': 'No AI analysis data'})
        
        # Filter PRP category issues
        prp_issues = [t for t in ai_analysis['test_analysis'] if t.get('category') == 'prp']
        
        if not prp_issues:
            return jsonify({'success': False, 'error': 'No PRP issues found'})
        
        # Build suggestions markdown
        suggestions = "## 🤖 AI-Suggested PRP Updates\n\n"
        suggestions += "Based on test failures, the following improvements are recommended:\n\n"
        
        for i, issue in enumerate(prp_issues, 1):
            suggestions += f"{i}. **{issue['test']}**\n"
            suggestions += f"   - Issue: {issue['reason']}\n\n"
        
        if ai_analysis.get('reasoning'):
            suggestions += f"### Analysis Summary\n\n{ai_analysis['reasoning']}\n"
        
        return jsonify({'success': True, 'suggestions': suggestions})
        
    except Exception as e:
        print(f"Error parsing PRP suggestions: {e}", flush=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/preview-prp-diff/<project_id>', methods=['POST'])
def preview_prp_diff(project_id):
    """Generate diff preview for PRP changes"""
    try:
        data = request.get_json()
        suggestions = data.get('suggestions', '')
        
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        prp_path = os.path.join(project_dir, 'prp', 'prp.md')
        
        if not os.path.exists(prp_path):
            return jsonify({'success': False, 'error': 'PRP file not found'})
        
        # Load current PRP
        with open(prp_path, 'r') as f:
            old_prp = f.read()
        
        # Generate new version (append suggestions)
        new_prp = old_prp.rstrip() + "\n\n---\n\n" + suggestions
        
        return jsonify({
            'success': True,
            'diff': {
                'old': old_prp,
                'new': new_prp
            }
        })
        
    except Exception as e:
        print(f"Error generating PRP diff: {e}", flush=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/apply-prp-changes/<project_id>', methods=['POST'])
def apply_prp_changes(project_id):
    """Apply PRP changes to file"""
    try:
        data = request.get_json()
        updated_prp = data.get('updated_prp', '')
        
        if not updated_prp:
            return jsonify({'success': False, 'error': 'No content provided'})
        
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        prp_path = os.path.join(project_dir, 'prp', 'prp.md')
        
        # Write updated PRP
        with open(prp_path, 'w') as f:
            f.write(updated_prp)
        
        return jsonify({
            'success': True,
            'redirect': f'/project/{project_id}/prp'
        })
        
    except Exception as e:
        print(f"Error applying PRP changes: {e}", flush=True)
        return jsonify({'success': False, 'error': str(e)})


# END PRP VERSIONS
# ============================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

