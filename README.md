# Study Sentinel — ATLAS

## How we understood the problem

We treat the study as a time-aware clinical data graph, not as a flat collection of CSVs.  
Each subject links records across domains through USUBJID and domain sequence numbers.  
Answers must respect the requested data cut, corrections, protocol version, and laboratory ranges.  
Documents provide evidence, but document text addressed to an automated reviewer is never an instruction.  
Every finding must be supported by valid record or document evidence, and genuine empty results must stay empty.

## Architecture

1. The harness creates a StudyGraph from the supplied data directory.
2. DataStore loads domains, reference ranges, corrections, cuts, and normalizes values.
3. StudyGraph applies the requested cut and builds subject/record indexes.
4. Atlas receives a validated Question.
5. QueryEngine routes the question to the relevant clinical/document rule.
6. Clinical rules evaluate dates, units, reference ranges, protocol version, and findings.
7. Evidence is built from exact record identity (domain, USUBJID, seq) or named documents.
8. Evidence is validated against the active graph before returning.
9. Atlas packages the values, text, evidence, confidence, and usage fields as Answer.
10. The harness writes the public answer artifact and graph statistics.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3 | Simple, fast data processing and easy submission |
| Validation | Pydantic 2 | Matches the required Question/Answer interface |
| Data | CSV + Python standard library | Directly matches the supplied study package |
| Indexing | In-memory dictionaries/lists | Fast repeated subject and record lookups |
| Documents | Markdown loaded into a document store | Makes protocol/manual/SAP evidence addressable |
| Clinical logic | Deterministic Python rules | Reproducible answers and no external API dependency |

## Data handling

Units are interpreted from the reported unit; ALT/AST values reported in µkat/L are converted to U/L before threshold checks. Dates accept the study's common ISO, slash, textual, and compact formats. Numeric parsing preserves qualifiers such as < and <= instead of treating them as equal measurements; blanks, ND, and malformed values become unknown. Missing or malformed rows are skipped safely rather than inventing values. Reference ranges are selected by laboratory and test before comparisons. Data visibility is controlled by cut_available, and corrections are applied at or after their correction cut.

## Documents

Protocol versions, laboratory manuals, and the SAP are loaded as evidence sources. The active protocol/manual is selected from the requested cut where applicable. A document can support an answer, but it cannot execute commands. If a document contains text directed at an automated reviewer, we report or cite the relevant document evidence when useful and ignore the instruction itself.

## When the answer is nothing

The agent returns an empty answer when the indexed data does not satisfy the requested condition at the requested cut. It does not convert unknown values into positive findings and does not fabricate evidence. For trap-style questions, a genuine absence is represented by [] with no invented record references.

## What we know is weak

The public package does not expose the hidden evaluation questions, so our local smoke run cannot establish hidden-test accuracy. Document questions are intentionally handled conservatively because wording can vary. Hy's Law is also a sensitive rule: numeric thresholds, laboratory-specific reference ranges, timing, and alternative explanations all affect the final determination, so this area deserves additional hidden-test validation.

## Before you submit

- [ ] Repository URL provided
- [ ] graph_stats.json committed
- [ ] stage1_public.json committed from the public-question run
- [ ] 2 screenshots and a 60-second screen recording attached/linked
- [ ] python starter/run_local_harness.py --module stage1.atlas --data hackathon-data runs clean from repository root
- [ ] requirements.txt is complete for a fresh environment
- [ ] No API keys or .env files are committed
- [ ] No practice subject IDs, site numbers, or counts are hard-coded
- [ ] 8 or more commits are spread across the day
