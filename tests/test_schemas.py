from starter.schemas import Question, Answer, RecordRef

def test_required_shapes():
    q=Question(question_id="q1",kind="count",text="count subjects",cut=1)
    a=Answer(question_id=q.question_id,answer=["1"],text="1",evidence=[],confidence=1.0,steps_used=1,tokens_used=0)
    assert a.question_id=="q1"
