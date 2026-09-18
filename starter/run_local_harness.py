"""Local harness for running the Stage 1 ATLAS implementation.

Usage:
    python starter/run_local_harness.py --module stage1.atlas --data hackathon-data
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import sys
import time
from pathlib import Path


def load_questions(data_dir: Path) -> list[dict]:
    """Load public questions when supplied by the competition data package."""
    candidates = [
        data_dir / "public_questions.json",
        data_dir / "questions.json",
        data_dir / "responses" / "public_questions.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    for key in ("questions", "public_questions"):
                        if isinstance(value.get(key), list):
                            return value[key]
            except (OSError, json.JSONDecodeError):
                pass
    return []


def make_question(question_data: dict, schemas_module):
    Question = getattr(schemas_module, "Question")
    return Question.model_validate(question_data)


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

    Atlas = module.Atlas
    atlas = Atlas(str(data_dir))

    questions = load_questions(data_dir)

    if not questions:
        # Smoke-test the required interface when the package does not expose
        # a public question file.
        questions = [
            {
                "question_id": "LOCAL-SMOKE-001",
                "kind": "lookup",
                "text": "Show the records for subject 042-S01-001",
                "cut": 12,
            }
        ]

    results = []
    for raw in questions:
        question = make_question(raw, schemas)
        started = time.perf_counter()
        answer = atlas.answer(question)
        elapsed_ms = (time.perf_counter() - started) * 1000

        if hasattr(answer, "model_dump"):
            payload = answer.model_dump()
        else:
            payload = answer

        payload["_elapsed_ms"] = round(elapsed_ms, 3)
        results.append(payload)

        print(json.dumps(payload, indent=2, default=str))

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
