"""Titanic agent — plan, call a tool, answer.

Three parts, same as any agent:

    planner  ->  decides which tool the question needs
    tools    ->  do the real work against the Titanic data
    answer   ->  turns the tool result into a sentence

The planner here is keyword rules, so this whole demo runs with no LLM and no
API key. Swapping those rules for an LLM call is a one-function change — see
"Add an LLM" in the README. Everything else, including the tracing, stays the same.
"""

from functools import lru_cache
from pathlib import Path

import mlflow
import pandas as pd
import yaml

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "ai_system_config.yaml"


@lru_cache(maxsize=1)
def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def load_data() -> pd.DataFrame:
    df = pd.read_csv(ROOT / load_config()["data"]["path"])
    df["AgeGroup"] = pd.cut(
        df["Age"],
        bins=[0, 12, 18, 35, 60, 120],
        labels=["child", "teen", "young adult", "adult", "senior"],
    )
    return df


# ---------------------------------------------------------------------------
# Tools. Each one shows up as its own TOOL span in the trace.
# ---------------------------------------------------------------------------

COLUMNS = {"sex": "Sex", "class": "Pclass", "embarked": "Embarked", "age_group": "AgeGroup"}


@mlflow.trace(span_type="TOOL", name="dataset_summary")
def dataset_summary() -> dict:
    """Overall size and survival statistics for the dataset."""
    df = load_data()
    return {
        "passengers": int(len(df)),
        "survivors": int(df["Survived"].sum()),
        "survival_rate_pct": float(df["Survived"].mean() * 100),
        "average_age": float(df["Age"].mean()),
        "average_fare": float(df["Fare"].mean()),
    }


@mlflow.trace(span_type="TOOL", name="survival_rate")
def survival_rate(group_by: str) -> dict:
    """Survival rate broken down by sex, class, embarked, or age_group."""
    column = COLUMNS.get(group_by)
    if column is None:
        return {"error": f"unsupported group_by '{group_by}'"}
    grouped = load_data().groupby(column, observed=True)["Survived"]
    return {
        "group_by": group_by,
        "rates_pct": {str(k): float(v * 100) for k, v in grouped.mean().items()},
        "counts": {str(k): int(v) for k, v in grouped.size().items()},
    }


@mlflow.trace(span_type="TOOL", name="find_passenger")
def find_passenger(name_contains: str) -> dict:
    """Look up passengers whose name contains the given text."""
    df = load_data()
    matches = df[df["Name"].str.contains(name_contains, case=False, na=False)]
    return {
        "search_term": name_contains,
        "matches": int(len(matches)),
        "passengers": matches[["Name", "Sex", "Age", "Pclass", "Fare", "Survived"]]
        .head(3)
        .to_dict(orient="records"),
    }


TOOLS = {
    "dataset_summary": dataset_summary,
    "survival_rate": survival_rate,
    "find_passenger": find_passenger,
}


# ---------------------------------------------------------------------------
# Planner. Replace this function with an LLM call to make the agent autonomous.
# ---------------------------------------------------------------------------

GROUP_KEYWORDS = {
    "sex": ["women", "men", "female", "male", "sex", "gender"],
    "class": ["class", "first class", "third class", "ticket class"],
    "embarked": ["embark", "port", "cherbourg", "southampton", "queenstown"],
    "age_group": ["age", "children", "child", "kids", "young", "old", "senior", "adult"],
}

SUMMARY_KEYWORDS = ["how many passengers", "total", "overall", "average", "dataset", "fare"]


@mlflow.trace(span_type="AGENT", name="plan")
def plan(question: str) -> dict:
    """Decide which tool to call and with what arguments."""
    q = question.lower()

    # A name in quotes, or "named X" / "surname X", means a lookup.
    for marker in ("named ", "surname ", "passenger called ", "name of "):
        if marker in q:
            term = q.split(marker, 1)[1].split("?")[0].strip().strip('"').split()[0]
            if term:
                return {"tool": "find_passenger", "args": {"name_contains": term},
                        "reason": f"question asks about a specific passenger ({term})"}

    if "surviv" in q or "die" in q or "died" in q:
        for group, words in GROUP_KEYWORDS.items():
            if any(w in q for w in words):
                return {"tool": "survival_rate", "args": {"group_by": group},
                        "reason": f"survival question mentioning {group}"}
        return {"tool": "dataset_summary", "args": {},
                "reason": "survival question with no specific breakdown"}

    if any(w in q for w in SUMMARY_KEYWORDS):
        return {"tool": "dataset_summary", "args": {}, "reason": "question about overall statistics"}

    return {"tool": None, "args": {}, "reason": "question is not about the Titanic dataset"}


# ---------------------------------------------------------------------------
# Answer formatting
# ---------------------------------------------------------------------------


@mlflow.trace(span_type="CHAIN", name="format_answer")
def format_answer(question: str, step: dict, result: dict) -> str:
    config = load_config()["response"]
    dp = config["decimals"]
    detailed = config["style"] == "detailed"

    if step["tool"] is None:
        return "I can only answer questions about the Titanic passenger dataset."

    if step["tool"] == "dataset_summary":
        answer = (
            f"The dataset has {result['passengers']} passengers, "
            f"{result['survivors']} of whom survived — a survival rate of "
            f"{result['survival_rate_pct']:.{dp}f}%."
        )
        if detailed:
            answer += (
                f" The average age was {result['average_age']:.{dp}f} years and the average"
                f" fare was ${result['average_fare']:.{dp}f}."
            )
        return answer

    if step["tool"] == "survival_rate":
        rates = result["rates_pct"]
        parts = [f"{k}: {v:.{dp}f}%" for k, v in rates.items()]
        best = max(rates, key=rates.get)
        answer = f"Survival rate by {result['group_by'].replace('_', ' ')} — " + ", ".join(parts) + "."
        answer += f" The highest was {best} at {rates[best]:.{dp}f}%."
        if detailed:
            counts = ", ".join(f"{k}: {v}" for k, v in result["counts"].items())
            answer += f" Group sizes — {counts}."
        return answer

    if step["tool"] == "find_passenger":
        if result["matches"] == 0:
            return f"No passenger matching '{result['search_term']}' is in the dataset."
        p = result["passengers"][0]
        outcome = "survived" if p["Survived"] == 1 else "did not survive"
        answer = (
            f"{p['Name']} was a {p['Sex']} passenger in class {p['Pclass']} who {outcome}."
        )
        if detailed:
            answer += f" Age {p['Age']}, fare ${p['Fare']:.{dp}f}. Total matches: {result['matches']}."
        return answer

    return "I could not answer that."


# ---------------------------------------------------------------------------
# The agent loop
# ---------------------------------------------------------------------------


def run_agent(question: str) -> dict:
    """Plan, call the chosen tool, format the answer."""
    step = plan(question)
    result = TOOLS[step["tool"]](**step["args"]) if step["tool"] else {}
    answer = format_answer(question, step, result)
    return {"answer": answer, "tool_used": step["tool"] or "none", "reason": step["reason"]}


if __name__ == "__main__":
    for q in [
        "What was the survival rate for women and men?",
        "How many passengers are in the dataset?",
        "What happened to the passenger named Braund?",
        "What is the capital of Australia?",
    ]:
        print(f"\nQ: {q}\nA: {run_agent(q)['answer']}")
