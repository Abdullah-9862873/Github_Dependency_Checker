import os
from flask import Flask, jsonify, request, Response

app = Flask(__name__)

API_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(API_DIR)

session = {
    'cycles': 0,
    'prs': 0,
    'packages': 0,
    'history': [],
}

HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <title>OpenClaw Guardian</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <h1>OpenClaw Guardian</h1>
    <p>Loading...</p>
    <script>
        document.body.innerHTML = '<h1>OpenClaw Guardian</h1><p>App loading... API: ' + window.location.origin + '</p>';
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return HTML_CONTENT, 200, {'Content-Type': 'text/html'}

@app.route('/api/status')
def get_status():
    return jsonify({
        'running': False,
        'config': {'repoUrl': '', 'tokenConfigured': False, 'checkInterval': 3600},
        'stats': session,
        'history': session['history'],
    })

@app.route('/api/config', methods=['POST'])
def save_config():
    return jsonify({'success': True, 'message': 'Config saved'})

@app.route('/api/run-once', methods=['POST'])
def run_once():
    return jsonify({'success': True, 'message': 'Demo mode'})

@app.route('/api/events')
def events():
    def _generate():
        yield "data: {}\n\n"
    return Response(_generate(), mimetype='text/event-stream')

handler = app
