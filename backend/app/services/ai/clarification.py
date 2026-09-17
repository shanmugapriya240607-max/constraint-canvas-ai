"""Deterministic questions, source evidence checks, and bounded answer application."""
import re
from datetime import datetime
from decimal import Decimal
from fastapi import HTTPException
from app.schemas.ai_parser import (
    ClarificationQuestion, InformationIssue, PlanningDraft,
    PlanDraft, ResourceDraft, TaskDraft,
)

CHOICES = {
    "duration_unit": ["seconds", "minutes", "hours"],
    "priority": ["low", "medium", "high", "critical"],
}


def question_list(issues):
    unique = {issue.field: issue for issue in reversed(issues)}
    questions = []
    for index, field in enumerate(sorted(unique), 1):
        issue = unique[field]
        leaf = field.rsplit(".", 1)[-1]
        suffix = " Include a date and UTC offset." if leaf in (
            "planning_start", "planning_end", "earliest_start", "deadline"
        ) else ""
        questions.append(ClarificationQuestion(
            id=f"q{index}", field=field, reason=issue.reason,
            question=f"Please confirm {field}.{suffix}",
            allowed_answers=CHOICES.get(leaf, []),
        ))
    return questions


def source_issues(draft, text):
    evidence = {entry.field: entry.quote for entry in draft.evidence}
    facts = []
    for key, value in draft.plan.model_dump().items():
        if value is not None:
            facts.append((f"plan.{key}", value))
    for collection in ("resources", "tasks"):
        for index, item in enumerate(getattr(draft, collection)):
            for key, value in item.model_dump().items():
                if key != "client_id" and value is not None and value != []:
                    facts.append((f"{collection}.{index}.{key}", value))
    for collection in ("requirements", "dependencies", "constraints", "custom_fields"):
        facts.extend((f"{collection}.{i}", item) for i, item in enumerate(getattr(draft, collection)))
    facts.extend((f"custom_values.{key}", value) for key, value in draft.custom_values.items())
    result = []
    for path, value in facts:
        quote = evidence.get(path, "")
        valid = bool(quote and quote in text)
        # Critical categorical facts cannot be inferred from an unrelated quotation.
        leaf = path.rsplit(".", 1)[-1]
        if valid and leaf == "duration_unit":
            valid = bool(re.search({"hours": r"\b(hours?|hrs?)\b", "minutes": r"\b(minutes?|mins?)\b",
                                    "seconds": r"\b(seconds?|secs?)\b"}[value], quote, re.I))
        if valid and leaf == "priority":
            valid = value in quote.casefold()
        if valid and leaf in ("duration_value", "capacity"):
            # Conservative: spelled-out/ambiguous quantities require review rather than guessing.
            numbers = {Decimal(number) for number in re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])", quote)}
            valid = Decimal(str(value)) in numbers
        if valid and leaf in ("name", "resource_type"):
            valid = str(value).casefold() in quote.casefold()
        if valid and leaf in ("planning_start", "planning_end", "earliest_start", "deadline"):
            timestamps = re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})", quote)
            parsed = []
            for stamp in timestamps:
                try:
                    parsed.append(datetime.fromisoformat(stamp))
                except ValueError:
                    pass
            valid = value in parsed
        if not valid:
            result.append(InformationIssue(field=path, reason="This extracted value needs explicit source evidence or user confirmation."))
    return result


def apply_answers(draft, answers):
    data = draft.model_dump(mode="json")
    answered = set()
    for answer in answers:
        if answer.field in answered:
            raise HTTPException(422, "Duplicate clarification answer")
        answered.add(answer.field)
        parts = answer.field.split(".")
        if len(parts) == 2 and parts[0] == "plan" and parts[1] in PlanDraft.model_fields:
            data["plan"][parts[1]] = answer.value
        elif len(parts) == 3 and parts[0] in ("tasks", "resources") and parts[1].isdigit():
            schema = TaskDraft if parts[0] == "tasks" else ResourceDraft
            index = int(parts[1])
            if index >= len(data[parts[0]]) or parts[2] not in schema.model_fields or parts[2] == "client_id":
                raise HTTPException(422, "Unknown clarification field")
            data[parts[0]][index][parts[2]] = answer.value
        elif len(parts) == 2 and parts[0] == "custom_values" and parts[1] in {item.name for item in draft.custom_fields}:
            data["custom_values"][parts[1]] = answer.value
        elif len(parts) == 1 and parts[0] in ("tasks", "resources", "requirements", "dependencies", "constraints"):
            data[parts[0]] = answer.value
        else:
            raise HTTPException(422, "Unknown clarification field; edit and confirm the structured draft instead")
    for key in ("missing_information", "ambiguities"):
        data[key] = [issue for issue in data[key] if not any(
            issue["field"] == field or issue["field"].startswith(field + ".") for field in answered
        )]
    return PlanningDraft.model_validate(data)
