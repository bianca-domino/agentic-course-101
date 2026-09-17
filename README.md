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

You can verify that all the files imported successfully from this repo by checking your Project **Code** page.

## Step 2 — Try the agent (1 min)

Launch a Workspace with the IDE of your choice and use the default Domino Standard Environment. Once the Workspace is running, open a new terminal and run:

```bash
python agent/core.py
```

You'll see it answer four questions and decline an off-topic one. Have a look at `agent/core.py` —
it's three tools, a planner, and an answer formatter, all in one file.

## Step 3 — Run the evaluation as a Job (2 min)

You can run a Job interactively in the UI, from the CLI, or from Domino API (see [Create and run Jobs](https://docs.domino.ai/6.3/platform-capabilities/core-concepts/jobs/create-and-run-jobs) for detailed steps for each option). To keep things simple, let's run it in the UI.

In your running Workspace, click **Run Job** and paste the following path to the `dev_eval.py` script in the **File Name or Command** field:

```
scripts/dev_eval.py
```

Click **Start** to run the agent over the 10 questions in `data/sample_questions.csv`. Each question becomes its own
trace with evaluation scores attached.

> [!IMPORTANT]
> Run it as a **Job**, not from the Workspace terminal. That's what creates a deployable agent
> version with lineage back to the exact commit and config.

Each time you run an evaluation script as a Domino Job, it creates an agent version containing traces and evaluation scores for that configuration.

## Step 4 — Look at what you captured (2 min)

You can view and analyze traces from any agent version by navigating to **Experiments** in the left nav of your Project and clicking into the run you just created. Click through the tabs to see what each tab holds for this run:

- **Overview** → The run's identity and provenance: who ran it, when, how long it took, the hardware and environment, and the Git commit it came from.
- **Parameters** → Everything from `ai_system_config.yaml`, so you always know which
  configuration produced these numbers.
- **Metrics** → Mean tool accuracy, answer accuracy, and overall score across all 10 questions.
- **Traces** → Click a trace to see the span tree: `plan` (which tool it chose and why), the
`<tool>` span with its arguments and return value, then `format_answer`. Plus latency for each step.
- **Outputs** → Any artifacts the run produced.
- **Logs** → The raw stdout and stderr from the Job, which is where you look when a run fails.

Question 10 is off-topic on purpose. Check that the agent declined it.

## Step 5 — Change one thing and compare (2 min)

In your running Workspace, open `ai_system_config.yaml`, change `style` from `concise` to `detailed` and save.

> [!IMPORTANT]
> You need to [sync all changes](https://docs.domino.ai/cloud/platform-capabilities/core-concepts/workspaces/sync-changes-in-a-workspace#sync-all-changes) before you can run the next Job.

Repeat Step 3 to start a new Job with the updated configuration.

Once the Job has run successfully, navigate to **Experiments** and click into the experiment. Select both agent versions and click the **Compare** icon (it looks like two overlapping squares).

Scroll down to see a side-by-side comparison of the two agent versions: Mean overall score goes from **0.96** to **0.99** — the detailed answers include the average fare,
which question 3 asks for. That's the loop the whole platform is built around: change one thing,
re-run the same dataset, see the difference before a user does.

> [!NOTE]
> If you compare Jobs in the **Jobs** dashboard, it will show differences in summary metadata and diagnostic statistics. If you compare Jobs in the **Experiments** view, you're comparing logged experiment runs rather than raw Job outputs, which is useful for seeing how configuration changes affected performance.

## Step 6 — Deploy it (1 min)

Click the agent version that had the best metrics, then click **Create Agent**. Specify an agent name, set the **Agent file** to `app.sh` and click **Create Agent**. To deploy your agent, navigate to **Deployments → Apps & Agents**, select your agent, then click **Deploy**. Customize the URL ending of your agent if you want to, then select a small hardware tier and click **Deploy Agent version**.  This deploys your agent as a chat page. Once the agent has deployed successfully, you can view your agent either by clicking **View Agent**.

Ask your agent a couple of questions about the Titanic set then check the **Usage** and **Performance** of your agent by navigating to your agent in **Deployments → Apps & Agents**.

`app/server.py` uses the same `@add_tracing` decorator, so live questions are traced too.  Select the **Monitoring** tab to watch them arrive as you ask your agent more questions.

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
- [Create a Git-based Project]()
- [Create and run Jobs](https://docs.domino.ai/6.3/platform-capabilities/core-concepts/jobs/create-and-run-jobs)
