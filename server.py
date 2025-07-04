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
        const canvas = document.getElementById("graph");
        const ctx = canvas.getContext("2d");
        let currentHistory = [];

        canvas.addEventListener("mousemove", handleHover);

        function drawGraph(history) {
            currentHistory = history;  // Store for hover
            const width = canvas.width;
            const height = canvas.height;

            ctx.clearRect(0, 0, width, height);

            if (history.length < 2) return;

            const padding = 50;
            const graphWidth = width - padding * 2;
            const graphHeight = height - padding * 2;

            const maxLoss = Math.max(...history);
            const minLoss = Math.min(...history);
            const range = maxLoss - minLoss || 1e-6;

            // Grid + Y-axis labels
            ctx.strokeStyle = "#ddd";
            ctx.fillStyle = "#666";
            ctx.font = "12px sans-serif";
            ctx.textAlign = "right";

            const yTicks = 5;
            for (let i = 0; i <= yTicks; i++) {
                const norm = i / yTicks;
                const y = padding + norm * graphHeight;
                const value = (maxLoss - norm * range).toFixed(2);

                ctx.beginPath();
                ctx.moveTo(padding, y);
                ctx.lineTo(width - padding, y);
                ctx.stroke();

                ctx.fillText(value, padding - 5, y + 4);
            }

            // Grid + X-axis labels
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

                ctx.fillText(step, x, height - padding + 20);
            }

            // Line plot
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

            // Axes
            ctx.strokeStyle = "#444";
            ctx.beginPath();
            ctx.moveTo(padding, padding);
            ctx.lineTo(padding, height - padding);
            ctx.lineTo(width - padding, height - padding);
            ctx.stroke();

            // Axis labels
            ctx.fillStyle = "#000";
            ctx.font = "14px sans-serif";

            ctx.fillText("Epoch", width / 2, height - 10);

            ctx.save();
            ctx.translate(15, height / 2);
            ctx.rotate(-Math.PI / 2);
            ctx.fillText("Loss", 0, 0);
            ctx.restore();
        }

        function handleHover(event) {
            if (currentHistory.length < 2) return;

            const rect = canvas.getBoundingClientRect();
            const xMouse = event.clientX - rect.left;
            const yMouse = event.clientY - rect.top;

            const padding = 50;
            const graphWidth = canvas.width - padding * 2;
            const graphHeight = canvas.height - padding * 2;

            const index = Math.round((xMouse - padding) / graphWidth * (currentHistory.length - 1));
            if (index < 0 || index >= currentHistory.length) return;

            const maxLoss = Math.max(...currentHistory);
            const minLoss = Math.min(...currentHistory);
            const range = maxLoss - minLoss || 1e-6;

            const x = padding + (index / (currentHistory.length - 1)) * graphWidth;
            const norm = (currentHistory[index] - minLoss) / range;
            const y = padding + (1 - norm) * graphHeight;

            // Redraw graph
            drawGraph(currentHistory);

            // Crosshair
            ctx.strokeStyle = "red";
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            ctx.moveTo(x, padding);
            ctx.lineTo(x, canvas.height - padding);
            ctx.moveTo(padding, y);
            ctx.lineTo(canvas.width - padding, y);
            ctx.stroke();
            ctx.setLineDash([]);

            // Tooltip
            const tooltip = `Epoch: ${index} | Loss: ${currentHistory[index].toFixed(4)}`;
            ctx.fillStyle = "#fff";
            ctx.fillRect(x + 8, y - 24, ctx.measureText(tooltip).width + 10, 20);
            ctx.strokeStyle = "#000";
            ctx.strokeRect(x + 8, y - 24, ctx.measureText(tooltip).width + 10, 20);
            ctx.fillStyle = "#000";
            ctx.fillText(tooltip, x + 13, y - 10);
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
