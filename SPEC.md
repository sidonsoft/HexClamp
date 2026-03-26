# HexClamp — Spec

## What it is

HexClamp is an **inspectable autonomous task loop** — a background agent that picks up bounded tasks, executes them, and produces traceable artifacts. Every decision, action, and result is written to disk. Nothing happens in invisible prompt state.

It is **not** a chatbot. It is **not** a general assistant. It runs tasks you give it and reports back with evidence.

---

## Goal

HexClamp succeeds when:

- Tasks enqueued by the operator complete with verifiable artifacts
- The loop never goes silent — failures are surfaced, not hidden
- Every meaningful action has traceable evidence in `state/`
- The operator can inspect full loop history at any time
- External actions (messaging, code execution) require explicit approval before taking effect

---

## Core loop

```
Observe → Condense → Plan → Execute → Verify → Persist
```

Each cycle:
1. **Observe** — ingest raw inputs (CLI enqueue, Telegram poll) as Events
2. **Condense** — compress Events + Open Loops into CurrentState
3. **Plan** — rank open loops, propose one action
4. **Execute** — run the action through the appropriate executor
5. **Verify** — check the result against success criteria (for code, browser, messaging)
6. **Persist** — write state, artifacts, and results to disk

One action per cycle. No batching. No ambiguity about what ran.

---

## Executors

| Executor | What it does | What it does NOT do |
|----------|--------------|---------------------|
| **research** | Ingest local files/repos, produce grounded 5-part findings | Write code, navigate the web, make decisions |
| **code** | Run coding tasks in a target workspace via brief | Touch production systems, run without verification |
| **browser** | Headless Chromium — navigate, screenshot, extract | Fill forms, interact with auth flows, scrape at scale |
| **messaging** | Send Telegram messages, with sentinel approval gate | Send to non-Telegram channels, persist conversations |

---

## State

All state lives in `state/`:

| File | What it holds |
|------|---------------|
| `event_queue.json` | Pending Events awaiting a loop cycle |
| `open_loops.json` | Ongoing tasks with evidence, status, and updates |
| `current_state.json` | Condensed view: goal, active context, recent events, current actions, verified results |
| `recent_changes.md` | Markdown log of completed research summaries |
| `polling_state.json` | Telegram polling offset (idempotency guard) |

Run artifacts land in `runs/<executor>_tasks/<action_id>/`.

State is **append-oriented where possible, atomic on write**. The store module is the only write path — no direct file writes.

---

## What's deliberately excluded

These are out of scope. Adding them would require a rewrite or a separate project.

- **Natural language chat** — HexClamp is not a chatbot. Telegram inbound is for task enqueue and approvals, not conversation.
- **Long-running autonomous reasoning** — one action per cycle, bounded by executor timeouts.
- **Web search / live external data** — research executor works on local files only.
- **Multi-agent coordination** — one loop, one operator.
- **Persistent learned memory** — each session starts fresh from state files. No LLM fine-tuning or embedding-based recall.
- **Code execution without verification** — code results must be verified before the loop closes the action.
- **Auto-retry without backoff** — retries are capped at 3, with backoff enforced by policy.
- **Production system mutation** — HexClamp runs in its own workspace by default. Code executor targets `HEXCLAMP_WORKSPACE` if set.

---

## Risk levels

Every action has a declared risk level:

- **low** — read-only, no side effects (research, browser navigation with screenshots)
- **medium** — local side effects (file writes to workspace, messaging with approval)
- **high** — external or irreversible effects (code execution, production sends)

`policies.yaml` defines the verification gate: **code, browser, and messaging always require verification**. Research does not.

---

## Failure modes

The loop handles failures explicitly:

- **Executor returns failed status** → action marked failed, open loop updated with evidence, loop continues
- **Consecutive failures (circuit breaker)** → loop pauses after 3 consecutive failures, operator notified via Telegram
- **Verification fails** → action stays open, retry proposed in next cycle
- **Context window full** → this is a CoPaw problem; HexClamp itself should never silently stop responding

---

## Eval

HexClamp does not self-evaluate outcomes. The operator does.

| Signal | How to track |
|--------|-------------|
| Task completion | Did the artifact in `runs/` match the enqueued goal? |
| Research quality | Is `state/recent_changes.md` accurate and grounded? |
| Loop reliability | Has the circuit breaker ever tripped? |
| False positives | Has the verifier ever accepted a bad result? |
| Silent failures | Any action marked done with no artifacts? |

Run `python3 -m agents.loop status` before each session to get a snapshot. Periodically review `state/open_loops.json` for stale items.

---

## Adding features

Before adding anything, ask:

1. Does this serve a **bounded task** or an **open-ended goal**?
2. Can it produce **traceable evidence** of what it did?
3. Does it have a **clear failure mode** that the loop can handle?
4. Does it **require** being in the loop, or could it be a separate tool?

If the answer to any of those is unclear, it probably doesn't belong in HexClamp yet.

---

## CI / hygiene

All commits must pass before merge:

```
python3 -m pytest -q
python3 -m ruff check .
python3 -m ruff format --check .
python3 -m mypy agents/ scripts/ --ignore-missing-imports
```

No exceptions. CI runs on every PR and push to `main`.
