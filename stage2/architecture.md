# Stage 2 MONITOR — Architecture Note

## Six-node review cycle

The existing Stage 1 Atlas is retained as the detection source. ReviewCrew.run_cycle(cut, protocol_version) runs six nodes in order:

1. **detect** — builds the requested cut and identifies serious AEs, mis-coded serious events, liver-signal candidates, dose deviations, prohibited medicines and data-quality timing problems.
2. **medical_review** — decides which findings need a medical-monitor escalation and keeps supported monitoring-only findings out of the escalation queue.
3. **data_manager** — converts actionable data-quality findings into specific record-cited site queries and suppresses duplicates using persistent memory.
4. **compliance** — evaluates findings against the protocol version supplied for the current cut and records subject-level deviations plus recurring site flags.
5. **human_gate** — sends escalations to /escalations and handles all three monitor decisions.
6. **execute** — assembles the ReviewReport and records cycle completion.

## Human gate

- **APPROVED:** the action becomes approved and is retained in memory.
- **REJECTED:** the action becomes monitoring-only, the monitor reason is retained, and the same escalation is not submitted again on a later cycle.
- **CLARIFY:** the crew answers the monitor's question from its existing StudyGraph (for example screening ALT and concomitant medication records), records the clarification in the trace, and resubmits the escalation.

## Memory

stage2_memory.json stores query identities, escalation identities, rejected actions, open queries and site-level recurring flags. A repeated cycle therefore produces no duplicate query or escalation. Trace entries are appended immediately to stage2_trace.jsonl as each node makes its decision.

## Mid-stage protocol changes

The cycle receives the protocol version explicitly. Compliance and prohibited-medication rules use that version rather than a stale previous version. Stage 1's cut-aware graph is rebuilt when the requested cut changes, so the same underlying dataset can be reviewed under the correct snapshot.

## Trace discipline

Every node writes a trace entry when it runs. Evidence is copied from domain record identities (domain, usubjid, seq) and is carried into query/escalation decisions. Human-gate clarification and its resubmission are separate trace decisions.
