import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starter.schemas import Question
from stage1.atlas import Atlas
from stage1.graph import StudyGraph

DATA_DIR = ROOT / "hackathon-data"
_GRAPH = StudyGraph(str(DATA_DIR))
_ATLAS = Atlas(_GRAPH)
_STATS = None


def get_stats():
    global _STATS
    if _STATS is None:
        _STATS = _GRAPH.build(12)
    return _STATS


def answer_question(text: str, cut: int):
    if _GRAPH.cut != cut:
        _GRAPH.build(cut)
    else:
        _GRAPH.ensure_fresh()
    question = Question(question_id="web", kind="lookup", text=text, cut=cut)
    return _ATLAS.answer(question).model_dump()


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api":
            self._send(404, {"error": "Not found"})
            return

        params = parse_qs(parsed.query)
        if params.get("stats", ["0"])[0] == "1":
            self._send(200, get_stats())
            return

        question = params.get("q", [""])[0].strip()
        try:
            cut = int(params.get("cut", ["12"])[0])
        except ValueError:
            cut = 12
        if not question:
            self._send(400, {"error": "Question is required"})
            return
        try:
            self._send(200, answer_question(question, cut))
        except Exception as exc:
            self._send(500, {"error": str(exc)})


def main():
    from http.server import HTTPServer
    HTTPServer(("127.0.0.1", 8000), handler).serve_forever()


if __name__ == "__main__":
    main()
