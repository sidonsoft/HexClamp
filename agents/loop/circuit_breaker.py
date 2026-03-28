"""Circuit breaker logic for HexClamp agent loop.

Prevents cascading failures by halting execution after consecutive errors.
"""

from typing import Dict, Any

from agents.store import STATE_DIR

# Circuit breaker state
_circuit_open = False
_consecutive_errors = 0
MAX_CONSECUTIVE_ERRORS = 3

# File paths for persistence
CIRCUIT_STATE_PATH = STATE_DIR / "circuit_breaker.json"
CIRCUIT_BREAKER_PATH = CIRCUIT_STATE_PATH  # Backward compatibility alias


def _reset_circuit() -> None:
    """Reset circuit breaker after successful operation."""
    global _circuit_open, _consecutive_errors
    _circuit_open = False
    _consecutive_errors = 0


def _reset_circuit_breaker() -> None:
    """Reset circuit breaker (backward compatibility alias)."""
    _reset_circuit()


def _trip_circuit() -> None:
    """Trip the circuit breaker after too many errors."""
    global _circuit_open
    _circuit_open = True


def _persist_circuit_breaker_state() -> None:
    """Persist circuit breaker state to disk."""
    from agents.store import write_json
    write_json(
        CIRCUIT_STATE_PATH,
        {
            "circuit_open": _circuit_open,
            "consecutive_errors": _consecutive_errors,
        },
    )


def _load_circuit_breaker_state() -> None:
    """Load circuit breaker state from disk on startup."""
    global _circuit_open, _consecutive_errors
    from agents.store import read_json
    state = read_json(CIRCUIT_STATE_PATH, default={})
    _circuit_open = state.get("circuit_open", False)
    _consecutive_errors = state.get("consecutive_errors", 0)


def is_circuit_open() -> bool:
    """Check if circuit breaker is currently open."""
    return _circuit_open


def get_circuit_state() -> Dict[str, Any]:
    """Get current circuit breaker state."""
    return {
        "circuit_open": _circuit_open,
        "consecutive_errors": _consecutive_errors,
        "max_errors": MAX_CONSECUTIVE_ERRORS,
    }


# Load persisted state on module import
_load_circuit_breaker_state()
