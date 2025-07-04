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
        <h2>activations</h2>
        <canvas id="activations_graph" width="600" height="300"></canvas>
    </div>

    <div class="section">
        <h2>Loss Graph</h2>
        <canvas id="loss_graph" width="600" height="300"></canvas>
    </div>

    <div class="section">
        <h2>dW</h2>
        <canvas id="dW_graph" width="600" height="300"></canvas>
    </div>

    <div class="section">
        <h2>dB</h2>
        <canvas id="dB_graph" width="600" height="300"></canvas>
    </div>









    <script>
        const graphState = {};  // Track lines per canvas for hover

        function drawGraphMulti(canvasId, lines, labelY = "") {
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;
            const ctx = canvas.getContext("2d");

            const width = canvas.width;
            const height = canvas.height;
            const padding = 50;

            const graphWidth = width - 2 * padding;
            const graphHeight = height - 2 * padding;

            // Flatten all data for bounds
            const allData = lines.flatMap(line => line.data);
            if (allData.length < 2) return;

            const maxY = Math.max(...allData);
            const minY = Math.min(...allData);
            const range = maxY - minY || 1e-6;

            ctx.clearRect(0, 0, width, height);

            // Draw grid and Y labels
            ctx.strokeStyle = "#ddd";
            ctx.fillStyle = "#666";
            ctx.font = "12px sans-serif";
            ctx.textAlign = "right";

            const yTicks = 5;
            for (let i = 0; i <= yTicks; i++) {
                const norm = i / yTicks;
                const y = padding + norm * graphHeight;
                const value = (maxY - norm * range).toFixed(2);
                ctx.beginPath();
                ctx.moveTo(padding, y);
                ctx.lineTo(width - padding, y);
                ctx.stroke();
                ctx.fillText(value, padding - 10, y + 4);
            }

            // Draw X ticks
            const xTicks = 5;
            ctx.textAlign = "center";
            const maxLen = Math.max(...lines.map(l => l.data.length));
            for (let i = 0; i <= xTicks; i++) {
                const frac = i / xTicks;
                const x = padding + frac * graphWidth;
                const step = Math.round(frac * (maxLen - 1));
                ctx.beginPath();
                ctx.moveTo(x, padding);
                ctx.lineTo(x, height - padding);
                ctx.stroke();
                ctx.fillText(step, x, height - padding + 20);
            }

            graphState[canvasId] = {
                lines,
                maxY,
                minY,
                padding,
                width,
                height
            };

            // Plot each line
            lines.forEach(({ data, color }) => {
                ctx.beginPath();
                for (let i = 0; i < data.length; i++) {
                    const x = padding + (i / (data.length - 1)) * graphWidth;
                    const norm = (data[i] - minY) / range;
                    const y = padding + (1 - norm) * graphHeight;
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }
                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                ctx.stroke();
            });

            // Draw axes
            ctx.strokeStyle = "#444";
            ctx.beginPath();
            ctx.moveTo(padding, padding);
            ctx.lineTo(padding, height - padding);
            ctx.lineTo(width - padding, height - padding);
            ctx.stroke();

            // Label Y-axis
            ctx.fillStyle = "#000";
            ctx.font = "14px sans-serif";
            ctx.save();
            ctx.translate(15, height / 2);
            ctx.rotate(-Math.PI / 2);
            ctx.fillText(labelY, 0, 0);
            ctx.restore();
        }


        document.querySelectorAll("canvas").forEach(canvas => {
            canvas.addEventListener("mousemove", (event) => handleMultiHover(canvas, event));
        });

        function handleMultiHover(canvas, event) {
            const ctx = canvas.getContext("2d");
            const { lines, maxY, minY, padding, width, height } = graphState[canvas.id] || {};
            if (!lines || lines.length === 0) return;

            const graphWidth = width - 2 * padding;
            const graphHeight = height - 2 * padding;

            const rect = canvas.getBoundingClientRect();
            const xMouse = event.clientX - rect.left;

            const maxLen = Math.max(...lines.map(l => l.data.length));
            const index = Math.round((xMouse - padding) / graphWidth * (maxLen - 1));
            if (index < 0 || index >= maxLen) return;

            ctx.clearRect(0, 0, width, height);
            drawGraphMulti(canvas.id, lines); // Redraw everything

            const x = padding + (index / (maxLen - 1)) * graphWidth;

            // Crosshair
            ctx.strokeStyle = "red";
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            ctx.moveTo(x, padding);
            ctx.lineTo(x, height - padding);
            ctx.stroke();
            ctx.setLineDash([]);

            // Tooltip
            const tooltipLines = [`Epoch: ${index}`];
            let yTooltip = padding;

            lines.forEach(({ data, color }, i) => {
                if (index < data.length) {
                    const value = data[index];
                    const norm = (value - minY) / (maxY - minY || 1e-6);
                    const y = padding + (1 - norm) * graphHeight;

                    tooltipLines.push(`${color}: ${value.toFixed(4)}`);
                    yTooltip = y;
                }
            });

            const tooltip = tooltipLines.join(" | ");
            ctx.fillStyle = "#fff";
            const tooltipWidth = ctx.measureText(tooltip).width + 10;
            ctx.fillRect(x + 8, yTooltip - 24, tooltipWidth, 20);
            ctx.strokeStyle = "#000";
            ctx.strokeRect(x + 8, yTooltip - 24, tooltipWidth, 20);
            ctx.fillStyle = "#000";
            ctx.fillText(tooltip, x + 13, yTooltip - 10);
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
                        drawGraphMulti("loss_graph", [
                            { data: data.history || [], color: "blue" },
                        ], "Loss");
                        drawGraphMulti("dW_graph", [
                            { data: data.dW_history_max || [], color: "blue" },
                            { data: data.dW_history_mean || [], color: "orange" },
                            { data: data.dW_history_min || [], color: "red" }
                        ], "dW");
                        drawGraphMulti("dB_graph", [
                            { data: data.dB_history_max || [], color: "blue" },
                            { data: data.dB_history_mean || [], color: "orange" },
                            { data: data.dB_history_min || [], color: "red" }
                        ], "dB");
                        drawGraphMulti("activations_graph", [
                            { data: data.act_history_max || [], color: "blue" },
                            { data: data.act_history_mean || [], color: "orange" },
                            { data: data.act_history_min || [], color: "red" }
                        ], "activations");
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
