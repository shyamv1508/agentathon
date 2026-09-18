from starter.schemas import RecordRef

def ref(row,document=None,section=None):
    return RecordRef(domain=row.get("_domain") or "",usubjid=row.get("USUBJID"),seq=row.get("_seq"),document=document,section=section)

def refs(rows,document=None,section=None):
    return [ref(r,document,section) for r in rows]

def validate(graph,evidence):
    valid=[]
    for e in evidence:
        if e.document or (e.domain,e.usubjid,e.seq) in graph.by_key:
            valid.append(e)
    return valid
