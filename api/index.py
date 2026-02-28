"""
OpenClaw Guardian — Vercel Serverless API
==========================================
Self-contained single-file Flask app for Vercel deployment.
- Embeds HTML inline (no template folder dependency)
- Uses relative API paths (no hardcoded localhost)
- No subprocess / blocking threads / infinite generators (serverless-safe)
- In-memory session state (resets on each cold start, as expected)
"""

import os
import json
import requests
from datetime import datetime
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# In-memory session state
# ---------------------------------------------------------------------------
_config = {
    'repo_url': '',
    'token': '',
    'check_interval': 3600,
}

_session = {
    'cycles': 0,
    'prs': 0,
    'packages': 0,
    'history': [],
}

_logs = []  # list of {message, level, ts}


def _add_log(message, level='info'):
    _logs.append({
        'message': message,
        'level': level,
        'ts': datetime.now().strftime('%H:%M:%S'),
    })
    # Keep only last 200 log lines
    if len(_logs) > 200:
        _logs.pop(0)


def _reset_session():
    _session['cycles'] = 0
    _session['prs'] = 0
    _session['packages'] = 0
    _session['history'] = []
    _logs.clear()


# ---------------------------------------------------------------------------
# GitHub helpers (pure API — no git clone needed)
# ---------------------------------------------------------------------------

def _gh_headers(token):
    return {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'OpenClaw-Guardian/1.0',
    }


def _get_repo_info(owner, repo, token):
    """Fetch default branch name."""
    r = requests.get(
        f'https://api.github.com/repos/{owner}/{repo}',
        headers=_gh_headers(token),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def _get_file_content(owner, repo, path, ref, token):
    """Return (content_str, sha) of a file via GitHub API."""
    r = requests.get(
        f'https://api.github.com/repos/{owner}/{repo}/contents/{path}',
        headers=_gh_headers(token),
        params={'ref': ref},
        timeout=15,
    )
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    data = r.json()
    import base64
    content = base64.b64decode(data['content']).decode('utf-8')
    return content, data['sha']


def _parse_package_json(content):
    try:
        return json.loads(content)
    except Exception:
        return None


def _get_latest_version(package_name):
    """Query npm registry for the latest version."""
    try:
        r = requests.get(
            f'https://registry.npmjs.org/{package_name}/latest',
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get('version')
    except Exception:
        pass
    return None


def _parse_version(v):
    """Strip semver prefix characters like ^, ~, >=."""
    return v.lstrip('^~>=<').split('-')[0].strip()


def _check_outdated(deps):
    """
    Given a dict of {name: version_range}, return list of
    {name, current, latest} for packages that have a newer version.
    """
    outdated = []
    for name, ver_range in (deps or {}).items():
        current = _parse_version(ver_range)
        latest = _get_latest_version(name)
        if latest and latest != current:
            # Basic semver comparison: just string compare major.minor.patch
            try:
                cv = tuple(int(x) for x in current.split('.'))
                lv = tuple(int(x) for x in latest.split('.'))
                if lv > cv:
                    outdated.append({'name': name, 'current': current, 'latest': latest})
            except Exception:
                pass
    return outdated


def _update_package_json_content(content, outdated):
    """
    Return updated package.json content string with bumped versions.
    Preserves the prefix (^, ~, etc.) of each dep.
    """
    pkg = json.loads(content)
    updated_names = []
    for item in outdated:
        name = item['name']
        latest = item['latest']
        for section in ('dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies'):
            if name in pkg.get(section, {}):
                old_val = pkg[section][name]
                prefix = ''
                for ch in old_val:
                    if ch in '^~>=<':
                        prefix += ch
                    else:
                        break
                pkg[section][name] = prefix + latest
                updated_names.append(f'{name}@{latest}')
    new_content = json.dumps(pkg, indent=2) + '\n'
    return new_content, updated_names


def _create_branch(owner, repo, branch_name, base_sha, token):
    r = requests.post(
        f'https://api.github.com/repos/{owner}/{repo}/git/refs',
        headers=_gh_headers(token),
        json={'ref': f'refs/heads/{branch_name}', 'sha': base_sha},
        timeout=15,
    )
    # 422 = branch already exists — that's OK
    if r.status_code not in (201, 422):
        r.raise_for_status()


def _commit_file(owner, repo, path, message, content_str, file_sha, branch, token):
    import base64
    encoded = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')
    r = requests.put(
        f'https://api.github.com/repos/{owner}/{repo}/contents/{path}',
        headers=_gh_headers(token),
        json={
            'message': message,
            'content': encoded,
            'sha': file_sha,
            'branch': branch,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def _open_pr(owner, repo, branch, base_branch, title, body, token):
    r = requests.post(
        f'https://api.github.com/repos/{owner}/{repo}/pulls',
        headers=_gh_headers(token),
        json={
            'title': title,
            'body': body,
            'head': branch,
            'base': base_branch,
        },
        timeout=15,
    )
    # 422 = PR already open for this branch — treat gracefully
    if r.status_code == 422:
        # Try to find the existing open PR
        prs = requests.get(
            f'https://api.github.com/repos/{owner}/{repo}/pulls',
            headers=_gh_headers(token),
            params={'head': f'{owner}:{branch}', 'state': 'open'},
            timeout=10,
        )
        if prs.ok and prs.json():
            return prs.json()[0].get('html_url', '')
        return ''
    r.raise_for_status()
    return r.json().get('html_url', '')


def _parse_github_url(url):
    """Extract (owner, repo) from a github.com URL."""
    url = url.rstrip('/')
    if url.endswith('.git'):
        url = url[:-4]
    parts = url.split('/')
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    return None, None


def _run_cycle():
    """
    Core logic: check package.json for outdated deps via npm registry,
    commit updates to a new branch, open a PR.
    Returns (success: bool, upgraded_packages: list[str], pr_url: str)
    """
    repo_url = _config['repo_url']
    token = _config['token']

    owner, repo = _parse_github_url(repo_url)
    if not owner or not repo:
        _add_log('❌ Cannot parse owner/repo from URL', 'error')
        return False, [], ''

    _add_log(f'🔍 Connecting to GitHub API for {owner}/{repo}…', 'info')

    try:
        repo_info = _get_repo_info(owner, repo, token)
    except Exception as e:
        _add_log(f'❌ Failed to reach GitHub API: {e}', 'error')
        return False, [], ''

    default_branch = repo_info.get('default_branch', 'main')
    # Get latest commit SHA
    branch_ref = requests.get(
        f'https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{default_branch}',
        headers=_gh_headers(token),
        timeout=15,
    )
    branch_ref.raise_for_status()
    base_sha = branch_ref.json()['object']['sha']

    # Fetch package.json
    _add_log('📦 Fetching package.json…', 'info')
    pkg_content, pkg_sha = _get_file_content(owner, repo, 'package.json', default_branch, token)
    if pkg_content is None:
        _add_log('⚠️ No package.json found in repository root — skipping', 'warning')
        return False, [], ''

    pkg = _parse_package_json(pkg_content)
    if pkg is None:
        _add_log('❌ package.json is not valid JSON', 'error')
        return False, [], ''

    # Collect all deps
    all_deps = {}
    for section in ('dependencies', 'devDependencies'):
        all_deps.update(pkg.get(section, {}))

    _add_log(f'🔍 Checking {len(all_deps)} package(s) for updates…', 'info')

    outdated = _check_outdated(all_deps)

    if not outdated:
        _add_log('✅ All dependencies are already up to date', 'success')
        return True, [], ''

    pkg_names = [f"{o['name']} ({o['current']} → {o['latest']})" for o in outdated]
    _add_log(f'📦 Found {len(outdated)} outdated package(s):', 'info')
    for o in outdated:
        _add_log(f"   • {o['name']}: {o['current']} → {o['latest']}", 'info')

    # Update package.json content
    new_content, upgraded_names = _update_package_json_content(pkg_content, outdated)

    # Create branch
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    branch_name = f'auto/dependency-update-{timestamp}'
    _add_log(f'🌿 Creating branch {branch_name}…', 'info')
    try:
        _create_branch(owner, repo, branch_name, base_sha, token)
    except Exception as e:
        _add_log(f'❌ Failed to create branch: {e}', 'error')
        return False, [], ''

    # Commit updated package.json
    _add_log('💾 Committing updated package.json…', 'info')
    commit_msg = f'chore(deps): bump {len(outdated)} package(s) to latest versions'
    try:
        _commit_file(owner, repo, 'package.json', commit_msg, new_content, pkg_sha, branch_name, token)
    except Exception as e:
        _add_log(f'❌ Failed to commit file: {e}', 'error')
        return False, [], ''

    # Open PR
    pr_title = f'chore(deps): update {len(outdated)} npm package(s)'
    pr_body = (
        '## Automated Dependency Update\n\n'
        'This PR was created automatically by **OpenClaw Guardian**.\n\n'
        '### Updated Packages\n\n'
        + '\n'.join(f'- `{o["name"]}`: `{o["current"]}` → `{o["latest"]}`' for o in outdated)
        + '\n'
    )
    _add_log('🔗 Opening Pull Request…', 'info')
    try:
        pr_url = _open_pr(owner, repo, branch_name, default_branch, pr_title, pr_body, token)
    except Exception as e:
        _add_log(f'⚠️ PR creation failed (branch was still committed): {e}', 'warning')
        pr_url = ''

    if pr_url:
        _add_log(f'✅ Pull Request created: {pr_url}', 'success')
    else:
        _add_log('⚠️ Could not get PR URL, but commit was pushed', 'warning')

    return True, upgraded_names, pr_url


# ---------------------------------------------------------------------------
# Embedded HTML (self-contained — no template folder needed on Vercel)
# ---------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClaw Guardian — Automated Dependency Updater</title>
    <meta name="description" content="OpenClaw Guardian automatically checks your GitHub repositories for outdated npm packages, upgrades them, and opens pull requests.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0b0d1a;
            --surface: rgba(255,255,255,0.04);
            --border: rgba(255,255,255,0.09);
            --accent: #00d4ff;
            --accent2: #7b2cbf;
            --success: #00c896;
            --danger: #ff5757;
            --warning: #ffb347;
            --text: #e8eaed;
            --muted: #6b7280;
            --radius: 16px;
            --radius-sm: 10px;
        }
        *,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Inter',sans-serif;background:var(--bg);background-image:radial-gradient(ellipse 80% 50% at 20% -10%,rgba(0,212,255,.08) 0%,transparent 50%),radial-gradient(ellipse 60% 40% at 80% 110%,rgba(123,44,191,.08) 0%,transparent 50%);min-height:100vh;color:var(--text);padding:24px 20px 60px}
        .container{max-width:1380px;margin:0 auto}
        header{display:flex;justify-content:space-between;align-items:center;padding:22px 28px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:28px;backdrop-filter:blur(12px)}
        .brand{display:flex;align-items:center;gap:14px}
        .brand-icon{width:44px;height:44px;background:linear-gradient(135deg,var(--accent),var(--accent2));border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1.4rem}
        .brand h1{font-size:1.5rem;font-weight:700;background:linear-gradient(90deg,var(--accent),var(--accent2));-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
        .brand p{font-size:.8rem;color:var(--muted);margin-top:2px}
        .status-pill{display:flex;align-items:center;gap:8px;padding:9px 18px;border-radius:50px;font-size:.82rem;font-weight:600;transition:all .4s}
        .status-dot{width:9px;height:9px;border-radius:50%}
        .status-running{background:rgba(0,200,150,.15);border:1px solid rgba(0,200,150,.4);color:var(--success)}
        .status-running .status-dot{background:var(--success);animation:pulse 1.5s infinite}
        .status-idle{background:rgba(107,114,128,.15);border:1px solid rgba(107,114,128,.3);color:var(--muted)}
        .status-idle .status-dot{background:var(--muted)}
        .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-bottom:22px}
        @media(max-width:900px){.grid-2{grid-template-columns:1fr}}
        .card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:26px;backdrop-filter:blur(10px)}
        .card-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px;padding-bottom:14px;border-bottom:1px solid var(--border)}
        .card-title{font-size:1.05rem;font-weight:600;display:flex;align-items:center;gap:10px}
        .form-group{margin-bottom:16px}
        label{display:block;margin-bottom:7px;font-size:.83rem;color:var(--muted);font-weight:500}
        input[type="text"],input[type="password"],input[type="number"]{width:100%;padding:13px 15px;border:1px solid var(--border);border-radius:var(--radius-sm);background:rgba(255,255,255,.04);color:var(--text);font-size:.95rem;font-family:'Inter',sans-serif;transition:border-color .2s,background .2s}
        input:focus{outline:none;border-color:var(--accent);background:rgba(0,212,255,.06)}
        .btn-row{display:flex;flex-wrap:wrap;gap:10px;margin-top:6px}
        .btn{padding:12px 22px;border:none;border-radius:var(--radius-sm);font-size:.9rem;font-weight:600;cursor:pointer;color:#fff;transition:all .22s;display:inline-flex;align-items:center;gap:7px}
        .btn:hover:not(:disabled){transform:translateY(-2px);filter:brightness(1.1);box-shadow:0 6px 20px rgba(0,0,0,.35)}
        .btn:disabled{opacity:.45;cursor:not-allowed;transform:none}
        .btn-primary{background:linear-gradient(135deg,var(--accent),var(--accent2))}
        .btn-success{background:linear-gradient(135deg,#00c896,#00a878)}
        .btn-danger{background:linear-gradient(135deg,#ff5757,#cc3030)}
        .stats-row{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:22px}
        .stat-box{text-align:center;padding:18px 10px;background:linear-gradient(135deg,rgba(0,212,255,.07),rgba(123,44,191,.07));border:1px solid rgba(0,212,255,.15);border-radius:var(--radius-sm);transition:all .4s}
        .stat-box.updated{animation:flash .6s ease}
        .stat-val{font-size:2.2rem;font-weight:700;color:var(--accent);line-height:1}
        .stat-lbl{font-size:.78rem;color:var(--muted);margin-top:6px}
        .progress-wrap{padding:12px 0 16px;text-align:center}
        .progress-bar{height:3px;background:var(--border);border-radius:3px;overflow:hidden;margin-top:10px}
        .progress-fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2));border-radius:3px;animation:sweep 2s ease-in-out infinite}
        .live-badge{display:flex;align-items:center;gap:6px;font-size:.75rem;color:var(--success);font-weight:500}
        .live-dot{width:7px;height:7px;background:var(--success);border-radius:50%;animation:blink 1.1s infinite}
        .log-box{background:rgba(0,0,0,.35);border-radius:var(--radius-sm);padding:14px;max-height:340px;overflow-y:auto;font-family:'JetBrains Mono',monospace;font-size:.78rem}
        .log-line{padding:5px 10px;margin-bottom:4px;border-radius:6px;border-left:3px solid;background:rgba(255,255,255,.02);line-height:1.5}
        .log-time{color:var(--muted);font-size:.7rem;margin-right:8px}
        .log-info{border-color:var(--accent);color:#cdd9e5}
        .log-success{border-color:var(--success);color:var(--success)}
        .log-error{border-color:var(--danger);color:var(--danger)}
        .log-warning{border-color:var(--warning);color:var(--warning)}
        .history-wrap{max-height:380px;overflow-y:auto}
        .history-empty{text-align:center;padding:48px;color:var(--muted);font-size:.9rem}
        .hist-card{padding:20px 22px;margin-bottom:14px;background:linear-gradient(135deg,rgba(0,212,255,.04),rgba(123,44,191,.04));border:1px solid var(--border);border-radius:var(--radius-sm);animation:slideIn .35s ease}
        .hist-card-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
        .hist-cycle-label{font-size:.9rem;font-weight:600;color:var(--accent);display:flex;align-items:center;gap:8px}
        .hist-meta{display:flex;gap:14px;align-items:center}
        .hist-time{font-size:.77rem;color:var(--muted)}
        .hist-count{font-size:.8rem;font-weight:700;color:var(--success);background:rgba(0,200,150,.12);border:1px solid rgba(0,200,150,.3);padding:3px 10px;border-radius:20px}
        .pkg-tags{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
        .pkg-tag{padding:5px 13px;border-radius:20px;background:rgba(0,212,255,.12);border:1px solid rgba(0,212,255,.25);color:var(--accent);font-size:.8rem;font-weight:500;font-family:'JetBrains Mono',monospace}
        .hist-pr-link a{color:var(--accent2);text-decoration:none;font-size:.83rem;font-weight:500;display:inline-flex;align-items:center;gap:6px}
        .hist-pr-link a:hover{text-decoration:underline}
        .vercel-badge{font-size:.72rem;color:var(--muted);padding:5px 12px;border:1px solid var(--border);border-radius:20px;background:rgba(255,255,255,.03)}
        @keyframes sweep{0%{width:0%}60%{width:75%}100%{width:100%}}
        @keyframes blink{50%{opacity:.3}}
        @keyframes pulse{50%{opacity:.5}}
        @keyframes slideIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
        @keyframes flash{0%,100%{background:rgba(0,212,255,.07)}50%{background:rgba(0,212,255,.25)}}
        .hidden{display:none!important}
        ::-webkit-scrollbar{width:5px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:rgba(255,255,255,.12);border-radius:3px}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="brand">
                <div class="brand-icon">🤖</div>
                <div>
                    <h1>OpenClaw Guardian</h1>
                    <p>Automated GitHub Dependency Updater</p>
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:12px">
                <span class="vercel-badge">☁️ Vercel Serverless</span>
                <div id="statusPill" class="status-pill status-idle">
                    <span class="status-dot"></span>
                    <span id="statusText">Agent Idle</span>
                </div>
            </div>
        </header>

        <!-- Row 1: Config + Control -->
        <div class="grid-2">
            <!-- Configuration -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">⚙️ Configuration</div>
                </div>
                <div class="form-group">
                    <label for="repoUrl">GitHub Repository URL</label>
                    <input type="text" id="repoUrl" placeholder="https://github.com/username/repo">
                </div>
                <div class="form-group">
                    <label for="githubToken">GitHub Personal Access Token</label>
                    <input type="password" id="githubToken" placeholder="ghp_xxxxxxxxxxxxxxxxxxxx">
                </div>
                <div class="form-group">
                    <label for="checkInterval">Check Interval (seconds)</label>
                    <input type="number" id="checkInterval" value="3600" min="60">
                </div>
                <div class="btn-row">
                    <button class="btn btn-primary" id="btnSave" onclick="saveConfig()">💾 Save Configuration</button>
                </div>
            </div>

            <!-- Agent Control + Stats -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">🎮 Agent Control</div>
                </div>
                <div class="stats-row">
                    <div class="stat-box" id="boxCycles">
                        <div class="stat-val" id="statCycles">0</div>
                        <div class="stat-lbl">Cycles Run</div>
                    </div>
                    <div class="stat-box" id="boxPackages">
                        <div class="stat-val" id="statPackages">0</div>
                        <div class="stat-lbl">Packages Upgraded</div>
                    </div>
                    <div class="stat-box" id="boxPRs">
                        <div class="stat-val" id="statPRs">0</div>
                        <div class="stat-lbl">PRs Created</div>
                    </div>
                </div>
                <div id="progressWrap" class="progress-wrap hidden">
                    <span style="font-size:.82rem;color:var(--muted)">⏳ Working — please wait…</span>
                    <div class="progress-bar"><div class="progress-fill"></div></div>
                </div>
                <div class="btn-row">
                    <button class="btn btn-primary" id="btnRunOnce" onclick="runOnce()">⚡ Run Once</button>
                </div>
            </div>
        </div>

        <!-- Row 2: Logs -->
        <div class="card" style="margin-bottom:22px">
            <div class="card-header">
                <div class="card-title">📋 Live Logs</div>
                <div class="live-badge"><span class="live-dot"></span> Live</div>
            </div>
            <div class="log-box" id="logBox">
                <div class="log-line log-info">
                    <span class="log-time">--:--:--</span>
                    Waiting — enter your repo URL and token, then run.
                </div>
            </div>
        </div>

        <!-- Row 3: Upgrade History -->
        <div class="card">
            <div class="card-header">
                <div class="card-title">📜 Upgrade History</div>
                <span id="histNote" style="font-size:.78rem;color:var(--muted)">Cleared on page reload or new config</span>
            </div>
            <div class="history-wrap" id="historyWrap">
                <div class="history-empty" id="histEmpty">No upgrades this session yet</div>
            </div>
        </div>
    </div>

    <script>
        /* OpenClaw Guardian — Frontend Controller
           Uses relative API paths so it works on any domain (localhost or Vercel). */

        const API = '';   // relative — works on localhost AND on Vercel
        let agentRunning = false;

        // ── Helpers ──────────────────────────────────────────────────
        function ts() { return new Date().toLocaleTimeString(); }

        function addLog(msg, level = 'info') {
            if (!msg) return;
            const box = document.getElementById('logBox');
            const line = document.createElement('div');
            line.className = `log-line log-${level}`;
            line.innerHTML = `<span class="log-time">${ts()}</span> ${msg}`;
            box.appendChild(line);
            box.scrollTop = box.scrollHeight;
        }

        function flashBox(id) {
            const el = document.getElementById(id);
            el.classList.remove('updated');
            void el.offsetWidth;
            el.classList.add('updated');
        }

        function showProgress(show) {
            document.getElementById('progressWrap').classList.toggle('hidden', !show);
            const pill = document.getElementById('statusPill');
            const txt  = document.getElementById('statusText');
            if (show) {
                pill.className = 'status-pill status-running';
                txt.textContent = 'Running…';
            } else {
                pill.className = 'status-pill status-idle';
                txt.textContent = 'Agent Idle';
            }
        }

        function setButtonsDisabled(disabled) {
            document.getElementById('btnRunOnce').disabled = disabled;
            document.getElementById('btnSave').disabled = disabled;
        }

        // ── Stats ─────────────────────────────────────────────────────
        function updateStats(s) {
            const cycles   = s.cycles   ?? 0;
            const packages = s.packages ?? 0;
            const prs      = s.prs      ?? 0;
            const prev = {
                c: parseInt(document.getElementById('statCycles').textContent)   || 0,
                p: parseInt(document.getElementById('statPackages').textContent) || 0,
                r: parseInt(document.getElementById('statPRs').textContent)      || 0,
            };
            document.getElementById('statCycles').textContent   = cycles;
            document.getElementById('statPackages').textContent = packages;
            document.getElementById('statPRs').textContent      = prs;
            if (cycles   !== prev.c) flashBox('boxCycles');
            if (packages !== prev.p) flashBox('boxPackages');
            if (prs      !== prev.r) flashBox('boxPRs');
        }

        // ── Upgrade History ───────────────────────────────────────────
        function updateHistory(history) {
            const wrap  = document.getElementById('historyWrap');
            const empty = document.getElementById('histEmpty');
            wrap.querySelectorAll('.hist-card').forEach(el => el.remove());
            if (!history || history.length === 0) {
                empty.style.display = 'block';
                return;
            }
            empty.style.display = 'none';
            const sorted = [...history].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            sorted.forEach((entry, idx) => {
                const pkgs   = entry.packages || [];
                const prUrl  = entry.pr_url   || '';
                const time   = new Date(entry.timestamp).toLocaleTimeString();
                const cycleN = history.length - idx;
                const card   = document.createElement('div');
                card.className = 'hist-card';
                card.innerHTML = `
                    <div class="hist-card-header">
                        <div class="hist-cycle-label">🔄 Cycle ${cycleN}</div>
                        <div class="hist-meta">
                            <span class="hist-time">🕐 ${time}</span>
                            <span class="hist-count">${pkgs.length} package${pkgs.length !== 1 ? 's' : ''}</span>
                        </div>
                    </div>
                    <div class="pkg-tags">${pkgs.map(p => `<span class="pkg-tag">${p}</span>`).join('')}</div>
                    ${prUrl
                        ? `<div class="hist-pr-link"><a href="${prUrl}" target="_blank">🔗 View Pull Request</a></div>`
                        : '<div style="font-size:.77rem;color:var(--muted)">No PR URL recorded</div>'}`;
                wrap.insertBefore(card, wrap.querySelector('.hist-card') || empty);
            });
        }

        // ── Full UI reset ─────────────────────────────────────────────
        function resetUI() {
            updateStats({ cycles: 0, packages: 0, prs: 0 });
            updateHistory([]);
            showProgress(false);
            document.getElementById('logBox').innerHTML =
                `<div class="log-line log-info"><span class="log-time">${ts()}</span> Ready — enter URL and token, then run.</div>`;
        }

        // ── Poll logs from server ─────────────────────────────────────
        let _logOffset = 0;
        async function pollLogs() {
            try {
                const res  = await fetch(`${API}/api/logs?offset=${_logOffset}`);
                const data = await res.json();
                if (data.logs && data.logs.length > 0) {
                    data.logs.forEach(l => addLog(l.message, l.level));
                    _logOffset = data.next_offset;
                }
            } catch { /* ignore */ }
        }

        // ── API calls ─────────────────────────────────────────────────
        async function fetchStatus() {
            try {
                const res  = await fetch(`${API}/api/status`);
                const data = await res.json();
                const url  = data.config?.repoUrl || '';
                document.getElementById('repoUrl').value       = url;
                document.getElementById('checkInterval').value = data.config?.checkInterval || 3600;
                document.getElementById('githubToken').value   = '';  // never prefill
                updateStats(data.stats   || {});
                updateHistory(data.history || []);
            } catch {
                addLog('⚠️ Cannot reach API', 'error');
            }
        }

        async function saveConfig() {
            const url      = document.getElementById('repoUrl').value.trim();
            const token    = document.getElementById('githubToken').value.trim();
            const interval = parseInt(document.getElementById('checkInterval').value) || 3600;
            if (!url)   { addLog('❌ Repository URL is required', 'error'); return; }
            if (!token) { addLog('❌ GitHub Token is required', 'error'); return; }
            if (!url.startsWith('https://github.com/')) {
                addLog('❌ URL must start with https://github.com/', 'error'); return;
            }
            document.getElementById('btnSave').disabled = true;
            try {
                const res  = await fetch(`${API}/api/config`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ repoUrl: url, githubToken: token, checkInterval: interval }),
                });
                const data = await res.json();
                if (data.success) {
                    resetUI();
                    _logOffset = 0;
                    addLog('✅ Configuration saved — ready for a fresh run', 'success');
                } else {
                    addLog(`❌ ${data.message || 'Failed to save config'}`, 'error');
                }
            } catch (err) {
                addLog(`❌ Save failed: ${err}`, 'error');
            }
            document.getElementById('btnSave').disabled = false;
        }

        async function runOnce() {
            const url   = document.getElementById('repoUrl').value.trim();
            const token = document.getElementById('githubToken').value.trim();
            if (!url || !token) {
                addLog('❌ Fill in URL and Token then click Save Configuration first', 'error');
                return;
            }
            // Save first
            await saveConfig();
            _logOffset = 0;

            showProgress(true);
            setButtonsDisabled(true);

            // Start log polling while the run-once call is in flight
            const pollInterval = setInterval(pollLogs, 1500);

            try {
                const res  = await fetch(`${API}/api/run-once`, { method: 'POST' });
                const data = await res.json();
                clearInterval(pollInterval);
                // Drain remaining logs
                await pollLogs();

                if (!data.success) {
                    addLog(`❌ ${data.message}`, 'error');
                } else {
                    if (data.stats)   updateStats(data.stats);
                    if (data.history) updateHistory(data.history);
                }
            } catch (err) {
                clearInterval(pollInterval);
                addLog(`❌ ${err}`, 'error');
            } finally {
                showProgress(false);
                setButtonsDisabled(false);
            }
        }

        // ── Bootstrap ─────────────────────────────────────────────────
        resetUI();
        fetchStatus();
    </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return HTML, 200, {'Content-Type': 'text/html'}


@app.route('/api/status')
def get_status():
    return jsonify({
        'running': False,
        'config': {
            'repoUrl':         _config['repo_url'],
            'tokenConfigured': bool(_config['token']),
            'checkInterval':   _config['check_interval'],
        },
        'stats':   _session,
        'history': _session['history'],
    })


@app.route('/api/config', methods=['POST'])
def save_config():
    data      = request.json or {}
    new_url   = (data.get('repoUrl',     '') or '').strip()
    new_token = (data.get('githubToken', '') or '').strip()
    interval  = int(data.get('checkInterval', 3600))

    if not new_url:
        return jsonify({'success': False, 'message': 'Repository URL is required'})
    if not new_token:
        return jsonify({'success': False, 'message': 'GitHub Token is required'})
    if not new_url.startswith('https://github.com/'):
        return jsonify({'success': False, 'message': 'Invalid URL — must start with https://github.com/'})
    if interval < 60:
        return jsonify({'success': False, 'message': 'Interval must be at least 60 seconds'})

    _config['repo_url']       = new_url
    _config['token']          = new_token
    _config['check_interval'] = interval
    _reset_session()
    _add_log('✅ Configuration saved — ready for a fresh run', 'success')
    return jsonify({'success': True})


@app.route('/api/run-once', methods=['POST'])
def run_once():
    if not _config['repo_url']:
        return jsonify({'success': False, 'message': 'GitHub Repository URL is not configured'})
    if not _config['token']:
        return jsonify({'success': False, 'message': 'GitHub Token is not configured'})

    _reset_session()
    _add_log('🔄 Starting dependency check…', 'info')

    try:
        success, upgraded_packages, pr_url = _run_cycle()
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _add_log(f'❌ Unexpected error: {e}', 'error')
        return jsonify({'success': False, 'message': str(e)})

    if success and upgraded_packages:
        _session['cycles']   += 1
        _session['prs']      += (1 if pr_url else 0)
        _session['packages'] += len(upgraded_packages)
        hist_entry = {
            'timestamp': datetime.now().isoformat(),
            'packages':  upgraded_packages,
            'pr_url':    pr_url,
        }
        _session['history'].append(hist_entry)
        _add_log(f'🏁 Done — {len(upgraded_packages)} package(s) upgraded', 'success')
    else:
        _add_log('🏁 Done — no changes needed', 'info')

    return jsonify({
        'success': True,
        'stats':   {
            'cycles':   _session['cycles'],
            'prs':      _session['prs'],
            'packages': _session['packages'],
        },
        'history': _session['history'],
    })


@app.route('/api/logs')
def get_logs():
    """Polling endpoint for frontend to fetch new log lines."""
    try:
        offset = int(request.args.get('offset', 0))
    except ValueError:
        offset = 0
    new_logs = _logs[offset:]
    return jsonify({
        'logs':        new_logs,
        'next_offset': offset + len(new_logs),
        'total':       len(_logs),
    })


# ---------------------------------------------------------------------------
# Vercel serverless handler
# ---------------------------------------------------------------------------
# Vercel looks for a module-level `app` (or `handler`) WSGI callable.
# We expose `app` which is already defined above.
handler = app
