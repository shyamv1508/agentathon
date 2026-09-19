import argparse
import json
from stage1.atlas import Atlas
from stage1.graph import StudyGraph
from stage2.crew import ReviewCrew
from stage3.watch import StudyWatch


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data",default="hackathon-data")
    p.add_argument("--hub",default="")
    p.add_argument("--gateway",default="")
    p.add_argument("--team-key",default="")
    p.add_argument("--budget-seconds",type=float,default=180)
    p.add_argument("--output",default="stage3_surveillance_report.json")
    args=p.parse_args()
    atlas=Atlas(StudyGraph(args.data))
    crew=ReviewCrew(args.hub,args.gateway,args.team_key,atlas)
    watch=StudyWatch(args.data,crew)
    report=watch.run_period(range(1,13),budget_seconds=args.budget_seconds)
    with open(args.output,"w",encoding="utf-8") as f: json.dump(report.model_dump(),f,indent=2)
    print("ATLAS WATCH — Stage 3")
    print(f"Cuts: 1-12 | Budget: {report.budget['seconds_used']} / {report.budget['seconds_budget']} s")
    print(f"Signals: {len(report.signals)} | Deviations: {len(report.deviations)} | Adversarial: {len(report.adversarial_events)}")
    print(f"Open items: {len(report.open_items)}")
    print(f"Decision log: {watch.decision_path}")
    print(f"Report: {args.output}")

if __name__ == "__main__":
    main()
