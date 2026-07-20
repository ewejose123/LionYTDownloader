#!/usr/bin/env python3
"""Gate agent tools until required Cognition Stack bootstrap blocks are opened."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ALLOWED_MCP_TOOLS = frozenset(
    {
        "open_block",
        "search_blocks",
        "list_blocks",
        "get_related_blocks",
        "search_library",
        "open_library_doc",
    }
)

DISCOVERY_ONLY_MESSAGE = """\
Cognition Stack bootstrap is required once at the start of this conversation (not on every follow-up message).

Your FIRST action in this new chat must be parallel open_block calls for every block listed in .cursor/cogstack-bootstrap.json.

Do not use Read, Grep, SemanticSearch, Shell, or other tools until all required blocks are opened. After bootstrap completes, later prompts in this same chat proceed normally without re-opening blocks."""


def workspace_root(payload: dict) -> Path | None:
    roots = payload.get("workspace_roots") or []
    return Path(roots[0]) if roots else None


def is_consumer_project(root: Path) -> bool:
    return (root / ".cogstack-scope").is_file()


def bootstrap_config(root: Path) -> dict | None:
    path = root / ".cursor" / "cogstack-bootstrap.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def state_path(root: Path, conversation_id: str) -> Path:
    return root / ".cursor" / ".cogstack-bootstrap" / f"{conversation_id}.json"


def load_state(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("opened_blocks", []))


def save_state(path: Path, opened: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"opened_blocks": sorted(opened)}, indent=2),
        encoding="utf-8",
    )


def required_blocks(config: dict) -> list[str]:
    blocks = config.get("required_blocks")
    if isinstance(blocks, list) and blocks:
        return blocks
    return ["cogstack-agent-procedure"]


def conversation_id(payload: dict) -> str:
    return (
        payload.get("conversation_id")
        or payload.get("session_id")
        or "unknown"
    )


def bootstrap_complete(root: Path, conv_id: str, config: dict) -> bool:
    if os.environ.get("COGSTACK_BOOTSTRAP_DISABLED") == "1":
        return True
    opened = load_state(state_path(root, conv_id))
    return all(block in opened for block in required_blocks(config))


def extract_mcp_call(tool_input: object) -> tuple[str | None, dict]:
    if not isinstance(tool_input, dict):
        return None, {}
    name = tool_input.get("toolName") or tool_input.get("tool_name")
    args = tool_input.get("arguments") or tool_input.get("tool_input") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    return name, args if isinstance(args, dict) else {}


def mcp_tool_name(payload: dict) -> str | None:
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool_name == "CallMcpTool":
        name, _ = extract_mcp_call(tool_input)
        return name

    if tool_name.startswith("MCP:"):
        return tool_name.split(":", 1)[-1]

    if tool_name in ALLOWED_MCP_TOOLS:
        return tool_name

    return None


def is_allowed_discovery_tool(payload: dict) -> bool:
    mcp_name = mcp_tool_name(payload)
    return mcp_name in ALLOWED_MCP_TOOLS


def emit(payload: dict) -> None:
    print(json.dumps(payload))
    sys.exit(0)


def allow() -> None:
    emit({"permission": "allow"})


def deny(message: str | None = None) -> None:
    emit(
        {
            "permission": "deny",
            "user_message": "Cognition Stack bootstrap required first.",
            "agent_message": message or DISCOVERY_ONLY_MESSAGE,
        }
    )


def handle_pre_tool_use(payload: dict) -> None:
    root = workspace_root(payload)
    if root is None or not is_consumer_project(root):
        allow()

    config = bootstrap_config(root)
    if config is None:
        allow()

    conv_id = conversation_id(payload)
    if bootstrap_complete(root, conv_id, config):
        allow()

    if is_allowed_discovery_tool(payload):
        allow()

    deny()


def parse_open_block_name(payload: dict) -> str | None:
    tool_input = payload.get("tool_input") or {}
    mcp_name = mcp_tool_name(payload)
    if mcp_name != "open_block":
        return None
    _, args = extract_mcp_call(tool_input)
    name = args.get("name")
    return name if isinstance(name, str) else None


def handle_post_tool_use(payload: dict) -> None:
    root = workspace_root(payload)
    if root is None or not is_consumer_project(root):
        emit({})

    config = bootstrap_config(root)
    if config is None:
        emit({})

    block_name = parse_open_block_name(payload)
    if not block_name or block_name not in required_blocks(config):
        emit({})

    tool_output = payload.get("tool_output") or ""
    try:
        out = json.loads(tool_output) if isinstance(tool_output, str) else tool_output
    except json.JSONDecodeError:
        emit({})

    if not isinstance(out, dict) or out.get("name") != block_name:
        emit({})

    conv_id = conversation_id(payload)
    sp = state_path(root, conv_id)
    opened = load_state(sp)
    opened.add(block_name)
    save_state(sp, opened)
    emit({})


def handle_session_end(payload: dict) -> None:
    root = workspace_root(payload)
    if root is None:
        emit({})

    conv_id = payload.get("session_id") or payload.get("conversation_id")
    if conv_id:
        sp = state_path(root, conv_id)
        if sp.is_file():
            sp.unlink()
    emit({})


def main() -> None:
    payload = json.load(sys.stdin)
    event = payload.get("hook_event_name", "")

    if event == "preToolUse":
        handle_pre_tool_use(payload)
    elif event == "postToolUse":
        handle_post_tool_use(payload)
    elif event == "sessionEnd":
        handle_session_end(payload)
    else:
        allow()


if __name__ == "__main__":
    main()
