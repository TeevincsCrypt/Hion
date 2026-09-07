"""Filesystem and structured-data tools, sandboxed to one mission.

These are real side effects on real files. Nothing here simulates work.
"""

from __future__ import annotations

import json
from typing import Any

from strands import tool
from strands.tools.decorator import DecoratedFunctionTool

from hion.tools.context import ExecutionContext

_MAX_READ_CHARS = 40_000


def build_workspace_tools(ctx: ExecutionContext) -> list[DecoratedFunctionTool]:
    """Create the workspace toolset bound to ``ctx``'s mission sandbox."""

    @tool
    def write_file(path: str, content: str) -> dict[str, Any]:
        """Create a new file in the mission workspace.

        Fails if the file already exists - use update_file to change an existing
        artifact, which is treated as a higher-risk action.

        Args:
            path: Relative path inside the mission workspace, e.g. "brief.md".
            content: Full text content of the file.
        """
        target = ctx.resolve(path)
        if target.exists():
            return {
                "status": "error",
                "error": f"{path} already exists. Use update_file to modify it.",
            }
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"status": "ok", "path": path, "bytes": target.stat().st_size}

    @tool
    def update_file(path: str, content: str) -> dict[str, Any]:
        """Replace the contents of an existing file in the mission workspace.

        Args:
            path: Relative path of an existing file inside the mission workspace.
            content: New full text content, replacing what was there.
        """
        target = ctx.resolve(path)
        if not target.exists():
            return {"status": "error", "error": f"{path} does not exist. Use write_file to create it."}
        previous_size = target.stat().st_size
        target.write_text(content, encoding="utf-8")
        return {
            "status": "ok",
            "path": path,
            "previous_bytes": previous_size,
            "bytes": target.stat().st_size,
        }

    @tool
    def read_file(path: str) -> dict[str, Any]:
        """Read a file from the mission workspace.

        Args:
            path: Relative path inside the mission workspace.
        """
        target = ctx.resolve(path)
        if not target.is_file():
            return {"status": "error", "error": f"{path} does not exist."}
        text = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > _MAX_READ_CHARS
        return {
            "status": "ok",
            "path": path,
            "content": text[:_MAX_READ_CHARS],
            "truncated": truncated,
        }

    @tool
    def list_files() -> dict[str, Any]:
        """List every file currently in the mission workspace."""
        root = ctx.workspace
        files = [
            {"path": str(p.relative_to(root)), "bytes": p.stat().st_size}
            for p in sorted(root.rglob("*"))
            if p.is_file()
        ]
        return {"status": "ok", "count": len(files), "files": files}

    @tool
    def save_dataset(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Save structured records as a JSON dataset in the mission workspace.

        Use this for comparison tables, competitor profiles, scored options - any
        data another agent will need to read back field by field.

        Args:
            name: Dataset name without extension, e.g. "competitors".
            rows: List of records. Keys should be consistent across rows.
        """
        target = ctx.resolve(f"data/{name}.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        columns = sorted({key for row in rows for key in row})
        return {"status": "ok", "name": name, "rows": len(rows), "columns": columns}

    @tool
    def load_dataset(name: str) -> dict[str, Any]:
        """Load a JSON dataset previously saved with save_dataset.

        Args:
            name: Dataset name without extension.
        """
        target = ctx.resolve(f"data/{name}.json")
        if not target.is_file():
            return {"status": "error", "error": f"Dataset {name!r} does not exist."}
        rows = json.loads(target.read_text(encoding="utf-8"))
        return {"status": "ok", "name": name, "rows": rows}

    return [write_file, update_file, read_file, list_files, save_dataset, load_dataset]
