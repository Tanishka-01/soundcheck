"""One-off redaction pass over results/ before publishing. Not part of the
harness. Replaces the Windows username in absolute paths (the only
category confirmed present) with [REDACTED_USER]. Reports exactly what
changed, file by file and occurrence count."""
import re
from pathlib import Path

ROOT = Path(__file__).parent

# Matches "Users" + 1-4 backslashes + "User" + 1-4 backslashes (JSON-escaped
# Windows paths), the hyphenated scratchpad-folder variant "Users-User", and
# a forward-slash variant for safety.
PATTERNS = [
    re.compile(r"(Users)(\\{1,4})User(\\{1,4})"),
    re.compile(r"Users-User"),
    re.compile(r"/Users/User(?=/)"),
]

# Third-party emails that leaked in via `pip show` output the agent ran --
# not the project owner's data, but redacted per explicit approval.
THIRD_PARTY_EMAILS = [
    "engineering.sdk@assemblyai.com",
    "user@assemblyai.com",
    "aymeric.augustin@m4x.org",
]


def redact(text: str) -> tuple[str, int]:
    count = 0

    def repl_backslash(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f"{m.group(1)}{m.group(2)}[REDACTED_USER]{m.group(3)}"

    text = PATTERNS[0].sub(repl_backslash, text)

    def repl_simple(pattern: re.Pattern, replacement: str, text: str) -> str:
        nonlocal count
        new_text, n = pattern.subn(replacement, text)
        count += n
        return new_text

    text = repl_simple(PATTERNS[1], "Users-[REDACTED_USER]", text)
    text = repl_simple(PATTERNS[2], "/Users/[REDACTED_USER]", text)
    for email in THIRD_PARTY_EMAILS:
        n = text.count(email)
        if n:
            count += n
            text = text.replace(email, "[REDACTED_EMAIL]")
    return text, count


def main():
    report = []
    for f in sorted((ROOT / "results").rglob("*")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        new_text, count = redact(text)
        if count:
            f.write_text(new_text, encoding="utf-8")
            report.append((str(f.relative_to(ROOT)), count))

    print(f"Redacted {sum(c for _, c in report)} occurrences across {len(report)} files.")
    for path, count in report:
        print(f"  {path}: {count} occurrence(s)")


if __name__ == "__main__":
    main()
