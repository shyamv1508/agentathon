import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from stage1.atlas import Atlas
from stage1.graph import StudyGraph
from stage1.rules import hys_law_candidates, prohibited_cm
from stage2.crew import Action, ReviewCrew


ROOT = Path(__file__).resolve().parents[1]


class FakeCrew(ReviewCrew):
    def __init__(self, atlas, decision="APPROVED", first_decision=None):
        super().__init__("", "", "", atlas)
        self.calls = []
        self.decision = decision
        self.first_decision = first_decision
        self.memory = {"queries": {}, "escalations": {}, "rejected": {},
                       "site_flags": {}, "open_queries": {}}

    def _post(self, base, path, payload):
        self.calls.append((path, payload))
        if path == "/escalations":
            count = len([x for x in self.calls if x[0] == "/escalations"])
            if count == 1 and self.first_decision:
                return {"id": "test-1", "decision": self.first_decision,
                        "reason": "Please confirm the screening ALT and concomitant medicine."}
            return {"id": f"test-{count}", "decision": self.decision,
                    "reason": "Test gateway decision."}
        if path == "/queries":
            return {"id": "query-test", "status": "OPEN"}
        return {}


def isolated_crew(atlas, **kwargs):
    crew = FakeCrew(atlas, **kwargs)
    crew.memory_path = Path(tempfile.mkdtemp()) / "memory.json"
    crew.trace_path = Path(tempfile.mkdtemp()) / "trace.jsonl"
    return crew


def check(name, fn):
    try:
        fn()
        print(f"[PASS] {name}")
        return True
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def stage1_harness():
    with tempfile.TemporaryDirectory() as td:
        env = os.environ.copy()
        env["STAGE2_MEMORY_PATH"] = str(Path(td) / "memory.json")
        env["STAGE2_TRACE_PATH"] = str(Path(td) / "trace.jsonl")
        p = subprocess.run(
            [sys.executable, "starter/run_local_harness.py", "--module",
             "stage1.atlas", "--data", "hackathon-data"],
            cwd=ROOT, capture_output=True, text=True, env=env, timeout=30)
        if p.returncode != 0:
            raise AssertionError(p.stderr or p.stdout)
        if "Wrote" not in p.stdout:
            raise AssertionError("harness did not generate public outputs")


def cut6_and_cut9():
    atlas = Atlas(StudyGraph("hackathon-data"))
    crew = isolated_crew(atlas)\n    report6 = crew.run_cycle(6, 2)
    assert report6.cut == 6 and report6.protocol_version == 2
    assert report6.stats["findings"] == 41
    assert any(a["code"] == "SAE_MISCODED" and a["usubjid"] == "042-S02-004"
               for a in report6.escalations)
    report9 = crew.run_cycle(9, 3)
    assert report9.cut == 9 and report9.protocol_version == 3
    assert report9.stats["findings"] == 49


def duplicate_prevention():
    atlas = Atlas(StudyGraph("hackathon-data"))
    crew = isolated_crew(atlas)
    first = crew.run_cycle(6, 2)
    second = crew.run_cycle(6, 2)
    assert first.stats["new_queries"] > 0
    assert first.stats["new_escalations"] > 0
    assert second.stats["new_queries"] == 0
    assert second.stats["new_escalations"] == 0


def amendment3():
    atlas = StudyGraph("hackathon-data")
    atlas.build(9)
    rows = [r for r in atlas.rows["CM"]
            if prohibited_cm(r, 3) and r.get("CMCLAS") == "SULFONYLUREA"]
    subjects = {r.get("USUBJID") for r in rows}
    assert len(rows) == 5 and len(subjects) == 5


def serious_ae_evidence():
    atlas = Atlas(StudyGraph("hackathon-data"))
    atlas.graph.build(6)
    crew = isolated_crew(atlas)
    report = crew.run_cycle(6, 2)
    item = next(a for a in report.escalations if a["code"] == "SAE_MISCODED")
    assert item["usubjid"] == "042-S02-004"
    assert item["severity"] == "CRITICAL"
    assert item["evidence"] == [{"domain": "AE", "usubjid": "042-S02-004", "seq": 1}]


def hys_law_s07():
    atlas = StudyGraph("hackathon-data")
    atlas.build(9)
    candidates = hys_law_candidates(atlas)
    item = next(x for x in candidates if x[0] == "042-S07-001")
    assert item[1].get("LBTESTCD") in {"ALT", "AST"}


def clarify():
    atlas = Atlas(StudyGraph("hackathon-data"))
    atlas.graph.build(9)
    crew = isolated_crew(atlas, decision="APPROVED", first_decision="CLARIFY")
    action = Action("HYS_LAW_CANDIDATE", "042-S07-001", "S07", "MAJOR",
                    "Clarify test.", [], ["Escalate"])
    result = crew._submit_escalation(action, 9)
    calls = [p for path, p in crew.calls if path == "/escalations"]
    assert len(calls) == 2
    clarification = calls[1]["clarification"]
    assert clarification["source"] == "StudyGraph"
    assert clarification["subject"] == "042-S07-001"
    assert "screening_alt" in clarification
    assert "concomitant_medications" in clarification
    assert result.status == "approved"


def rejected():
    atlas = Atlas(StudyGraph("hackathon-data"))
    atlas.graph.build(9)
    crew = isolated_crew(atlas, decision="REJECTED")
    action = Action("HYS_LAW_CANDIDATE", "042-S05-003", "S05", "MAJOR",
                    "Reject test.", [], ["Monitor"])
    first = crew._submit_escalation(action, 9)
    second = crew._submit_escalation(
        Action("HYS_LAW_CANDIDATE", "042-S05-003", "S05", "MAJOR",
               "Same rejection.", [], ["Monitor"]), 9)
    assert first.status == "monitoring" and second.status == "monitoring"
    assert len([x for x in crew.calls if x[0] == "/escalations"]) == 1
    assert crew.memory["rejected"]


def report_outputs():
    stats = json.loads((ROOT / "graph_stats.json").read_text(encoding="utf-8"))
    public = json.loads((ROOT / "stage1_public.json").read_text(encoding="utf-8"))
    assert stats["subjects"] == 241
    assert stats["records"] == 26482
    assert public["questions_run"] >= 1
    assert public["answers"]
    assert public["answers"][0]["question_id"] == "LOCAL-SMOKE-001"


def main():
    tests = [
        ("Stage 1 harness", stage1_harness),
        ("Cut 6 / Protocol v2", cut6_and_cut9),
        ("Same-cut duplicate prevention", duplicate_prevention),
        ("Amendment 3 / Sulfonylurea", amendment3),
        ("Serious AE miscode evidence", serious_ae_evidence),
        ("Hy's Law / S07 unit handling", hys_law_s07),
        ("CLARIFY flow", clarify),
        ("REJECTED flow", rejected),
        ("Required Stage 1 outputs", report_outputs),
    ]
    print("ATLAS — FULL QA")
    print("=" * 30)
    passed = sum(check(name, fn) for name, fn in tests)
    print()
    print(f"RESULT: {passed}/{len(tests)} PASS")
    if passed != len(tests):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
