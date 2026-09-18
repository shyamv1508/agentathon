from .normalization import parse_number,parse_date

def protocol_version(cut): return 1 if cut<=4 else 2 if cut<=8 else 3

def lab_value(row):
    n,q=parse_number(row.get("LBORRES"))
    if n is None:return None,q,""
    unit=(row.get("LBORRESU") or "").strip()
    if row.get("LBTESTCD") in {"ALT","AST"} and unit.lower() in {"ukat/l","µkat/l","ukat / l"}:
        return n*60,q,"U/L"
    return n,q,unit

def serious_ae(row):
    return str(row.get("AESER","")).upper()=="Y" or str(row.get("AESHOSP","")).upper()=="Y"

def prohibited_cm(row,version):
    cls=str(row.get("CMCLAS","")).upper()
    return cls=="SYSTEMIC_GLUCOCORTICOID" or (version>=3 and cls=="SULFONYLUREA")

def _reference_high(graph,row):
    test=str(row.get("LBTESTCD","")).strip().upper()
    subject=str(row.get("USUBJID",""))
    parts=subject.split("-")
    site=parts[1].upper() if len(parts)>=3 else "CENTRAL"
    ref=graph.store.reference_ranges.get((site,test))
    if ref is None:
        ref=graph.store.reference_ranges.get(("CENTRAL",test))
    if ref is None:
        return None
    high,q=parse_number(ref.get("HIGH"))
    if high is None:
        return None
    unit=str(ref.get("UNIT","")).strip().lower()
    if unit in {"ukat/l","µkat/l","ukat / l"} and test in {"ALT","AST"}:
        high*=60
    return high

def hys_law_candidates(graph):
    out=[]
    for subject,doms in graph.by_subject.items():
        labs=doms.get("LB",[])
        for a in labs:
            if a.get("LBTESTCD") not in {"ALT","AST"}: continue
            av,aq,_=lab_value(a)
            if av is None or aq in {"<","<="}: continue
            ul = _reference_high(graph,a)
            if ul is None or av<=3*ul: continue
            ad=parse_date(a.get("LBDTC"))
            if not ad: continue
            for b in labs:
                if b.get("LBTESTCD")!="BILI": continue
                bv,bq,_=lab_value(b); bd=parse_date(b.get("LBDTC"))
                bili_ul = _reference_high(graph,b)
                if bv is None or bq in {"<","<="} or bili_ul is None or not bd or abs((bd-ad).days)>14 or bv<=2*bili_ul: continue
                out.append((subject,a,b))
    seen=set(); result=[]
    for x in out:
        if x[0] not in seen: seen.add(x[0]); result.append(x)
    return result

def dosing_findings(graph):
    expected={"DRUG":10.0,"PLACEBO":0.0}; out=[]
    for subject,doms in graph.by_subject.items():
        dm=(doms.get("DM") or [None])[0]; arm=(dm or {}).get("ARM")
        if arm not in expected: continue
        ex=doms.get("EX",[])
        if not ex:
            out.append((subject,"MISSING_EX",[])); continue
        for r in ex:
            n,_=parse_number(r.get("EXDOSE"))
            if n is not None and n!=expected[arm]: out.append((subject,"DOSING_ERROR",[r]))
    return out
