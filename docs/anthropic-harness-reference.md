# Anthropic Harness Design — Technical Reference

**Source:** https://www.anthropic.com/engineering/harness-design-long-running-apps  
**Published:** Mar 24, 2026  
**Author:** Prithvi Rajasekaran (Anthropic Labs)

---

## Core Problems Identified

### 1. Context Anxiety
Models lose coherence on lengthy tasks as context window fills. Some exhibit "context anxiety" — wrapping up work prematurely as they approach their perceived context limit.

**Solution:** Context resets (clear context entirely, start fresh agent with structured handoff) vs compaction (summarize in place).

| Approach | Pros | Cons |
|----------|------|------|
| **Context Reset** | Clean slate, eliminates anxiety | Orchestration complexity, token overhead |
| **Compaction** | Preserves continuity | Anxiety can persist |

**Finding:** Claude Sonnet 4.5 exhibited context anxiety strongly enough that compaction alone was insufficient.

---

### 2. Self-Evaluation Bias
When asked to evaluate their own work, agents confidently praise mediocre output. Particularly pronounced for subjective tasks (design) but also occurs on verifiable tasks.

**Solution:** Generator-evaluator separation (GAN-inspired pattern).

**Key insight:** Tuning a standalone evaluator to be skeptical is more tractable than making a generator critical of its own work.

---

## Three-Agent Architecture

```
┌─────────────┐
│  Planner    │  1-4 sentence prompt → full product spec
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Generator  │  Works in sprints, one feature at a time
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Evaluator  │  Playwright MCP, clicks through running app
└─────────────┘
```

### Planner Agent
- Takes 1-4 sentence prompt → expands to full product spec
- Ambitious about scope
- Focused on product context + high-level technical design (not granular implementation)
- Weaves AI features into specs
- Prevents under-scoping

### Generator Agent
- Works in sprints, one feature at a time
- Stack: React, Vite, FastAPI, SQLite/PostgreSQL
- Self-evaluates before handing off to QA
- Uses git for version control
- After each evaluation: refine current direction OR pivot to different aesthetic

### Evaluator Agent
- Uses Playwright MCP to interact with live application
- Tests UI features, API endpoints, database states
- Grades each sprint against criteria + bugs found
- Hard thresholds — if any fall below, sprint fails with detailed feedback

---

## Frontend Design Criteria (4 Grading Criteria)

| Criterion | What It Measures | Weight |
|-----------|------------------|--------|
| **Design Quality** | Coherent whole vs collection of parts? Colors, typography, layout combine for distinct mood/identity | High |
| **Originality** | Custom decisions vs template layouts, library defaults, AI patterns? Penalize "AI slop" (purple gradients over white cards) | High |
| **Craft** | Technical execution: typography hierarchy, spacing, color harmony, contrast ratios | Low (default competence) |
| **Functionality** | Usability: can users understand what interface does, find primary actions, complete tasks? | Low (default competence) |

**Rationale:** Emphasize design quality + originality because Claude already scores well on craft/functionality by default.

**Evaluator calibration:** Few-shot examples with detailed score breakdowns to align judgment and reduce score drift.

---

## Sprint Contracts

**Purpose:** Bridge gap between high-level spec and testable implementation.

**Process:**
1. Generator proposes: what it will build + how success will be verified
2. Evaluator reviews: is this sufficient? what's missing?
3. Iterate until agreed
4. Generator builds against contract
5. Evaluator grades against contract (not moving goalposts)

**Communication pattern:** File-based — one agent writes file, another reads + responds (in same file or new file).

**Benefits:**
- Clear target for generator (no ambiguity)
- Protection from moving goalposts
- Evaluator can catch gaps before code is written
- Concrete criteria for evaluation (not vibes)

---

## Evaluator Tuning Loop

**Problem:** Out of box, Claude is poor QA agent.
- Identifies legitimate issues, then talks itself into approving anyway
- Tests superficially, misses subtle bugs

**Tuning process:**
```
Read evaluator logs → Find judgment divergences → Update QA prompt → Repeat
```

**Result after tuning:** Evaluator files specific, actionable bugs.

**Example findings:**
| Contract Criterion | Evaluator Finding |
|--------------------|-------------------|
| Rectangle fill tool allows click-drag to fill area | FAIL — Tool only places tiles at drag start/end. `fillRectangle` function exists but isn't triggered on mouseUp |
| User can select and delete entity spawn points | FAIL — Delete key handler requires both `selection` AND `selectedEntityId`, but clicking only sets `selectedEntityId`. Should be `selection \|\| selectedEntityId` |
| User can reorder animation frames via API | FAIL — Route defined after `/{frame_id}` routes. FastAPI matches 'reorder' as integer, returns 422 |

---

## Results Comparison

### Retro Game Maker

| Harness | Duration | Cost | Quality |
|---------|----------|------|---------|
| Solo | 20 min | $9 | Broken (game unplayable, wiring broken) |
| Full harness | 6 hr | $200 | Playable (physics rough but functional) |

**20x cost, but quality difference immediately apparent.**

### Digital Audio Workstation (Opus 4.6, simplified harness)

| Agent & Phase | Duration | Cost |
|---------------|----------|------|
| Planner | 4.7 min | $0.46 |
| Build (Round 1) | 2 hr 7 min | $71.08 |
| QA (Round 1) | 8.8 min | $3.24 |
| Build (Round 2) | 1 hr 2 min | $36.89 |
| QA (Round 2) | 6.8 min | $3.09 |
| Build (Round 3) | 10.9 min | $5.88 |
| QA (Round 3) | 9.6 min | $4.06 |
| **Total** | **3 hr 50 min** | **$124.70** |

**QA caught real gaps:**
- Core DAW features display-only (clips can't drag, no instrument UI panels, no visual effect editors)
- Audio recording stub-only
- Clip resize/split not implemented

---

## Harness Simplification Over Time

**Principle:** Every component encodes an assumption about what the model can't do alone. Assumptions may be incorrect or go stale as models improve.

**Approach:** "Find simplest solution possible, only increase complexity when needed"

### Opus 4.5 → 4.6 Improvements
- Removed sprint decomposition (model can sustain 2+ hours coherently)
- Evaluator moved from per-sprint to single pass at end
- Evaluator usefulness became task-dependent:
  - On 4.5: builds at edge of capability, evaluator caught meaningful issues
  - On 4.6: boundary moved outward, evaluator unnecessary for simpler tasks but still valuable for edge cases

**Key insight:** Evaluator is not fixed yes/no decision. Worth the cost when task sits beyond what current model does reliably solo.

---

## Key Principles

### 1. Context Engineering
- Context resets solve anxiety but add complexity
- Match approach to model's characteristics (Sonnet 4.5 needed resets, Opus 4.6 less so)

### 2. Generator-Evaluator Separation
- External feedback gives generator something concrete to iterate against
- Evaluator tuning is real work — expect several rounds before reasonable performance

### 3. Sprint Contracts
- Negotiate "done" before building
- File-based communication keeps work faithful to spec without over-specifying early

### 4. Assumptions Go Stale
- Stress-test each harness component
- When new model lands: re-examine harness, strip away pieces no longer load-bearing

### 5. Evaluator Usefulness Is Task-Dependent
- Not a fixed yes/no decision
- Worth cost when task is at edge of model's solo capability

---

## Creative Leaps Observed

**Dutch art museum website:**
- Iterations 1-9: Clean, dark-themed landing page (visually polished but expected)
- **Iteration 10:** Scrapped approach entirely → 3D room with checkered floor (CSS perspective), artwork on walls, doorway-based navigation between gallery rooms

**Pattern:** Kind of creative leap not seen in single-pass generation. Emerged from iterative feedback loop.

---

## Future Directions

1. **Models improve** → work longer on more complex tasks
2. **Scaffold may matter less** over time (wait for next model)
3. **OR:** Better models enable more complex harnesses achieving tasks beyond baseline

**Best practice:**
- Experiment with current model
- Read traces on realistic problems
- Tune performance to achieve desired outcomes
- When new model lands: re-examine harness, strip away pieces no longer load-bearing

---

## Relevance to HexClamp

**HexClamp already implements:**
- ✅ File-backed state (`state/`, `runs/`)
- ✅ Verifier component (`agents/verifier.py`)
- ✅ Condenser (`agents/condenser.py`)
- ✅ Narrow executor contracts

**Gaps identified:**
- ⚠️ Verifier may be lenient (needs tuning loop)
- ⚠️ No acceptance criteria per loop (sprint contracts)
- ⚠️ Condensation automatic (no explicit context resets)
- ⚠️ No metrics tracking
- ⚠️ Static verifier (doesn't learn from mistakes)

**See:** `ROADMAP.md` for implementation plan.
