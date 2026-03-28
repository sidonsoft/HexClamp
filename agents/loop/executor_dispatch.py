"""Executor dispatch for HexClamp agent loop.

Routes actions to appropriate executors (code, browser, research, messaging).
"""

from typing import Any, Dict, Optional

from agents.models import Event, OpenLoop, Action


def _execute_event_action(action: Action, event: Event) -> Dict[str, Any]:
    """Execute an action triggered by an event.
    
    Args:
        action: The action to execute
        event: The triggering event
        
    Returns:
        Execution result dict
    """
    from agents.loop.config_loader import executor_enabled
    
    if action.executor == "code":
        if not executor_enabled("code"):
            return {"error": "Code executor disabled"}
        from agents.executors import execute_code_for_event
        return execute_code_for_event(action, event)
    
    if action.executor == "browser":
        if not executor_enabled("browser"):
            return {"error": "Browser executor disabled"}
        from agents.executors import execute_browser_for_event
        return execute_browser_for_event(action, event)
    
    if action.executor == "messaging":
        if not executor_enabled("messaging"):
            return {"error": "Messaging executor disabled"}
        from agents.executors import execute_message_for_event
        return execute_message_for_event(action, event)
    
    # Default to research
    if not executor_enabled("research"):
        return {"error": "Research executor disabled"}
    from agents.executors import execute_research_for_event
    return execute_research_for_event(action, event)


def _execute_loop_action(action: Action, loop: OpenLoop) -> Dict[str, Any]:
    """Execute an action for loop progression.
    
    Args:
        action: The action to execute
        loop: The loop being processed
        
    Returns:
        Execution result dict
    """
    from agents.loop.config_loader import executor_enabled
    
    if action.executor == "code":
        if not executor_enabled("code"):
            return {"error": "Code executor disabled"}
        from agents.executors import execute_code_for_loop
        return execute_code_for_loop(action, loop)
    
    if action.executor == "browser":
        if not executor_enabled("browser"):
            return {"error": "Browser executor disabled"}
        from agents.executors import execute_browser_for_loop
        return execute_browser_for_loop(action, loop)
    
    if action.executor == "messaging":
        if not executor_enabled("messaging"):
            return {"error": "Messaging executor disabled"}
        from agents.executors import execute_message_for_loop
        return execute_message_for_loop(action, loop)
    
    # Default to research
    if not executor_enabled("research"):
        return {"error": "Research executor disabled"}
    from agents.executors import execute_research_for_loop
    return execute_research_for_loop(action, loop)
