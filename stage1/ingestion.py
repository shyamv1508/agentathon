import os
from .normalization import csv_rows, norm_domain_row, safe_int

BASE_DOMAINS=("DM","AE","LB","VS","EX","CM","DS","MH","EG")
META_FILES={"reference_ranges.csv","corrections.csv","cuts.csv"}

class DataStore:
    def __init__(self,data_dir):
        nested=os.path.join(data_dir,"data")
        self.data_dir=nested if os.path.isdir(nested) else data_dir
        self.raw={}; self.corrections=[]; self.cuts=[]; self.refs=[]; self.reference_ranges={}
        self._load()

    def _discover_domains(self):
        if not os.path.isdir(self.data_dir):
            return list(BASE_DOMAINS)
        names=[]
        for name in os.listdir(self.data_dir):
            if not name.lower().endswith(".csv") or name in META_FILES:
                continue
            names.append(os.path.splitext(name)[0].upper())
        return sorted(set(BASE_DOMAINS).union(names))

    def _load(self):
        rp=os.path.join(self.data_dir,"reference_ranges.csv")
        self.refs=csv_rows(rp) if os.path.exists(rp) else []
        for r in self.refs:
            key=(str(r.get("LAB","")).strip().upper(),str(r.get("LBTESTCD","")).strip().upper())
            self.reference_ranges[key]=r

        for d in self._discover_domains():
            p=os.path.join(self.data_dir,d+".csv")
            if not os.path.exists(p):
                p=os.path.join(self.data_dir,d.lower()+".csv")
            if os.path.exists(p):
                self.raw[d]=[norm_domain_row(d,r) for r in csv_rows(p)]

        cp=os.path.join(self.data_dir,"corrections.csv")
        self.corrections=csv_rows(cp) if os.path.exists(cp) else []
        cutp=os.path.join(self.data_dir,"cuts.csv")
        self.cuts=csv_rows(cutp) if os.path.exists(cutp) else []

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
