import argparse
from pathlib import Path

from starter.schemas import Question, Answer
from .graph import StudyGraph
from .queries import QueryEngine
from .documents import DocumentStore
from .evidence import validate


class Atlas:
    def __init__(self, graph: StudyGraph):
        self.graph = graph
        data_dir = Path(graph.data_dir)
        self.documents = DocumentStore(str(data_dir / "documents"))
        self.engine = QueryEngine(graph, self.documents)

    def answer(self, question: Question) -> Answer:
        if self.graph.cut != question.cut:
            self.graph.build(question.cut)
        else:
            self.graph.ensure_fresh()
        values, evidence, text = self.engine.execute(question)
        evidence = validate(self.graph, evidence)
        confidence = 1.0 if evidence else (0.95 if not values else 0.55)
        return Answer(
            question_id=question.question_id,
            answer=[str(x) for x in values],
            text=text,
            evidence=evidence,
            confidence=confidence,
            steps_used=3,
            tokens_used=0,
        )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--cut", type=int, default=12)
    p.add_argument("--question")
    a = p.parse_args()

    atlas = Atlas(StudyGraph(a.data))
    stats = atlas.graph.build(a.cut)

    print("ATLAS StudyGraph")
    print(f"Cut: {stats['cut']}")
    print(f"Subjects: {stats['subjects']}")
    print(f"Records: {stats['records']}")
    print(f"Nodes: {stats['nodes']}")
    print(f"Edges: {stats['edges']}")
    print(f"Build time: {stats['build_time_ms']} ms")

    if a.question:
        question = Question(question_id="cli", kind="lookup", text=a.question, cut=a.cut)
        print(atlas.answer(question).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
