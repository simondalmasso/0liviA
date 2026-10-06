---
name: wolfram-setup
description: >
  Install and activate the Wolfram Engine, and set up the Wolfram MCP server (local or remote).
  Use when: installing Wolfram Engine, activating a Wolfram Engine license, setting up wolframscript,
  configuring the Wolfram MCP server for any AI assistant or coding client,
  or connecting to the free remote Wolfram MCP service.
argument-hint: 'Optional: specify OS (macOS, Windows, Linux) and/or MCP client name'
---

# Wolfram Setup

This skill gets a user set up with Wolfram tools. The goal is a working Wolfram MCP server connected to their AI assistant or client environment. It works across any combination of LLM and client — chat interfaces, coding agents, terminal-integrated assistants, etc.

## Step 1: Determine what kind of assistance is possible

First, establish whether you can execute shell commands in this session.

**If you can execute shell commands on the user's system** (coding agent, terminal-integrated assistant):  
Run the smoke test and proceed interactively — go to Step 2A.

**If you cannot execute shell commands on the user's system** (chat interface, read/write-only environment):  
All steps will be instructional. Ask the user to run commands and report results back to you — go to Step 2B.

## Step 2A: Assess the user's installation (shell-capable)

Run the following:

```bash
wolframscript -code 'Print[$InstallationDirectory]; Print[$Version];'
```

Three possible outcomes:

- **Succeeds** → they have a local kernel. Go to Step 3.
- **Fails, but a Wolfram app is present** → `wolframscript` may not be on PATH. Check before concluding nothing is installed:
  - macOS: `/Applications/Wolfram*.app`, `/Applications/Mathematica.app`
  - Windows: `C:\Program Files\Wolfram Research\`
  - Linux: `/usr/local/Wolfram/`

  If a Wolfram app is found, guide the user to fix PATH or run `wolframscript -configure` — do not install a redundant Engine. See `references/get-wolfram-engine.md` § Advanced configuration.
- **Fails, no Wolfram app found** → they have nothing. Go to Step 3 to choose a path.

## Step 2B: Assess the user's installation (instructional mode)

Ask the user: "Do you have Mathematica, the Wolfram app, or the Wolfram Engine installed on your system?"

- **Yes** → they have a local kernel. Go to Step 3.
- **No** → Go to Step 3 to choose a path.

## Step 3: Get a Wolfram kernel (only if needed)

If the user already has a kernel, skip to Step 4. Otherwise, explain both options and let them choose:

**Option A — Remote MCP service (quick, no install)**  
No software to install. The free remote service at `agenttools.wolfram.com/mcp` gives immediate access to Wolfram tools. The evaluator is stateless with fixed resource limits, but it's a great starting point. Skip to Step 4 and use Option 2 in `references/setup-mcp-server.md`.

**Option B — Wolfram Engine (local, more powerful)**  
A full local kernel with stateful evaluation and no resource limits — better for computation-heavy work. Requires a free Wolfram ID and license. See `references/get-wolfram-engine.md` for platform-specific steps, including automated install commands (winget on Windows, brew on macOS). Key points:
- The user must [create a Wolfram ID](https://account.wolfram.com/login/create) and [obtain a free license](https://account.wolfram.com/access/wolfram-engine/free) themselves
- Offer to run the platform installer automatically; always ask permission first
- Activate with `wolframscript -activate` (run interactively if possible; otherwise relay to the user)
- Each Wolfram ID supports 2 free activation keys; contact [support@wolfram.com](mailto:support@wolfram.com) to reset if needed
- **Required verification:** after activation, run `wolframscript -code '1+1'` and confirm it prints `2` before proceeding to Step 4. On Windows in IDE environments, restart the editor first if `wolframscript` is not found.

## Step 4: Set up the Wolfram MCP server

Read `references/setup-mcp-server.md` for full instructions. Summary:

- **Has local kernel** → Option 1 (local server via `InstallMCPServer`). Ask which client they're using; the paclet picks the right tool bundle automatically, but an explicit server name can be passed if the user has a preference.
- **No local kernel** → Option 2 (remote service at `agenttools.wolfram.com/mcp`). Add the URL to their client's MCP config — no API key needed.

In instructional mode, provide the exact commands and config snippets for the user to run themselves.

After setup, ask the user to restart or reload their client.

## Step 5: Verify

Confirm the MCP server is working by asking the client to evaluate a simple Wolfram Language expression:

```
What is Expand[(x+1)^5] in Wolfram Language?
```

If the MCP tools respond correctly, setup is complete.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `wolframscript` not found after install (Windows/IDE) | The new PATH entry isn't visible until the editor is restarted — restart VSCode/JetBrains and try again before further troubleshooting |
| `wolframscript` still not found after restart | Check PATH; run `wolframscript -kernelpath /path/to/WolframKernel` — see [support article](https://support.wolfram.com/47243) |
| "No valid keys" on activation | Each Wolfram ID has 2 keys — [contact Wolfram](mailto:support@wolfram.com) to reset |
| Activation fails behind a proxy | Set `https_proxy` environment variable before running `wolframscript` |
| macOS Gatekeeper blocks the app | Right-click the `.app` → Open, then confirm in the security dialog |
| MCP server not appearing in client | Restart the client; check MCP config JSON for syntax errors |
| MCP server installed but not appearing in client | `InstallMCPServer` may have written to a different config path than the one the client reads. See `references/setup-mcp-server.md` § Config path troubleshooting. |

For `wolframscript -configure` usage and advanced configuration keys, see `references/get-wolfram-engine.md` § Advanced configuration.

## Technical Support

Contact Wolfram at [support@wolfram.com](mailto:support@wolfram.com).
