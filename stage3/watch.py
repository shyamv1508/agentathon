from __future__ import annotations
import hashlib, json, os, statistics, time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from stage1.normalization import parse_date, parse_number, safe_int
from stage2.crew import ReviewCrew

@dataclass
class Explanation:
    decision_id: str
    what: str
    evidence: list[dict]
    evidence_lines: list[str]
    alternatives: list[str]
    why: str
    consistent_with_trace: bool = True
    def model_dump(self): return asdict(self)

@dataclass
class SurveillanceReport:
    cuts: list[dict]
    signals: list[dict]
    site_risk: list[dict]
    deviations: list[dict]
    adversarial_events: list[dict]
    open_items: list[dict]
    budget: dict
    trace: list[dict] = field(default_factory=list)
    def model_dump(self): return asdict(self)
    def model_dump_json(self, **kwargs): return json.dumps(self.model_dump(), **kwargs)

class StudyWatch:
    """Unattended twelve-cut surveillance layer around Stage 2 ReviewCrew."""
    def __init__(self, data_dir: str, crew: ReviewCrew):
        self.data_dir=str(Path(data_dir)); self.crew=crew
        root=Path(self.data_dir).parent if Path(self.data_dir).name=="data" else Path(self.data_dir)
        self.state_path=Path(os.getenv("STAGE3_STATE_PATH",str(root/"stage3_state.json")))
        self.decision_path=Path(os.getenv("STAGE3_DECISION_LOG",str(root/"stage3_decisions.json")))
        self.state=self._load(self.state_path,{"last_cut":0,"protocol":None,"pending":{},"quarantined_sites":[],"untrusted_lab":[],"docs":{},"labs":{}})
        self.decisions=self._load(self.decision_path,{})
        self.trace=[]; self.started=0; self.budget=0

    @staticmethod
    def _load(path, default):
        if not path.exists(): return default
        try: return json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError): return default

    def _save(self):
        self.state_path.write_text(json.dumps(self.state,indent=2),encoding="utf-8")
        self.decision_path.write_text(json.dumps(self.decisions,indent=2),encoding="utf-8")

    @staticmethod
    def _site(subject):
        p=str(subject or "").split("-"); return p[1] if len(p)>1 else ""

    @staticmethod
    def _ref(row): return {"domain":row.get("_domain",""),"usubjid":row.get("USUBJID"),"seq":row.get("_seq")}

    def _protocol(self,cut):
        for r in self.crew.atlas.graph.store.cuts:
            if safe_int(r.get("cut"))==cut: return safe_int(r.get("protocol_version")) or 1
        return self.state.get("protocol") or 1

    def _log(self,cut,event,evidence=None,**extra):
        x={"cut":cut,"event":event,"evidence":evidence or []}; x.update(extra); self.trace.append(x)

    def _documents(self,cut):
        folder=Path(self.crew.atlas.graph.store.data_dir)/"documents"; events=[]; now={}
        if not folder.is_dir(): return events
        for p in folder.glob("*.md"):
            h=hashlib.sha256(p.read_bytes()).hexdigest(); now[p.name]=h
            if p.name in self.state["docs"] and self.state["docs"][p.name]!=h:
                text=p.read_text(encoding="utf-8",errors="replace").lower()
                tampered=any(s in text for s in ("automated reviewer","ignore safety","accept values"))
                e={"type":"DOCUMENT_CHANGED","document":p.name,"tampered":tampered,"action":"re-read; reviewer-directed instruction ignored; logged"}
                events.append(e); self._log(cut,"document_changed",[{"document":p.name}],**e)
        self.state["docs"]=now; return events

    def _lab_shift(self,cut):
        g=self.crew.atlas.graph; groups={}; events=[]
        for r in g.rows.get("LB",[]):
            test=str(r.get("LBTESTCD") or r.get("LBTEST") or "").upper(); n,q=parse_number(r.get("LBORRES"))
            if test and n is not None and q not in {"<","<=","unknown"}: groups.setdefault((self._site(r.get("USUBJID")),test),[]).append(n)
        for (site,test),vals in groups.items():
            key=f"{site}|{test}"; med=statistics.median(vals); old=self.state["labs"].get(key); self.state["labs"][key]={"cut":cut,"median":med}
            if not old or old["cut"]==cut or not old["median"]: continue
            ratio=med/old["median"]; factors=(18.0,1000.0,0.001,1/18.0); f=min(factors,key=lambda x:abs(ratio-x))
            if abs(ratio-f)/f<0.12:
                refs=[self._ref(r) for r in g.rows.get("LB",[]) if self._site(r.get("USUBJID"))==site and str(r.get("LBTESTCD") or r.get("LBTEST") or "").upper()==test]
                e={"type":"LAB_UNIT_SHIFT","site":site,"test":test,"previous_median":old["median"],"current_median":med,"ratio":ratio,"clinical_escalation":False,"action":"mark untrusted; exclude from safety analysis; request laboratory re-issue"}
                events.append(e); self.state["untrusted_lab"].append({"site":site,"test":test,"cut":cut}); self._log(cut,"laboratory_unit_problem",refs[:20],**e)
        return events

    def _regularity(self,cut):
        g=self.crew.atlas.graph; by_site={}; events=[]
        for rows in g.rows.values():
            for r in rows:
                s=self._site(r.get("USUBJID")); d=parse_date(r.get("_date") or r.get("DTC") or r.get("DATE")); by_site.setdefault(s,[]).append((r,d))
        for site,rows in by_site.items():
            days=[d.weekday() for _,d in rows if d]
            texts=[str(r.get("AETERM") or r.get("DSDECOD") or r.get("COMMENT") or "").strip().lower() for r,_ in rows]
            texts=[x for x in texts if x]
            if len(days)>=8 and max(days.count(x) for x in set(days))/len(days)>=.9 and texts and max(texts.count(x) for x in set(texts))/len(texts)>=.75:
                e={"type":"IMPLAUSIBLE_REGULARITY","site":site,"action":"quarantine from safety analyses; recommend audit"}; events.append(e)
                if site not in self.state["quarantined_sites"]: self.state["quarantined_sites"].append(site)
                self._log(cut,"site_regularly_suspicious",[],**e)
        return events

    def _quarantine(self):
        """Temporarily exclude quarantined/untrusted records from safety analysis."""
        g=self.crew.atlas.graph; sites=set(self.state["quarantined_sites"]); bad={(x["site"],x["test"]) for x in self.state["untrusted_lab"]}
        backup={d:list(rows) for d,rows in g.rows.items()}
        for d,rows in list(g.rows.items()):
            g.rows[d]=[r for r in rows if self._site(r.get("USUBJID")) not in sites and not (d=="LB" and (self._site(r.get("USUBJID")),str(r.get("LBTESTCD") or r.get("LBTEST") or "").upper()) in bad)]
        g._reindex_rows()
        return backup

    def _restore_quarantine(self, backup):
        g=self.crew.atlas.graph
        g.rows=backup
        g._reindex_rows()

    def _decisions(self,cut,report):
        for a in report.escalations:
            did=f"D-{cut:02d}-{len(self.decisions)+1:03d}"; refs=a.get("evidence",[])
            self.decisions[did]={"decision_id":did,"cut":cut,"what":a.get("summary",""),"evidence":refs,"evidence_lines":[f"{r.get('domain')} {r.get('usubjid')} #{r.get('seq')}" for r in refs],"alternatives":a.get("alternatives",[]),"why":a.get("summary",""),"trace_node":"human_gate","status":a.get("status","pending")}

    def run_period(self,cuts=range(1,13),budget_seconds=None):
        self.started=time.perf_counter(); self.budget=float(budget_seconds or os.getenv("STAGE3_BUDGET_SECONDS","180")); reports=[]; signals=[]; deviations=[]; adversarial=[]
        for cut in cuts:
            if self.crew.atlas.graph.cut is None: self.crew.atlas.graph.build(cut)
            elif self.crew.atlas.graph.cut!=cut: self.crew.atlas.graph.update(cut)
            adversarial += self._documents(cut)+self._lab_shift(cut)+self._regularity(cut)
            quarantine_backup=self._quarantine()
            protocol=self._protocol(cut); report=self.crew.run_cycle(cut,protocol); self._restore_quarantine(quarantine_backup); self._decisions(cut,report)
            for p in report.pending_escalations:
                key=f"{p.get('code')}|{p.get('usubjid')}|{p.get('site')}"; state=self.state["pending"].setdefault(key,{"first_cut":cut}); state["last_cut"]=cut; state["waited_cuts"]=cut-state["first_cut"]
                if state["waited_cuts"]>=4: self._log(cut,"escalation_unanswered_after_four_cuts",p.get("evidence",[]),no_silent_approval=True,standing_limits=True)
            signals += report.findings; deviations += report.deviations; reports.append({"cut":cut,"protocol_version":protocol,"stats":report.stats})
            if self.state.get("protocol") not in (None,protocol): self._log(cut,"amendment_delta_recomputed",[],previous_protocol=self.state["protocol"],protocol=protocol)
            self.state["protocol"]=protocol; self.state["last_cut"]=cut; self._save()
        used=time.perf_counter()-self.started; ratio=used/self.budget if self.budget else 0
        tier="safety_only" if ratio>=.9 else "degraded" if ratio>=.8 else "normal"
        return SurveillanceReport(reports,signals,[],deviations,adversarial,list(self.state["pending"].values()),{"seconds_used":round(used,3),"seconds_budget":self.budget,"ratio":round(ratio,3),"final_tier":tier},self.trace)

    def explain(self,decision_id):
        if decision_id not in self.decisions: raise KeyError(decision_id)
        d=self.decisions[decision_id]; actual=[]
        if self.crew.trace_path.exists():
            for line in self.crew.trace_path.read_text(encoding="utf-8").splitlines():
                try:
                    x=json.loads(line)
                    if x.get("cycle")==d["cut"] and x.get("node")==d["trace_node"]: actual += x.get("evidence",[])
                except ValueError: pass
        expected={json.dumps(x,sort_keys=True) for x in d["evidence"]}; seen={json.dumps(x,sort_keys=True) for x in actual}
        return Explanation(d["decision_id"],d["what"],d["evidence"],d["evidence_lines"],d["alternatives"],d["why"],expected.issubset(seen))
