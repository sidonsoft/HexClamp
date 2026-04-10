# CI Fix Summary — 2026-04-09

## Issue
CI run #24193806064 failed due to GLM-5.1 code review findings.

**Error:** `ModuleNotFoundError: No module named 'filelock'`

---

## Root Causes

### 1. Missing Dependency Installation
**Problem:** `filelock` dependency not installed during CI  
**Cause:** `dependencies` section was placed **after** `optional-dependencies` in `pyproject.toml`  
**Fix:** Moved `dependencies` block before `optional-dependencies`

### 2. Ruff Linting Errors
**Problem:** 5 linting errors in source code  
**Causes:**
- F401: Unused import (`datetime.timezone` in `loop.py`)
- I001: Unsorted import blocks in multiple files

**Fix:** Ran `ruff check src/ --fix` to auto-correct all issues

---

## Files Changed

| File | Changes |
|------|---------|
| `pyproject.toml` | Reordered sections (dependencies before optional-dependencies) |
| `src/hexclamp/agent.py` | Import sorting |
| `src/hexclamp/loop.py` | Removed unused `timezone` import, import sorting |
| `src/hexclamp/store.py` | Import sorting (`filelock` moved to standard lib section) |

---

## Commits

1. **71f397e** — fix: move dependencies before optional-dependencies in pyproject.toml
2. **d81fb21** — fix: resolve ruff linting errors from GLM-5.1 review

---

## CI Results

### Before (Run #24193806064)
- ❌ test (3.11) — Failed (filelock missing)
- ❌ test (3.10) — Cancelled
- ❌ test (3.12) — Cancelled
- ✅ build — Success

### After (Run #24219723859)
- ✅ test (3.10) — 20s
- ✅ test (3.11) — 14s
- ✅ test (3.12) — 19s
- ✅ build — 9s

**All jobs passing!** 🎉

---

## Verification

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest --cov=src/hexclamp --cov-report=term-missing

# Run linter
ruff check src/

# Run type checker
mypy src/
```

All checks should pass locally.

---

## Notes

- **Node.js 20 deprecation warning** — GitHub Actions will migrate to Node.js 24 by June 2026
- Consider updating `actions/checkout@v4` and `actions/setup-python@v5` to Node.js 24 compatible versions

