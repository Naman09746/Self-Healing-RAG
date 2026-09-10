from backend.experiments.config_registry import ConfigRegistry


def test_config_registry_defaults():
    registry = ConfigRegistry()
    defaults = registry.get_defaults()
    assert defaults["top_k"] == 5
    assert defaults["hybrid_search_alpha"] == 0.5
    assert defaults["rerank_threshold"] == 0.0
    assert defaults["chunk_variant"] == "c700_o100"


def test_validate_and_clamp_bounds():
    registry = ConfigRegistry()

    # Out-of-bounds parameters
    proposed = {
        "top_k": 50,  # Max is 20
        "hybrid_search_alpha": 1.8,  # Max is 1.0
        "routing_confidence_threshold": 0.1,  # Min is 0.3
        "chunk_variant": "invalid_variant",
    }
    clamped = registry.validate_and_clamp(proposed)

    assert clamped["top_k"] == 20
    assert clamped["hybrid_search_alpha"] == 1.0
    assert clamped["routing_confidence_threshold"] == 0.3
    assert clamped["chunk_variant"] == "c700_o100"  # Falls back to default


def test_resolve_settings_overrides():
    registry = ConfigRegistry()
    params = {"chunk_variant": "c500_o50", "top_k": 7}
    overrides = registry.resolve_settings_overrides(params)

    assert overrides["VECTOR_COLLECTION_NAME"] == "rag_collection_c500_o50"
    assert overrides["top_k"] == 7
    assert "chunk_variant" not in overrides
