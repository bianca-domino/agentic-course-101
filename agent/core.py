"""Titanic agent — an LLM with three tools.

The LLM reads the question, decides which tool to call, calls it, and writes the
answer from what came back. Domino traces every step: the decision, the tool
call, its arguments and result, plus tokens, latency and cost.

Configured by the LLM_* environment variables (README step 3) and the settings
in ai_system_config.yaml.
"""

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests
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


def _api_key() -> str:
    """Domino-hosted endpoints authenticate with the local access token; external
    providers use LLM_API_KEY."""
    if os.environ.get("LLM_API_KEY"):
        return os.environ["LLM_API_KEY"]
    try:  # available inside any Domino Workspace, Job or App
        return requests.get("http://localhost:8899/access-token", timeout=5).text.strip()
    except Exception:
        return os.environ.get("DOMINO_USER_API_KEY", "EMPTY")


def _base_url() -> str:
    base_url = os.environ.get("LLM_BASE_URL")
    if not base_url:
        raise RuntimeError("LLM_BASE_URL is not set — see README step 3.")
    return base_url.rstrip("/")


def list_endpoint_models(base_url: str) -> list:
    """Ask the endpoint which models it serves (every OpenAI-compatible API has this)."""
    response = requests.get(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {_api_key()}"},
        timeout=15,
    )
    response.raise_for_status()
    return [m["id"] for m in response.json().get("data", [])]


@lru_cache(maxsize=1)
def resolve_model_name(base_url: str) -> str:
    """Work out which model name to send to the endpoint.

    An endpoint serves the model under the name it was registered with, which is
    rarely the Hugging Face path. So we always ask the endpoint what it serves,
    and only use an explicit LLM_MODEL (or model.name in the YAML) when the
    endpoint confirms it — a stale override is a 404 waiting to happen.
    """
    explicit = os.environ.get("LLM_MODEL") or load_config()["model"].get("name")
    explicit = None if not explicit or explicit == "auto" else explicit
    source = "LLM_MODEL" if os.environ.get("LLM_MODEL") else "ai_system_config.yaml"

    try:
        served = list_endpoint_models(base_url)
    except Exception as exc:
        if explicit:
            print(f"[agent] could not reach {base_url}/models ({exc}); trying '{explicit}'.")
            return explicit
        raise RuntimeError(
            f"Could not ask {base_url}/models which model to use ({exc}). "
            "Check LLM_BASE_URL, or set LLM_MODEL to the name you registered."
        ) from exc

    if not served:
        raise RuntimeError(f"{base_url} reports no available models. Is the endpoint running?")

    if explicit and explicit not in served:
        print(
            f"[agent] {source} says '{explicit}', but the endpoint serves {served}. "
            f"Using '{served[0]}' instead — clear {source} to silence this."
        )
        return served[0]

    if explicit:
        print(f"[agent] model '{explicit}' (pinned in {source}, confirmed by the endpoint)")
        return explicit

    if len(served) > 1:
        print(f"[agent] endpoint serves {served}; using '{served[0]}'. Set LLM_MODEL to choose.")
    else:
        print(f"[agent] model '{served[0]}' (discovered from the endpoint)")
    return served[0]


def active_prompt(config: dict) -> str:
    """The prompt named by prompt.active — the one thing Step 7 changes."""
    prompts = config["prompt"]
    name = prompts.get("active", "baseline")
    if name not in prompts:
        raise RuntimeError(f"prompt.active is '{name}', which is not defined in the config.")
    return prompts[name].strip()


@lru_cache(maxsize=1)
def create_agent() -> Agent:
    """Build the agent from ai_system_config.yaml plus the LLM_* environment variables."""
    config = load_config()

    base_url = _base_url()
    model_name = resolve_model_name(base_url)

    agent = Agent(
        OpenAIModel(
            model_name,
            provider=OpenAIProvider(base_url=base_url, api_key=_api_key()),
        ),
        system_prompt=active_prompt(config),
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
    import sys

    if "--models" in sys.argv:  # diagnostics: what does the endpoint actually serve?
        url = _base_url()
        print(f"LLM_BASE_URL : {url}")
        print(f"LLM_MODEL    : {os.environ.get('LLM_MODEL') or '(not set)'}")
        print(f"config name  : {load_config()['model'].get('name')}")
        print(f"served models: {list_endpoint_models(url)}")
        sys.exit(0)

    resolve_model_name(_base_url())
    print()
    for q in [
        "What was the survival rate for women compared to men?",
        "How many passengers are in the dataset?",
        "What happened to the passenger named Braund?",
        "What is the capital of Australia?",
    ]:
        out = run_agent(q)
        print(f"\nQ: {q}\nA: {out['answer']}\n   (tool: {out['tool_used']})")
