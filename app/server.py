"""Chat UI for the Titanic agent, deployed as a Domino App.

Flask only, so there is nothing extra to install. The same @add_tracing
decorator used in dev_eval.py runs here, so every question a user asks in
production becomes a trace.
"""

import sys
from pathlib import Path

# Make the project root importable when this file is run from app/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domino.agents.tracing import add_tracing, init_tracing
from flask import Flask, jsonify, request

from agent.core import load_config, run_agent

init_tracing()

app = Flask(__name__)


@add_tracing(name="titanic_question", autolog_frameworks=["pydantic_ai"])
def answer_question(data_point: dict) -> dict:
    return run_agent(data_point["question"])


PAGE = """
<!doctype html>
<title>Titanic Agent</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 3rem auto; padding: 0 1rem; }
  #log { margin: 1.5rem 0; }
  .msg { padding: .6rem .9rem; border-radius: .6rem; margin: .4rem 0; }
  .you { background: #eef1f5; }
  .bot { background: #e8f4ec; }
  .tool { font-size: .75rem; color: #667; margin-left: .9rem; }
  form { display: flex; gap: .5rem; }
  input { flex: 1; padding: .6rem; border: 1px solid #ccd; border-radius: .5rem; }
  button { padding: .6rem 1rem; border: 0; border-radius: .5rem; background: #2b6cb0; color: #fff; }
</style>
<h2>Titanic Agent</h2>
<p>Ask about passengers, survival rates, or fares. Every answer is traced in Domino.</p>
<div id="log"></div>
<form onsubmit="ask(event)">
  <input id="q" placeholder="What was the survival rate for women and men?" autofocus>
  <button>Ask</button>
</form>
<script>
async function ask(e) {
  e.preventDefault();
  const input = document.getElementById('q');
  const log = document.getElementById('log');
  const question = input.value.trim();
  if (!question) return;
  input.value = '';
  log.insertAdjacentHTML('beforeend', `<div class="msg you">${question}</div>`);
  const base = location.pathname.endsWith('/') ? location.pathname : location.pathname + '/';
  const res = await fetch(base + 'ask', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({question})
  });
  const data = await res.json();
  log.insertAdjacentHTML('beforeend',
    `<div class="msg bot">${data.answer}</div><div class="tool">tool: ${data.tool_used}</div>`);
  window.scrollTo(0, document.body.scrollHeight);
}
</script>
"""


@app.route("/")
def index():
    return PAGE


@app.route("/ask", methods=["POST"])
def ask():
    question = (request.get_json(silent=True) or {}).get("question", "")
    try:
        return jsonify(answer_question({"question": question}))
    except Exception as exc:
        return jsonify({"answer": f"Something went wrong: {exc}", "tool_used": "none"})


if __name__ == "__main__":
    load_config()  # fail fast if the config or data is missing
    app.run(host="0.0.0.0", port=8888, debug=False)
