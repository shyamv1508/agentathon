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
    args = p.parse_args()

    atlas = Atlas(StudyGraph(args.data))
    crew = ReviewCrew(args.hub, args.gateway, args.team_key, atlas)
    report = crew.run_cycle(args.cut, args.protocol)
    print(json.dumps(report.model_dump(), indent=2))


if __name__ == "__main__":
    main()
