"""Tests for MCP config loader server key handling."""

from __future__ import annotations

import pytest

from src.components.shared.tools.mcp.config_loader import _merge_configs, _validate_and_build


def test_validate_and_build_reads_mcp_servers() -> None:
    cfg = _validate_and_build(
        {
            "enabled": True,
            "mcp_servers": {
                "demo": {
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "demo-mcp"],
                }
            },
        }
    )

    assert cfg.enabled is True
    assert "demo" in cfg.servers
    assert cfg.servers["demo"].command == "npx"


def test_validate_and_build_rejects_legacy_servers_key() -> None:
    with pytest.raises(ValueError, match="Legacy key 'servers' is no longer supported"):
        _validate_and_build(
            {
                "enabled": True,
                "servers": {
                    "legacy": {
                        "transport": "stdio",
                        "command": "npx",
                        "args": ["-y", "legacy-mcp"],
                    }
                },
            }
        )


def test_validate_and_build_requires_mcp_servers_mapping() -> None:
    with pytest.raises(ValueError, match="Top-level 'mcp_servers' must be a mapping"):
        _validate_and_build({"enabled": True, "mcp_servers": ["invalid"]})


def test_merge_configs_merges_mcp_servers() -> None:
    merged = _merge_configs(
        [
            {"enabled": True, "mcp_servers": {"a": {"command": "one"}}},
            {"mcp_servers": {"b": {"command": "two"}}},
        ]
    )

    assert merged["enabled"] is True
    assert set(merged["mcp_servers"].keys()) == {"a", "b"}
