# Roadmap

## Current Status

**HexClamp** is a fresh start (v0.4.0) with core features from the archived HexClampRefactor repo.

---

## v0.4.0 - Foundation (COMPLETED 2026-04-07)

### Status

Fresh start - core features implemented and tested.

### Completed Features

- [x] Structured loop: Observe → Condense → Plan → Execute → Verify → Persist
- [x] Event system with webhook support (GitHub, Slack, GitLab)
- [x] Scheduler with cron and interval timers
- [x] File-backed state management
- [x] OpenClaw agent adapter
- [x] Reference CLI agent implementation
- [x] GitHub Actions CI/CD
- [x] 36 tests, ruff, mypy all passing

### Quality Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Test Coverage | 80%+ | TBD |
| Mypy Errors | 0 | ✅ |
| Ruff Errors | 0 | ✅ |
| CI/CD | Required | ✅ |

---

## v0.5.0 - Observability

### Goals

Better visibility into loop execution.

### Features

- [ ] Metrics collection (cycle times, success rates)
- [ ] Structured logging (JSON format)
- [ ] Metrics dashboard (terminal + web)
- [ ] Action timing breakdown

### Details

- Track cycle duration, action duration, verification time
- JSON logs for parsing by log aggregators
- Simple terminal dashboard
- Web dashboard at http://localhost:8000 (optional)

---

## v0.6.0 - Smart Planning

### Goals
Improve action planning and prioritization.

### Features
- [ ] Dependency tracking between loops
- [ ] Batch actions for efficiency
- [ ] Context-aware action classification
- [ ] Learned priorities from success/failure

### Details
- Loops can declare dependencies on other loops
- Group similar actions for batch execution
- Use LLM to classify action type from description
- Learn which priorities work best for task types

---

## v0.7.0 - Verification Enhancements

### Goals
More sophisticated result verification.

### Features
- [ ] Multi-stage verification
- [ ] Verification templates
- [ ] External verification (run tests, lint, etc.)
- [ ] Verification learning

### Details
- Complex verification workflows
- Reusable verification patterns
- Auto-run configured tests/linters
- Improve verification based on false positives/negatives

---

## v0.8.0 - Integration Hub

### Goals
Connect to external services and tools.

### Features
- [ ] GitHub integration (issues, PRs)
- [ ] Slack/Discord notifications
- [ ] File watching (auto-trigger on file changes)
- [ ] Database connectors

### Details
- Sync loops with GitHub issues
- Send notifications to Slack/Discord
- Watch files/directories for changes
- Query/update external databases

---

## v1.0.0 - Stable Release

### Goals
Production-ready with documentation.

### Features
- [ ] Comprehensive documentation
- [ ] API documentation (if library)
- [ ] Tutorial / getting started guide
- [ ] Production deployment guide
- [ ] Security audit

### Details
- Full documentation site
- OpenAPI spec for HTTP interface
- Step-by-step tutorial
- Docker, Kubernetes deployment examples
- Security review and hardening

---

## Backlog

The following are ideas for future versions, not yet scheduled:

### Ideas
- **Multi-agent coordination**: Multiple agents working on shared loops
- **Hierarchical loops**: Parent/child loop relationships
- **Conditional actions**: Execute actions based on conditions
- **Rollback**: Ability to undo completed actions
- **Scheduling**: Advanced scheduling (cron, rate limiting)
- **Caching**: Cache frequent computations
- **Plugins**: Plugin system for extensions
- **Metrics export**: Prometheus, Datadog integration
- **Secrets management**: Secure storage for API keys
- **Encryption**: Encrypt state files at rest
