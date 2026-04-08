# Roadmap Plan: v0.5.0 - Observability

**Target Date:** 2026-05-07 (4 weeks from now)  
**Status:** 🟡 In Progress  
**Last Updated:** 2026-04-07  
**Created By:** roadmap-planner skill

---

## Summary

| Metric | Value |
|--------|-------|
| Total Features | 4 |
| Completed | 0 |
| In Progress | 0 |
| Not Started | 4 |
| Blockers | 0 |
| Total Tasks | 48 |
| Estimated Effort | 3-4 weeks |

---

## Priority Order

**Recommended implementation order:**

1. 🔴 **Structured Logging** (foundational, used by everything)
2. 🔴 **Metrics Collection** (depends on logging)
3. 🟡 **Terminal Dashboard** (quick feedback, low effort)
4. 🟡 **Web Dashboard** (more effort, optional)

---

## Features

### 🔴 High Priority

#### 1. Structured Logging

**Effort:** Small (2-3 days)  
**Status:** ⚪ Not Started  
**Owner:** @developer  
**GitHub Issue:** #1

**Description:**
Replace print statements and basic logging with structured JSON logging. This enables log aggregation, searching, and analysis. All HexClamp components will emit consistent JSON log entries.

**Why First:**
- Foundational for all other observability features
- Low effort (2-3 days)
- Used by metrics collection
- Improves debugging immediately

**Acceptance Criteria:**
- [ ] All log messages use JSON format
- [ ] Each log entry includes: timestamp, level, module, message, context
- [ ] Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- [ ] Can configure log level via environment variable
- [ ] Can configure output format (JSON vs human-readable)
- [ ] No sensitive data in logs

**Tasks:**
- [ ] Create `hexclamp/logging.py` module
- [ ] Define JSON log schema with required fields
- [ ] Implement `HexClampLogger` class with structured output
- [ ] Add context support (loop_id, action_id, etc.)
- [ ] Replace all `logger.info()` calls with structured logging
- [ ] Add log level configuration via `LOG_LEVEL` env var
- [ ] Add format configuration via `LOG_FORMAT` env var (json/text)
- [ ] Write unit tests for logging module
- [ ] Update all modules to use new logging
- [ ] Update CHANGELOG.md

**Dependencies:**
- None (foundational)

**Risks:**
- None identified

**Files Affected:**
- `src/hexclamp/logging.py` (new)
- All existing modules (update imports)

---

#### 2. Metrics Collection

**Effort:** Medium (4-5 days)  
**Status:** ⚪ Not Started  
**Owner:** @developer  
**GitHub Issue:** #2

**Description:**
Collect and expose metrics about loop execution: cycle count, success/failure rates, cycle duration, action duration, queue depth. Metrics are emitted via structured logs and available via programmatic API.

**Why Second:**
- Depends on structured logging
- Provides data for dashboards
- Medium effort (4-5 days)

**Acceptance Criteria:**
- [ ] Track cycle count (total, successful, failed)
- [ ] Track cycle duration (min, max, avg, p95)
- [ ] Track action duration by type
- [ ] Track queue depth (open loops, in-progress)
- [ ] Track webhook events received
- [ ] Track scheduler triggers
- [ ] Expose metrics via `loop.get_metrics()` API
- [ ] Emit metrics as JSON log entries on each cycle

**Tasks:**
- [ ] Create `hexclamp/metrics.py` module
- [ ] Define `MetricsCollector` class
- [ ] Add cycle counter metrics
- [ ] Add duration histograms (cycle, action)
- [ ] Add queue gauge metrics
- [ ] Add event counter metrics
- [ ] Implement `loop.get_metrics()` method
- [ ] Add metrics emission to loop cycle
- [ ] Add metrics emission to webhook receiver
- [ ] Add metrics emission to scheduler
- [ ] Write unit tests for metrics
- [ ] Update CHANGELOG.md

**Dependencies:**
- Structured logging (feature #1)

**Risks:**
- Performance impact of metrics collection (mitigation: use efficient counters)

**Files Affected:**
- `src/hexclamp/metrics.py` (new)
- `src/hexclamp/loop.py` (add metrics)
- `src/hexclamp/webhook.py` (add metrics)
- `src/hexclamp/scheduler.py` (add metrics)

---

### 🟡 Medium Priority

#### 3. Terminal Dashboard

**Effort:** Small (2-3 days)  
**Status:** ⚪ Not Started  
**Owner:** @developer  
**GitHub Issue:** #3

**Description:**
Simple terminal-based dashboard showing real-time HexClamp status. Displays loop count by status, recent activity, and key metrics. Updates in place using ANSI escape codes.

**Why Third:**
- Quick visual feedback during development
- Low effort (2-3 days)
- Doesn't require web framework

**Acceptance Criteria:**
- [ ] Show loop counts by status (open, in-progress, completed, failed)
- [ ] Show recent activity (last 5 loops)
- [ ] Show key metrics (cycles/minute, success rate)
- [ ] Auto-refresh every 5 seconds
- [ ] ANSI escape codes for in-place updates
- [ ] Keyboard interrupt to exit
- [ ] `hexclamp dashboard` CLI command

**Tasks:**
- [ ] Create `hexclamp/dashboard.py` module
- [ ] Implement `TerminalDashboard` class
- [ ] Add loop status display
- [ ] Add activity feed
- [ ] Add metrics summary
- [ ] Implement auto-refresh loop
- [ ] Add ANSI escape codes for in-place updates
- [ ] Handle keyboard interrupt gracefully
- [ ] Add `hexclamp dashboard` CLI subcommand
- [ ] Write unit tests
- [ ] Update README.md with dashboard usage
- [ ] Update CHANGELOG.md

**Dependencies:**
- Metrics collection (feature #2)

**Risks:**
- Terminal compatibility issues (mitigation: test on common terminals)

**Files Affected:**
- `src/hexclamp/dashboard.py` (new)
- `src/hexclamp/cli.py` (add dashboard command)

---

#### 4. Web Dashboard (Optional)

**Effort:** Medium (4-5 days)  
**Status:** ⚪ Not Started  
**Owner:** @developer  
**GitHub Issue:** #4

**Description:**
Web-based dashboard at http://localhost:8000 showing HexClamp status and metrics. Uses simple Flask server with auto-refreshing HTML page. Optional feature - can be disabled.

**Why Fourth:**
- More effort than terminal dashboard
- Optional (terminal dashboard may be sufficient)
- Requires web framework

**Acceptance Criteria:**
- [ ] Flask server with `/` endpoint showing dashboard
- [ ] Real-time updates via Server-Sent Events (SSE) or polling
- [ ] Show loop status distribution (pie chart or bar)
- [ ] Show metrics over time (line charts)
- [ ] Show recent activity log
- [ ] `/metrics` endpoint returning JSON
- [ ] `/health` endpoint for health checks
- [ ] Can disable via configuration
- [ ] Runs on port 8000 (configurable)

**Tasks:**
- [ ] Create `hexclamp/webdashboard.py` module
- [ ] Implement Flask app with dashboard routes
- [ ] Add HTML template for dashboard
- [ ] Add JavaScript for real-time updates
- [ ] Implement `/metrics` JSON endpoint
- [ ] Implement `/health` endpoint
- [ ] Add port configuration via `DASHBOARD_PORT` env var
- [ ] Add enable/disable via `DASHBOARD_ENABLED` env var
- [ ] Add `hexclamp webdashboard` CLI command
- [ ] Write integration tests
- [ ] Update README.md with web dashboard usage
- [ ] Update CHANGELOG.md

**Dependencies:**
- Metrics collection (feature #2)

**Risks:**
- Flask dependency may be heavy for some use cases (mitigation: make optional)

**Files Affected:**
- `src/hexclamp/webdashboard.py` (new)
- `src/hexclamp/cli.py` (add webdashboard command)

---

## GitHub Issues

| Issue | Title | Feature | Priority | Status |
|-------|-------|---------|----------|--------|
| #1 | Structured Logging | Logging | 🔴 High | Open |
| #2 | Metrics Collection | Metrics | 🔴 High | Open |
| #3 | Terminal Dashboard | Dashboard | 🟡 Medium | Open |
| #4 | Web Dashboard | Dashboard | 🟡 Medium | Open |

---

## Dependencies

### Internal
- Structured logging must be completed before metrics collection
- Metrics collection should be completed before dashboards

### External
- Flask for web dashboard (optional)

### Waiting On
- Nothing currently blocking

---

## Risks & Blockers

### 🔴 Critical Blockers

| Blocker | Impact | Resolution | Owner | ETA |
|---------|--------|------------|-------|-----|
| None | - | - | - | - |

### 🟡 Potential Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Metrics performance impact | Low | Medium | Use efficient counters, make optional |
| Flask dependency | Low | Low | Make web dashboard optional |
| Terminal compatibility | Low | Low | Test on common terminals |

---

## Weekly Plan

### Week 1: Structured Logging (Apr 7-14)

| Day | Task | Feature | Status |
|-----|------|---------|--------|
| Mon | Create logging module structure | Logging | ⚪ TODO |
| Tue | Implement JSON log schema | Logging | ⚪ TODO |
| Wed | Implement HexClampLogger | Logging | ⚪ TODO |
| Thu | Add env var configuration | Logging | ⚪ TODO |
| Fri | Update all modules, write tests | Logging | ⚪ TODO |

**Week 1 Goal:** Structured logging complete

### Week 2: Metrics Collection (Apr 14-21)

| Day | Task | Feature | Status |
|-----|------|---------|--------|
| Mon | Create metrics module | Metrics | ⚪ TODO |
| Tue | Add cycle counter metrics | Metrics | ⚪ TODO |
| Wed | Add duration histograms | Metrics | ⚪ TODO |
| Thu | Add queue/event metrics | Metrics | ⚪ TODO |
| Fri | Add to loop/webhook/scheduler | Metrics | ⚪ TODO |

**Week 2 Goal:** Metrics collection complete

### Week 3: Terminal Dashboard + Web Start (Apr 21-28)

| Day | Task | Feature | Status |
|-----|------|---------|--------|
| Mon | Create dashboard module | Terminal | ⚪ TODO |
| Tue | Implement status display | Terminal | ⚪ TODO |
| Wed | Add activity feed | Terminal | ⚪ TODO |
| Thu | Add to CLI | Terminal | ⚪ TODO |
| Fri | Start web dashboard | Web | ⚪ TODO |

**Week 3 Goal:** Terminal dashboard complete, web started

### Week 4: Web Dashboard + Release (Apr 28-May 7)

| Day | Task | Feature | Status |
|-----|------|---------|--------|
| Mon | Complete web dashboard | Web | ⚪ TODO |
| Tue | Add real-time updates | Web | ⚪ TODO |
| Wed | Add /metrics and /health | Web | ⚪ TODO |
| Thu | Final testing | All | ⚪ TODO |
| Fri | Update CHANGELOG, release v0.5.0 | Release | ⚪ TODO |

**Week 4 Goal:** All features complete, v0.5.0 released

---

## Progress Updates

### 2026-04-07 - Planning Session

**Completed:**
- ✅ Created ROADMAP.md with full roadmap
- ✅ Created ROADMAP_PLAN.md for v0.5.0
- ✅ Identified 4 features with 48 tasks
- ✅ Created GitHub issues #1-#4

**In Progress:**
- 🟡 Planning v0.5.0

**Blockers:**
- None

**Next Steps:**
1. Start work on Structured Logging (#1)
2. Create `src/hexclamp/logging.py` module
3. Update this plan weekly

**Burndown:**
- Total tasks: 48
- Completed: 0 (0%)
- Remaining: 48 (100%)

---

## Definition of Done

A feature is considered **done** when:

- ✅ All tasks completed
- ✅ Tests written and passing
- ✅ Code reviewed and merged
- ✅ Documentation updated
- ✅ Added to CHANGELOG.md
- ✅ GitHub issue closed

---

## Release Checklist

When all features are complete:

- [ ] Update CHANGELOG.md with v0.5.0 section
- [ ] Update VERSION to 0.5.0
- [ ] Run all tests (pytest)
- [ ] Run lint (ruff)
- [ ] Run type check (mypy)
- [ ] Create git tag v0.5.0
- [ ] Push tag to GitHub
- [ ] Create GitHub release

---

## Notes

- Target completion: 2026-05-07 (4 weeks)
- Weekly progress updates every Monday
- Observability features improve debugging and monitoring
- Make web dashboard optional to avoid unnecessary dependencies
