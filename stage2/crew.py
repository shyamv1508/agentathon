import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from stage1.atlas import Atlas
from stage1.rules import (
    hys_law_candidates,
    prohibited_cm,
    protocol_version,
    serious_ae,
    dosing_findings,
)
from stage1.normalization import parse_date, parse_number


@dataclass
class Finding:
    code: str
    usubjid: str
    site: str
    severity: str
    rationale: str
    evidence: list[dict] = field(default_factory=list)
    category: str = "data"
    status: str = "open"


@dataclass
class Action:
    code: str
    usubjid: str | None
    site: str | None
    severity: str
    summary: str
    evidence: list[dict]
    alternatives: list[str] = field(default_factory=list)
    status: str = "pending"
    monitor_reason: str = ""
    external_id: str | None = None


@dataclass
class ReviewReport:
    cut: int
    protocol_version: int
    findings: list[dict]
    escalations: list[dict]
    queries: list[dict]
    deviations: list[dict]
    trace: list[dict]
    stats: dict
    pending_escalations: list[dict] = field(default_factory=list)

    def model_dump(self):
        return asdict(self)

    def model_dump_json(self, **kwargs):
        return json.dumps(self.model_dump(), **kwargs)


class ReviewCrew:
    """
    Six-node deterministic MONITOR review crew.

    The Stage 1 Atlas remains the source of clinical findings. This layer adds
    review, site queries, compliance, human-gate handling, memory and trace.
    """

    def __init__(self, hub_url, gateway_url, team_key, atlas: Atlas):
        self.hub_url = (hub_url or "").rstrip("/")
        self.gateway_url = (gateway_url or "").rstrip("/")
        self.team_key = team_key or ""
        self.atlas = atlas
        data_dir = Path(atlas.graph.data_dir)
        root = data_dir.parent if data_dir.name == "data" else data_dir.parent
        self.memory_path = Path(os.getenv("STAGE2_MEMORY_PATH", str(root / "stage2_memory.json")))
        self.trace_path = Path(os.getenv("STAGE2_TRACE_PATH", str(root / "stage2_trace.jsonl")))
        self.memory = self._load_memory()
        self.cycle_trace = []
        self.pending_escalations = []

    # ---------- persistent memory ----------

    def _load_memory(self):
        if not self.memory_path.exists():
            return {
                "queries": {},
                "escalations": {},
                "rejected": {},
                "site_flags": {},
                "open_queries": {},
            }
        try:
            data = json.loads(self.memory_path.read_text(encoding="utf-8"))
            for key in ("queries", "escalations", "rejected", "site_flags", "open_queries"):
                data.setdefault(key, {})
            return data
        except (OSError, ValueError):
            return {
                "queries": {},
                "escalations": {},
                "rejected": {},
                "site_flags": {},
                "open_queries": {},
            }

    def _save_memory(self):
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.memory_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.memory, indent=2), encoding="utf-8")
        tmp.replace(self.memory_path)

    def _trace(self, node, decision, evidence=None, **extra):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle": self.atlas.graph.cut,
            "node": node,
            "decision": decision,
            "evidence": evidence or [],
        }
        entry.update(extra)
        self.cycle_trace.append(entry)
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    # ---------- HTTP gateway ----------

    def _post(self, base, path, payload):
        if not base:
            return None
        url = base + ("" if path.startswith("/") else "/") + path
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.team_key:
            headers["Authorization"] = "Bearer " + self.team_key
            headers["X-Team-Key"] = self.team_key
        try:
            req = Request(url, data=body, headers=headers, method="POST")
            with urlopen(req, timeout=15) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except (HTTPError, URLError, TimeoutError, ValueError, OSError):
            return None

    # ---------- evidence helpers ----------

    @staticmethod
    def _ref(row):
        return {
            "domain": row.get("_domain", ""),
            "usubjid": row.get("USUBJID"),
            "seq": row.get("_seq"),
        }

    @staticmethod
    def _site(usubjid):
        parts = str(usubjid or "").split("-")
        return parts[1] if len(parts) >= 2 else ""

    def _atlas_answer(self, kind, text, cut):
        from starter.schemas import Question
        return self.atlas.answer(
            Question(
                question_id="stage2",
                kind=kind,
                text=text,
                cut=cut,
            )
        )

    # ---------- node 1: detect ----------

    def _detect(self, cut, protocol):
        g = self.atlas.graph
        if g.cut != cut:
            g.build(cut)
        else:
            g.ensure_fresh()

        findings = []

        # Serious AEs. serious_ae deliberately includes AESHOSP=Y.
        for row in g.rows.get("AE", []):
            if serious_ae(row):
                evidence = [self._ref(row)]
                hosp = str(row.get("AESHOSP", "")).upper() == "Y"
                aeser = str(row.get("AESER", "")).upper() == "Y"
                if hosp and not aeser:
                    code = "SAE_MISCODED"
                    rationale = (
                        f"{row.get('AETERM', 'Adverse event')} has AESHOSP=Y but "
                        "AESER=N; hospitalisation makes the event serious under the protocol."
                    )
                else:
                    code = "SERIOUS_AE"
                    rationale = f"{row.get('AETERM', 'Adverse event')} meets the serious AE definition."
                findings.append(Finding(
                    code=code,
                    usubjid=row.get("USUBJID"),
                    site=self._site(row.get("USUBJID")),
                    severity="CRITICAL",
                    rationale=rationale,
                    evidence=evidence,
                    category="safety",
                ))

        # Dosing findings from the Stage 1 rule.
        for subject, reason, rows in dosing_findings(g):
            evidence = [self._ref(r) for r in rows if r.get("_domain")]
            findings.append(Finding(
                code="MISSING_DOSE" if reason == "MISSING_EX" else "DOSE_DEVIATION",
                usubjid=subject,
                site=self._site(subject),
                severity="MAJOR",
                rationale=(
                    "No exposure record is present for the assigned arm."
                    if reason == "MISSING_EX"
                    else "Recorded exposure dose does not match the protocol dose."
                ),
                evidence=evidence,
                category="data",
            ))

        # Prohibited concomitant medication under the protocol in force.
        for row in g.rows.get("CM", []):
            if prohibited_cm(row, protocol):
                findings.append(Finding(
                    code="PROHIBITED_MED",
                    usubjid=row.get("USUBJID"),
                    site=self._site(row.get("USUBJID")),
                    severity="MAJOR",
                    rationale=f"Concomitant medication class {row.get('CMCLAS', '')} is prohibited under protocol v{protocol}.",
                    evidence=[self._ref(row)],
                    category="compliance",
                ))

        # Hy's Law candidates are safety candidates, but screening elevation
        # is explicitly reviewed before escalation.
        for subject, alt_ast, bili in hys_law_candidates(g):
            findings.append(Finding(
                code="HYS_LAW_CANDIDATE",
                usubjid=subject,
                site=self._site(subject),
                severity="MAJOR",
                rationale="ALT/AST and bilirubin thresholds meet the candidate criteria within 14 days.",
                evidence=[self._ref(alt_ast), self._ref(bili)],
                category="safety",
            ))

        # Data-quality findings: AE before first dose and missing EX.
        first_dose = {}
        for subject, rows in g.by_subject.items():
            doses = []
            for row in rows.get("EX", []):
                d = parse_date(row.get("EXSTDTC") or row.get("EXTRTSDT") or row.get("EXDATE"))
                if d:
                    doses.append(d)
            if doses:
                first_dose[subject] = min(doses)

        for row in g.rows.get("AE", []):
            subject = row.get("USUBJID")
            ae_date = parse_date(row.get("AESTDTC"))
            dose_date = first_dose.get(subject)
            if ae_date and dose_date and ae_date < dose_date:
                findings.append(Finding(
                    code="AE_BEFORE_FIRST_DOSE",
                    usubjid=subject,
                    site=self._site(subject),
                    severity="MAJOR",
                    rationale=(
                        f"AE starts {ae_date.isoformat()}, before first dose "
                        f"{dose_date.isoformat()}."
                    ),
                    evidence=[self._ref(row)],
                    category="data",
                ))

        # De-duplicate exact finding identities within a cycle.
        unique = {}
        for f in findings:
            key = (f.code, f.usubjid, tuple(
                (e.get("domain"), e.get("usubjid"), e.get("seq"))
                for e in f.evidence
            ))
            unique[key] = f
        findings = list(unique.values())

        self._trace(
            "detect",
            f"{len(findings)} findings under protocol v{protocol}",
            [e for f in findings for e in f.evidence],
            findings=len(findings),
            safety=sum(f.category == "safety" for f in findings),
            data=sum(f.category == "data" for f in findings),
            compliance=sum(f.category == "compliance" for f in findings),
        )
        return findings

    # ---------- node 2: medical review ----------

    def _medical_review(self, findings, cut):
        actions = []
        for f in findings:
            if f.code in {"SERIOUS_AE", "SAE_MISCODED"}:
                actions.append(Action(
                    code=f.code,
                    usubjid=f.usubjid,
                    site=f.site,
                    severity="CRITICAL",
                    summary=(
                        f"{f.rationale} The event requires medical-monitor review."
                    ),
                    evidence=f.evidence,
                    alternatives=[
                        "Confirm serious event and expedite reporting",
                        "Accept entered coding only if supported by protocol and source evidence",
                    ],
                ))
            elif f.code == "HYS_LAW_CANDIDATE":
                # Screening value is a confounder for this stage's example.
                screening_high = self._screening_liver_high(f.usubjid)
                if screening_high:
                    self._trace(
                        "medical_review",
                        f"{f.code} {f.usubjid} -> MONITOR: screening liver value already elevated",
                        f.evidence,
                        subject=f.usubjid,
                    )
                    continue
                actions.append(Action(
                    code=f.code,
                    usubjid=f.usubjid,
                    site=f.site,
                    severity="MAJOR",
                    summary="Liver-signal candidate requires medical-monitor review.",
                    evidence=f.evidence,
                    alternatives=[
                        "Escalate for possible Hy's Law case",
                        "Keep as monitoring if alternative explanation is supported",
                    ],
                ))
            elif f.code == "DOSE_DEVIATION":
                # A recurring dose problem can produce a site-level escalation.
                continue

        self._trace(
            "medical_review",
            f"{len(actions)} escalation drafts; liver candidates not supported for escalation remain monitor-only",
            [e for a in actions for e in a.evidence],
            escalation_drafts=len(actions),
        )
        return actions

    def _screening_liver_high(self, subject):
        rows = self.atlas.graph.by_subject.get(subject, {}).get("LB", [])
        for r in rows:
            visit = str(r.get("VISIT", "")).upper()
            if "SCREEN" not in visit:
                continue
            if r.get("LBTESTCD") not in {"ALT", "AST"}:
                continue
            n, q = parse_number(r.get("LBORRES"))
            if n is not None and q not in {"<", "<=", "unknown"}:
                # Conservative: any known screening ALT/AST above its local ULN.
                from stage1.rules import _reference_high
                ul = _reference_high(self.atlas.graph, r)
                if ul is not None and n > ul:
                    return True
        return False

    # ---------- node 3: data manager ----------

    def _query_key(self, subject, domain, seq, issue):
        return f"{subject}|{domain}|{seq}|{issue}"

    def _data_manager(self, findings, cut):
        queries = []
        for f in findings:
            if f.category != "data":
                continue
            if f.code == "AE_BEFORE_FIRST_DOSE":
                issue = f.code
                e = f.evidence[0]
                key = self._query_key(f.usubjid, e["domain"], e["seq"], issue)
                if key in self.memory["queries"]:
                    continue
                text = (
                    f"AE record {e['domain']} seq {e['seq']} for {f.usubjid} "
                    f"starts before first dose. Please verify the AE start date "
                    "against source and correct or confirm."
                )
            elif f.code in {"MISSING_DOSE", "DOSE_DEVIATION"}:
                e = f.evidence[0] if f.evidence else {"domain": "EX", "seq": None}
                key = self._query_key(f.usubjid, e["domain"], e.get("seq"), f.code)
                if key in self.memory["queries"]:
                    continue
                text = (
                    f"Exposure record {e.get('domain')} seq {e.get('seq')} for "
                    f"{f.usubjid} does not match the expected protocol dose. "
                    "Please verify the dose and correct or confirm."
                    if f.code == "DOSE_DEVIATION"
                    else f"No exposure record is present for {f.usubjid}. "
                         "Please verify the first-dose record and correct or confirm."
                )
            else:
                continue

            payload = {
                "usubjid": f.usubjid,
                "domain": e["domain"],
                "seq": e.get("seq"),
                "cut": cut,
                "text": text,
            }
            response = self._post(self.gateway_url, "/queries", payload)
            qid = (response or {}).get("id")
            record = {**payload, "id": qid, "status": (response or {}).get("status", "OPEN")}
            self.memory["queries"][key] = record
            if record["status"] not in {"CLOSED", "RESOLVED"}:
                self.memory["open_queries"][key] = record
            queries.append(record)

        # Site recurrence: two or more distinct subjects with dose issues.
        site_subjects = {}
        for f in findings:
            if f.code in {"DOSE_DEVIATION", "MISSING_DOSE"}:
                site_subjects.setdefault(f.site, set()).add(f.usubjid)
        for site, subjects in site_subjects.items():
            if len(subjects) >= 2:
                self.memory["site_flags"][site] = {
                    "site": site,
                    "subjects": sorted(subjects),
                    "reason": "Recurring dose deviations across subjects",
                    "last_cut": cut,
                }

        self._save_memory()
        self._trace(
            "data_manager",
            f"{len(queries)} queries raised; {len(self.memory['queries']) - len(queries)} retained prior queries; 0 duplicate new queries",
            [e for q in queries for e in [{
                "domain": q["domain"], "usubjid": q["usubjid"], "seq": q["seq"]
            }]],
            queries=len(queries),
            duplicates=0,
        )
        return queries

    # ---------- node 4: compliance ----------

    def _compliance(self, cut, protocol, findings):
        deviations = []
        g = self.atlas.graph

        for f in findings:
            if f.code == "PROHIBITED_MED":
                deviations.append({
                    "code": "PROHIBITED_MED",
                    "usubjid": f.usubjid,
                    "site": f.site,
                    "protocol_version": protocol,
                    "evidence": f.evidence,
                    "text": f.rationale,
                })
            elif f.code in {"DOSE_DEVIATION", "MISSING_DOSE"}:
                deviations.append({
                    "code": f.code,
                    "usubjid": f.usubjid,
                    "site": f.site,
                    "protocol_version": protocol,
                    "evidence": f.evidence,
                    "text": f.rationale,
                })

        # Eligibility-style checks available directly from DM.
        for row in g.rows.get("DM", []):
            subject = row.get("USUBJID")
            if not subject:
                continue
            age, q = parse_number(row.get("AGE"))
            if age is not None and (age < 18 or age > 75):
                deviations.append({
                    "code": "AGE_ELIGIBILITY",
                    "usubjid": subject,
                    "site": self._site(subject),
                    "protocol_version": protocol,
                    "evidence": [self._ref(row)],
                    "text": f"Age {age} is outside the supported eligibility range.",
                })

        self._trace(
            "compliance",
            f"{len(deviations)} deviations under protocol v{protocol}",
            [e for d in deviations for e in d["evidence"]],
            deviations=len(deviations),
        )
        return deviations

    # ---------- node 5: human gate ----------

    def _submit_escalation(self, action, cut):
        key = f"{action.code}|{action.usubjid}|{action.site}"
        if key in self.memory["rejected"]:
            action.status = "monitoring"
            action.monitor_reason = self.memory["rejected"][key].get("reason", "Previously rejected.")
            return action

        if key in self.memory["escalations"]:
            previous = self.memory["escalations"][key]
            action.status = previous.get("status", "pending")
            action.external_id = previous.get("id")
            return action

        payload = {
            "code": action.code,
            "usubjid": action.usubjid,
            "site": action.site,
            "severity": action.severity,
            "summary": action.summary,
            "evidence": action.evidence,
            "alternatives": action.alternatives,
            "cut": cut,
        }
        response = self._post(self.gateway_url, "/escalations", payload) or {}
        decision = str(response.get("decision", "PENDING")).upper()
        action.external_id = response.get("id")
        if decision == "APPROVED":
            action.status = "approved"
            self._trace(
                "human_gate",
                f"{action.code} {action.usubjid} -> APPROVED: {response.get('reason', 'action approved')}",
                action.evidence,
            )
            self.memory["escalations"][key] = {
                **payload, "id": action.external_id, "status": "approved",
                "reason": response.get("reason", ""),
            }
        elif decision == "REJECTED":
            action.status = "monitoring"
            action.monitor_reason = response.get("reason", "Rejected by medical monitor.")
            self.memory["rejected"][key] = {
                **payload, "id": action.external_id, "reason": action.monitor_reason
            }
            self.memory["escalations"][key] = {
                **payload, "id": action.external_id, "status": "monitoring",
                "reason": action.monitor_reason,
            }
            self._trace(
                "human_gate",
                f"{action.code} {action.usubjid} -> REJECTED: downgraded to monitoring",
                action.evidence,
                reason=action.monitor_reason,
            )
        elif decision == "CLARIFY":
            answer = self._answer_clarify(response.get("reason", ""), action.usubjid, cut)
            resubmitted = {
                **payload,
                "id": action.external_id,
                "clarification": answer,
                "cut": cut,
            }
            response2 = self._post(self.gateway_url, "/escalations", resubmitted) or {}
            decision2 = str(response2.get("decision", "PENDING")).upper()
            action.external_id = response2.get("id") or action.external_id
            if decision2 == "APPROVED":
                action.status = "approved"
            elif decision2 == "REJECTED":
                action.status = "monitoring"
                action.monitor_reason = response2.get("reason", "Rejected after clarification.")
                self.memory["rejected"][key] = {
                    **payload, "id": action.external_id, "reason": action.monitor_reason
                }
            else:
                action.status = "pending"
            self.memory["escalations"][key] = {
                **payload,
                "id": action.external_id,
                "status": action.status,
                "clarification": answer,
                "reason": response2.get("reason", ""),
            }
            self._trace(
                "human_gate",
                f"{action.code} {action.usubjid} -> CLARIFY; answered from graph; resubmitted -> {decision2}",
                action.evidence,
                clarification=answer,
            )
        else:
            action.status = "pending"
            self.memory["escalations"][key] = {
                **payload, "id": action.external_id, "status": "pending"
            }
            self._trace(
                "human_gate",
                f"{action.code} {action.usubjid} -> PENDING",
                action.evidence,
            )

        self._save_memory()
        return action

    def _answer_clarify(self, reason, subject, cut):
        text = str(reason).lower()
        g = self.atlas.graph
        answer = {"subject": subject, "cut": cut, "source": "StudyGraph"}

        if "alt" in text:
            labs = g.by_subject.get(subject, {}).get("LB", [])
            vals = []
            for r in labs:
                if r.get("LBTESTCD") == "ALT" and "SCREEN" in str(r.get("VISIT", "")).upper():
                    vals.append({
                        "value": r.get("LBORRES"),
                        "unit": r.get("LBORRESU"),
                        "evidence": self._ref(r),
                    })
            answer["screening_alt"] = vals

        if "medicine" in text or "conmed" in text or "hepatotoxic" in text:
            meds = g.by_subject.get(subject, {}).get("CM", [])
            answer["concomitant_medications"] = [
                {
                    "name": r.get("CMTRT"),
                    "class": r.get("CMCLAS"),
                    "evidence": self._ref(r),
                }
                for r in meds
            ]

        if "screening_alt" not in answer and "concomitant_medications" not in answer:
            p = g.patient360(subject)
            answer["patient360"] = {
                d: len(rows) for d, rows in p["domains"].items()
            }

        return answer

    def _human_gate(self, actions, cut):
        handled = []
        for action in actions:
            handled.append(self._submit_escalation(action, cut))

        # Site-level escalation after repeated subject deviations.
        for site, flag in self.memory["site_flags"].items():
            subjects = flag.get("subjects", [])
            key = f"SITE_RECURRING_DOSE|{site}"
            if len(subjects) < 2 or key in self.memory["escalations"]:
                continue
            action = Action(
                code="SITE_RECURRING_DOSE",
                usubjid=None,
                site=site,
                severity="MAJOR",
                summary=f"Recurring dose deviations affect multiple subjects at site {site}.",
                evidence=[],
                alternatives=["Open site-level corrective action", "Continue subject-level monitoring"],
            )
            handled.append(self._submit_escalation(action, cut))

        pending = [asdict(a) for a in handled if a.status == "pending"]
        self.pending_escalations = pending
        self._trace(
            "human_gate",
            f"{len(pending)} escalations await the medical monitor",
            [e for a in handled for e in a.evidence],
            pending=len(pending),
        )
        return handled

    # ---------- node 6: execute ----------

    def _execute(self, cut, protocol, findings, actions, queries, deviations):
        report = {
            "cut": cut,
            "protocol_version": protocol,
            "findings": [asdict(f) for f in findings],
            "escalations": [asdict(a) for a in actions],
            "queries": queries,
            "deviations": deviations,
        }
        self._trace(
            "execute",
            f"cycle complete: {len(findings)} findings, {len(actions)} escalations, {len(queries)} queries, {len(deviations)} deviations",
            [e for f in findings for e in f.evidence],
        )
        return report

    def run_cycle(self, cut: int, protocol_version: int) -> ReviewReport:
        self.cycle_trace = []
        self.pending_escalations = []

        findings = self._detect(cut, protocol_version)
        actions = self._medical_review(findings, cut)
        queries = self._data_manager(findings, cut)
        deviations = self._compliance(cut, protocol_version, findings)
        actions = self._human_gate(actions, cut)
        result = self._execute(cut, protocol_version, findings, actions, queries, deviations)

        stats = {
            "findings": len(findings),
            "escalations": len(actions),
            "pending_escalations": len(self.pending_escalations),
            "queries": len(queries),
            "deviations": len(deviations),
            "new_queries": len(queries),
            "new_escalations": sum(a.status == "approved" or a.status == "pending" for a in actions),
            "trace_entries": len(self.cycle_trace),
        }
        return ReviewReport(
            cut=cut,
            protocol_version=protocol_version,
            findings=result["findings"],
            escalations=result["escalations"],
            queries=result["queries"],
            deviations=result["deviations"],
            trace=list(self.cycle_trace),
            stats=stats,
            pending_escalations=self.pending_escalations,
        )
