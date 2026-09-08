from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from backend.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SEARCH_SPACE_PATH = Path(__file__).parent / "search_space.yaml"


class ConfigRegistry:
    """Manages the parameter search space, constraints, and validation/clamping."""

    def __init__(self, search_space_file: Optional[Path] = None):
        self.path = search_space_file or DEFAULT_SEARCH_SPACE_PATH
        self.schema: Dict[str, Any] = self._load_schema()

    def _load_schema(self) -> Dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(f"Search space configuration file not found at {self.path}")
        with open(self.path, "r") as f:
            data = yaml.safe_load(f)
        return data.get("parameters", {})

    def get_defaults(self) -> Dict[str, Any]:
        """Return default values for all parameters in the search space."""
        return {k: v.get("default") for k, v in self.schema.items()}

    def get_schema_summary(self) -> str:
        """Generate a concise textual representation of the search space for LLM prompts."""
        lines = []
        for name, spec in self.schema.items():
            param_type = spec.get("type", "unknown")
            desc = spec.get("description", "")
            default = spec.get("default")
            if param_type in ("int", "float"):
                min_v = spec.get("min")
                max_v = spec.get("max")
                step = spec.get("step")
                lines.append(f"- {name} ({param_type}, default={default}): range [{min_v}, {max_v}], step={step}. {desc}")
            elif param_type == "categorical":
                opts = spec.get("options", [])
                lines.append(f"- {name} (categorical, default={default}): choices {opts}. {desc}")
        return "\n".join(lines)

    def validate_and_clamp(self, candidate_params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and safely clamp parameters against bounds."""
        clamped: Dict[str, Any] = {}

        for name, value in candidate_params.items():
            if name not in self.schema:
                logger.warning("Ignoring unrecognized parameter in proposal", param=name)
                continue

            spec = self.schema[name]
            param_type = spec.get("type")

            if param_type == "int":
                try:
                    val = int(round(float(value)))
                    min_val = spec.get("min", val)
                    max_val = spec.get("max", val)
                    clamped[name] = max(min_val, min(max_val, val))
                except (ValueError, TypeError):
                    logger.warning("Invalid int value, using default", param=name, value=value)
                    clamped[name] = spec.get("default")

            elif param_type == "float":
                try:
                    val = float(value)
                    min_val = spec.get("min", val)
                    max_val = spec.get("max", val)
                    clamped_val = max(min_val, min(max_val, val))
                    step = spec.get("step", 0.05)
                    # Round to step precision
                    decimals = len(str(step).split(".")[1]) if "." in str(step) else 2
                    clamped[name] = round(clamped_val, decimals)
                except (ValueError, TypeError):
                    logger.warning("Invalid float value, using default", param=name, value=value)
                    clamped[name] = spec.get("default")

            elif param_type == "categorical":
                options = spec.get("options", [])
                if value in options:
                    clamped[name] = value
                else:
                    logger.warning("Invalid categorical choice, using default", param=name, value=value)
                    clamped[name] = spec.get("default")

        # Fill any missing parameters with defaults
        for name, spec in self.schema.items():
            if name not in clamped:
                clamped[name] = spec.get("default")

        return clamped

    def resolve_settings_overrides(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert clamped parameters into Settings field overrides."""
        overrides: Dict[str, Any] = {}

        # Handle collection mapping for chunk variants
        if "chunk_variant" in params:
            variant = params["chunk_variant"]
            mapping = self.schema.get("chunk_variant", {}).get("collection_mapping", {})
            collection_name = mapping.get(variant, "rag_collection")
            overrides["CHROMA_COLLECTION_NAME"] = collection_name

        # Include other parameters that match settings fields or components
        for k, v in params.items():
            if k != "chunk_variant":
                overrides[k] = v

        return overrides
