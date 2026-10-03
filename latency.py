import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path

DATA = json.loads((Path(__file__).parent / "q-vercel-latency.json").read_text())

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
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
        if payload is not None:
            body = json.dumps(payload).encode()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.end_headers()

    def do_OPTIONS(self):
        self._send(204)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            regions = body.get("regions", [])
            threshold = float(body.get("threshold_ms", 0))
        except Exception:
            return self._send(400, {"error": "invalid JSON body"})
        metrics = compute(regions, threshold)
        # Per-region keys at top level, plus the same data under "regions".
        self._send(200, {**metrics, "regions": metrics})
