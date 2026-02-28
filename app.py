from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"status": "ok", "message": "OpenClaw Guardian"})

@app.route('/api/status')
def status():
    return jsonify({
        'running': False,
        'config': {'repoUrl': '', 'tokenConfigured': False, 'checkInterval': 3600},
        'stats': {'cycles': 0, 'prs': 0, 'packages': 0},
        'history': []
    })
