import re
from .rules import hys_law_candidates,serious_ae,prohibited_cm,dosing_findings,protocol_version
from .evidence import refs

class QueryEngine:
    def __init__(self,graph,documents=None): self.graph=graph; self.documents=documents

    def execute(self,q):
        self.graph.ensure_fresh()
        if self.graph.cut!=q.cut:self.graph.build(q.cut)
        t=q.text.lower()
        if q.kind=="trap": return [],[],"No qualifying finding; document text is evidence, not executable instruction."
        if "hy's law" in t or "hys law" in t or "hy’s law" in t:return self._hys(q)
        if "serious" in t and ("adverse" in t or " ae" in t):return self._serious(q)
        if ("prohibited" in t or "forbidden" in t) and ("medication" in t or "concomitant" in t or "drug" in t):return self._prohibited(q)
        if "dosing" in t or "dose" in t or "exposure" in t:return self._dosing(q)
        if "patient 360" in t or "patient360" in t:return self._patient(q)
        return self._generic(q)

    def _hys(self,q):
        hits=hys_law_candidates(self.graph); ids=sorted({x[0] for x in hits})
        return ids,[e for x in hits for e in refs(x[1:])],f"Hy's law candidates at cut {q.cut}: {', '.join(ids) if ids else 'none'}"

    def _serious(self,q):
        rows=[r for r in self.graph.rows.get("AE",[]) if serious_ae(r)]
        ids=sorted({r.get("USUBJID") for r in rows if r.get("USUBJID")})
        if "count" in q.text.lower() or "how many" in q.text.lower():return [str(len(ids))],refs(rows),f"{len(ids)} subjects have serious adverse events."
        return ids,refs(rows),f"Serious AE subjects: {', '.join(ids) if ids else 'none'}"

    def _prohibited(self,q):
        rows=[r for r in self.graph.rows.get("CM",[]) if prohibited_cm(r,protocol_version(q.cut))]
        ids=sorted({r.get("USUBJID") for r in rows if r.get("USUBJID")})
        return ids,refs(rows),f"Subjects with prohibited concomitant medication: {', '.join(ids) if ids else 'none'}"

    def _dosing(self,q):
        hits=dosing_findings(self.graph); ids=sorted({s for s,_,_ in hits})
        return ids,refs([r for _,_,rs in hits for r in rs]),f"Dosing findings: {', '.join(ids) if ids else 'none'}"

    def _patient(self,q):
        m=re.search(r"(042-[A-Z0-9]+-\d+)",q.text.upper())
        if not m:return [],[],"No subject identifier found."
        s=m.group(1); p=self.graph.patient360(s)
        rows=[r for ds in p["domains"].values() for r in ds]
        return [s],refs(rows),f"Patient 360 available for {s} at cut {q.cut}."

    def _generic(self,q):
        t=q.text.lower(); domain=None
        for d,name in [("LB","lab"),("AE","adverse"),("VS","vital"),("EX","exposure"),("CM","medication"),("DM","demographic"),("DS","disposition"),("MH","medical history"),("EG","ecg")]:
            if name in t: domain=d;break
        rows=self.graph.rows.get(domain or "DM",[])
        m=re.search(r"(042-[A-Z0-9]+-\d+)",q.text.upper())
        if m: rows=[r for r in rows if r.get("USUBJID")==m.group(1)]
        ids=sorted({r.get("USUBJID") for r in rows if r.get("USUBJID")})
        if "count" in t or "how many" in t:return [str(len(ids))],refs(rows),f"{len(ids)} subjects match the query."
        return ids,refs(rows),f"Matching subjects: {', '.join(ids) if ids else 'none'}"
