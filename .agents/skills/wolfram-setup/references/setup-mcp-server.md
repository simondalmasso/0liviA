# Setting Up the Wolfram MCP Server

This guide explains how to connect your agent to a Wolfram MCP server.

There are two options:

1. **Local server** — Best performance; requires a local Wolfram Engine installation.
2. **Remote Wolfram MCP Service** — Free; no local installation needed; stateless evaluator with fixed resource limits.

---

## Option 1: Local Server (via DeployAgentTools)

If `wolframscript` is available on your system, you can install and configure the Wolfram MCP server locally.

### Step 1: Install the server for your client

Run this command — it installs the AgentTools paclet if needed and configures the MCP server in one step:

```
wolframscript -code 'PacletSymbol["Wolfram/AgentTools","DeployAgentTools"]["<ClientName>"]'
```

Replace `<ClientName>` with the name of the client being configured (e.g. `"ClaudeCode"`, `"ClaudeDesktop"`).

To see the full list of supported client names first:

```
wolframscript -code 'PacletSymbol["Wolfram/AgentTools","$SupportedMCPClients"] // Keys'
```

The paclet automatically selects the most appropriate tool bundle for each client (e.g. `"WolframLanguage"` for Claude Code, `"Wolfram"` for Claude Desktop). You can override this by passing an explicit server name as the second argument:

```wl
Wolfram`AgentTools`InstallMCPServer["<ClientName>", "<ServerName>"]
```

Available server names:

| Server Name | Primary Use Case |
| --- | --- |
| `Wolfram` | General-purpose: Wolfram\|Alpha results and Wolfram Language evaluation |
| `WolframAlpha` | Natural language queries via Wolfram\|Alpha |
| `WolframLanguage` | Wolfram Language development |

Here are the tools provided by these servers:

| Tool | Description | Wolfram | WolframAlpha | WolframLanguage |
| --- | --- | :---: | :---: | :---: |
| `WolframAlphaContext` | Semantic search for Wolfram\|Alpha results | | X | |
| `WolframLanguageContext` | Semantic search across Wolfram Language resources | | | X |
| `WolframContext` | Combines `WolframAlphaContext` and `WolframLanguageContext` | X | | |
| `WolframLanguageEvaluator` | Evaluates Wolfram Language code | X | | X |
| `WolframAlpha` | Submit queries to Wolfram\|Alpha | X | X | |
| `ReadNotebook` | Reads Wolfram notebooks (.nb) as markdown text | | | X |
| `WriteNotebook` | Create Wolfram notebooks (.nb) from markdown text | | | X |
| `SymbolDefinition` | Retrieves Wolfram Language symbol definitions | | | X |
| `CodeInspector` | Inspects Wolfram Language code and returns a formatted report of issues | | | X |
| `TestReport` | Runs Wolfram Language test files (.wlt) and returns a report | | | X |

For project-level installation (supported by some clients):

```wl
InstallMCPServer[{"ClaudeCode", "/path/to/project"}]
```

### Step 3: Restart your client

After installation, ask the user to restart or reload the MCP client to pick up the new server configuration.

---

## Option 2: Remote Wolfram MCP Service (Free)

The Wolfram MCP Service is a free hosted option that requires no local Wolfram Engine installation and no sign-in.

The remote service provides these tools:

| Tool | Description |
| --- | --- |
| `WolframContext` | Combines `WolframAlphaContext` and `WolframLanguageContext` |
| `WolframLanguageEvaluator` | Evaluates Wolfram Language code |
| `WolframAlpha` | Submit queries to Wolfram\|Alpha |

Note the following differences compared to the local `WolframLanguageEvaluator`:

- **Stateless** — definitions do not persist between calls
- **Fixed resource limits** — memory and time are constrained

For coding agents or anything requiring heavy computation or stateful evaluation, the local server is strongly recommended.

### Step 1: Add Wolfram from the app's connector directory (try this first)

The Wolfram MCP server is now listed in the connector/app directories of the major
agent apps, so the simplest setup needs no manual configuration. If the user's app has
a built-in connector or app store, recommend this route first: have them open that
directory, search for **Wolfram**, and add/enable it. No sign-in is required, and the
app handles the connection — including the transport — automatically.

Fall back to the manual configuration in Step 2 only if the user's app has no connector
directory, or the listed connector will not connect.

### Step 2: Configure your client manually (fallback)

The remote server URL is:

```
https://agenttools.wolfram.com/mcp
```

The transport type is **streamable HTTP**.

#### For clients that support remote MCP servers natively

Add this to your MCP configuration:

```json
{
  "wolfram": {
    "type": "http",
    "url": "https://agenttools.wolfram.com/mcp"
  }
}
```
This is a remote HTTP server, so the configuration must declare `"type": "http"` — clients that default to a local stdio transport will fail to connect if it is omitted.

#### For clients that require a stdio wrapper

Use `mcp-remote` as a bridge:

```json
{
  "wolfram": {
    "command": "npx",
    "args": [
      "-y", "mcp-remote@latest",
      "https://agenttools.wolfram.com/mcp"
    ]
  }
}
```

### Step 3: Restart your client

If needed in your active client, ask the user to restart or reload the MCP client to connect to the remote server.

---

## Config path troubleshooting

If `InstallMCPServer` succeeds but the MCP server doesn't appear after restarting the client, the paclet may have written to a different config path than the one the client reads.

### Step 1: Check what path was written

Ask the user to paste the full output of the `InstallMCPServer` call. The output shows the path of the config file that was modified.

### Step 2: Find where the client actually reads its config

Ask the user to search their filesystem for all instances of the client's config file. For example, for Claude Desktop:

**macOS / Linux:**
```bash
find ~ -name "claude_desktop_config.json" 2>/dev/null
```

**Windows (PowerShell):**
```powershell
Get-ChildItem -Path $env:USERPROFILE -Recurse -Filter "claude_desktop_config.json" -ErrorAction SilentlyContinue
```

Use an equivalent search for other clients (substituting the appropriate config filename).

### Step 3: Reconcile the paths

Compare the path from Step 1 with the paths found in Step 2.

- **If they match** — the config is correct; the issue is likely a client restart or JSON syntax error.
- **If they differ** — re-run `InstallMCPServer` pointing directly at the correct config file:

```wl
Wolfram`AgentTools`InstallMCPServer[File["/path/to/correct/config.json"]]
```

Substitute the actual path the client uses (found in Step 2). Then restart the client.

---

## More Information

- Wolfram MCP Service: <https://agenttools.wolfram.com/mcp>
- AgentTools paclet: <https://resources.wolframcloud.com/PacletRepository/resources/Wolfram/AgentTools/>
- Connecting to Wolfram Cloud MCP: <https://www.wolfram.com/artificial-intelligence/mcp/cloud/wolfram-mcp-cloud/>
