# ATLAS — Autonomous Trial Logic & Analysis System

**Agentathon 2026 · Evidence-first clinical trial intelligence**

**Team**
- Kamalesh G A
- Ashwinkumar N
- Rithish Barath
- Swaminathan V

**Live Demo:** https://agentathon-three.vercel.app/

## Overview

ATLAS is an evidence-first clinical trial intelligence platform that turns heterogeneous study data into a time-aware, queryable knowledge graph and connects three stages of study intelligence:

1. **ATLAS** — understands the study and answers evidence-grounded questions.
2. **MONITOR** — reviews detected findings through a six-node workflow with human oversight.
3. **WATCH** — continuously monitors successive data cuts and explains safety/data-integrity decisions.

Our design principle is simple:

> **Every important finding should be traceable back to the evidence that produced it.**

The core reasoning path is deterministic and does not require an external LLM or API key.

## Architecture

```
                    Clinical Study Data
                 ┌───────────────────────┐
                 │ DM AE LB VS EX CM DS  │
                 │ MH EG + corrections  │
                 └───────────┬───────────┘
                             ↓
                    Ingestion + Normalization
                             ↓
                       StudyGraph
                  time-aware indexed graph
                             ↓
                         ATLAS
                  evidence-grounded QA
                             ↓
                        MONITOR
        detect → medical → data → compliance
                    → human gate → execute
                             ↓
                          WATCH
             12-cut unattended surveillance
                             ↓
                 Mission Control Web UI
             Patient 360 + Evidence + Explain
```

### Data flow

Data is loaded from separate clinical-domain CSV files by the ingestion layer. Records are normalized and indexed using **Domain + USUBJID + Sequence**, allowing information from different files to be connected to the same study subject.

For example:

```
042-S07-001
   ├── DM → demographics
   ├── LB → ALT / AST / bilirubin
   ├── AE → adverse events
   ├── CM → medications
   ├── EX → dosing/exposure
   └── MH → medical history
```

This enables cross-domain reasoning without repeatedly scanning and manually joining the raw CSV files.

## Problem 1 — ATLAS

ATLAS builds a cut-aware StudyGraph and answers four required question types:

- **Count** — exact counts with supporting evidence.
- **Lookup** — exact record references.
- **Finding** — subjects satisfying protocol/rule conditions.
- **Trap** — conservative answers when evidence does not support a claim.

### Key capabilities

- Dynamic data-cut handling.
- Corrections applied according to their effective cut.
- Protocol-aware reasoning across amendments.
- Cross-domain subject/record indexing.
- Laboratory reference-range checks.
- Hy's Law detection.
- Serious Adverse Event detection.
- Prohibited medication checks.
- Dosing validation.
- Numeric/date normalization.
- Evidence identity and validation.
- Document evidence treated as evidence, not executable instructions.
- Graceful handling of missing, malformed, unknown, and below-detection values.

Run the local ATLAS harness:

```bash
python starter/run_local_harness.py --module stage1.atlas --data hackathon-data
```

## Problem 2 — MONITOR

MONITOR extends ATLAS findings into the required six-node workflow:

```
1. Detect
2. Medical Review
3. Data Manager
4. Compliance
5. Human Gate
6. Execute
```

The workflow maintains persistent memory to reduce duplicate queries and escalations.

The Human Gate supports:

- **APPROVED** → execute.
- **REJECTED** → downgrade to monitoring without re-escalation.
- **CLARIFY** → perform an additional StudyGraph lookup and resubmit.

Every node contributes to the trace so decisions remain auditable.

Run the monitor workflow:

```bash
python -m stage2 --data hackathon-data --cut 6 --protocol 2
```

Run the unified Stage 2 regression suite:

```bash
python -m stage2.test_all
```

## Problem 3 — WATCH

WATCH extends MONITOR into unattended surveillance across **12 successive study cuts**.

It handles:

- Incremental and corrected study data.
- Delayed or unanswered human review.
- Suspicious site behavior.
- Laboratory unit shifts.
- Edited/adversarial documents.
- Protocol amendments that invalidate derived findings.
- Mid-period onboarding of new sites/domains.
- A single execution/model budget across the full surveillance period.

Safety-critical deterministic checks continue even when the execution budget becomes constrained.

Run the public 12-cut surveillance:

```bash
python -m stage3.run_watch --data hackathon-data --budget-seconds 180
```

The run produces a surveillance report and decision log with trace-backed explanations.

## What makes the platform different

Beyond the required challenge workflows, we built a usable study-intelligence layer around them:

- **Mission Control** — interactive visual command center for the study.
- **Patient 360** — one-click subject view across multiple clinical domains.
- **Live data-cut selector** — inspect study state at different cuts.
- **Evidence exploration** — move from a finding to the records supporting it.
- **Reverse lookup** — find subjects associated with medications, diseases, or adverse events.
- **Human Gate UI** — review and act on pending decisions.
- **Explainable WATCH decisions** — each decision records what happened, evidence, alternatives, rationale, and trace information.
- **Automatic CSV domain discovery** — new compatible domains can be discovered without adding a hard-coded ingestion branch.
- **Fingerprint-based freshness detection** — detects underlying data changes and refreshes the graph when required.
- **Evidence validation** — prevents unsupported or fabricated record references.
- **Deterministic safety path** — core safety checks do not depend on generative model availability.
- **Graceful data handling** — malformed or unknown values are not silently converted into clinical findings.
- **Unified architecture** — ATLAS, MONITOR, and WATCH operate as one continuous pipeline rather than isolated scripts.

## Technology

| Layer | Technology |
|---|---|
| Language | Python 3 |
| Backend/API | FastAPI |
| Frontend | HTML, CSS, JavaScript |
| Validation | Pydantic |
| Data | CSV / JSON |
| Graph / indexing | In-memory StudyGraph |
| Version control | Git / GitHub |
| Deployment | Vercel |
| Reasoning | Deterministic, evidence-grounded rules |

## Evidence and safety principles

### Cut-aware reasoning

A record is visible only when its availability/correction timing is valid for the requested cut. This prevents later information from leaking into earlier study states.

### Laboratory normalization

Reference ranges are loaded from `reference_ranges.csv`. ALT/AST values reported in µkat/L are converted to U/L before threshold evaluation:

```
1 µkat/L = 60 U/L
```

### Conservative numeric handling

- `<5` remains below detection; it is not treated as zero.
- `ND` and blank values remain unknown.
- `12,4` is interpreted as 12.4.
- Invalid or missing values are skipped by rules that require valid measurements.

### Document safety

Protocol and laboratory documents can provide evidence, but text that attempts to instruct an automated reviewer is treated as untrusted content. It can be cited; it cannot modify execution or safety rules.

### No fabricated evidence

If the available data does not establish a finding, the system returns an empty result rather than inventing a subject, record, or conclusion.

## Project structure

```
agentathon/
├── starter/
│   ├── schemas.py
│   └── run_local_harness.py
├── stage1/
│   ├── atlas.py
│   ├── graph.py
│   ├── ingestion.py
│   ├── normalization.py
│   ├── rules.py
│   ├── evidence.py
│   ├── documents.py
│   └── queries.py
├── stage2/
│   └── crew.py
├── stage3/
│   └── watch.py
├── api/
├── index.html
├── app.js
├── styles.css
└── hackathon-data/
    ├── data/
    ├── documents/
    └── responses/
```

## Web interface

The web application provides an interactive Mission Control view for:

- StudyGraph exploration.
- Safety and monitoring signals.
- Subject selection.
- Patient 360.
- Laboratory and medication exploration.
- Natural-language clinical queries.
- Evidence inspection.
- Human Gate review.
- WATCH surveillance and decision explanations.

The application is deployed as a public demonstration and the core system can also be run locally.

## Limitations

The hidden evaluation questions are not included in the public package, so local tests cannot guarantee hidden-test accuracy. The system therefore favors conservative evidence handling over unsupported conclusions, particularly for document-language questions and complex clinical rules such as Hy's Law.

## Final demonstration

**ATLAS → MONITOR → WATCH**

One system to understand the study, review the study, and continuously watch the study — while keeping decisions grounded in evidence and human oversight.
