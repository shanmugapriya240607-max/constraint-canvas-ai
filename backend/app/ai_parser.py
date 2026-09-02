import os
import re
from typing import Optional, List, Dict, Tuple
from dotenv import load_dotenv
import openai
from pydantic import ValidationError
from app.schemas import ExtractedProblem, Task, Objective

load_dotenv()

SYSTEM_PROMPT = """You are a planning-task extraction engine.

Read the user's planning requirement and convert it into structured planning data.

Identify:
1. Problem title
2. Optimization objective
3. Tasks
4. Duration of every task
5. Earliest start times
6. Deadlines
7. Task dependencies
8. Required resources
9. Passive tasks
10. Missing information
11. Ambiguities
12. Assumptions

Rules:
- Return data conforming exactly to the supplied schema.
- Never invent a duration, deadline or start time.
- If a duration is not stated, use null and add a missing-information question.
- A dependency must represent a real before/after requirement.
- Words such as “before,” “after,” “only then” and “must finish before” indicate dependencies.
- Sentence order alone does not prove a dependency.
- Preserve the original source text for each task.
- Use 24-hour HH:MM time.
- Mark automatic background activities such as a washing-machine cycle as passive only when the text supports it.
- Do not calculate the final schedule.
- Do not return Markdown.
"""

class AIParserError(Exception):
    """Base exception for AI Parser failures."""
    pass

class AIConfigurationError(AIParserError):
    """Raised when OpenAI API key or configuration is missing."""
    pass

class AITimeoutError(AIParserError):
    """Raised when OpenAI API call times out or connection fails."""
    pass

class AIValidationError(AIParserError):
    """Raised when OpenAI response fails schema validation."""
    pass


def parse_time_to_24h(hour_str: str, min_str: Optional[str], ampm_str: Optional[str]) -> str:
    """Helper to convert hour, minute, and AM/PM strings into 24-hour HH:MM format."""
    h = int(hour_str)
    m = int(min_str) if min_str else 0
    if ampm_str:
        ampm = ampm_str.upper()
        if ampm == "PM" and h < 12:
            h += 12
        elif ampm == "AM" and h == 12:
            h = 0
    return f"{h:02d}:{m:02d}"


def parse_planning_text_openai(text: str, client: Optional[openai.OpenAI] = None) -> ExtractedProblem:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not client:
        if not api_key or not api_key.strip():
            raise AIConfigurationError("OPENAI_API_KEY is not configured.")
        client = openai.OpenAI(api_key=api_key.strip())

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format=ExtractedProblem,
            temperature=0.0,
        )
        
        parsed_result = completion.choices[0].message.parsed
        if parsed_result is None:
            raise AIValidationError("The intelligence service returned empty parsing results.")
        parsed_result.parser_mode = "OPENAI"
        return parsed_result

    except (openai.APITimeoutError, openai.APIConnectionError) as exc:
        raise AITimeoutError("OpenAI connection timed out or network error occurred.") from exc

    except (ValidationError, openai.LengthFinishReasonError) as exc:
        raise AIValidationError("The intelligence service returned an invalid planning structure.") from exc

    except openai.OpenAIError as exc:
        raise AIParserError(f"OpenAI API error: {str(exc)}") from exc


def parse_planning_text_offline(text: str) -> ExtractedProblem:
    """
    Deterministic offline NLP parser extracts tasks, durations, deadlines, and dependencies
    without making any external API calls.
    """
    if not text or not text.strip():
        raise AIValidationError("Planning text is empty.")

    clean_text = text.strip()

    # 1. Extract Overall Deadline if present (e.g., "by 9:00 AM", "before 6:00 PM", "by 18:00")
    deadline_match = re.search(
        r"(?:by|before|finish by|finish before|due at|due by|reach the office by|submit my assignment before|submit before)\s+([0-2]?[0-9])(?::([0-5][0-9]))?\s*(AM|PM|am|pm)?",
        clean_text,
        re.IGNORECASE,
    )
    overall_deadline = None
    if deadline_match:
        h_str, m_str, ampm_str = deadline_match.groups()
        overall_deadline = parse_time_to_24h(h_str, m_str, ampm_str)

    # 2. Extract Tasks and Durations using regex patterns
    dur_regex = re.compile(
        r"(?:([A-Za-z0-9\s']+?)\s+(?:takes|requires|duration of|lasts|is)\s+([0-9\.]+)\s*(minutes|minute|mins|min|hours|hour|hrs|hr))"
        r"|(?:(?:need to|have to|must|want to)\s+([A-Za-z0-9\s']+?)\s+for\s+([0-9\.]+)\s*(minutes|minute|mins|min|hours|hour|hrs|hr))"
        r"|(?:([0-9\.]+)\s*(minutes|minute|mins|min|hours|hour|hrs|hr)\s+(?:for|to|on)\s+([A-Za-z0-9\s']+))",
        re.IGNORECASE,
    )

    matches = dur_regex.findall(clean_text)
    extracted_raw_tasks: List[Tuple[str, int]] = []
    seen_names = set()

    for match in matches:
        t_name = None
        dur_val = None
        unit = None

        if match[0] and match[1]:  # Pattern A
            t_name = match[0]
            dur_val = float(match[1])
            unit = match[2].lower()
        elif match[3] and match[4]:  # Pattern B
            t_name = match[3]
            dur_val = float(match[4])
            unit = match[5].lower()
        elif match[6] and match[8]:  # Pattern C
            dur_val = float(match[6])
            unit = match[7].lower()
            t_name = match[8]

        if t_name and dur_val:
            # Clean task name
            cleaned_name = re.sub(
                r"^(?:and|then|after|after that|before|to|I|I need to|I must|tomorrow|today|first|need to|must|have to)\s+",
                "",
                t_name.strip(),
                flags=re.IGNORECASE,
            ).strip()

            # Clean trailing words
            cleaned_name = re.sub(r"\s+(?:and|then|which|that)$", "", cleaned_name, flags=re.IGNORECASE).strip()

            # Convert hours to minutes
            duration_mins = int(round(dur_val * 60)) if "hour" in unit or "hr" in unit else int(round(dur_val))

            norm_key = cleaned_name.lower()
            if cleaned_name and norm_key not in seen_names:
                formatted_name = cleaned_name[0].upper() + cleaned_name[1:] if len(cleaned_name) > 0 else cleaned_name
                extracted_raw_tasks.append((formatted_name, duration_mins))
                seen_names.add(norm_key)

    # Check for unstated tasks mentioned in list format
    missing_tasks = []
    action_phrases = re.findall(r"(?:wake up|get ready|eat breakfast|travel to office|research|writing|proofreading|submission)", clean_text, re.IGNORECASE)
    for phrase in action_phrases:
        p_norm = phrase.lower()
        matched = any(p_norm in t[0].lower() or t[0].lower() in p_norm for t in extracted_raw_tasks)
        if not matched:
            missing_tasks.append(phrase.capitalize())

    if missing_tasks:
        missing_list_str = ", ".join(f"'{m}'" for m in missing_tasks)
        raise AIValidationError(f"The following tasks are missing explicit durations: {missing_list_str}")

    if not extracted_raw_tasks:
        raise AIValidationError("Could not identify any tasks with valid durations in the prompt.")

    # 3. Create Task Objects with Stable Task IDs (task_1, task_2, ...)
    task_objects: List[Task] = []

    for idx, (name, dur) in enumerate(extracted_raw_tasks):
        t_id = f"task_{idx + 1}"
        task_obj = Task(
            id=t_id,
            name=name,
            duration_minutes=dur,
            depends_on=[],
            resources=["person"],
            source_text=f"{name} takes {dur} minutes",
        )
        task_objects.append(task_obj)

    # 4. Clause-Based Keyword Dependency Extraction
    sub_phrases = re.split(r"[\.\;]|\,\s*and\s+|\,\s*", clean_text)

    def task_keywords(t_name: str) -> List[str]:
        return [w.lower() for w in t_name.split() if w.lower() not in ("to", "the", "a", "an", "and", "for", "my", "or")]

    def find_task_in_subphrase(subphrase: str, t_name: str) -> Tuple[bool, int]:
        kw_list = task_keywords(t_name)
        p_lower = subphrase.lower()
        min_idx = 999999
        found = False
        for kw in kw_list:
            idx = p_lower.find(kw)
            if idx != -1:
                found = True
                if idx < min_idx:
                    min_idx = idx
        return found, min_idx

    for sp in sub_phrases:
        sp_lower = sp.lower()
        if not any(k in sp_lower for k in ("before", "after", "then", "following", "prior")):
            continue

        for i, t_i in enumerate(task_objects):
            found_i, idx_i = find_task_in_subphrase(sp_lower, t_i.name)
            if not found_i:
                continue

            for j, t_j in enumerate(task_objects):
                if i == j:
                    continue

                found_j, idx_j = find_task_in_subphrase(sp_lower, t_j.name)
                if not found_j:
                    continue

                if "before" in sp_lower or "prior" in sp_lower:
                    if idx_i < idx_j:
                        if t_i.id not in t_j.depends_on:
                            t_j.depends_on.append(t_i.id)
                elif "after" in sp_lower or "following" in sp_lower:
                    if idx_j < idx_i:
                        if t_i.id not in t_j.depends_on:
                            t_j.depends_on.append(t_i.id)
                elif "then" in sp_lower:
                    if idx_i < idx_j:
                        if t_i.id not in t_j.depends_on:
                            t_j.depends_on.append(t_i.id)

    # 5. Assign overall deadline to the final task in the dependency chain
    if overall_deadline:
        has_dependents = set()
        for t in task_objects:
            for dep in t.depends_on:
                has_dependents.add(dep)
        
        leaf_tasks = [t for t in task_objects if t.id not in has_dependents]
        if leaf_tasks:
            leaf_tasks[-1].deadline = overall_deadline
        else:
            task_objects[-1].deadline = overall_deadline

    # 6. Determine Objective Type
    if re.search(r"\b(late as possible|as late as possible|latest start)\b", clean_text, re.IGNORECASE):
        objective = Objective(type="LATEST_START", description="Start routine as late as possible")
    elif re.search(r"\b(early as possible|as early as possible|earliest finish|minimize makespan)\b", clean_text, re.IGNORECASE):
        objective = Objective(type="EARLIEST_FINISH", description="Finish tasks as early as possible")
    else:
        objective = Objective(type="MINIMIZE_MAKESPAN", description="Minimize overall schedule duration")

    first_task_name = task_objects[0].name if task_objects else "Planning"
    title = f"{first_task_name} Schedule"

    return ExtractedProblem(
        problem_title=title,
        objective=objective,
        tasks=task_objects,
        missing_information=[],
        ambiguities=[],
        assumptions=["Parsed using deterministic natural language rules."],
        extraction_confidence=0.95,
        parser_mode="OFFLINE_RULES",
    )


def parse_planning_text(text: str, client: Optional[openai.OpenAI] = None) -> ExtractedProblem:
    """
    Dispatcher function selecting between OpenAI parser and Offline Deterministic parser
    based on PARSER_MODE environment variable.
    """
    parser_mode_env = os.getenv("PARSER_MODE", "offline").lower().strip()

    if parser_mode_env == "openai":
        try:
            return parse_planning_text_openai(text, client=client)
        except Exception as exc:
            # Fallback transparently to offline parser if OpenAI fails
            result = parse_planning_text_offline(text)
            result.parser_mode = "OFFLINE_RULES"
            return result
    else:
        # Default or PARSER_MODE=offline
        return parse_planning_text_offline(text)
