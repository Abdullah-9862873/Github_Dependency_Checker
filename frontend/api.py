"""
OpenClaw Guardian — API Server

Lifecycle rules (all session-based, nothing is persisted across reloads):
  1. Server startup      → wipe repos, memory file, config credentials; reset session
  2. Save Configuration  → save URL+token to config.yaml; reset session
  3. Run Once / Start    → wipe repos, reclone fresh, run; update session counters
  4. Page Reload (GET /) → wipe repos, memory file, config credentials; reset session
"""

import os
import sys
import json
import shutil
import threading
from datetime import datetime
from flask import Flask, jsonify, request, render_template, Response
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR  = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

CONFIG_FILE = os.path.join(PROJECT_ROOT, 'openclaw-guardian', 'config.yaml')
MEMORY_FILE = os.path.join(PROJECT_ROOT, 'openclaw-guardian', 'memory.json')
REPOS_DIR   = os.path.join(PROJECT_ROOT, 'openclaw-guardian', 'repos')

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder=os.path.join(FRONTEND_DIR, 'templates'))
CORS(app)


# ---------------------------------------------------------------------------
# Session counters  (purely in-memory — wiped on every reset)
# ---------------------------------------------------------------------------
session = {
    'cycles':   0,
    'prs':      0,
    'packages': 0,
    'history':  [],   # list of { timestamp, packages: [str], pr_url: str }
}

def _reset_session():
    """Reset all session counters to zero — called on every wipe."""
    session['cycles']   = 0
    session['prs']      = 0
    session['packages'] = 0
    session['history']  = []
    print("[session] counters reset")

# ---------------------------------------------------------------------------
# Server-Sent Events
# ---------------------------------------------------------------------------
class EventEmitter:
    def __init__(self):
        self.listeners = []
        self._lock = threading.Lock()

    def add_listener(self, cb):
        with self._lock:
            self.listeners.append(cb)

    def remove_listener(self, cb):
        with self._lock:
            if cb in self.listeners:
                self.listeners.remove(cb)

    def emit(self, event_type, data):
        with self._lock:
            snapshot = list(self.listeners)
        dead = []
        for cb in snapshot:
            try:
                cb({'type': event_type, 'data': data})
            except Exception:
                dead.append(cb)
        for cb in dead:
            self.remove_listener(cb)

event_emitter = EventEmitter()

# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------
def _delete_repos():
    """Force-delete all cloned repos using Windows 'rd /s /q' to handle
    read-only .git objects that shutil.rmtree cannot remove (WinError 5)."""
    import stat, subprocess as _sp
    try:
        if not os.path.exists(REPOS_DIR):
            return
        for item in os.listdir(REPOS_DIR):
            item_path = os.path.join(REPOS_DIR, item)
            if not os.path.isdir(item_path):
                continue
            # Primary: Windows rd /s /q — ignores read-only flags
            try:
                _sp.run(['cmd', '/c', 'rd', '/s', '/q', item_path],
                        capture_output=True, text=True, timeout=60)
                if not os.path.exists(item_path):
                    print(f"[repos] deleted: {item}")
                    continue
            except Exception:
                pass
            # Fallback: chmod every file then rmtree
            def _rm_ro(func, path, _):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(item_path, onerror=_rm_ro)
            if not os.path.exists(item_path):
                print(f"[repos] deleted (fallback): {item}")
            else:
                print(f"[repos] WARNING — could not fully delete: {item}")
    except Exception as e:
        print(f"[repos] error: {e}")

def _reset_memory_file():
    """Write an empty memory.json so the agent always starts fresh."""
    try:
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump({"last_updated": [], "successful_upgrades": 0, "repo_url": ""}, f, indent=4)
    except Exception as e:
        print(f"[memory] write error: {e}")

def _clear_config_credentials():
    """Set repo_url and token to empty strings in config.yaml."""
    try:
        import yaml
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                cfg = yaml.safe_load(f) or {}
        cfg.setdefault('github', {})
        cfg['github']['repo_url'] = ''
        cfg['github']['token']    = ''
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(cfg, f, default_flow_style=False)
        print("[config] credentials cleared")
    except Exception as e:
        print(f"[config] clear error: {e}")

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

# ---------------------------------------------------------------------------
# Compound reset helpers
# ---------------------------------------------------------------------------
def _wipe_repos_and_memory():
    """Wipe repos + reset memory file + reset session counters."""
    _delete_repos()
    _reset_memory_file()
    _reset_session()
    print("[reset] repos + memory + session wiped")

def _wipe_everything():
    """Full wipe: repos, memory file, config credentials, session counters."""
    _delete_repos()
    _reset_memory_file()
    _clear_config_credentials()
    _reset_session()
    print("[reset] full wipe complete")

# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------
def _get_agent():
    original_dir = os.getcwd()
    agent_dir    = os.path.join(PROJECT_ROOT, 'openclaw-guardian')
    try:
        os.chdir(agent_dir)
        if agent_dir not in sys.path:
            sys.path.insert(0, agent_dir)
        import importlib.util, argparse
        spec  = importlib.util.spec_from_file_location(
                    "main_module", os.path.join(agent_dir, 'main.py'))
        mod   = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        args  = argparse.Namespace(config='config.yaml', once=False, verbose=True)
        return mod.OpenClawGuardian(args)
    except Exception as e:
        print(f"[agent] init error: {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        os.chdir(original_dir)

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _validate_config():
    cfg   = _read_config()
    url   = cfg.get('github', {}).get('repo_url', '').strip()
    token = cfg.get('github', {}).get('token', '').strip()
    if not url:
        return False, 'GitHub Repository URL is not configured'
    if not token:
        return False, 'GitHub Token is not configured'
    if not url.startswith('https://github.com/'):
        return False, 'Invalid GitHub URL — must start with https://github.com/'
    return True, None

# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

# ── Page load / reload ────────────────────────────────────────────────────
@app.route('/')
def index():
    """Rule 4: full wipe on every page load."""
    _wipe_everything()
    return render_template('index.html')

# ── Status poll ───────────────────────────────────────────────────────────
@app.route('/api/status')
def get_status():
    cfg = _read_config()
    return jsonify({
        'running': False,
        'config': {
            'repoUrl':         cfg.get('github', {}).get('repo_url', ''),
            'tokenConfigured': bool(cfg.get('github', {}).get('token', '')),
            'checkInterval':   cfg.get('agent', {}).get('check_interval', 3600),
        },
        # Return current session counters — zero until a cycle finishes
        'stats': {
            'cycles':   session['cycles'],
            'prs':      session['prs'],
            'packages': session['packages'],
        },
        'history': session['history'],
    })

# ── Save configuration ─────────────────────────────────────────────────
@app.route('/api/config', methods=['POST'])
def save_config():
    """Rule 2 & 5: validate, save credentials, always wipe session."""
    data      = request.json or {}
    new_url   = (data.get('repoUrl',      '') or '').strip()
    new_token = (data.get('githubToken',  '') or '').strip()
    interval  = int(data.get('checkInterval', 3600))

    if not new_url:
        return jsonify({'success': False, 'message': 'Repository URL is required'})
    if not new_token:
        return jsonify({'success': False, 'message': 'GitHub Token is required'})
    if not new_url.startswith('https://github.com/'):
        return jsonify({'success': False,
                        'message': 'Invalid URL — must start with https://github.com/'})
    if interval < 60:
        return jsonify({'success': False, 'message': 'Interval must be at least 60 seconds'})

    # Build and persist config
    cfg = _read_config()
    cfg.setdefault('github', {})
    cfg.setdefault('agent',  {})
    cfg.setdefault('paths',  {})
    cfg['github']['repo_url']            = new_url
    cfg['github']['token']               = new_token
    cfg['agent']['check_interval']       = interval
    cfg['agent'].setdefault('branch_prefix', 'auto/dependency-update')
    cfg['paths']['working_directory']    = './repos'
    cfg['paths']['memory_file']          = './memory.json'
    _write_config(cfg)
    print(f"[config] saved  url={new_url}")

    # Always reset session and repos on every Save Configuration
    _wipe_repos_and_memory()

    # Tell frontend to wipe its display
    event_emitter.emit('reset', {})
    event_emitter.emit('log', {
        'message': '✅ Configuration saved — ready for a fresh run',
        'level':   'success'
    })
    return jsonify({'success': True})

# ── Run once ───────────────────────────────────────────────────────────
@app.route('/api/run-once', methods=['POST'])
def run_once():
    """
    Rule 3: wipe repos + memory, reclone fresh, run one cycle.
    After the cycle, push session stats and history to frontend via SSE.
    """
    ok, err = _validate_config()
    if not ok:
        event_emitter.emit('log', {'message': f'❌ {err}', 'level': 'error'})
        return jsonify({'success': False, 'message': err})

    _wipe_repos_and_memory()   # fresh slate — session counters also resetted here

    def _do_cycle():
        event_emitter.emit('cycle_start', {})
        event_emitter.emit('log', {'message': '🔄 Starting fresh run — deleting old clone…', 'level': 'info'})

        # --- Init agent ---
        try:
            agent = _get_agent()
        except Exception as e:
            event_emitter.emit('log', {'message': f'❌ Failed to initialise agent: {e}', 'level': 'error'})
            event_emitter.emit('cycle_complete', {})
            return

        event_emitter.emit('log', {'message': '📂 Cloning repository from GitHub…', 'level': 'info'})
        event_emitter.emit('log', {'message': '📦 Installing npm dependencies…',      'level': 'info'})
        event_emitter.emit('log', {'message': '🔍 Checking for outdated packages…',   'level': 'info'})

        # --- Run the cycle ---
        try:
            result = agent.run_cycle()
            print(f"[DEBUG] agent.run_cycle() returned: {result}")
            
            # Handle tuple return: (success, upgraded_packages, pr_url)
            if isinstance(result, tuple):
                success, upgraded_packages, pr_url = result
            else:
                success = result
                upgraded_packages = []
                pr_url = ''
        except Exception as e:
            import traceback; traceback.print_exc()
            event_emitter.emit('log', {'message': f'❌ Cycle error: {e}', 'level': 'error'})
            event_emitter.emit('cycle_complete', {})
            return

        # --- Update session counters ---
        print(f"[DEBUG] Before update - session: cycles={session['cycles']}, prs={session['prs']}, packages={session['packages']}")
        print(f"[DEBUG] success={success}, upgraded_packages={upgraded_packages}, pr_url={pr_url}")
        if success and upgraded_packages:
            session['cycles']   += 1
            session['prs']      += 1
            session['packages'] += len(upgraded_packages)

            # Append to history
            hist_entry = {
                'timestamp': datetime.now().isoformat(),
                'packages':  upgraded_packages,
                'pr_url':    pr_url,
            }
            session['history'].append(hist_entry)

            # Log each package
            for pkg in upgraded_packages:
                event_emitter.emit('log', {'message': f'   ✔ {pkg}', 'level': 'success'})
            event_emitter.emit('log', {
                'message': f'📦 Upgraded {len(upgraded_packages)} package(s)',
                'level': 'success'
            })
            if pr_url:
                event_emitter.emit('log', {'message': f'🔗 Pull Request created: {pr_url}', 'level': 'success'})
            event_emitter.emit('log', {'message': '✅ Cycle complete — PR created!', 'level': 'success'})
            print(f"[DEBUG] After update - session: cycles={session['cycles']}, prs={session['prs']}, packages={session['packages']}")
        else:
            event_emitter.emit('log', {
                'message': '✅ All dependencies are already up to date',
                'level': 'success'
            })
            event_emitter.emit('no_upgrades', {})

        # --- Push session stats + history to frontend ---
        event_emitter.emit('stats', {
            'cycles':   session['cycles'],
            'prs':      session['prs'],
            'packages': session['packages'],
        })
        event_emitter.emit('history', session['history'])
        event_emitter.emit('cycle_complete', {
            'timestamp': datetime.now().isoformat(),
        })
        event_emitter.emit('log', {
            'message': f'🏁 Finished at {datetime.now().strftime("%H:%M:%S")}',
            'level': 'info'
        })

    # Run in background thread but wait for completion
    result_container = [None]
    def _run_and_wait():
        _do_cycle()
        result_container[0] = True
    
    thread = threading.Thread(target=_run_and_wait, daemon=True)
    thread.start()
    thread.join()  # Wait for cycle to complete
    
    print(f"[DEBUG] Returning response - cycles={session['cycles']}, prs={session['prs']}, packages={session['packages']}, history_len={len(session['history'])}")
    
    # Return stats directly in response
    return jsonify({
        'success': True,
        'stats': {
            'cycles': session['cycles'],
            'prs': session['prs'],
            'packages': session['packages'],
        },
        'history': session['history']
    })

# ── SSE event stream ───────────────────────────────────────────────────
@app.route('/api/events')
def events():
    import time

    def _generate():
        queue = []
        lock  = threading.Lock()

        def _listener(ev):
            with lock:
                queue.append(ev)

        event_emitter.add_listener(_listener)
        try:
            while True:
                with lock:
                    while queue:
                        yield f"data: {json.dumps(queue.pop(0))}\n\n"
                time.sleep(0.25)
        except GeneratorExit:
            event_emitter.remove_listener(_listener)

    return Response(_generate(), mimetype='text/event-stream')

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 60)
    print("  OpenClaw Guardian API Server")
    print("=" * 60)
    _wipe_everything()   # Rule 1: full clean slate on startup
    print("[init] Server clean — all data wiped")
    print("→  http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
