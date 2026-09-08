"""A fake OpenAI compatible chat completions server for tests.

It answers by recognising which HSL prompt it received: the planner (a
family document plan), the persona elicitation (an action in the expected
JSON), the briefing drafter (the deterministic text back, optionally with a
rogue number to prove the critic rejects it) and ASK (a phrased answer
carrying a marker). Runs on the loopback, so the model layer's https rule
permits it.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _Handler(BaseHTTPRequestHandler):
    calls = []
    rogue_briefing = False

    def log_message(self, *args):  # silence
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        msgs = body.get("messages", [])
        system = next((m["content"] for m in msgs if m["role"] == "system"), "")
        user = next((m["content"] for m in msgs if m["role"] == "user"), "")
        _Handler.calls.append({"system": system[:60], "user": user[:80], "path": self.path,
                               "auth": self.headers.get("Authorization", "")})
        if "battery parameters" in system:                        # planner
            text = json.dumps({"families": [
                {"name": "planned_vendor_fault", "note": "the case the model planned", "seeds": 1,
                 "vendor_shares": [0.40, 0.15], "vendor_rhos": [0.85, 0.30], "shock_size": 0.05,
                 "vendor_fault_time": 300},
                {"name": "planned_out_of_bounds", "seeds": 1, "vendor_shares": [0.9], "vendor_rhos": [2.0]},
                {"name": "quiet", "seeds": 1}], "rationale": "one faulty vendor family, one invalid, one reserved"})
        elif "trading agent built on a foundation model" in system:     # persona elicitation
            text = json.dumps({"table": [["strong_sell", "sell", "hold", "buy", "strong_buy"]] * 3})
        elif "supervisory briefings" in system:                    # drafter: a short draft built from the artefacts
            try:
                art = json.loads(user.split("Artefacts JSON:\n", 1)[1].rsplit("\n\nDraft a one page", 1)[0])
                gap = art["decision_gap"]["decision_gap"]
                text = f"# Model draft\n\nThe decision gap is {gap:.2f} on this battery."
            except Exception:  # noqa: BLE001
                text = "# Model draft\n\nNo figures."
            if _Handler.rogue_briefing:
                text += "\n\nThe decision gap is 0.9999 according to me."
        elif "Herding Scenario Lab supervisory terminal" in system:  # ASK
            text = "[model phrased] " + (user.split("DETERMINISTIC ANSWER (computed from the artefacts):\n")[-1].split("\n\nQUESTION:")[0][:200])
        else:
            text = "unrecognised prompt"
        out = json.dumps({"choices": [{"message": {"role": "assistant", "content": text}}],
                          "model": body.get("model")}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


class FakeModelServer:
    def __init__(self):
        self.httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}/v1"

    def start(self):
        _Handler.calls.clear()
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()

    @property
    def calls(self):
        return list(_Handler.calls)

    @staticmethod
    def set_rogue_briefing(flag):
        _Handler.rogue_briefing = flag


if __name__ == "__main__":
    import time
    s = FakeModelServer().start()
    print(s.base, flush=True)
    while True:
        time.sleep(3600)
