from pydantic import BaseModel
from typing import List, Optional, Literal

class RecordRef(BaseModel):
    domain: str
    usubjid: Optional[str]
    seq: Optional[int]
    document: Optional[str]
    section: Optional[str]

class Question(BaseModel):
    question_id: str
    kind: Literal["count", "lookup", "finding", "trap"]
    text: str
    cut: int

class Answer(BaseModel):
    question_id: str
    answer: List[str]
    text: str
    evidence: List[RecordRef]
    confidence: float
    steps_used: int
    tokens_used: int
