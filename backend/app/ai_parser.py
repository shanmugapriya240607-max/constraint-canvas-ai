import os
from typing import Optional
from dotenv import load_dotenv
import openai
from pydantic import ValidationError
from app.schemas import ExtractedProblem

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


def parse_planning_text(text: str, client: Optional[openai.OpenAI] = None) -> ExtractedProblem:
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
        return parsed_result

    except (openai.APITimeoutError, openai.APIConnectionError) as exc:
        raise AITimeoutError("OpenAI connection timed out or network error occurred.") from exc

    except (ValidationError, openai.LengthFinishReasonError) as exc:
        raise AIValidationError("The intelligence service returned an invalid planning structure.") from exc

    except openai.OpenAIError as exc:
        raise AIParserError(f"OpenAI API error: {str(exc)}") from exc
