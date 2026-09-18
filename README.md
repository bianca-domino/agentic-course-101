# Lesson 1 — Build your first agent in Domino

Host an LLM, give it tools, evaluate it, and deploy it as an agent.

The agent answers questions about the Titanic passenger dataset. The LLM reads each question,
decides which tool to call, and writes the answer from what the tool returned. Domino traces every
step, scores every answer, and deploys the exact version you evaluated.

```
question ──> LLM decides ──> survival_rate("sex") ──> "Women survived at 74.2%, men at 18.9%."
                             dataset_summary()
                             find_passenger("Braund")
```

**Time:** about 10 minutes, plus a few minutes for the LLM endpoint to start the first time. If your
team already has an endpoint or an external provider key, skip to Step 3.

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

### Hiring the assistant: model vs endpoint

Before any of that, you need the assistant themselves. That's the LLM, and it comes in two parts
that are easy to confuse.

**Registering a model** is putting a CV on file. It records who this person is and what they can
do — but a CV can't answer questions. Nothing is running yet, and nothing is costing you anything.

**Deploying an endpoint** is hiring them: a desk, a machine to work on, and a phone number on the
door. Now there's somebody at the other end when you call. That phone number is the `BASE_URL` your
agent dials, and it's why the endpoint has to exist before your code can call the model.

**Where they sit is your choice.** A Domino-hosted endpoint is an assistant working *in your
building*, on your GPUs — nothing leaves the site, you pick the hardware, you pay for the desk while
they're on the clock. An external provider is *phoning an agency*: no desk to set up and a sharper
assistant on the line, but your questions leave the building. Both dial the same way
(OpenAI-compatible), so switching later is a config change, not a rewrite.

This lesson hires in-house so you see the whole path. Step 2 has the swap if you'd rather phone out.

### Mapping it to this repo

| The analogy | In the repo or the UI |
| --- | --- |
| The CV on file | a registered model, under **Models → Register** |
| The hired assistant with a phone number | an endpoint, under **Models → Endpoints** |
| Their phone number | `LLM_BASE_URL` |
| The filing cabinet they may consult | `data/titanic.csv` |
| The three lookups they're trained to do | the tools in `agent/core.py` |
| The job brief pinned above the desk | `prompt.active` in `ai_system_config.yaml` |
| The test paper with known answers | `data/sample_questions.csv` |
| The marking scheme | `agent/evaluator.py` |
| Sitting them down to take the test | `scripts/dev_eval.py`, run as a Job |
| Their shown working, question by question | the **Traces** tab |
| Their file: this version, this brief, these marks | an agent version in the Experiment Manager |
| Putting them on the front desk | `app/server.py`, launched by `app.sh` |
| Reading their notes while they're on the desk | the **Monitoring** tab |

### Two things the analogy makes obvious

**Why the job brief is a separate file.** Rewriting the brief is not the same as hiring a different
assistant. In Step 7 you swap a vague brief for a specific one, set the same test again, and compare
the marks — same assistant, better instructions. That's why Domino logs the brief as parameters
right next to the scores.

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
├── requirements.txt             # pydantic-ai-slim, installed at startup
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

## Step 2 — Host an LLM

Two parts: register the model, then deploy it as an endpoint. You need **Project Collaborator**
permissions.

**Register it.** Go to **Models → Register → Gen AI model**. Choose **Hugging Face** as the source,
set the path to `Qwen/Qwen2.5-7B-Instruct`, set Type to **LLM**, and create. Name it whatever you
like — the agent discovers the served name automatically in Step 3.

**Deploy it.** From the registered model's **Endpoints** tab, click **Create endpoint**, then:

- **Environment** → **Domino vLLM Environment**, which serves an OpenAI-compatible API.
- **Hardware Tier** → a GPU tier with at least 16 GB of VRAM for this 7B model.
- **Advanced → vLLM arguments** → add `--enable-auto-tool-choice` and `--tool-call-parser hermes`.
  Optionally add `--served-model-name titanic-llm` to choose the name the endpoint answers to.
- **Access** → add yourself, and anyone else who'll run the lesson.

> [!IMPORTANT]
> Those two vLLM arguments are what let the model call tools. Without them the agent has a brain but
> no hands, and every answer will be a guess.

The endpoint takes a few minutes to start. When it's running, open its **Calling** tab and copy the
URL — that's your `BASE_URL` for the next step.

> [!NOTE]
> **Prefer an external provider?** Skip the registration and endpoint entirely: use the provider's
> base URL and key in Step 3 with a model like `gpt-4o-mini`. Nothing else in the lesson changes.
> [Set up LLM access](https://docs.domino.ai/cloud/platform-capabilities/features/llms/index)
> compares the two approaches, and
> [Host an LLM](https://docs.domino.ai/cloud/platform-capabilities/features/llms/host-an-llm) is the
> full hosting guide.

## Step 3 — Point the agent at it

In **Settings → Environment variables**, add:

| Name | Value |
| --- | --- |
| `LLM_BASE_URL` | The URL from the endpoint's **Calling** tab |
| `LLM_API_KEY` | External providers only. For a Domino-hosted endpoint, leave it out |
| `LLM_MODEL` | Optional. Only needed to pin a specific model — see below |

That's usually the only variable you need.

**No key to manage.** For a Domino-hosted endpoint, `agent/core.py` picks up the access token that
Domino serves at `http://localhost:8899/access-token` inside every Workspace, Job, and App.

**No model name to look up.** An endpoint serves your model under the name you registered it with,
which is rarely the Hugging Face path. Rather than make you match it by hand, the agent asks the
endpoint (`GET /v1/models`) and uses what it reports. That's what `name: auto` means in
`ai_system_config.yaml`. Set `LLM_MODEL`, or replace `auto` with an exact name, when an endpoint
serves more than one model or you want the choice recorded in the config.

If you do pin a name, the agent checks it against the endpoint first and falls back to what's
actually served — with a message saying so — rather than failing with a 404.

Served names are often not what you'd expect. A Domino endpoint commonly reports its model as `.`,
the local path vLLM loaded it from, rather than the Hugging Face path or the name you registered.
That's normal, and it's why the default is discovery rather than a name in the config. Add
`--served-model-name <something>` in Step 2 if you'd rather it had a readable one.

## Step 4 — Try it

Launch a Workspace on the Domino Standard Environment, open a terminal, and run:

```bash
pip install -q --no-warn-conflicts -r requirements.txt
python agent/core.py
```

It prints the model it resolved, then four answers and one refusal.

To see what your endpoint actually serves, without running the agent:

```bash
python agent/core.py --models
```

> [!NOTE]
> Pip may print `ERROR: pip's dependency resolver...` listing packages like `langchain-community`
> or `snowflake-connector-python`. Those conflicts already exist in the Domino Standard Environment
> and have nothing to do with this agent — the install still succeeded. Confirm with
> `python -c "import pydantic_ai; print(pydantic_ai.__version__)"`.

Four questions, and one off-topic question it should decline. Each answer prints the tool the LLM
chose. Open `agent/core.py` — the three tools are plain Python functions, and their docstrings are
what the LLM reads to decide when to call them.

## Step 5 — Evaluate it as a Job

In your Workspace, click **Run Job**, put this in **File Name or Command**, and click **Start**:

```
bash scripts/run_eval.sh
```

This runs all 10 questions in `data/sample_questions.csv`. Each becomes its own trace, scored by
`agent/evaluator.py` on three metrics: did the LLM pick the right tool, does the answer contain the
right figures, and is it concise.

> [!IMPORTANT]
> Run it as a **Job**, not from the terminal. Only Job runs create a deployable agent version with
> lineage back to the exact commit and config.

## Step 6 — Review what you captured

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

## Step 7 — Improve the prompt and compare

Your first run used the `baseline` prompt in `ai_system_config.yaml`: a reasonable first draft that
never mentions the tools. Now switch to the `improved` one, which tells the agent to look everything
up, quote the figures it got back, and refuse questions outside the dataset. Change one line:

```yaml
prompt:
  active: improved     # was: baseline
```

> [!IMPORTANT]
> [Sync your changes](https://docs.domino.ai/cloud/platform-capabilities/core-concepts/workspaces/sync-changes-in-a-workspace#sync-all-changes)
> before starting the next Job, or it will run the old code.

Repeat Step 5, then in **Experiments** select both agent versions and click **Compare**. The
improved prompt should score higher, and the comparison shows you where: answers that quote the
real numbers rather than paraphrasing them, and question 10 declined instead of answered.

Open the **Traces** comparison to see both versions answering the same question side by side. That's
the difference between knowing one version is better and knowing *why* — which is what you need
before putting it in front of users.

> [!NOTE]
> Not every knob moves the needle. Re-running with `temperature` at 0.9 instead of 0.1 will likely
> produce near-identical scores, because this task has one obvious tool per question and the
> evaluator checks figures rather than phrasing. That's a useful result too: it tells you
> temperature isn't where the quality lives for this agent, so don't spend your time there.

## Step 8 — Deploy the winner

Open the better agent version, click **Create Agent**, name it, set **Agent file** to `app.sh`, and
create. Then go to **Deployments → Apps & Agents**, select it, click **Deploy**, pick a small
hardware tier, and deploy.

Ask it a few questions. `app/server.py` uses the same `@add_tracing` decorator as the evaluation
script, so production conversations are traced too — watch them arrive under the **Monitoring** tab,
alongside **Usage** and **Performance**.

**Clean up:** stop the agent from **Deployments → Apps & Agents**, stop your Workspace, and stop the
LLM endpoint under **Models → Endpoints** — it holds a GPU while it runs.

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

To avoid the startup install altogether, add `RUN pip install "pydantic-ai-slim[openai]"` to a
compute environment's Dockerfile instructions and select that environment for the Job and the App.

This lesson uses Pydantic AI, but Domino auto-instruments any MLflow-supported framework: LangChain,
OpenAI Agents SDK, LlamaIndex, and others. Traces are captured wherever the model is hosted, so an
external provider looks the same in the Experiment Manager as a Domino-hosted one.

## Coming up

- **Lesson 2 — the feedback loop:** LLM-as-judge evaluation, scoring production traces on a
  schedule, and iterating when quality drops.
- **Lesson 3 — multi-agent:** calling one agent from another, and what that looks like in a trace.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Hugging Face model missing from the list | Some models need their licence accepted on Hugging Face first |
| Endpoint stuck on "Starting" | The hardware tier is too small for the model. Check the endpoint logs and pick a tier with more VRAM |
| `LLM_BASE_URL is not set` | Add the Step 3 variables, then restart the Workspace so they load |
| `404 — The model 'X' does not exist` | Run `python agent/core.py --models` to see what the endpoint serves. If `LLM_MODEL` is set to something else, clear it in **Settings → Environment variables** and restart the Workspace so the change loads |
| The model name looks stale after editing it | Environment variables are injected at startup. Restart the Workspace (or start a new Job) after changing them |
| 401 from the endpoint | Check the URL came from the **Calling** tab and that you have access to the endpoint |
| The agent answers without calling a tool | The vLLM tool-calling arguments are missing — see Step 2 |
| No run in the Experiment Manager | The script ran from a terminal. Run it as a Job |
| Pip prints dependency-resolver errors | Pre-existing DSE conflicts, unrelated to this agent. Check the install worked with `python -c "import pydantic_ai"` |
| `ModuleNotFoundError: domino.agents` | Your environment predates Domino 6.2. Add `RUN pip install "dominodatalab[agents]"` to its Dockerfile instructions and rebuild |

## Docs

- [Set up LLM access](https://docs.domino.ai/cloud/platform-capabilities/features/llms/index)
- [Host an LLM](https://docs.domino.ai/cloud/platform-capabilities/features/llms/host-an-llm)
- [Agents in Domino](https://docs.domino.ai/cloud/platform-capabilities/features/agents/index)
- [Agentic AI overview](https://docs.domino.ai/cloud/platform-capabilities/features/agents/agentic-ai-overview)
- [Develop agentic systems](https://docs.domino.ai/cloud/platform-capabilities/features/agents/develop)
- [Create and run Jobs](https://docs.domino.ai/6.3/platform-capabilities/core-concepts/jobs/create-and-run-jobs)
