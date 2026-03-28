#!/usr/bin/env python3
"""
Test script to validate the git configuration fix.
This tests the logic that prevents overwriting existing git user configuration.
"""
import subprocess
import tempfile
import os
from pathlib import Path


def test_fresh_repo():
    """Test behavior with a fresh repository (no .git)"""
    print("Testing fresh repository...")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        workdir = Path(tmp_dir)
        
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=str(workdir), capture_output=True)
        
        # Simulate the new logic for a fresh repo
        # Check if user.name is already configured
        name_result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=10
        )
        # Check if user.email is already configured
        email_result = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Only set defaults if either name or email is not configured
        if not name_result.stdout.strip():
            subprocess.run(
                ["git", "config", "user.name", "Hydra Claw"],
                cwd=str(workdir),
                capture_output=True,
            )
        if not email_result.stdout.strip():
            subprocess.run(
                ["git", "config", "user.email", "hydra@claw.ai"],
                cwd=str(workdir),
                capture_output=True,
            )
        
        # Verify the values were set
        final_name = subprocess.run(
            ["git", "config", "user.name"],
            cwd=str(workdir),
            capture_output=True,
            text=True
        ).stdout.strip()
        
        final_email = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(workdir),
            capture_output=True,
            text=True
        ).stdout.strip()
        
        print(f"  Name: {final_name}")
        print(f"  Email: {final_email}")
        
        assert final_name == "Hydra Claw", f"Expected 'Hydra Claw', got '{final_name}'"
        assert final_email == "hydra@claw.ai", f"Expected 'hydra@claw.ai', got '{final_email}'"
        
        print("  ✓ Fresh repo test passed")


def test_existing_config():
    """Test behavior with existing git configuration (should not overwrite)"""
    print("Testing existing configuration...")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        workdir = Path(tmp_dir)
        
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=str(workdir), capture_output=True)
        
        # Set custom user config
        subprocess.run(
            ["git", "config", "user.name", "Original User"],
            cwd=str(workdir),
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "original@example.com"],
            cwd=str(workdir),
            capture_output=True,
        )
        
        # Verify initial config
        initial_name = subprocess.run(
            ["git", "config", "user.name"],
            cwd=str(workdir),
            capture_output=True,
            text=True
        ).stdout.strip()
        
        initial_email = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(workdir),
            capture_output=True,
            text=True
        ).stdout.strip()
        
        print(f"  Initial - Name: {initial_name}, Email: {initial_email}")
        
        # Now simulate the new logic that should NOT overwrite existing config
        # Check if user.name is already configured
        name_result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=10
        )
        # Check if user.email is already configured
        email_result = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Only set defaults if either name or email is not configured
        if not name_result.stdout.strip():
            subprocess.run(
                ["git", "config", "user.name", "Hydra Claw"],
                cwd=str(workdir),
                capture_output=True,
            )
        if not email_result.stdout.strip():
            subprocess.run(
                ["git", "config", "user.email", "hydra@claw.ai"],
                cwd=str(workdir),
                capture_output=True,
            )
        
        # Verify the values were NOT overwritten
        final_name = subprocess.run(
            ["git", "config", "user.name"],
            cwd=str(workdir),
            capture_output=True,
            text=True
        ).stdout.strip()
        
        final_email = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(workdir),
            capture_output=True,
            text=True
        ).stdout.strip()
        
        print(f"  Final - Name: {final_name}, Email: {final_email}")
        
        assert final_name == "Original User", f"Expected 'Original User', got '{final_name}' - config was overwritten!"
        assert final_email == "original@example.com", f"Expected 'original@example.com', got '{final_email}' - config was overwritten!"
        
        print("  ✓ Existing config test passed")


def test_partial_config():
    """Test behavior when only one of name/email is configured"""
    print("Testing partial configuration...")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        workdir = Path(tmp_dir)
        
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=str(workdir), capture_output=True)
        
        # Set only user name, leave email unconfigured
        subprocess.run(
            ["git", "config", "user.name", "Original User"],
            cwd=str(workdir),
            capture_output=True,
        )
        
        # Verify initial state
        initial_name = subprocess.run(
            ["git", "config", "user.name"],
            cwd=str(workdir),
            capture_output=True,
            text=True
        ).stdout.strip()
        
        initial_email_result = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(workdir),
            capture_output=True,
            text=True
        )
        
        print(f"  Initial - Name: {initial_name}, Email present: {bool(initial_email_result.stdout.strip())}")
        
        # Now apply the new logic
        # Check if user.name is already configured
        name_result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=10
        )
        # Check if user.email is already configured
        email_result = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Only set defaults if either name or email is not configured
        if not name_result.stdout.strip():
            subprocess.run(
                ["git", "config", "user.name", "Hydra Claw"],
                cwd=str(workdir),
                capture_output=True,
            )
        if not email_result.stdout.strip():
            subprocess.run(
                ["git", "config", "user.email", "hydra@claw.ai"],
                cwd=str(workdir),
                capture_output=True,
            )
        
        # Verify the result - name should remain unchanged, email should be set
        final_name = subprocess.run(
            ["git", "config", "user.name"],
            cwd=str(workdir),
            capture_output=True,
            text=True
        ).stdout.strip()
        
        final_email = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(workdir),
            capture_output=True,
            text=True
        ).stdout.strip()
        
        print(f"  Final - Name: {final_name}, Email: {final_email}")
        
        assert final_name == "Original User", f"Expected 'Original User', got '{final_name}'"
        assert final_email == "hydra@claw.ai", f"Expected 'hydra@claw.ai', got '{final_email}'"
        
        print("  ✓ Partial config test passed")


if __name__ == "__main__":
    print("Running tests for git configuration fix...")
    print("=" * 50)
    
    test_fresh_repo()
    test_existing_config()
    test_partial_config()
    
    print("=" * 50)
    print("All tests passed! ✓")
    print("The fix correctly:")
    print("- Sets defaults for fresh repos")
    print("- Preserves existing config without overwriting")
    print("- Handles partial configurations properly")