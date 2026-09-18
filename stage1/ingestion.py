import os
from .normalization import csv_rows, norm_domain_row, safe_int

DOMAINS=("DM","AE","LB","VS","EX","CM","DS","MH","EG")

class DataStore:
    def __init__(self,data_dir):
        self.data_dir=data_dir
        self.raw={}; self.corrections=[]; self.cuts=[]; self.refs=[]
        self._load()

    def _load(self):
        for d in DOMAINS:
            p=os.path.join(self.data_dir,d+".csv")
            self.raw[d]=[norm_domain_row(d,r) for r in csv_rows(p)] if os.path.exists(p) else []
        cp=os.path.join(self.data_dir,"corrections.csv")
        self.corrections=csv_rows(cp) if os.path.exists(cp) else []
        cutp=os.path.join(self.data_dir,"cuts.csv")
        self.cuts=csv_rows(cutp) if os.path.exists(cutp) else []
        rp=os.path.join(self.data_dir,"reference_ranges.csv")
        self.refs=csv_rows(rp) if os.path.exists(rp) else []

    def rows(self,cut):
        corr={}
        for c in self.corrections:
            cc=safe_int(c.get("cut"))
            if cc is not None and cc<=cut:
                key=(c.get("domain"),c.get("usubjid"),safe_int(c.get("seq")),c.get("field"))
                corr[key]=c.get("new_value")
        out={}
        for d,rows in self.raw.items():
            visible=[]
            for row in rows:
                ca=safe_int(row.get("cut_available"))
                if ca is None or ca<=cut:
                    r=dict(row)
                    for field in list(r):
                        key=(d,r.get("USUBJID"),r.get("_seq"),field)
                        if key in corr: r[field]=corr[key]
                    visible.append(r)
            out[d]=visible
        return out
