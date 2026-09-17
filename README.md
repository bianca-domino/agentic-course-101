# Lesson 1 — Build your first agent in Domino

Build, trace, evaluate, compare, and deploy a working agent in under 10 minutes.

**No LLM, no API key, no environment build.** Everything this lesson needs is already in the
Domino Standard Environment. The point of Lesson 1 is the Domino workflow — traces, agent versions,
comparison, deployment — not prompt engineering. Once that clicks, swapping in an LLM is a
one-function change (see [Add an LLM](#add-an-llm) at the end).

The agent answers questions about the Titanic passenger dataset. It does what every agent does:
**plans** which tool a question needs, **calls** that tool, then turns the result into an answer.

```
question ──> plan ──> survival_rate("sex") ──> "Survival rate by sex — female: 74.2%, male: 18.9%."
                      dataset_summary()
                      find_passenger("Braund")
```

---

## Repo layout

```
.
├── README.md
├── app.sh                       # App command Domino runs to launch the agent
├── ai_system_config.yaml        # agent settings, logged as parameters on every run
├── requirements.txt             # reference only — all of it ships in the DSE
├── agent/
│   ├── __init__.py
│   ├── core.py                  # the agent: planner, three tools, answer formatting
│   └── evaluator.py             # scores each answer (deterministic, no LLM judge)
├── app/
│   └── server.py                # Flask chat UI for the deployed agent
├── scripts/
│   └── dev_eval.py              # batch evaluation — the script you run as a Job
└── data/
    ├── titanic.csv              # the dataset (891 passengers)
    └── sample_questions.csv     # 10 test questions with expected tool and answer
```

Every path in the code resolves from the project root, so the scripts run the same from a Workspace
terminal, a Job, or the App.

---

## Step 1 — Create the project (2 min)

**Projects → Create Project** → Choose a Git-based project → Click **Input URL**, then paste this repo's URL and create your project. (Or create a blank project and upload these files.)

That's the whole setup. No environment variables, no endpoint, no credentials.

You can verify that all the files imported successfully from this repo by checking the **Code** section in the Project navigation pane.

## Step 2 — Try the agent (1 min)

Launch a Workspace with the IDE of your choice and use the default Domino Standard Environment. Once the Workspace is running, open a new terminal and run:

```bash
python agent.py
```

You'll see it answer four questions and decline an off-topic one. Have a look at `agent/core.py` —
it's three tools, a planner, and an answer formatter, all in one file.

## Step 3 — Run the evaluation as a Job (2 min)

**Jobs → Run**, with the command:

```
python scripts/dev_eval.py
```

This runs the agent over the 10 questions in `data/sample_questions.csv`. Each question becomes its own
trace with evaluation scores attached.

> Run it as a **Job**, not from the Workspace terminal. That's what creates a deployable agent
> version with lineage back to the exact commit and config.

## Step 4 — Look at what you captured (2 min)

Open **Experiments** in the left nav and select the run you just created.

- **Traces** tab → click a trace to see the span tree: `plan` (which tool it chose and why), the
  `TOOL` span with its arguments and return value, then `format_answer`. Plus latency for each step.
- **Metrics** tab → mean tool accuracy, answer accuracy, and overall score across all 10 questions.
- **Parameters** tab → everything from `ai_system_config.yaml`, so you always know which
  configuration produced these numbers.

Question 10 is off-topic on purpose. Check that the agent declined it.

## Step 5 — Change one thing and compare (2 min)

Open `ai_system_config.yaml`, change `style` from `concise` to `detailed`, save, and run the Job
again. Then tick both runs in **Experiments** and click **Compare**.

Mean overall score goes from **0.96** to **0.99** — the detailed answers include the average fare,
which question 3 asks for. That's the loop the whole platform is built around: change one thing,
re-run the same dataset, see the difference before a user does.

## Step 6 — Deploy it (1 min)

From the better run, click **Deploy Agent**, set the app command to `app.sh`, pick the smallest
hardware tier, and deploy. Your agent shows up under **Deployments → Apps & Agents** as a chat page.

`app/server.py` uses the same `@add_tracing` decorator, so live questions are traced too — open the
deployed agent's **Monitoring** tab to watch them arrive.

---

## How the tracing works

Two decorators, and that's it.

```python
# agent/core.py — each tool becomes a TOOL span inside the trace
@mlflow.trace(span_type="TOOL", name="survival_rate")
def survival_rate(group_by): ...

# scripts/dev_eval.py — the top-level call becomes the trace, everything nests inside it
@add_tracing(name="titanic_question", evaluator=judge)
def answer_question(data_point):
    return run_agent(data_point["question"])

with DominoAgentContext(agent_config_path="ai_system_config.yaml"):
    for row in questions:
        answer_question(row)
```

`@add_tracing` captures the call and everything beneath it, then runs `judge` on the result.
`DominoAgentContext` groups those traces into one comparable agent version and logs your YAML
config alongside them.

## Add an LLM

The planner is keyword rules so this lesson runs anywhere. To make the agent decide for itself,
replace one function — `plan()` in `agent/core.py` — with an LLM call, and set `planner.mode: llm`
in the config. Nothing else changes: same tools, same tracing, same evaluation, same deployment.

With a framework like Pydantic AI, the agent and its tools replace the planner outright, and you
tell `@add_tracing` to auto-instrument it:

```python
@add_tracing(name="titanic_question", autolog_frameworks=["pydantic_ai"], evaluator=judge)
def answer_question(data_point):
    return {"answer": create_agent().run_sync(data_point["question"]).output}
```

Domino auto-instruments any MLflow-supported framework — LangChain, Pydantic AI, OpenAI Agents SDK,
LlamaIndex, and others. The LLM itself can be an external provider or one you host in Domino
(**Models → Endpoints**); see [Set up LLM access](https://docs.domino.ai/cloud/platform-capabilities/features/llms).

## Coming up

- **Lesson 2 — the feedback loop:** LLM-as-judge evaluation, scoring production traces on a
  schedule, and iterating when quality drops.
- **Lesson 3 — multi-agent:** calling one agent from another, and what that looks like in a trace.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| No run appears in the Experiment Manager | The script was run from a Workspace terminal. Run it as a Job |
| `ModuleNotFoundError: agent` | Make sure `agent/__init__.py` exists — it's what makes `agent` an importable package |
| `ModuleNotFoundError: domino.agents` | Your environment predates Domino 6.2. Add `RUN pip install "dominodatalab[agents]"` to the environment's Dockerfile instructions and rebuild |
| The app won't start | Check the App command is `app.sh` and that the hardware tier has at least 1 GB of memory |

## Docs

- [Agents in Domino](https://docs.domino.ai/cloud/platform-capabilities/features/agents/index)
- [Agentic AI overview](https://docs.domino.ai/cloud/platform-capabilities/features/agents/agentic-ai-overview)
- [Develop agentic systems](https://docs.domino.ai/cloud/platform-capabilities/features/agents/develop)
