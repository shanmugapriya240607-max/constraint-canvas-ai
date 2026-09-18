"""Small provider-only schema; the existing planning models remain authoritative."""
import json

from app.schemas.ai_parser import PlanningDraft


def extraction_json_schema():
    def obj(properties):
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}

    def array(item):
        return {"type": "array", "items": item}

    string = {"type": "string"}
    optional_string = {"type": ["string", "null"]}
    optional_number = {"type": ["number", "null"]}
    optional_integer = {"type": ["integer", "null"]}
    issue = obj({"field": string, "reason": string})
    return obj({
        "plan": obj({name: optional_string for name in (
            "name", "description", "planning_start", "planning_end")}),
        "resources": array(obj({
            "client_id": string, "name": optional_string, "resource_type": optional_string,
            "capacity": optional_integer,
            "availability": array(obj({"available_from": string, "available_until": string})),
        })),
        "tasks": array(obj({
            "client_id": string, "name": optional_string, "duration_value": optional_number,
            "duration_unit": {"type": ["string", "null"], "enum": ["seconds", "minutes", "hours", None]},
            "priority": {"type": ["string", "null"], "enum": ["low", "medium", "high", "critical", None]},
            "earliest_start": optional_string, "deadline": optional_string, "deadline_text": optional_string,
        })),
        "requirements": array(obj({
            "task_id": string, "resource_type": optional_string, "quantity": optional_integer,
            "required_resource_id": optional_string,
        })),
        "dependencies": array(obj({"before_task_id": string, "after_task_id": string})),
        "constraints": array(obj({
            "semantic": string, "operator": string, "hardness": {"type": "string", "enum": ["hard", "soft"]},
            "weight": optional_number,
            "parameters_json": {"type": "string", "description": "A JSON object encoded as a string, with only explicitly stated constraint parameters. Use client IDs for references."},
        })),
        "missing_information": array(issue), "ambiguities": array(issue),
        "evidence": array(obj({"field": string, "quote": string})),
    })


def to_planning_json(raw):
    """Decode transport-only parameter strings, then enforce full Pydantic rules."""
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 256_000:
        raise ValueError("Oversized extraction")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Non-finite JSON value")

    def decode(value):
        return json.loads(value, object_pairs_hook=unique_object, parse_constant=reject_constant)

    data = decode(raw)
    if not isinstance(data, dict):
        raise ValueError("Extraction must be an object")
    constraints = data.get("constraints", [])
    if not isinstance(constraints, list):
        raise ValueError("Constraints must be an array")
    for constraint in constraints:
        if not isinstance(constraint, dict):
            raise ValueError("Constraint must be an object")
        if "parameters_json" in constraint:
            if "parameters" in constraint or not isinstance(constraint["parameters_json"], str):
                raise ValueError("Ambiguous or invalid constraint parameters")
            parameters = decode(constraint.pop("parameters_json"))
            if not isinstance(parameters, dict):
                raise ValueError("Constraint parameters must be an object")
            constraint["parameters"] = parameters
    # No eval, execution, database access or solver calls. Unknown fields and invalid
    # domain values are rejected by the same models used for preview/confirmation.
    return PlanningDraft.model_validate(data).model_dump_json()
