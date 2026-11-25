# browser-expert

Expert-grade browser automation skill & deterministic toolkit for AI coding agents (Antigravity, QoderCLI, Claude Code, Codex, Cursor).

## Why this exists

Clicking screenshots in an LLM loop is fragile, slow, and expensive. `browser-expert` turns browser automation into a **5-layer production workflow**:

1. **Auth Vault (`scripts/auth_vault.py`)** — Per-site persistent Chrome profile & storage-state registry (`BROWSER_VAULT_DIR`), avoiding repeated logins while keeping credentials outside Git.
2. **Dual-Mode Control** — Accessibility-tree refs via `agent-browser` (fast Rust CDP) as primary channel; on-demand `chrome-devtools-mcp` for deep network/console/performance inspection.
3. **Protocol Distillation (`scripts/har_to_client.py`)** — Record a workflow once into HAR 1.2, filter noise, and generate a standalone deterministic Python API client (`client.py` + `endpoints.json`). Run #2..1000 runs at 50x speed with zero LLM tokens.
4. **Black-Box Forensics** — Stop retrying blind after 2 failures; dump URL, snapshot, console errors, and screenshot.
5. **Write-Action Preflight Gate (`scripts/preflight_guard.py`)** — Classify planned browser actions into `READ`, `WRITE_CONFIRM`, or `BLOCKED` so high-risk mutations always pause for human approval before clicking Submit.

## Quick Start

```bash
# 1. Initialize a persistent site profile in the vault
python scripts/auth_vault.py init my-portal
python scripts/auth_vault.py list

# 2. Distill a recorded HAR into a deterministic API client
python scripts/har_to_client.py sample.har --out-dir ./distilled --domain api.example.com

# 3. Preflight-check an action plan before execution
python scripts/preflight_guard.py --actions plan.json

# 4. Run regression tests
python -m unittest discover -s tests -v
```

## Configuration

Copy `.env.example` to `.env` (never commit `.env`):

- `BROWSER_VAULT_DIR`: Directory storing persistent browser profiles & session states (defaults to `~/.browser-expert-vault`).

## License

MIT
