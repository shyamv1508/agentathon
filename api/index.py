import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
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
_CREW = None



class GateDecision(BaseModel):
    cut: int
    code: str
    usubjid: str | None = None
    decision: str
    reason: str = ""

app = FastAPI(title="ATLAS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def get_crew():
    global _CREW
    if _CREW is None:
        os.environ.setdefault("STAGE2_MEMORY_PATH", "/tmp/atlas_stage2_memory.json")
        os.environ.setdefault("STAGE2_TRACE_PATH", "/tmp/atlas_stage2_trace.jsonl")
        _CREW = ReviewCrew("", "", "", _ATLAS)
    return _CREW


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
    answer = _ATLAS.answer(question)
    # Keep the web UI evidence-first even when a query branch returns subject IDs
    # without attaching its record refs.
    if answer.answer and not answer.evidence:
        subjects = [x for x in answer.answer if isinstance(x, str) and x.startswith("042-")]
        if subjects:
            from stage1.evidence import refs
            rows = []
            for subject in subjects:
                patient = _GRAPH.patient360(subject)
                for domain_rows in patient.get("domains", {}).values():
                    rows.extend(domain_rows)
            answer.evidence = refs(rows)
    return answer.model_dump()


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
    return {"status": "ok", "service": "ATLAS", "version": "stage2-live"}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ATLAS", "graph_loaded": _GRAPH.cut is not None}


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



@app.get("/api/patient/{usubjid}")
def patient(usubjid: str, cut: int = 12):
    if cut < 1 or cut > 12:
        raise HTTPException(status_code=400, detail="cut must be between 1 and 12")
    if _GRAPH.cut != cut:
        _GRAPH.build(cut)
    return _GRAPH.patient360(usubjid)


@app.get("/api/lookup")
def lookup(type: str = "", value: str = "", cut: int = 12):
    if cut < 1 or cut > 12:
        raise HTTPException(status_code=400, detail="cut must be between 1 and 12")
    if not value.strip():
        raise HTTPException(status_code=400, detail="Lookup value is required")
    if _GRAPH.cut != cut:
        _GRAPH.build(cut)
    needle = value.strip().lower()
    if type.lower() == "medication":
        rows = _GRAPH.rows.get("CM", [])
        matches = [r for r in rows if needle in str(r.get("CMTRT", "")).lower()]
    elif type.lower() == "disease":
        rows = _GRAPH.rows.get("MH", [])
        matches = [r for r in rows if needle in str(r.get("MHTERM", "")).lower()]
    elif type.lower() == "adverse_event":
        rows = _GRAPH.rows.get("AE", [])
        matches = [r for r in rows if needle in str(r.get("AETERM", "")).lower()]
    else:
        raise HTTPException(status_code=400, detail="type must be medication, disease, or adverse_event")
    subjects = sorted({r.get("USUBJID") for r in matches if r.get("USUBJID")})
    return {"type": type, "value": value, "subjects": subjects, "count": len(subjects), "evidence": [
        {"domain": r.get("_domain"), "usubjid": r.get("USUBJID"), "seq": r.get("_seq")} for r in matches
    ]}

@app.get("/api/cycle")
def cycle(cut: int = 12):
    if cut < 1 or cut > 12:
        raise HTTPException(status_code=400, detail="cut must be between 1 and 12")
    protocol = 3 if cut >= 9 else 2 if cut >= 6 else 1
    try:
        report = get_crew().run_cycle(cut, protocol)
        return report.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/gate")
def gate(payload: GateDecision):
    if payload.cut < 1 or payload.cut > 12:
        raise HTTPException(status_code=400, detail="cut must be between 1 and 12")
    try:
        protocol = 3 if payload.cut >= 9 else 2 if payload.cut >= 6 else 1
        if _GRAPH.cut != payload.cut:
            _GRAPH.build(payload.cut)
        result = get_crew().resolve_human_decision(payload.cut, payload.code, payload.usubjid, payload.decision, payload.reason)
        return {"ok": True, "protocol": protocol, "decision": payload.decision.upper(), "escalation": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
