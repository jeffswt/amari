from azure.ai.ml.entities import SparkComponent

from . import _FunctionalComponent


def extract_component_spec(cm: _FunctionalComponent) -> dict:
    """Generate AML-style component specifications."""

    return {
        "name": cm.name,
        "version": cm.version,
        "display_name": cm.display_name,
        "type": "spark",
        "description": cm.docs,
        "is_deterministic": cm.is_deterministic,
        "tags": {
            "category": "GenericComponents",
            "contact": cm.tag_contact,
        },
    }
