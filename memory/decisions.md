# Decisions

- Use file-backed state as the default operating memory.
- Build scaffold and schemas before the full loop implementation.
- Start with a single executor vertical slice.

---

## 2026-03-28: Bug Fix & Security Pass

**Decision:** Fix all 11 identified issues in a single session (4 bugs, 4 security, 3 quality)

**Rationale:**
- High-severity issues affecting user experience (false positives dropping messages)
- Security vulnerabilities (SSRF gaps, silent auth failures)
- Code quality debt (duplicated functions, naming inconsistencies)

**Approach:**
- Fix bugs first (#1-#4)
- Address security issues by severity (Sec-2 🔴 → Sec-3 → Sec-1 → Sec-4)
- Clean up quality improvements last (Qual-1-3)
- Independent verification by coderplus agent

**Outcome:** All 11 fixes verified and merged. See `memory/2026-03-28-hexclamp-final-review.md`.

---

## 2026-03-26: Harness Improvements
