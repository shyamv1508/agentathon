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

    def build(self,cut:int|None=None)->dict:
        cut=12 if cut is None else int(cut)
        t=time.perf_counter()
        self.rows=self.store.rows(cut); self.cut=cut
        self.by_key={}; self.by_subject=defaultdict(lambda: defaultdict(list))
        for d,rows in self.rows.items():
            for r in rows:
                seq=r.get("_seq")
                key=(d,r.get("USUBJID"),seq)
                self.by_key[key]=r
                self.by_subject[r.get("USUBJID")][d].append(r)
        for domains in self.by_subject.values():
            for rows in domains.values():
                rows.sort(key=lambda r: ((r.get('_date') or '9999-99-99'), r.get('_seq') or 0))
        self.subjects={s:dict(domains) for s,domains in self.by_subject.items() if s}
        records=sum(len(v) for v in self.rows.values())
        edges=records
        h=hashlib.sha256()
        for name in sorted(os.listdir(self.store.data_dir)):
            if name.endswith(".csv"):
                p=os.path.join(self.store.data_dir,name)
                try:
                    st=os.stat(p); h.update(name.encode()); h.update(str(st.st_size).encode()); h.update(str(st.st_mtime_ns).encode())
                except OSError: pass
        self._fingerprint=h.hexdigest()
        return {"nodes":records+len(self.subjects),"edges":edges,"records":records,"subjects":len(self.subjects),"build_time_ms":round((time.perf_counter()-t)*1000,3),"cut":cut}

    def patient360(self,usubjid:str)->dict:
        if self.cut is None: self.build()
        return {"usubjid":usubjid,"cut":self.cut,"domains":{d:list(self.by_subject.get(usubjid,{}).get(d,[])) for d in self.rows}}
