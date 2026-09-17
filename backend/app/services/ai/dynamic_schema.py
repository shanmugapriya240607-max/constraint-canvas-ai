"""Bounded runtime schema generation using allowlisted types, never executable input."""
import json
from datetime import time
from typing import Annotated
from pydantic import AwareDatetime, ConfigDict, Field, create_model
from app.schemas.ai_parser import CustomField

TYPES = {"string": str, "integer": int, "float": float, "boolean": bool,
         "datetime": AwareDatetime, "time": time}


def build_dynamic_model(definitions: list[CustomField]):
    if len(definitions) > 30 or len({item.name for item in definitions}) != len(definitions):
        raise ValueError("Custom fields must have unique names and at most 30 definitions")
    fields = {}
    for definition in definitions:
        python_type = TYPES[definition.type]
        options = {}
        if definition.type in ("integer", "float"):
            options = {"ge": definition.minimum, "le": definition.maximum}
            if definition.type == "float":
                options["allow_inf_nan"] = False
        elif definition.type == "string":
            options["max_length"] = 2000
        if not definition.required:
            python_type = python_type | None
        fields[definition.name] = (
            Annotated[python_type, Field(**options)], ... if definition.required else None,
        )
    return create_model(
        "CustomPlanningFields",
        __config__=ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True),
        **fields,
    )


def validate_custom_fields(definitions, values):
    model = build_dynamic_model(definitions)
    # Strict JSON validation accepts ISO datetime/time strings but rejects type coercion.
    return model.model_validate_json(json.dumps(values, allow_nan=False)).model_dump(mode="json")
