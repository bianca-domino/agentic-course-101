"""Scoring for each answer. Deterministic — no LLM judge, no API key.

Returns a plain dict of metric name -> number. Domino attaches it to the trace
and averages it across the run. Replace this later with an LLM-as-judge and
nothing else in the project has to change.
"""


def score_answer(question: str, answer: str, tool_used: str, expected: str, expected_tool: str) -> dict:
    answer_lower = (answer or "").lower()

    # 1. Did it pick the right tool?
    tool_score = 1.0 if tool_used == expected_tool else 0.0

    # 2. Does the answer contain the figures or names it should?
    #    Multiple expected terms are separated by "|" and all must appear.
    terms = [t.strip().lower() for t in expected.split("|") if t.strip()]
    accuracy_score = (sum(1 for t in terms if t in answer_lower) / len(terms)) if terms else tool_score

    # 3. Is it short enough to be useful?
    conciseness_score = 1.0 if len(answer) <= 200 else 0.5

    return {
        "tool_score": tool_score,
        "accuracy_score": round(accuracy_score, 3),
        "conciseness_score": conciseness_score,
        "overall_score": round(0.4 * tool_score + 0.4 * accuracy_score + 0.2 * conciseness_score, 3),
    }
