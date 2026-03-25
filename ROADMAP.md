# HexClamp Roadmap — Harness Improvements

**Created:** 2026-03-26  
**Source:** Anthropic harness design lessons + HexClamp current state  
**Priority:** High

---

## Current State Analysis

### What HexClamp Already Does Well ✅

**1. File-Backed State**
- Everything persists to disk (`state/`, `runs/`)
- No invisible prompt state
- Survives restarts, fully inspectable

**2. Built-in Verifier**
- `agents/verifier.py` validates claimed results against evidence
- Requires minimum evidence by action type
- Circuit breaker after 3 consecutive failures

**3. Condensation Pattern**
- `agents/condenser.py` compresses events + loops into CurrentState
- Avoids loading entire history into context
- Similar to Anthropic's context management

**4. Narrow Executor Contracts**
- Each executor has clear authority (research, code, browser, message)
- Verification is mandatory for meaningful actions
- Approval required for external actions (Telegram)

---

## High-Value Improvements (from Anthropic Lessons)

### 1. Enhanced Verifier — Generator-Evaluator Separation 🎯

**Current gap:** Verifier exists but may suffer from same issues Anthropic found:
- Out of box, Claude is poor QA agent
- Identifies issues then talks itself into approving
- Tests superficially, misses subtle bugs

**Improvement:**
```python
# Current: verifier checks evidence files exist
# Enhanced: verifier uses rigorous checklist

VERIFIER_CHECKLIST = {
    "research": [
        "Claims grounded in actual file content?",
        "Sources cited with line numbers?",
        "No speculation presented as fact?",
        "Contradictions flagged?",
    ],
    "code": [
        "Tests pass (not just syntax)?",
        "Edge cases handled?",
        "Error states tested?",
        "Matches original loop goal?",
    ],
    "browser": [
        "Screenshot shows expected state?",
        "Network requests succeeded?",
        "Console errors checked?",
        "Interactive elements actually work?",
    ],
    "message": [
        "Content matches approved draft?",
        "Recipient verified?",
        "No sensitive data leaked?",
    ],
}
```

**Impact:** Reduce false positives (bad results marked "done") by 50%+

**Files to modify:**
- `agents/verifier.py` — Add checklist-based validation
- `prompts/verifier.md` — Update with rigorous criteria
- `config/policies.yaml` — Add verification requirements

---

### 2. Pre-Execution Contracts — Sprint Contracts for Actions 📋

**Current gap:** Open loops have goals, but "done" criteria may be ambiguous

**Before:**
```json
{
  "goal": "Research Python async best practices",
  "status": "open"
}
```

**After:**
```json
{
  "goal": "Research Python async best practices",
  "acceptance_criteria": [
    "Summary document in runs/{timestamp}_research.md",
    "At least 3 authoritative sources cited",
    "Code examples included for each pattern",
    "Anti-patterns section with what to avoid"
  ],
  "verification_commands": [
    "grep -c 'Source:' runs/{timestamp}_research.md >= 3",
    "grep -c '```python' runs/{timestamp}_research.md >= 2"
  ],
  "status": "open"
}
```

**Implementation:**
- `agents/planner.py` — When ranking loops, also generate acceptance criteria
- `agents/models.py` — Add `acceptance_criteria` and `verification_commands` to OpenLoop
- `prompts/planner.md` — Update to generate contracts, not just goals

**Impact:** Reduce rework cycles by 30%+, clearer handoffs between planner→executor→verifier

---

### 3. Context Reset Pattern — Explicit Condensation Triggers 🔄

**Current gap:** Condenser runs every cycle, but may not solve "context anxiety"

**Anthropic finding:** Compaction alone didn't solve context anxiety. Needed explicit context resets.

**Improvement:**
```python
# agents/condenser.py

CONDENSATION_TRIGGERS = {
    "context_tokens": 0.5,  # Condense at 50% context window
    "loop_count": 10,       # Condense after 10 loops
    "event_count": 20,      # Condense after 20 events
    "error_detected": True, # Force condense on errors
}

# When condensing, write handoff file
def condense_with_handoff(state):
    handoff = {
        "completed": [...],
        "current_state": {...},
        "next_steps": [...],
        "open_questions": [...],
        "gotchas": [...],
    }
    write_json(STATE_DIR / "handoff.json", handoff)
    return condensed_state
```

**Files to modify:**
- `agents/condenser.py` — Add triggers, write handoff files
- `agents/loop.py` — Check for handoff on startup
- `state/handoff.json` — New file for context transfers

**Impact:** Prevent context anxiety, enable longer-running tasks without quality degradation

---

### 4. Metrics Tracking — Quality Dashboard 📊

**Current gap:** No systematic tracking of quality metrics

**Add to `scripts/status.py` or new `scripts/metrics.py`:**

```python
METRICS = {
    "tasks_completed": count_completed_loops(),
    "bugs_found_post_completion": count_post_completion_fixes(),
    "rework_cycles": count_loop_retries(),
    "verifier_false_positives": count_verifier_overrides(),
    "circuit_breaker_trips": count_circuit_breaker_activations(),
    "avg_loop_duration": average_loop_time(),
}

# Output as dashboard
def print_metrics_dashboard():
    print("HexClamp Quality Metrics")
    print("=" * 40)
    print(f"Tasks completed: {metrics['tasks_completed']}")
    print(f"Bugs post-completion: {metrics['bugs_found_post_completion']} (target: ↓)")
    print(f"Rework cycles: {metrics['rework_cycles']} (target: ↓)")
    print(f"Verifier false positives: {metrics['verifier_false_positives']}")
    print(f"Circuit breaker trips: {metrics['circuit_breaker_trips']}")
```

**Files to create:**
- `scripts/metrics.py` — Metrics collection and dashboard
- `memory/metrics-log.md` — Historical tracking

**Impact:** Data-driven improvements, can measure if changes actually help

---

### 5. Evaluator Tuning Loop — Continuous Improvement 🔧

**Current gap:** Verifier is static, doesn't learn from mistakes

**Anthropic pattern:**
```
Run evaluation → Read logs → Find judgment divergences → Update prompt → Repeat
```

**Implementation:**
```python
# When verifier passes something that later fails:
def log_verifier_mistake(action, result, later_evidence):
    mistake = {
        "timestamp": datetime.now().isoformat(),
        "action_id": action.id,
        "what_was_missed": later_evidence,
        "verdict_at_time": result.verdict,
        "category": categorize_mistake(later_evidence),
    }
    append_json_array(STATE_DIR / "verifier-mistakes.json", mistake)

# Monthly: analyze patterns, update verifier prompt
def update_verifier_prompt():
    mistakes = read_json(STATE_DIR / "verifier-mistakes.json")
    patterns = analyze_mistake_patterns(mistakes)
    # Generate new verifier.md with lessons learned
```

**Files to modify:**
- `agents/verifier.py` — Log mistakes when discovered
- `prompts/verifier.md` — Update based on patterns
- `scripts/update-verifier.py` — Automated prompt improvement

**Impact:** Verifier gets smarter over time, false positive rate decreases

---

## Implementation Priority

### Phase 1: Foundation (Week 1-2)
**Goal:** Add metrics tracking + enhanced verifier checklist

- [ ] `scripts/metrics.py` — Metrics dashboard
- [ ] `agents/verifier.py` — Checklist-based validation
- [ ] `prompts/verifier.md` — Update with rigorous criteria
- [ ] `memory/metrics-log.md` — Start tracking

**Success:** Can run `python -m scripts.metrics` and see quality dashboard

---

### Phase 2: Contracts (Week 3-4)
**Goal:** Pre-execution contracts for all actions

- [ ] `agents/models.py` — Add acceptance_criteria to OpenLoop
- [ ] `agents/planner.py` — Generate contracts when ranking loops
- [ ] `prompts/planner.md` — Update to create contracts
- [ ] `agents/verifier.py` — Check against contract, not just vibes

**Success:** All new loops have explicit acceptance criteria

---

### Phase 3: Context Management (Week 5-6)
**Goal:** Explicit context resets, not just condensation

- [ ] `agents/condenser.py` — Add triggers, write handoff files
- [ ] `agents/loop.py` — Check for handoff on startup
- [ ] `state/handoff.json` — New file format
- [ ] Test on long-running tasks (10+ loops)

**Success:** Can run 20+ loop tasks without quality degradation

---

### Phase 4: Continuous Improvement (Ongoing)
**Goal:** Verifier gets smarter over time

- [ ] `agents/verifier.py` — Log mistakes
- [ ] `scripts/update-verifier.py` — Analyze patterns monthly
- [ ] `memory/verifier-lessons.md` — Track improvements
- [ ] Quarterly: Review all assumptions

**Success:** Verifier false positive rate decreases month-over-month

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Overhead slows loop | Medium | Start with non-critical loops; measure net time saved |
| Contracts feel rigid | Low | Allow emergency overrides with logging |
| Metrics become burdensome | Low | Automate collection; keep dashboard simple |
| Verifier mistakes log grows | Low | Archive quarterly; focus on recent patterns |

---

## Related

- **CoPaw Harness Improvements:** `~/.copaw/vault/projects/active/harness-improvements/`
- **Anthropic Article:** https://www.anthropic.com/engineering/harness-design-long-running-apps
- **HexClamp SPEC:** `SPEC.md`
- **HexClamp Architecture:** `docs/architecture.md`

---

## Next Action

**Start with Phase 1, Task 1:** Create `scripts/metrics.py` to establish baseline metrics before making changes.

Can't improve what you don't measure.
