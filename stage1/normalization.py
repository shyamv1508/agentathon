import re
from datetime import datetime
from typing import Any

DATE_FORMATS=("%Y-%m-%d","%Y/%m/%d","%d-%b-%Y","%d-%B-%Y","%d/%m/%Y","%m/%d/%Y","%Y%m%d")

def parse_date(value: Any):
    if value is None or str(value).strip()=="":
        return None
    s=str(value).strip()
    for fmt in DATE_FORMATS:
        try: return datetime.strptime(s,fmt).date()
        except ValueError: pass
    try: return datetime.fromisoformat(s.replace("Z","")).date()
    except ValueError: return None

def parse_number(value: Any):
    if value is None: return None, None
    s=str(value).strip()
    if not s or s.upper() in {"ND","NA","N/A","NULL","NONE"}: return None, "unknown"
    s=s.replace(",",".") if re.fullmatch(r"[-+]?\d+,\d+",s) else s
    m=re.fullmatch(r"([<>]=?)?\s*([-+]?\d+(?:\.\d+)?)",s)
    if not m: return None, "unknown"
    return float(m.group(2)), m.group(1)

def csv_rows(path):
    import csv
    with open(path,encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def safe_int(v):
    try: return int(float(str(v).strip()))
    except (TypeError,ValueError): return None

def norm_domain_row(domain,row):
    r=dict(row)
    seq_keys=("LBSEQ","AESEQ","VSSEQ","EXSEQ","CMSEQ","DSSEQ","MHSEQ","EGSEQ")
    for k in seq_keys:
        if k in r:
            r["_seq"]=safe_int(r[k]); break
    else:
        for k,v in r.items():
            if str(k).upper().endswith("SEQ"):
                r["_seq"]=safe_int(v); break
    r["_domain"]=domain
    date_candidates=("LBDTC","AESTDTC","VSDTC","EXSTDTC","CMSTDTC","DSSTDTC","BRTHDTC","EGDTC","DTC","DATE","START_DATE","STARTDT")
    r["_date"]=next((parse_date(r.get(k)) for k in date_candidates if parse_date(r.get(k))),None)
    return r
