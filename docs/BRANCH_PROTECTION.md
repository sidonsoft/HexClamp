# Branch Protection Setup

## Main Branch Rules

Go to **Settings → Branches → Branch protection rules → Add rule**:

### Required Rules for `main`

```
Pattern: main

☑ Require a pull request before merging
  - Require at least 1 approval (recommended: 2 for production)
  - Dismiss stale approvals when new commits are pushed
  - Require review from Code Owners
  
☑ Require status checks to pass before merging
  - Required checks:
    - `lint-and-test` (CI workflow)
    
☑ Require branches to be up to date before merging

☑ Do not allow bypassing the above rules
```

## For Production Releases

Consider adding:
```
☑ Require signed commits
☑ Require linear history
☑ Include administrators in protection rules
```

## CODEOWNERS File

Create `.github/CODEOWNERS` to auto-request reviews:

```
# Code ownership rules
*       @your-github-username

# Specific directories can have different owners
/agents/ @your-github-username
/scripts/ @your-github-username
```

## Required GitHub Secrets

Set these in **Settings → Secrets and variables → Actions**:

| Secret | Description | Required For |
|--------|-------------|--------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for messaging executor | CI tests, local dev |
| `CODECOV_TOKEN` | Codecov upload token | CI coverage uploads |

### Getting the Codecov Token

1. Go to [codecov.io](https://codecov.io) and sign in with GitHub
2. Navigate to your repository settings
3. Copy the "Upload Token"
4. Add as `CODECOV_TOKEN` secret in GitHub

### Getting the Telegram Bot Token

1. Talk to [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot or use existing one
3. Copy the bot token
4. Add as `TELEGRAM_BOT_TOKEN` secret in GitHub (and locally as environment variable)

## Local Development Setup

For local runs, set environment variables:

```bash
# Copy example env file
cp .env.example .env

# Edit with your values
export TELEGRAM_BOT_TOKEN="your-token-here"
```
