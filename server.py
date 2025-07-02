# server.py
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from functools import partial
import numpy as np

class DashboardHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, shared_state=None, **kwargs):
        self.shared_state = shared_state
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self._render_dashboard().encode())

        elif self.path == "/vars":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()

            # Convert numpy types to native Python
            clean = self._sanitize(self.shared_state)
            self.wfile.write(json.dumps(clean).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def _sanitize(self, state):
        result = {}
        for k, v in state.items():
            if isinstance(v, np.generic):
                result[k] = v.item()
            elif isinstance(v, np.ndarray):
                result[k] = v.tolist()
            else:
                result[k] = v
        return result

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
        <canvas id="graph" width="600" height="300"></canvas>
    </div>

    <script>
        const ctx = document.getElementById("graph").getContext("2d");
        function drawGraph(history) {
            const canvas = document.getElementById("graph");
            const ctx = canvas.getContext("2d");

            const width = canvas.width;
            const height = canvas.height;

            ctx.clearRect(0, 0, width, height);

            if (history.length < 2) return;

            const maxLoss = Math.max(...history);
            const minLoss = Math.min(...history);
            const range = maxLoss - minLoss || 1e-6;

            const padding = 40;
            const graphWidth = width - padding * 2;
            const graphHeight = height - padding * 2;

            // Draw Y axis grid + labels
            ctx.strokeStyle = "#ddd";
            ctx.fillStyle = "#666";
            ctx.font = "12px sans-serif";
            ctx.textAlign = "right";

            const yTicks = 5;
            for (let i = 0; i <= yTicks; i++) {
                const norm = i / yTicks;
                const y = padding + norm * graphHeight;
                const value = (maxLoss - norm * range).toFixed(4);

                ctx.beginPath();
                ctx.moveTo(padding, y);
                ctx.lineTo(width - padding, y);
                ctx.stroke();

                ctx.fillText(value, padding - 5, y + 4);
            }

            // Draw X axis grid + labels
            const xTicks = 5;
            ctx.textAlign = "center";
            for (let i = 0; i <= xTicks; i++) {
                const frac = i / xTicks;
                const x = padding + frac * graphWidth;
                const step = Math.round(frac * (history.length - 1));

                ctx.beginPath();
                ctx.moveTo(x, padding);
                ctx.lineTo(x, height - padding);
                ctx.stroke();

                ctx.fillText(step, x, height - padding + 15);
            }

            // Draw line plot
            ctx.beginPath();
            for (let i = 0; i < history.length; i++) {
                const x = padding + (i / (history.length - 1)) * graphWidth;
                const norm = (history[i] - minLoss) / range;
                const y = padding + (1 - norm) * graphHeight;

                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.strokeStyle = "blue";
            ctx.lineWidth = 2;
            ctx.stroke();

            // Draw axes
            ctx.strokeStyle = "#444";
            ctx.beginPath();
            ctx.moveTo(padding, padding);
            ctx.lineTo(padding, height - padding);
            ctx.lineTo(width - padding, height - padding);
            ctx.stroke();
        }

        function updateDashboard() {
            fetch("/vars")
                .then(res => res.json())
                .then(data => {
                    document.getElementById("variables").innerHTML = `
                        <b>Epoch:</b> ${data.epoch} <br/>
                        <b>dW:</b> ${data.current_dW} <br/>
                        <b>Loss:</b> ${data.loss.toFixed(6)}
                    `;
                    document.getElementById("warnings").innerHTML = data.warnings.map(w => `<li>${w}</li>`).join("");
                    document.getElementById("log").innerText = data.log.slice(-20).join("\\n");
                    if (data.history && data.history.length > 1) {
                        drawGraph(data.history);
                    }
                });
        }

        setInterval(updateDashboard, 1000);
        updateDashboard();
    </script>
</body>
</html>
        """

def start_dashboard_server(shared_state, port=8010):
    handler_with_state = partial(DashboardHandler, shared_state=shared_state)
    server = HTTPServer(('127.0.0.1', port), handler_with_state)
    print(f"🟢 Dashboard running at http://127.0.0.1:{port}")
    server.serve_forever()
