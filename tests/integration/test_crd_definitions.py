"""Integration tests for CRD definition consistency."""

import pytest

from rhoai_mcp.plugin_manager import PluginManager

# CRD kinds that must be present
KNOWN_CRD_KINDS = {"Notebook", "InferenceService", "DataSciencePipelinesApplication"}


@pytest.fixture(scope="module")
def loaded_pm() -> PluginManager:
    """Module-scoped PluginManager with all plugins loaded."""
    pm = PluginManager()
    pm.load_core_plugins()
    return pm


def test_plugins_with_crds_provide_definitions(loaded_pm: PluginManager) -> None:
    """Plugins that declare requires_crds must also provide CRD definitions."""
    metadata_list = loaded_pm.get_all_metadata()
    all_crds = loaded_pm.get_all_crd_definitions()
    provided_kinds = {crd.kind for crd in all_crds}

    for meta in metadata_list:
        if not meta.requires_crds:
            continue
        for crd_kind in meta.requires_crds:
            assert crd_kind in provided_kinds, (
                f"Plugin {meta.name} requires CRD '{crd_kind}' but no definition was provided"
            )


def test_crd_definitions_have_required_fields(loaded_pm: PluginManager) -> None:
    """Every CRDDefinition must have non-empty group, version, plural, and kind."""
    all_crds = loaded_pm.get_all_crd_definitions()
    assert all_crds, "Expected at least one CRD definition"

    for crd in all_crds:
        assert crd.group and isinstance(crd.group, str), (
            f"CRD {crd.kind}: group must be a non-empty string"
        )
        assert crd.version and isinstance(crd.version, str), (
            f"CRD {crd.kind}: version must be a non-empty string"
        )
        assert crd.plural and isinstance(crd.plural, str), (
            f"CRD {crd.kind}: plural must be a non-empty string"
        )
        assert crd.kind and isinstance(crd.kind, str), "CRD: kind must be a non-empty string"


def test_no_duplicate_crd_definitions(loaded_pm: PluginManager) -> None:
    """No two CRD definitions may share the same (group, kind) pair."""
    all_crds = loaded_pm.get_all_crd_definitions()
    seen: set[tuple[str, str, str]] = set()
    duplicates: list[tuple[str, str, str]] = []

    for crd in all_crds:
        key = (crd.group, crd.kind, crd.version)
        if key in seen:
            duplicates.append(key)
        seen.add(key)

    assert not duplicates, f"Duplicate CRD (group, kind, version) triples: {duplicates}"


def test_known_crds_present(loaded_pm: PluginManager) -> None:
    """Verify that well-known RHOAI CRDs are provided by the plugin system."""
    all_crds = loaded_pm.get_all_crd_definitions()
    provided_kinds = {crd.kind for crd in all_crds}

    missing = KNOWN_CRD_KINDS - provided_kinds
    assert not missing, f"Expected CRD kinds not found: {missing}"
