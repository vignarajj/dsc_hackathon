"""Live smoke test: send sample pages to a running API and print a pass/fail table.

This spends real Meta model calls, so it only runs with --yes.

    uv run python scripts/smoke.py --yes
    uv run python scripts/smoke.py --yes --base-url https://api.example.app --ask
    uv run python scripts/smoke.py --yes --describe --delay 13 photo.jpg
    uv run python scripts/smoke.py --yes path/to/photo.jpg other.png

With no paths, it uses the four sample pages in frontend/public/samples/.
Exit status is 0 when every page passes, 1 otherwise.
"""

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

SAMPLES = Path(__file__).resolve().parents[2] / "frontend" / "public" / "samples"
FORM = {
    "concepts": "stamp,signature,photograph,rectangle",
    "redact": "signature,photograph",
    "redact_text": "true",
    "extract": "true",
}
# The page's default choices make 9 calls per image; see the root README.
CALLS_PER_PAGE = 9
# --describe adds one call per described region, up to 8 per image.
DESCRIBE_CALLS_PER_PAGE = 8
# 60 s over a limit of 5 requests a minute, rounded up: --delay 13 stays under it.
RATE_LIMIT_HINT = "rate limited: run with --delay 13, or raise RATE_LIMIT_PER_MINUTE"


@dataclass(frozen=True)
class Expect:
    doc_type: str
    regions: tuple[str, ...] = ()
    sensitive: tuple[str, ...] = ()
    question: str = "What is this document about?"


# What each sample page should give. Pages not listed get the general checks only.
EXPECTED = {
    "invoice": Expect("invoice", ("stamp",), ("phone", "email"), "What is the total due?"),
    "signed-form": Expect(
        "form", ("signature", "photograph"), ("phone", "email"), "Whose form is this?"
    ),
    "handwritten-note": Expect("note", (), ("phone",), "When is the plumber coming?"),
    "chat": Expect("chat", (), ("phone", "email"), "What was agreed?"),
    # No sample receipt ships with the repo; name your photo receipt.jpg to get these checks.
    "receipt": Expect("receipt", question="What was the total?"),
}


@dataclass
class Row:
    name: str
    seconds: float = 0.0
    problems: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def passed(self) -> bool:
        return not self.problems


def check_result(
    name: str, body: dict[str, object], expect: Expect | None, describe: bool = False
) -> Row:
    """Compare one /api/process result with what the page should give."""
    row = Row(name)
    if not body.get("overlay_png_base64"):
        row.problems.append("no overlay")
    if not str(body.get("cleaned_text") or "").strip():
        row.problems.append("no text read")
    if not body.get("redacted_png_base64"):
        row.problems.append("no share-safe image")
    boxes = [box for box in body.get("boxes", []) if isinstance(box, dict)]
    labels = [box.get("label") for box in boxes]
    if describe and boxes:
        undescribed = sum(1 for box in boxes if not str(box.get("description") or "").strip())
        if undescribed == len(boxes):
            row.problems.append("no region descriptions (off on this server, or all failed)")
        elif undescribed:
            row.problems.append(f"{undescribed} of {len(boxes)} regions have no description")
    categories = {
        span.get("category") for span in body.get("sensitive", []) if isinstance(span, dict)
    }
    document = body.get("document") if isinstance(body.get("document"), dict) else None
    fields = document.get("fields", []) if document else []
    grounded = sum(1 for item in fields if isinstance(item, dict) and item.get("found_in_text"))
    if expect is not None:
        if document is None:
            row.problems.append("no document data")
        elif document.get("type") != expect.doc_type:
            row.problems.append(f"type {document.get('type')!r}, expected {expect.doc_type!r}")
        for label in expect.regions:
            if label not in labels:
                row.problems.append(f"no {label} found")
        for category in expect.sensitive:
            if category not in categories:
                row.problems.append(f"no {category} masked")
        if document is not None and expect.doc_type in {"invoice", "receipt", "form"}:
            if grounded < 3:
                row.problems.append(f"{grounded} grounded fields, expected 3 or more")
    counts = ", ".join(f"{label}: {labels.count(label)}" for label in dict.fromkeys(labels))
    row.summary = (
        f"type={document.get('type') if document else '-'} "
        f"regions=[{counts}] sensitive={len(categories)} kinds "
        f"fields={grounded}/{len(fields)} grounded warnings={len(body.get('warnings', []))}"
    )
    return row


def _problem_for_status(response: httpx.Response) -> str:
    detail = response.json().get("detail") if response.content else ""
    hint = f" ({RATE_LIMIT_HINT})" if response.status_code == 429 else ""
    return f"HTTP {response.status_code}: {detail}{hint}"


def run(
    client: httpx.Client,
    paths: list[Path],
    ask: bool = False,
    describe: bool = False,
    delay: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Row]:
    """Send each page. `delay` seconds pass before every request after the first."""
    rows: list[Row] = []
    form = {**FORM, "describe": "true"} if describe else FORM
    sent = 0

    def pause() -> None:
        nonlocal sent
        if sent and delay > 0:
            sleep(delay)
        sent += 1

    for path in paths:
        expect = EXPECTED.get(path.stem)
        media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        pause()
        started = time.perf_counter()
        try:
            response = client.post(
                "/api/process", data=form, files={"image": (path.name, path.read_bytes(), media)}
            )
        except httpx.HTTPError as exc:
            rows.append(Row(path.stem, time.perf_counter() - started, [type(exc).__name__]))
            continue
        seconds = time.perf_counter() - started
        if response.status_code != 200:
            rows.append(Row(path.stem, seconds, [_problem_for_status(response)]))
            continue
        body = response.json()
        row = check_result(path.stem, body, expect, describe)
        row.seconds = seconds
        if ask:
            pause()
            answer = client.post(
                "/api/ask",
                json={
                    "question": (expect or Expect("other")).question,
                    "text": body.get("cleaned_text", ""),
                    "fields": (body.get("document") or {}).get("fields", []),
                },
            )
            if answer.status_code != 200:
                row.problems.append(f"ask: {_problem_for_status(answer)}")
            else:
                row.summary += f" answer={answer.json().get('answer', '')[:40]!r}"
        rows.append(row)
    return rows


def table(rows: list[Row]) -> str:
    lines = [f"{'page':<18} {'result':<6} {'seconds':>7}  details"]
    for row in rows:
        result = "pass" if row.passed else "FAIL"
        details = row.summary if row.passed else "; ".join(row.problems)
        lines.append(f"{row.name:<18} {result:<6} {row.seconds:>7.1f}  {details}")
    passed = sum(row.passed for row in rows)
    lines.append(f"{passed} of {len(rows)} pages passed")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("paths", nargs="*", type=Path, help="images to send (default: samples)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--ask", action="store_true", help="also ask one question per page")
    parser.add_argument("--describe", action="store_true", help="also describe each region")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="wait this long before each request after the first, to stay under a rate limit",
    )
    parser.add_argument("--yes", action="store_true", help="spend the model calls")
    args = parser.parse_args(argv)
    paths = args.paths or sorted(SAMPLES.glob("*.jpg"))
    per_page = CALLS_PER_PAGE + (1 if args.ask else 0)
    calls = len(paths) * (per_page + (DESCRIBE_CALLS_PER_PAGE if args.describe else 0))
    estimate = "up to" if args.describe else "about"
    print(f"{len(paths)} pages against {args.base_url}: {estimate} {calls} model calls.")
    if not args.yes:
        print("Nothing sent. Run again with --yes to spend the calls.")
        return 1
    with httpx.Client(base_url=args.base_url, timeout=200) as client:
        rows = run(client, paths, args.ask, args.describe, args.delay)
    print(table(rows))
    return 0 if all(row.passed for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
