"""Circuit breaker logic for HexClamp agent loop.

Prevents cascading failures by halting execution after consecutive errors.
"""

import sys
from typing import Dict, Any

from agents.store import STATE_DIR

# File paths for persistence
CIRCUIT_STATE_PATH = STATE_DIR / "circuit_breaker.json"
CIRCUIT_BREAKER_PATH = CIRCUIT_STATE_PATH  # Backward compatibility alias


class CircuitBreaker:
    """Encapsulated circuit breaker state with disk persistence.
    
    Thread-safe-ish (single-threaded agent loop).
    Maintains sync with module globals for test compatibility.
    """
    
    def __init__(self, module: Any = None) -> None:
        """Initialize circuit breaker.
        
        Args:
            module: Module object to sync globals with (for test compatibility)
        """
        self._module = module
        self._open: bool = False
        self._consecutive_errors: int = 0
        self._max_errors: int = 3
    
    def _sync(self) -> None:
        """Adopt module globals if they differ from instance state.
        
        This allows tests to patch module globals and have the class pick up changes.
        """
        if self._module:
            if hasattr(self._module, '_circuit_open'):
                if self._module._circuit_open != self._open:
                    self._open = self._module._circuit_open
            if hasattr(self._module, '_consecutive_errors'):
                if self._module._consecutive_errors != self._consecutive_errors:
                    self._consecutive_errors = self._module._consecutive_errors
    
    def _push(self) -> None:
        """Write instance state to module globals unconditionally."""
        if self._module:
            self._module._circuit_open = self._open
            self._module._consecutive_errors = self._consecutive_errors
    
    def reset(self) -> None:
        """Reset circuit breaker after successful operation."""
        self._open = False
        self._consecutive_errors = 0
        self._push()
    
    def trip(self) -> None:
        """Trip the circuit breaker after too many errors."""
        self._open = True
        self._push()
    
    def record_error(self) -> bool:
        """Record an error and check if circuit should trip.
        
        Returns:
            True if circuit tripped (too many errors), False otherwise
        """
        self._sync()
        self._consecutive_errors += 1
        if self._consecutive_errors >= self._max_errors:
            self.trip()
            return True
        self._push()
        return False
    
    def record_success(self) -> None:
        """Record a successful operation (resets error counter)."""
        self._open = False
        self._consecutive_errors = 0
        self._push()
    
    def is_open(self) -> bool:
        """Check if circuit breaker is currently open."""
        self._sync()
        return self._open
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        self._sync()
        return {
            "circuit_open": self._open,
            "consecutive_errors": self._consecutive_errors,
            "max_errors": self._max_errors,
        }
    
    def persist(self) -> None:
        """Persist circuit breaker state to disk."""
        try:
            from agents.store import write_json
            write_json(
                CIRCUIT_STATE_PATH,
                {
                    "circuit_open": self._open,
                    "consecutive_errors": self._consecutive_errors,
                },
            )
        except Exception:
            pass  # Ignore persistence errors on startup
    
    def load(self) -> None:
        """Load circuit breaker state from disk."""
        try:
            from agents.store import read_json
            state = read_json(CIRCUIT_STATE_PATH, default={})
            self._open = state.get("circuit_open", False)
            self._consecutive_errors = state.get("consecutive_errors", 0)
            self._push()
        except Exception:
            pass  # Ignore load errors on startup


# Module-level instance (singleton)
# Also export module globals for backward compatibility
_circuit_open = False
_consecutive_errors = 0
MAX_CONSECUTIVE_ERRORS = 3

_breaker = CircuitBreaker(sys.modules[__name__])


# Backward compatibility functions (module-level API)
def _reset_circuit() -> None:
    """Reset circuit breaker after successful operation."""
    _breaker.reset()

def _reset_circuit_breaker() -> None:
    """Reset circuit breaker (backward compatibility alias)."""
    _breaker.reset()

def _trip_circuit() -> None:
    """Trip the circuit breaker after too many errors."""
    _breaker.trip()

def _persist_circuit_breaker_state() -> None:
    """Persist circuit breaker state to disk."""
    _breaker.persist()

def _load_circuit_breaker_state() -> None:
    """Load circuit breaker state from disk on startup."""
    _breaker.load()

def is_circuit_open() -> bool:
    """Check if circuit breaker is currently open."""
    return _breaker.is_open()

def get_circuit_state() -> Dict[str, Any]:
    """Get current circuit breaker state."""
    return _breaker.get_state()


# Load persisted state on module import
_load_circuit_breaker_state()