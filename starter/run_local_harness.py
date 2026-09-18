"""Local harness for running the Stage 1 ATLAS implementation."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path


def load_questions(data_dir: Path) -> list[dict]:
    candidates = [
        data_dir / "public_questions.json",
        data_dir / "questions.json",
        data_dir / "responses" / "public_questions.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for key in ("questions", "public_questions"):
                if isinstance(value.get(key), list):
                    return value[key]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", required=True)
    parser.add_argument("--data", required=True)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    data_dir = (repo_root / args.data).resolve()
    if not data_dir.exists():
        parser.error(f"data directory does not exist: {data_dir}")

    module = importlib.import_module(args.module)
    schemas = importlib.import_module("starter.schemas")
    if not hasattr(module, "Atlas"):
        raise RuntimeError(f"{args.module} must expose an Atlas class")

    graph = module.StudyGraph(str(data_dir))
    atlas = module.Atlas(graph)
    questions = load_questions(data_dir)

    if not questions:
        questions = [{
            "question_id": "LOCAL-SMOKE-001",
            "kind": "lookup",
            "text": "Show the records for subject 042-S01-001",
            "cut": 12,
        }]

    results = []
    for raw in questions:
        question = schemas.Question.model_validate(raw)
        started = time.perf_counter()
        answer = atlas.answer(question)
        elapsed_ms = (time.perf_counter() - started) * 1000
        payload = answer.model_dump() if hasattr(answer, "model_dump") else answer
        payload["_elapsed_ms"] = round(elapsed_ms, 3)
        results.append(payload)
        print(json.dumps(payload, indent=2, default=str))

    graph_stats = graph.build(12)
    stats_path = repo_root / "graph_stats.json"
    stats_path.write_text(json.dumps(graph_stats, indent=2), encoding="utf-8")

    output = {
        "module": args.module,
        "data": str(data_dir),
        "questions_run": len(results),
        "max_elapsed_ms": max(item["_elapsed_ms"] for item in results),
        "answers": results,
    }
    output_path = repo_root / "stage1_public.json"
    output_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {output_path}")
    print(f"Wrote {stats_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
