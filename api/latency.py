import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path

DATA = json.loads((Path(__file__).parent / "q-vercel-latency.json").read_text())

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin, X-Requested-With",
    "Access-Control-Expose-Headers": "*",
    "Access-Control-Max-Age": "86400",
}


def percentile(values, p):
    """Linear-interpolation percentile (same as numpy's default)."""
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def compute(regions, threshold):
    out = {}
    for r in regions:
        rows = [x for x in DATA if x["region"] == r]
        if not rows:
            continue
        lat = [x["latency_ms"] for x in rows]
        upt = [x["uptime_pct"] for x in rows]
        out[r] = {
            "avg_latency": round(sum(lat) / len(lat), 4),
            "p95_latency": round(percentile(lat, 95), 4),
            "avg_uptime": round(sum(upt) / len(upt), 4),
            "breaches": sum(1 for v in lat if v > threshold),
        }
    return out


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload=None):
        self.send_response(status)
        for k, v in CORS.items():
            self.send_header(k, v)
        body = json.dumps(payload).encode() if payload is not None else b""
        if payload is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self):
        requested = self.headers.get("Access-Control-Request-Headers", "")
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            requested or "Content-Type, Authorization, Accept, Origin, X-Requested-With",
        )
        self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self._send(200, {"status": "ok", "usage": "POST {regions, threshold_ms}"})

    def do_HEAD(self):
        self._send(200)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            regions = body.get("regions", [])
            threshold = float(body.get("threshold_ms", 0))
            metrics = compute(regions, threshold)
            self._send(200, {**metrics, "regions": metrics})
        except Exception as e:
            self._send(400, {"error": str(e)})
