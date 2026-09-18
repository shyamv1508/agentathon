from collections import defaultdict
import time
from .ingestion import DataStore

class StudyGraph:
    def __init__(self,data_dir:str):
        self.data_dir=data_dir
        self.store=DataStore(data_dir)
        self.cut=None; self.rows={}; self.subjects={}
        self.by_key={}; self.by_subject=defaultdict(lambda: defaultdict(list))

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
        self.subjects={s:dict(domains) for s,domains in self.by_subject.items() if s}
        records=sum(len(v) for v in self.rows.values())
        edges=sum(max(0,len(ds)-1) for ds in self.by_subject.values())
        return {"nodes":records+len(self.subjects),"edges":edges,"records":records,"subjects":len(self.subjects),"build_time_ms":round((time.perf_counter()-t)*1000,3),"cut":cut}

    def patient360(self,usubjid:str)->dict:
        if self.cut is None: self.build()
        return {"usubjid":usubjid,"cut":self.cut,"domains":{d:list(self.by_subject.get(usubjid,{}).get(d,[])) for d in self.rows}}
