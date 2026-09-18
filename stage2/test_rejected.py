from pathlib import Path

from stage1.atlas import Atlas
from stage2.crew import Action, ReviewCrew
from stage1.graph import StudyGraph


class RejectCrew(ReviewCrew):
    def __init__(self, atlas):
        super().__init__("", "", "", atlas)
        self.calls = []
        self.memory = {
            "queries": {},
            "escalations": {},
            "rejected": {},
            "site_flags": {},
            "open_queries": {},
        }

    def _post(self, base, path, payload):
        self.calls.append((path, payload))
        return {
            "id": "reject-1",
            "decision": "REJECTED",
            "reason": "Monitor only; source evidence does not support escalation.",
        }


def main():
    atlas = Atlas(StudyGraph(str(Path("hackathon-data"))))
    atlas.graph.build(9)

    crew = RejectCrew(atlas)
    action = Action(
        "HYS_LAW_CANDIDATE",
        "042-S05-003",
        "S05",
        "MAJOR",
        "Deterministic rejection test.",
        [],
        ["Continue monitoring"],
    )

    first = crew._submit_escalation(action, 9)
    assert first.status == "monitoring"
    assert first.monitor_reason
    assert len(crew.calls) == 1

    second_action = Action(
        "HYS_LAW_CANDIDATE",
        "042-S05-003",
        "S05",
        "MAJOR",
        "Same escalation on a later cycle.",
        [],
        ["Continue monitoring"],
    )
    second = crew._submit_escalation(second_action, 9)

    assert second.status == "monitoring"
    assert second.monitor_reason == first.monitor_reason
    assert len(crew.calls) == 1, "Rejected escalation must not be resubmitted"
    assert crew.memory["rejected"], "Rejection must be persisted in memory"

    print("REJECTED TEST: PASS")
    print("First decision: REJECTED -> monitoring")
    print("Second attempt: not resubmitted")
    print("Rejection memory: retained")


if __name__ == "__main__":
    main()
