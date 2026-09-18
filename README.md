# Study Sentinel — ATLAS

**Members:**  
Kamalesh G A  
Ashwinkumar N  
Rithish Barath  
Swaminathan V

## Run it

```bash
pip install -r requirements.txt
python -m stage1.atlas --data path/to/hackathon-data
```

These commands run from a clean checkout; replace the data path with the supplied `hackathon-data` directory.

## How we understood the problem

We treat the study as a time-aware evidence system rather than a collection of independent CSV lookups.  
The hard part is answering across domains while respecting data cuts, corrections, protocol changes, and laboratory ranges.  
We chose deterministic rules and indexed records so repeated questions do not repeatedly scan the raw dataset.  
We treat documents as evidence sources, not executable instructions, including text aimed at automated reviewers.  
We put external APIs, model-dependent decisions, and a separate UI out of scope.

## Architecture

```
Question -> Atlas -> QueryEngine -> StudyGraph indexes -> clinical/document rules
                                      -> Evidence validation -> Answer
Data -> DataStore -> cut/corrections -> StudyGraph
Documents -> DocumentStore ----------------^
```

DataStore loads and normalizes CSVs; StudyGraph builds subject/record indexes; Atlas routes questions; QueryEngine applies the relevant rule; the evidence layer validates record identity or document references; Atlas returns the required Answer schema.

## Tech stack

| Layer | What we used | Why this, not the obvious alternative |
|---|---|---|
| Language | Python 3 | Fast to implement deterministic data rules without deployment overhead. |
| Data handling | CSV + standard library | Matches the supplied package directly; no database setup or dependency-heavy ETL. |
| Graph / storage | In-memory dictionaries/lists | Repeated subject/record queries are fast and simpler than introducing a graph database. |
| Model, if any | None; deterministic rules | Reproducibility and evidence discipline matter more than free-form generation here. |
| Interface | Pydantic Question/Answer + CLI | Matches the required contract and is easy to run from a clean checkout. |
| Testing | Local harness + smoke queries | Exercises the real Atlas path and catches schema/evidence failures before submission. |

## Data handling

**Units:** `reference_ranges.csv` supplies laboratory limits. `stage1/ingestion.py` loads them; `stage1/rules.py` applies them. ALT/AST reported in µkat/L are converted to U/L (×60) before threshold checks.

**Dates:** `stage1/normalization.py` accepts ISO, slash-separated, textual month, and compact YYYYMMDD dates. Unrecognised dates become unknown rather than being guessed.

**Non-numeric laboratory values:** `<5` stays a below-detection qualifier, `ND` and empty values become unknown, and `12,4` is parsed as 12.4. They are not zero because the source does not establish a zero measurement.

**Malformed rows:** rows that can still be safely represented are kept; missing/invalid values are treated as unknown and skipped by rules that require a valid value. We do not invent replacements.

## Documents

`protocol_v1/v2/v3.md`, the laboratory manuals, and `sap.md` are loaded by `stage1/documents.py` and used as document evidence. Protocol version is selected from the cut; laboratory/manual and SAP content can support answers. A sentence addressed to an automated reviewer is treated as untrusted document text: it may be cited as evidence, but it never changes data, rules, or execution.

## When the answer is nothing

The agent returns `[]` when no record satisfies the requested condition at the active cut, and it keeps evidence empty when there is no valid supporting record. Unknown values are not promoted to findings, and evidence is never fabricated.

## Graph

Records are indexed as domain/subject/sequence identities, with subjects linking their domain records. The graph preserves cut-aware visibility and cross-domain lookup so rules can reason over a subject without repeatedly joining raw tables. Build statistics are recorded in `graph_stats.json`.

## What we know is weak

The hidden evaluation questions are not exposed in the public package, so local tests cannot prove hidden-test accuracy. Document-question wording may vary, so those queries are intentionally conservative. Hy's Law remains the most sensitive rule because timing, laboratory-specific ranges, and alternative explanations can affect the determination; this needs further hidden-test validation.
