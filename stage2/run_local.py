import argparse
import json

from stage1.atlas import Atlas
from stage1.graph import StudyGraph
from stage2.crew import ReviewCrew


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="hackathon-data")
    p.add_argument("--cut", type=int, default=6)
    p.add_argument("--protocol", type=int, default=2)
    p.add_argument("--hub", default="")
    p.add_argument("--gateway", default="")
    p.add_argument("--team-key", default="")
    p.add_argument("--output", default="stage2_report.json")
    args = p.parse_args()

    atlas = Atlas(StudyGraph(args.data))
    crew = ReviewCrew(args.hub, args.gateway, args.team_key, atlas)
    report = crew.run_cycle(args.cut, args.protocol)
    payload = report.model_dump()

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    stats = payload.get("stats", {})
    pending = payload.get("pending_escalations", [])

    print("ATLAS MONITOR — Stage 2")
    print(f"Cut: {args.cut}")
    print(f"Protocol: v{args.protocol}")
    print()
    print(f"Findings: {stats.get('findings', 0)}")
    print(f"Escalations: {stats.get('escalations', 0)}")
    print(f"Pending: {stats.get('pending_escalations', len(pending))}")
    print(f"Queries: {stats.get('queries', 0)}")
    print(f"Deviations: {stats.get('deviations', 0)}")
    print(f"New queries: {stats.get('new_queries', 0)}")
    print(f"New escalations: {stats.get('new_escalations', 0)}")
    print(f"Trace entries: {stats.get('trace_entries', len(payload.get('trace', [])))}")
    print()
    print("Pending escalations:")
    for i, item in enumerate(pending, 1):
        kind = item.get("code") or item.get("type") or item.get("reason") or "UNKNOWN"
        subject = item.get("usubjid") or item.get("site") or "—"
        print(f"{i}. {kind} — {subject}")

    print()
    print(f"Full report saved to: {args.output}")


if __name__ == "__main__":
    main()
