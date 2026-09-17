"""Run the agent over sample_questions.csv — one trace per question.

Run this as a Domino Job:  python dev_eval.py

That creates an agent version in the Experiment Manager holding every trace,
its evaluation scores, and your ai_system_config.yaml as parameters. Only runs
that come from a Job can be deployed.
"""

import csv
from pathlib import Path
from typing import Any, Dict

from domino.agents.tracing import add_tracing

try:  # current SDK
    from domino.agents.logging import DominoAgentContext
except ImportError:  # older SDK
    from domino.agents.logging import DominoRun as DominoAgentContext

from agent import run_agent
from evaluation import score_answer

ROOT = Path(__file__).parent
CONFIG_PATH = str(ROOT / "ai_system_config.yaml")
QUESTIONS_PATH = ROOT / "sample_questions.csv"

AGGREGATED_METRICS = [
    ("tool_score", "mean"),
    ("accuracy_score", "mean"),
    ("overall_score", "mean"),
]


def judge(span) -> Dict[str, float]:
    """Runs automatically after each traced call. Whatever it returns lands on the trace."""
    data_point = span.inputs["data_point"]
    output = span.outputs or {}
    return score_answer(
        question=data_point["question"],
        answer=output.get("answer", ""),
        tool_used=output.get("tool_used", "none"),
        expected=data_point.get("expected", ""),
        expected_tool=data_point.get("expected_tool", ""),
    )


@add_tracing(name="titanic_question", evaluator=judge)
def answer_question(data_point: Dict[str, Any]) -> Dict[str, Any]:
    """One question -> one trace, with the plan and tool call nested inside it."""
    return run_agent(data_point["question"])


def agent_context():
    """The kwarg for summary statistics is named differently across SDK versions."""
    for kwarg in ("custom_summary_metrics", "aggregated_metrics"):
        try:
            return DominoAgentContext(agent_config_path=CONFIG_PATH, **{kwarg: AGGREGATED_METRICS})
        except TypeError:
            continue
    return DominoAgentContext(agent_config_path=CONFIG_PATH)  # means are logged by default


def main() -> None:
    with agent_context():
        with open(QUESTIONS_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                print(f"\n[{row['question_id']}] {row['question']}")
                result = answer_question(row)
                print(f"  tool: {result['tool_used']}")
                print(f"  ->    {result['answer']}")

    print("\nDone. Open Experiments in your project to see the run and its traces.")


if __name__ == "__main__":
    main()
