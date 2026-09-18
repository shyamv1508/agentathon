import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starter.schemas import Question
from stage1.atlas import Atlas
from stage1.graph import StudyGraph
from stage2.crew import ReviewCrew
import os

DATA_DIR = ROOT / "hackathon-data"
_GRAPH = StudyGraph(str(DATA_DIR))
_ATLAS = Atlas(_GRAPH)
_STATS = None

app = FastAPI(title="ATLAS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_stats():
    global _STATS
    if _STATS is None:
        _STATS = _GRAPH.build(12)
    return _STATS


def answer_question(text: str, cut: int):
    if cut < 1 or cut > 12:
        raise ValueError("cut must be between 1 and 12")
    if _GRAPH.cut != cut:
        _GRAPH.build(cut)
    else:
        _GRAPH.ensure_fresh()
    question = Question(question_id="web", kind="lookup", text=text, cut=cut)
    return _ATLAS.answer(question).model_dump()


@app.get("/")
def home():
    return FileResponse(ROOT / "index.html")


@app.get("/styles.css")
def styles():
    return FileResponse(ROOT / "styles.css")


@app.get("/app.js")
def javascript():
    return FileResponse(ROOT / "app.js")


@app.get("/api")
def api_home():
    return {"status": "ok", "service": "ATLAS"}


@app.get("/api/stats")
def stats(cut: int = 12):
    if cut < 1 or cut > 12:
        raise HTTPException(status_code=400, detail="cut must be between 1 and 12")
    return _GRAPH.build(cut)


@app.get("/api/query")
def query(q: str = "", cut: int = 12):
    question = q.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    try:
        return answer_question(question, cut)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.get("/api/cycle")
def cycle(cut: int = 12):
    if cut < 1 or cut > 12:
        raise HTTPException(status_code=400, detail="cut must be between 1 and 12")
    protocol = 3 if cut >= 9 else 2 if cut >= 6 else 1
    try:
        os.environ.setdefault("STAGE2_MEMORY_PATH", "/tmp/atlas_stage2_memory.json")
        os.environ.setdefault("STAGE2_TRACE_PATH", "/tmp/atlas_stage2_trace.jsonl")
        crew = ReviewCrew("", "", "", _ATLAS)
        report = crew.run_cycle(cut, protocol)
        return report.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
