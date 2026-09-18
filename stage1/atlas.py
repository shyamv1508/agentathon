import argparse,os
from starter.schemas import Question,Answer
from .graph import StudyGraph
from .queries import QueryEngine
from .documents import DocumentStore

class Atlas:
    def __init__(self,graph:StudyGraph):
        self.graph=graph
        self.documents=DocumentStore(os.path.join(os.path.dirname(graph.data_dir),"documents"))
        self.engine=QueryEngine(graph,self.documents)

    def answer(self,question:Question)->Answer:
        values,evidence,text=self.engine.execute(question)
        confidence=1.0 if evidence else (0.95 if not values else 0.55)
        return Answer(question_id=question.question_id,answer=[str(x) for x in values],text=text,evidence=evidence,confidence=confidence,steps_used=3,tokens_used=0)

def main():
    p=argparse.ArgumentParser();p.add_argument("--data",required=True);p.add_argument("--cut",type=int,default=12);p.add_argument("--question")
    a=p.parse_args();atlas=Atlas(StudyGraph(a.data));atlas.graph.build(a.cut)
    if a.question:print(atlas.answer(Question(question_id="cli",kind="lookup",text=a.question,cut=a.cut)).model_dump_json(indent=2))
if __name__=="__main__":main()
