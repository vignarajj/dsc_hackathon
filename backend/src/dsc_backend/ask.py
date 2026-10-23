from dataclasses import dataclass

from dsc_backend.boxes import load_json_object
from dsc_backend.errors import PipelineError

MAX_QUESTION_CHARS = 300
MAX_TEXT_CHARS = 20_000
MAX_FIELDS = 20
NOT_IN_DOCUMENT = "The document does not say."
_MAX_ANSWER_CHARS = 600

ASK_FORMAT = {
    "type": "json_schema",
    "name": "answer",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["answer", "quote"],
        "properties": {
            "answer": {"type": "string"},
            "quote": {"type": "string"},
        },
    },
}


@dataclass(frozen=True)
class Question:
    question: str
    text: str
    fields: list[tuple[str, str]]


@dataclass(frozen=True)
class Answer:
    answer: str
    quote: str | None


def question_for_request(question: object, text: object, fields: object) -> Question:
    """Check an ask request. Every limit is a 400 with a sentence the page can show."""
    if not isinstance(question, str) or not question.strip():
        raise PipelineError(400, "Type a question.")
    if len(question) > MAX_QUESTION_CHARS:
        raise PipelineError(400, f"Keep the question under {MAX_QUESTION_CHARS} characters.")
    if not isinstance(text, str):
        raise PipelineError(400, "Send the document text with the question.")
    if len(text) > MAX_TEXT_CHARS:
        raise PipelineError(400, f"The document text is over {MAX_TEXT_CHARS} characters.")
    pairs: list[tuple[str, str]] = []
    if fields is not None:
        if not isinstance(fields, list):
            raise PipelineError(400, "fields must be a list of label and value pairs.")
        for item in fields[:MAX_FIELDS]:
            if (
                isinstance(item, dict)
                and isinstance(item.get("label"), str)
                and isinstance(item.get("value"), str)
            ):
                pairs.append((item["label"][:40], item["value"][:200]))
    return Question(question=question.strip(), text=text, fields=pairs)


def parse_answer(reply: str, text: str) -> Answer:
    """Read Muse's answer. The quote is kept only if it is really in the text."""
    data = load_json_object(reply)
    answer = data.get("answer") if data is not None else None
    quote = data.get("quote") if data is not None else None
    if not isinstance(answer, str) or not answer.strip():
        raise PipelineError(502, "The model request failed")
    answer = " ".join(answer.split())[:_MAX_ANSWER_CHARS]
    if not isinstance(quote, str) or not quote.strip() or answer == NOT_IN_DOCUMENT:
        return Answer(answer=answer, quote=None)
    quote = quote.strip()
    return Answer(answer=answer, quote=quote if quote in text else None)
