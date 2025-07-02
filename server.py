import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from functools import partial
import threading
import time
import numpy as np

class DashboardHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, shared_state=None, **kwargs):
        self.shared_state = shared_state
        super().__init__(*args, **kwargs)

    def do_GET(self):
        print(f"🟡 Received GET: {self.path}")
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self._render_dashboard().encode())
        elif self.path == "/vars":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            # Clean up numpy types for JSON
            clean = json.dumps(self._sanitize(self.shared_state))
            self.wfile.write(clean.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def _render_dashboard(self):
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Training Monitor</title>
    <style>
        body { font-family: sans-serif; margin: 2em; }
        .section { margin-bottom: 2em; }
        #graph { width: 600px; height: 300px; border: 1px solid #ccc; }
        pre { background: #f0f0f0; padding: 1em; overflow: auto; height: 200px; }
    </style>
</head>
<body>
    <h1>Live Training Monitor</h1>

    <div class="section">
        <h2>Variables</h2>
        <div id="variables"></div>
    </div>

    <div class="section">
        <h2>Warnings</h2>
        <ul id="warnings"></ul>
    </div>

    <div class="section">
        <h2>Log</h2>
        <pre id="log"></pre>
    </div>

    <div class="section">
        <h2>Loss Graph</h2>
        <canvas id="graph"></canvas>
    </div>

    <script>
        const graphCtx = document.getElementById("graph").getContext("2d");
        function drawGraph(history) {
            graphCtx.clearRect(0, 0, 600, 300);
            graphCtx.beginPath();
            graphCtx.moveTo(0, 300 - history[0] * 300);
            for (let i = 1; i < history.length; i++) {
                let x = (i / history.length) * 600;
                let y = 300 - history[i] * 300;
                graphCtx.lineTo(x, y);
            }
            graphCtx.strokeStyle = "blue";
            graphCtx.stroke();
        }

        function updateDashboard() {
            fetch("/vars")
                .then(res => res.json())
                .then(data => {
                    document.getElementById("variables").innerHTML = `
                        <b>Epoch:</b> ${data.epoch} <br/>
                        <b>Loss:</b> ${data.loss.toFixed(5)}
                    `;

                    document.getElementById("warnings").innerHTML = data.warnings.map(w => `<li>${w}</li>`).join("");

                    document.getElementById("log").innerText = data.log.slice(-20).join("\\n");

                    if (data.history && data.history.length > 1)
                        drawGraph(data.history);
                });
        }

        setInterval(updateDashboard, 1000);  // refresh every second
        updateDashboard(); // initial load
    </script>
</body>
</html>
        """

    def _sanitize(self, state):
        clean = {}
        for k, v in state.items():
            if isinstance(v, (np.generic,)):
                clean[k] = v.item()
            elif isinstance(v, np.ndarray):
                clean[k] = v.tolist()
            else:
                clean[k] = v
        return clean



class VarHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, shared_state=None, **kwargs):
        self.shared_state = shared_state
        super().__init__(*args, **kwargs)

    def do_GET(self):
        print(f"🟡 Received GET: {self.path}")
        if self.path == "/vars":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            cleaned = {k: (v.item() if isinstance(v, (np.generic,)) else v)
                for k, v in self.shared_state.items()}

            self.wfile.write(json.dumps(cleaned).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

# ✅ Start server using functools.partial to pass shared_state
def start_server(shared_state, port=8010):
    handler_with_state = partial(VarHandler, shared_state=shared_state)
    server = HTTPServer(('127.0.0.1', port), handler_with_state)
    print(f"🟢 Server running at http://127.0.0.1:{port}/vars")
    server.serve_forever()