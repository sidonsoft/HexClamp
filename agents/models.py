from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Event:
    id: str
    timestamp: str
    source: str
    kind: str
    payload: Dict[str, Any]
    tags: List[str]
    priority: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CurrentState:
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Event:
        return cls(**data)


@dataclass
class Action:
    id: str
    type: str
    goal: str
    inputs: List[str]
    executor: str
    success_criteria: str
    risk: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CurrentState:
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Action:
        return cls(**data)


@dataclass
class OpenLoop:
    id: str
    title: str
    status: str
    priority: str
    owner: str
    created_at: str
    updated_at: str
    next_step: str
    blocked_by: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    verification_commands: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CurrentState:
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OpenLoop:
        return cls(**data)


@dataclass
class Result:
    action_id: str
    status: str
    summary: str
    evidence: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    follow_up: List[str] = field(default_factory=list)
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CurrentState:
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Result:
        return cls(**data)


@dataclass
class CurrentState:
    goal: str
    active_context: List[str] = field(default_factory=list)
    recent_events: List[str] = field(default_factory=list)
    current_actions: List[str] = field(default_factory=list)
    open_loops: List[str] = field(default_factory=list)
    last_verified_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CurrentState:
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CurrentState:
        return cls(**data)
