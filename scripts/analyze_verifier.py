#!/usr/bin/env python3
"""
Analyze verifier mistakes and suggest prompt improvements.

This script analyzes the verifier learning state to identify patterns
in verification failures and suggests improvements to verifier prompts.

Usage:
    PYTHONPATH=/Users/burnz/Code/HexClamp python scripts/analyze_verifier.py [--json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from agents.store import STATE_DIR
from agents.verifier import _load_learning_state, VERIFIER_LEARNING_THRESHOLD


def analyze_learning_state() -> dict:
    """Load and analyze verifier learning state."""
    state = _load_learning_state()
    
    analysis = {
        "total_checks": state.get("total_checks", 0),
        "false_positives": state.get("false_positives", 0),
        "accuracy_rate": 0.0,
        "action_types": {},
        "repeated_misses": [],
        "suggestions": [],
    }
    
    # Calculate accuracy rate
    if analysis["total_checks"] > 0:
        analysis["accuracy_rate"] = (
            (analysis["total_checks"] - analysis["false_positives"])
            / analysis["total_checks"]
            * 100.0
        )
    
    # Analyze by action type
    types = state.get("types", {})
    for action_type, type_state in types.items():
        checks = type_state.get("checks", 0)
        failures = type_state.get("failures", 0)
        misses = type_state.get("misses", {})
        
        analysis["action_types"][action_type] = {
            "checks": checks,
            "failures": failures,
            "failure_rate": (failures / checks * 100.0) if checks > 0 else 0.0,
            "miss_count": len(misses),
        }
        
        # Find repeated misses (above threshold)
        for miss_key, count in misses.items():
            if count >= VERIFIER_LEARNING_THRESHOLD:
                analysis["repeated_misses"].append({
                    "action_type": action_type,
                    "miss": miss_key,
                    "count": count,
                })
    
    # Generate suggestions
    if analysis["false_positives"] > 0:
        analysis["suggestions"].append(
            "Consider adding stricter evidence requirements to reduce false positives"
        )
    
    for repeated in analysis["repeated_misses"]:
        analysis["suggestions"].append(
            f"Add checklist item for '{repeated['miss']}' in {repeated['action_type']} actions "
            f"(missed {repeated['count']} times)"
        )
    
    return analysis


def print_analysis(analysis: dict) -> None:
    """Print human-readable analysis."""
    print("\n" + "=" * 60)
    print("  HEXCLAMP VERIFIER LEARNING ANALYSIS")
    print("=" * 60 + "\n")
    
    print(f"Total verification checks: {analysis['total_checks']}")
    print(f"False positives: {analysis['false_positives']}")
    print(f"Accuracy rate: {analysis['accuracy_rate']:.1f}%")
    print()
    
    print("By Action Type:")
    print("-" * 60)
    for action_type, stats in analysis["action_types"].items():
        print(f"  {action_type}:")
        print(f"    Checks: {stats['checks']}, Failures: {stats['failures']}")
        print(f"    Failure rate: {stats['failure_rate']:.1f}%")
        print(f"    Unique misses: {stats['miss_count']}")
    print()
    
    if analysis["repeated_misses"]:
        print(f"Repeated Misses (≥{VERIFIER_LEARNING_THRESHOLD} times):")
        print("-" * 60)
        for miss in analysis["repeated_misses"]:
            print(f"  • [{miss['action_type']}] '{miss['miss']}' ({miss['count']}x)")
        print()
    
    if analysis["suggestions"]:
        print("Suggestions for Prompt Improvement:")
        print("-" * 60)
        for i, suggestion in enumerate(analysis["suggestions"], 1):
            print(f"  {i}. {suggestion}")
        print()
    
    print("=" * 60)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Analyze verifier mistakes and suggest improvements")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    analysis = analyze_learning_state()
    
    if args.json:
        print(json.dumps(analysis, indent=2))
    else:
        print_analysis(analysis)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
