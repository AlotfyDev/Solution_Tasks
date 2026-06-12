# MCP Server Configuration for IDEs

## Overview

The Task Toolkit MCP server supports two transport modes:

| Mode | Command | Use Case |
|------|---------|----------|
| **stdio** (default) | `task-mcp` | IDE spawns as subprocess |
| **SSE** | `task-mcp --sse` | Network daemon, multiple clients |

## Cline

### stdio (recommended)

Add to `cline_mcp_settings.json` (`~/AppData/Roaming/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
or per-project `.vscode/cline_mcp_settings.json`):

```json
{
  "mcpServers": {
    "task-toolkit": {
      "command": "task-mcp",
      "args": [],
      "env": {},
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### SSE

```json
{
  "mcpServers": {
    "task-toolkit": {
      "url": "http://127.0.0.1:8000/sse",
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

Start the server first:
```bash
task-mcp --sse
# Output: [task-mcp] Starting MCP server on 127.0.0.1:8000 (SSE)
# Output: [task-mcp] Connect URL: http://127.0.0.1:8000/sse
```

## Kilocode

### stdio

Kilocode reads MCP server config from `mcp_servers` in its settings:

```json
{
  "mcp_servers": {
    "task-toolkit": {
      "command": "task-mcp",
      "args": []
    }
  }
}
```

### SSE

```json
{
  "mcp_servers": {
    "task-toolkit": {
      "url": "http://127.0.0.1:8000/sse"
    }
  }
}
```

## VS Code (GitHub Copilot / Continue.dev)

### stdio

```json
{
  "mcpServers": {
    "task-toolkit": {
      "command": "task-mcp",
      "args": []
    }
  }
}
```

## Available Tools

Once connected, the IDE exposes these MCP tools:

| Tool | Purpose |
|------|---------|
| `list_tasks` | List tasks by schema, status, phase |
| `get_task` | Full task with sub-entities |
| `insert_task` | Add task from JSON |
| `update_status` | Change task state |
| `delete_task` | Remove task |
| `link_tasks` | Create relationships |
| `status_report` | Full progress report |
| `gap_analysis` | Find coverage gaps |
| `dependency_chain` | Trace dependencies |
| `search_tasks` | Search by text |
| `validate_task` | Check JSON validity |
| `get_history` | View change log |

## Port Discovery

Without `--port`, the server scans `8000-9000` for a free port:

```bash
task-mcp --sse                      # auto: scan 8000-9000
task-mcp --sse --port 8080          # explicit port
task-mcp --sse --port-range 9000-9999  # custom scan range
```

The port is printed to stderr on startup.
