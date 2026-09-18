# Stage 2 — MONITOR

Stage 2 wraps the existing Stage 1 ATLAS with six deterministic review nodes:

1. detect
2. medical_review
3. data_manager
4. compliance
5. human_gate
6. execute

The crew keeps persistent memory in `stage2_memory.json` and appends decisions to
`stage2_trace.jsonl`. Set `STAGE2_MEMORY_PATH` and `STAGE2_TRACE_PATH` to use
different locations.

The human gate supports APPROVED, REJECTED and CLARIFY. CLARIFY is answered from
the existing StudyGraph and the escalation is resubmitted.

Example:

```python
from stage1.atlas import Atlas
from stage1.graph import StudyGraph
from stage2.crew import ReviewCrew

atlas = Atlas(StudyGraph("hackathon-data"))
crew = ReviewCrew("", "", "demo-team", atlas)
report = crew.run_cycle(6, 2)
print(report.model_dump_json(indent=2))
```
