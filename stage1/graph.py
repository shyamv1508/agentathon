from collections import defaultdict
import time
import hashlib
import os
from .ingestion import DataStore

class StudyGraph:
    def __init__(self,data_dir:str):
        self.data_dir=data_dir
        self.store=DataStore(data_dir)
        self.cut=None; self.rows={}; self.subjects={}
        self.by_key={}; self.by_subject=defaultdict(lambda: defaultdict(list)); self._fingerprint=''

    def _reindex_rows(self):
        self.by_key={}; self.by_subject=defaultdict(lambda: defaultdict(list))
        for d,rows in self.rows.items():
            for r in rows:
                key=(d,r.get("USUBJID"),r.get("_seq"))
                self.by_key[key]=r
                self.by_subject[r.get("USUBJID")][d].append(r)
        for domains in self.by_subject.values():
            for rows in domains.values():
                rows.sort(key=lambda r: ((r.get('_date') or '9999-99-99'), r.get('_seq') or 0))
        self.subjects={s:dict(domains) for s,domains in self.by_subject.items() if s}

    def build(self,cut:int|None=None)->dict:
        cut=12 if cut is None else int(cut)
        t=time.perf_counter()
        self.rows=self.store.rows(cut); self.cut=cut
        self._reindex_rows()
        records=sum(len(v) for v in self.rows.values())
        edges=records
        self._fingerprint=self._fingerprint_now()
        return {"nodes":records+len(self.subjects),"edges":edges,"records":records,"subjects":len(self.subjects),"build_time_ms":round((time.perf_counter()-t)*1000,3),"cut":cut}

    def update(self,cut:int)->dict:
        """Advance to a cut without re-reading CSV files; patch only changed record keys."""
        cut=int(cut); t=time.perf_counter()
        target=self.store.rows(cut)
        old={(d,r.get('USUBJID'),r.get('_seq')):r for d,rows in self.rows.items() for r in rows}
        new={(d,r.get('USUBJID'),r.get('_seq')):r for d,rows in target.items() for r in rows}
        changed={k for k in set(old)|set(new) if old.get(k)!=new.get(k)}
        for d in target:
            self.rows.setdefault(d,[])
        for key in changed:
            d=key[0]
            self.rows[d]=[r for r in self.rows.get(d,[]) if (d,r.get('USUBJID'),r.get('_seq'))!=key]
            if key in new: self.rows[d].append(new[key])
        for d in list(self.rows):
            if d not in target: self.rows.pop(d,None)
        self.cut=cut; self._reindex_rows(); self._fingerprint=self._fingerprint_now()
        return {"cut":cut,"changed_records":len(changed),"records":sum(len(v) for v in self.rows.values()),"subjects":len(self.subjects),"update_time_ms":round((time.perf_counter()-t)*1000,3)}

    def _fingerprint_now(self):
        h=hashlib.sha256()
        for name in sorted(os.listdir(self.store.data_dir)):
            if name.endswith(".csv"):
                p=os.path.join(self.store.data_dir,name)
                try:
                    st=os.stat(p); h.update(name.encode()); h.update(str(st.st_size).encode()); h.update(str(st.st_mtime_ns).encode())
                except OSError: pass
        return h.hexdigest()

    def ensure_fresh(self):
        if self.cut is None: self.build(12)
        elif self._fingerprint_now()!=self._fingerprint: self.update(self.cut)

    def patient360(self,usubjid:str)->dict:
        if self.cut is None: self.build()
        return {"usubjid":usubjid,"cut":self.cut,"domains":{d:list(self.by_subject.get(usubjid,{}).get(d,[])) for d in self.rows}}
