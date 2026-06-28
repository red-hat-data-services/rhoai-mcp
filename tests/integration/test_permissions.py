"""Integration tests for tool permission consistency."""

import re
from unittest.mock import MagicMock

import pytest

from rhoai_mcp.plugin_manager import PluginManager
from rhoai_mcp.server import RHOAIServer

VALID_VERBS = {"get", "list", "watch", "create", "update", "patch", "delete"}

SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@pytest.fixture(scope="module")
def permissions() -> dict[str, list[dict[str, str]]]:
    """Module-scoped fixture returning the merged permission map."""
    pm = PluginManager()
    pm.load_core_plugins()
    return pm.collect_tool_permissions()


@pytest.fixture(scope="module")
def registered_tool_names() -> set[str]:
    """Module-scoped fixture returning all registered tool function names."""
    pm = PluginManager()
    pm.load_core_plugins()

    mcp = MagicMock()
    names: set[str] = set()

    def capture_tool(*_args: object, **kwargs: object) -> object:
        tool_name = kwargs.get("name")

        def decorator(func: object) -> object:
            assert callable(func)
            names.add(str(tool_name) if tool_name else func.__name__)
            return func

        return decorator

    mcp.tool = capture_tool

    server = RHOAIServer()
    pm.register_all_tools(mcp, server)
    return names


def test_all_permissions_have_required_fields(
    permissions: dict[str, list[dict[str, str]]],
) -> None:
    """Every permission entry must contain apiGroup, resource, and verb as strings."""
    required_keys = {"apiGroup", "resource", "verb"}

    for tool_name, perm_list in permissions.items():
        for i, perm in enumerate(perm_list):
            for key in required_keys:
                assert key in perm, f"Tool '{tool_name}' permission[{i}] missing key '{key}'"
                assert isinstance(perm[key], str), (
                    f"Tool '{tool_name}' permission[{i}]['{key}'] "
                    f"must be a string, got {type(perm[key])}"
                )


def test_permission_verbs_are_valid(
    permissions: dict[str, list[dict[str, str]]],
) -> None:
    """All permission verbs must be standard Kubernetes RBAC verbs."""
    invalid: list[tuple[str, str]] = []

    for tool_name, perm_list in permissions.items():
        for perm in perm_list:
            verb = perm.get("verb", "")
            if verb not in VALID_VERBS:
                invalid.append((tool_name, verb))

    assert not invalid, f"Invalid permission verbs found: {[(t, v) for t, v in invalid]}"


def test_governed_tools_exist_as_registered_tools(
    permissions: dict[str, list[dict[str, str]]],
    registered_tool_names: set[str],
) -> None:
    """Every tool name in the permissions map must correspond to a registered tool."""
    governed_names = set(permissions.keys())
    unregistered = governed_names - registered_tool_names

    assert not unregistered, (
        f"Permission entries reference tools that are not registered: {unregistered}"
    )


def test_minimum_permission_count(
    permissions: dict[str, list[dict[str, str]]],
) -> None:
    """Sanity check: at least 30 total permission entries across all tools."""
    total = sum(len(perm_list) for perm_list in permissions.values())
    assert total >= 30, f"Expected at least 30 permission entries, got {total}"
