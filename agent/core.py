"""Titanic agent — an LLM with three tools.

The LLM reads the question, decides which tool to call, calls it, and writes the
answer from what came back. Domino traces every step: the decision, the tool
call, its arguments and result, plus tokens, latency and cost.

Configured by the LLM_* environment variables (README step 2) and the settings
in ai_system_config.yaml.
"""

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml
from pydantic_ai import Agent

try:  # pydantic-ai >= 1.0
    from pydantic_ai.models.openai import OpenAIChatModel as OpenAIModel
except ImportError:  # older releases
    from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

# Project root — one level up from this file, so paths work no matter where
# the script is launched from.
ROOT = Path(__file__).resolve().parents[1]
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
# Tools. The docstring is what the LLM reads to decide when to call each one.
# ---------------------------------------------------------------------------

COLUMNS = {"sex": "Sex", "class": "Pclass", "embarked": "Embarked", "age_group": "AgeGroup"}


def dataset_summary() -> dict:
    """Overall statistics: passenger count, survivors, survival rate, average age and fare."""
    df = load_data()
    return {
        "passengers": int(len(df)),
        "survivors": int(df["Survived"].sum()),
        "survival_rate_pct": round(float(df["Survived"].mean() * 100), 1),
        "average_age": round(float(df["Age"].mean()), 1),
        "average_fare": round(float(df["Fare"].mean()), 1),
    }


def survival_rate(group_by: str) -> dict:
    """Survival rate broken down by a column.

    Args:
        group_by: one of "sex", "class", "embarked", "age_group".
    """
    column = COLUMNS.get(group_by.strip().lower())
    if column is None:
        return {"error": f"unsupported group_by '{group_by}'. Use sex, class, embarked or age_group."}
    grouped = load_data().groupby(column, observed=True)["Survived"]
    return {
        "group_by": group_by,
        "rates_pct": {str(k): round(float(v * 100), 1) for k, v in grouped.mean().items()},
        "counts": {str(k): int(v) for k, v in grouped.size().items()},
    }


def find_passenger(name_contains: str) -> dict:
    """Look up passengers whose name contains the given text, for example "Braund"."""
    df = load_data()
    matches = df[df["Name"].str.contains(name_contains, case=False, na=False)]
    return {
        "search_term": name_contains,
        "matches": int(len(matches)),
        "passengers": matches[["Name", "Sex", "Age", "Pclass", "Fare", "Survived"]]
        .head(3)
        .to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def create_agent() -> Agent:
    """Build the agent from ai_system_config.yaml plus the LLM_* environment variables."""
    config = load_config()

    base_url = os.environ.get("LLM_BASE_URL")
    if not base_url:
        raise RuntimeError("LLM_BASE_URL is not set — see README step 2.")
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("DOMINO_USER_API_KEY", "EMPTY")
    model_name = os.environ.get("LLM_MODEL") or config["model"]["name"]

    agent = Agent(
        OpenAIModel(
            model_name,
            provider=OpenAIProvider(base_url=base_url.rstrip("/"), api_key=api_key),
        ),
        system_prompt=config["prompt"]["system"],
        model_settings={
            "temperature": config["model"]["temperature"],
            "max_tokens": config["model"]["max_tokens"],
        },
        retries=2,
    )
    agent.tool_plain(dataset_summary)
    agent.tool_plain(survival_rate)
    agent.tool_plain(find_passenger)
    return agent


def run_agent(question: str) -> dict:
    """Ask the agent one question. Returns the answer and the tools it chose to call."""
    result = create_agent().run_sync(question)
    tools_used = [
        part.tool_name
        for message in result.all_messages()
        for part in message.parts
        if type(part).__name__ == "ToolCallPart"
    ]
    return {
        "answer": result.output,
        "tool_used": tools_used[0] if tools_used else "none",
        "tools_used": tools_used,
    }


if __name__ == "__main__":
    for q in [
        "What was the survival rate for women compared to men?",
        "How many passengers are in the dataset?",
        "What happened to the passenger named Braund?",
        "What is the capital of Australia?",
    ]:
        out = run_agent(q)
        print(f"\nQ: {q}\nA: {out['answer']}\n   (tool: {out['tool_used']})")
