from pathlib import Path

from stage1.atlas import Atlas
from stage2.crew import Action, ReviewCrew
from stage1.graph import StudyGraph


class FakeGatewayCrew(ReviewCrew):
    def __init__(self, atlas):
        super().__init__("", "", "", atlas)
        self.calls = []

    def _post(self, base, path, payload):
        self.calls.append((path, payload))
        if path == "/escalations" and len([c for c in self.calls if c[0] == "/escalations"]) == 1:
            return {
                "id": "clarify-1",
                "decision": "CLARIFY",
                "reason": "Please confirm the screening ALT and any hepatotoxic concomitant medicine.",
            }
        return {"id": "clarify-2", "decision": "APPROVED", "reason": "Clarification received."}


def main():
    atlas = Atlas(StudyGraph(str(Path("hackathon-data"))))
    atlas.graph.build(9)

    crew = FakeGatewayCrew(atlas)
    subject = "042-S07-001"

    action = Action(
        "HYS_LAW_CANDIDATE", subject, "S07", "MAJOR",
        "Deterministic CLARIFY flow test.", [],
        ["Escalate for medical review"],
    )

    handled = crew._submit_escalation(action, 9)
    calls = [payload for path, payload in crew.calls if path == "/escalations"]

    assert len(calls) == 2, "Expected initial escalation plus one resubmission"
    assert calls[1].get("clarification"), "Resubmission must contain clarification"
    clarification = calls[1]["clarification"]
    assert clarification["source"] == "StudyGraph"
    assert clarification["subject"] == subject
    assert "screening_alt" in clarification
    assert "concomitant_medications" in clarification
    assert handled.status == "approved"

    print("CLARIFY TEST: PASS")
    print("Initial decision: CLARIFY")
    print("Resubmission decision: APPROVED")
    print(f"Clarification source: {clarification['source']}")
    print(f"Screening ALT records: {len(clarification['screening_alt'])}")
    print(f"Concomitant medication records: {len(clarification['concomitant_medications'])}")


if __name__ == "__main__":
    main()
