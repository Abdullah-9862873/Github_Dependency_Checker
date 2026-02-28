import os
import json
from flask import Flask, jsonify, request, render_template, Response

app = Flask(__name__)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'openclaw-guardian', 'config.yaml')
MEMORY_FILE = os.path.join(PROJECT_ROOT, 'openclaw-guardian', 'memory.json')

session = {
    'cycles': 0,
    'prs': 0,
    'packages': 0,
    'history': [],
}

def _read_config():
    try:
        import yaml
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}

def _write_config(cfg):
    try:
        import yaml
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(cfg, f, default_flow_style=False)
    except Exception as e:
        print(f"[config] write error: {e}")

def _reset_session():
    session['cycles'] = 0
    session['prs'] = 0
    session['packages'] = 0
    session['history'] = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    cfg = _read_config()
    return jsonify({
        'running': False,
        'config': {
            'repoUrl': cfg.get('github', {}).get('repo_url', ''),
            'tokenConfigured': bool(cfg.get('github', {}).get('token', '')),
            'checkInterval': cfg.get('agent', {}).get('check_interval', 3600),
        },
        'stats': {
            'cycles': session['cycles'],
            'prs': session['prs'],
            'packages': session['packages'],
        },
        'history': session['history'],
    })

@app.route('/api/config', methods=['POST'])
def save_config():
    data = request.json or {}
    new_url = (data.get('repoUrl', '') or '').strip()
    new_token = (data.get('githubToken', '') or '').strip()
    interval = int(data.get('checkInterval', 3600))

    if not new_url:
        return jsonify({'success': False, 'message': 'Repository URL is required'})
    if not new_token:
        return jsonify({'success': False, 'message': 'GitHub Token is required'})
    if not new_url.startswith('https://github.com/'):
        return jsonify({'success': False, 'message': 'Invalid URL — must start with https://github.com/'})
    if interval < 60:
        return jsonify({'success': False, 'message': 'Interval must be at least 60 seconds'})

    cfg = _read_config()
    cfg.setdefault('github', {})
    cfg.setdefault('agent', {})
    cfg['github']['repo_url'] = new_url
    cfg['github']['token'] = new_token
    cfg['agent']['check_interval'] = interval
    _write_config(cfg)

    _reset_session()

    return jsonify({'success': True})

@app.route('/api/run-once', methods=['POST'])
def run_once():
    ok, err = True, None
    cfg = _read_config()
    url = cfg.get('github', {}).get('repo_url', '').strip()
    token = cfg.get('github', {}).get('token', '').strip()
    
    if not url:
        ok, err = False, 'GitHub Repository URL is not configured'
    elif not token:
        ok, err = False, 'GitHub Token is not configured'
    else:
        ok, err = True, None
    
    if not ok:
        return jsonify({'success': False, 'message': err})

    _reset_session()

    try:
        import requests
        from datetime import datetime
        
        repo_name = url.replace('https://github.com/', '').strip('/')
        api_url = f'https://api.github.com/repos/{repo_name}'
        
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        response = requests.get(api_url, headers=headers)
        
        if response.status_code == 200:
            session['cycles'] = 1
            session['history'].append({
                'timestamp': datetime.now().isoformat(),
                'packages': ['demo-package'],
                'pr_url': ''
            })
            return jsonify({
                'success': True,
                'message': 'API connected successfully (Vercel demo mode)',
                'stats': session.copy()
            })
        else:
            return jsonify({
                'success': False,
                'message': f'GitHub API error: {response.status_code}'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/api/events')
def events():
    def _generate():
        yield "data: {\"type\":\"log\",\"data\":{\"message\":\"Connected\",\"level\":\"info\"}}\n\n"
    return Response(_generate(), mimetype='text/event-stream')

handler = app
