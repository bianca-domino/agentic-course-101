# Lesson 1 — Build your first agent in Domino

Connect an LLM, give it tools, evaluate it, and deploy it — in under 10 minutes.

The agent answers questions about the Titanic passenger dataset. The LLM reads each question,
decides which tool to call, and writes the answer from what the tool returned. Domino traces every
step, scores every answer, and deploys the exact version you evaluated.

```
question ──> LLM decides ──> survival_rate("sex") ──> "Women survived at 74.2%, men at 18.9%."
                             dataset_summary()
                             find_passenger("Braund")
```

---

## Mental model: your new research assistant

Imagine you've hired an assistant to answer questions about the Titanic passenger records. They're
new, so they can't do anything you haven't set up for them.

You give them **one filing cabinet** — the passenger records, and nothing else. You pin **a short
job brief** above their desk: always look it up, never guess, keep it to two sentences, don't wander
off topic. You teach them **three specific lookups** they're allowed to perform, and you leave it to
them to judge which lookup a question calls for.

Before you let them near a real visitor, you give them **a test with a marking scheme**: ten
questions you already know the answers to. And you ask them to **show their working** on every one —
not just the answer, but which drawer they opened and why.

If they pass, they go to **the front desk** to help real visitors. And you keep reading their
working notes while they're out there.

### Mapping it to this repo

| The analogy | In the repo |
| --- | --- |
| The assistant themselves | the LLM you connect in Step 2 |
| The filing cabinet they may consult | `data/titanic.csv` |
| The three lookups they're trained to do | the tools in `agent/core.py` |
| The job brief pinned above the desk | `ai_system_config.yaml` |
| The test paper with known answers | `data/sample_questions.csv` |
| The marking scheme | `agent/evaluator.py` |
| Sitting them down to take the test | `scripts/dev_eval.py`, run as a Job |
| Their shown working, question by question | the **Traces** tab |
| Their file: this version, this brief, these marks | an agent version in the Experiment Manager |
| Putting them on the front desk | `app/server.py`, launched by `app.sh` |
| Reading their notes while they're on the desk | the **Monitoring** tab |

### Two things the analogy makes obvious

**Why the job brief is a separate file.** Rewriting the brief is not the same as hiring a different
assistant. In Step 6 you change one line of `ai_system_config.yaml`, set the same test again, and
compare the marks — same assistant, different instructions. That's why Domino logs the brief as
parameters right next to the scores.

**Why the test matters.** Your assistant decides for themselves which drawer to open. That's what
makes them useful, and it's also why you can't just assume they got it right. The test, the marking
scheme, and the shown working are how you find out — before a visitor does.

---

## Repo layout

```
.
├── README.md
├── app.sh                       # App command Domino runs to launch the agent
├── ai_system_config.yaml        # model, prompt, settings — logged as parameters on every run
├── requirements.txt             # pydantic-ai, installed at startup
├── agent/
│   ├── __init__.py
│   ├── core.py                  # the agent: LLM connection and three tools
│   └── evaluator.py             # scores each answer
├── app/
│   └── server.py                # Flask chat UI for the deployed agent
├── scripts/
│   ├── dev_eval.py              # batch evaluation over the test questions
│   └── run_eval.sh              # Job command: installs deps, runs dev_eval.py
└── data/
    ├── titanic.csv              # the dataset (891 passengers)
    └── sample_questions.csv     # 10 test questions with expected tool and answer
```

Every path resolves from the project root, so the scripts behave the same in a Workspace, a Job, or
the App.

---

## Step 1 — Create the project

**Projects → Create Project → Git-based → Input URL**, paste this repo's URL, and create.

Check the project's **Code** page to confirm the files imported.

## Step 2 — Connect an LLM

Go to **Settings → Environment variables** and add the following variables:

| Name | Value |
| --- | --- |
| `LLM_BASE_URL` | Your endpoint URL, ending in `/v1` |
| `LLM_API_KEY` | Your provider key — for a Domino-hosted endpoint, your Domino user API key |
| `LLM_MODEL` | The model the endpoint serves, e.g. `Qwen/Qwen2.5-7B-Instruct` or `gpt-4o-mini` |

Any OpenAI-compatible endpoint works. To host the model in Domino instead, register it under
**Develop → Models → Register → Gen AI model**, deploy it under **Models → Endpoints**, and copy the
`BASE_URL` from the endpoint's **Calling** tab.

> [!IMPORTANT]
> The endpoint must support **tool calling**, or the agent can't reach its tools. On a
> Domino-hosted endpoint, add the vLLM arguments `--enable-auto-tool-choice` and
> `--tool-call-parser hermes` on the endpoint's **Advanced** tab.

## Step 3 — Try the agent

Launch a Workspace on the Domino Standard Environment, open a terminal, and run:

```bash
pip install -q -r requirements.txt
python agent/core.py
```

Four questions, and one off-topic question it should decline. Each answer prints the tool the LLM
chose. Open `agent/core.py` — the three tools are plain Python functions, and their docstrings are
what the LLM reads to decide when to call them.

## Step 4 — Evaluate it as a Job

In your Workspace, click **Run Job**, put this in **File Name or Command**, and click **Start**:

```
bash scripts/run_eval.sh
```

This runs teh agent over all 10 questions in `data/sample_questions.csv`. Each becomes its own trace, scored by
`agent/evaluator.py` on three metrics: did the LLM pick the right tool, does the answer contain the
right figures, and is it concise.

> [!IMPORTANT]
> Run it as a **Job**, not from the terminal. Only Job runs create a deployable agent version with
> lineage back to the exact commit and config.

## Step 5 — Review what you captured

Go to **Experiments** and open the run. Each tab holds a different slice:

- **Overview** → who ran it, when, on what hardware, and from which Git commit.
- **Parameters** → your `ai_system_config.yaml`, so you know which configuration produced these numbers.
- **Metrics** → mean tool accuracy, answer accuracy, and overall score across all 10 questions.
- **Traces** → one row per question. Open one to see the span tree: the LLM's tool choice, the tool
  call with its arguments and result, the final answer, plus tokens, latency, and cost.
- **Outputs** → artifacts the run produced.
- **Logs** → raw stdout and stderr, where you look when a run fails.

Check question 10 — the off-topic one — and question 4, where the LLM has to pick `survival_rate`
over `dataset_summary`.

## Step 6 — Change one thing and compare

Open `ai_system_config.yaml`, change `temperature` from `0.1` to `0.9`, and save.

> [!IMPORTANT]
> [Sync your changes](https://docs.domino.ai/cloud/platform-capabilities/core-concepts/workspaces/sync-changes-in-a-workspace#sync-all-changes)
> before starting the next Job, or it will run the old code.

Repeat Step 4, then in **Experiments** select both agent versions and click the **Compare** icon. You'll see
the aggregate metrics side by side; open the **Traces** comparison to see both configurations
answering the same question, so you can tell not just which is better but why.

That's the loop the platform is built around: change one thing, re-run the same test, see the
difference before a user does.

## Step 7 — Deploy the winner

Open the better agent version, click **Create Agent**, name it, set **Agent file** to `app.sh`, and
create. Then go to **Deployments → Apps & Agents**, select it, click **Deploy**, pick a small
hardware tier, and deploy. Once the agent is ready, click **View Agent**. Ask it a few questions.

`app/server.py` uses the same `@add_tracing` decorator as the evaluation
script, so production conversations are traced too — watch them arrive under **Deployments → Apps & Agents** → **Monitoring** tab, alongside **Usage** and **Performance**.

**Clean up:** stop the agent from **Deployments → Apps & Agents**, and stop your Workspace.

---

## How the tracing works

One decorator and one context manager.

```python
# scripts/dev_eval.py
@add_tracing(name="titanic_question", autolog_frameworks=["pydantic_ai"], evaluator=judge)
def answer_question(data_point):
    return run_agent(data_point["question"])

with DominoAgentContext(agent_config_path="ai_system_config.yaml"):
    for row in questions:
        answer_question(row)
```

`@add_tracing` captures the call and everything beneath it — including every LLM and tool call the
framework makes — then runs `judge` on the result. `DominoAgentContext` groups those traces into one
comparable agent version and logs your YAML config as its parameters.

This lesson uses Pydantic AI, but Domino auto-instruments any MLflow-supported framework: LangChain,
OpenAI Agents SDK, LlamaIndex, and others. Swap the framework, keep the same two lines.

## Coming up

- **Lesson 2 — the feedback loop:** LLM-as-judge evaluation, scoring production traces on a
  schedule, and iterating when quality drops.
- **Lesson 3 — multi-agent:** calling one agent from another, and what that looks like in a trace.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `LLM_BASE_URL is not set` | Add the Step 2 variables, then restart the Workspace so they load |
| 401 or 404 from the endpoint | Check the URL ends in `/v1` and `LLM_MODEL` matches a model the endpoint serves |
| The agent answers without calling a tool | Tool calling isn't enabled on the endpoint — see the note in Step 2 |
| No run in the Experiment Manager | The script ran from a terminal. Run it as a Job |
| `ModuleNotFoundError: domino.agents` | Your environment predates Domino 6.2. Add `RUN pip install "dominodatalab[agents]"` to its Dockerfile instructions and rebuild |

## Docs

- [Agents in Domino](https://docs.domino.ai/cloud/platform-capabilities/features/agents/index)
- [Agentic AI overview](https://docs.domino.ai/cloud/platform-capabilities/features/agents/agentic-ai-overview)
- [Develop agentic systems](https://docs.domino.ai/cloud/platform-capabilities/features/agents/develop)
- [Create and run Jobs](https://docs.domino.ai/6.3/platform-capabilities/core-concepts/jobs/create-and-run-jobs)
