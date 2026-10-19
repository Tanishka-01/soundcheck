"""One-off scan for secrets/PII in results/ before publishing. Not part of
the harness. Prints only locations and pattern labels -- never the matched
secret value itself."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent

env_key = None
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("ASSEMBLYAI_API_KEY="):
        env_key = line.split("=", 1)[1].strip()

creds = json.loads((Path.home() / ".claude" / ".credentials.json").read_text(encoding="utf-8"))["claudeAiOauth"]
access_token = creds["accessToken"]
refresh_token = creds["refreshToken"]

secrets = {
    "ASSEMBLYAI_API_KEY": env_key,
    "claude accessToken": access_token,
    "claude refreshToken": refresh_token,
}

emails = ["tanishkawani@gmail.com", "wani.31@buckeyemail.osu.edu"]
generic_email_re = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
username_path_variants = ["Users\\\\User\\\\", "Users\\User\\", "/Users/User/", "/c/Users/User/"]
apikey_shape_res = [
    ("anthropic-style sk-ant-", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("generic sk-", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("github ghp_", re.compile(r"ghp_[A-Za-z0-9]{30,}")),
    ("AWS AKIA", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Bearer token", re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")),
    ("32-hex (assemblyai-shaped)", re.compile(r"\b[0-9a-f]{32}\b")),
    ("JWT-shaped", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]

files = sorted((ROOT / "results").rglob("*"))
findings = {}
for f in files:
    if not f.is_file():
        continue
    try:
        text = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    hits = []
    for name, val in secrets.items():
        if val and val in text:
            hits.append("LITERAL SECRET: " + name)
    for em in emails:
        if em in text:
            hits.append("EMAIL: " + em)
    found = set(generic_email_re.findall(text))
    unknown = found - set(emails)
    if unknown:
        hits.append("OTHER EMAIL-LIKE: " + str(unknown))
    for variant in username_path_variants:
        if variant in text:
            hits.append("USERNAME PATH containing: " + repr(variant))
    for label, pat in apikey_shape_res:
        m = pat.findall(text)
        if m:
            hits.append(f"KEY-SHAPED PATTERN ({label}): {len(m)} match(es)")
    if hits:
        findings[str(f.relative_to(ROOT))] = hits

print("Scanned", len(files), "entries under results/.")
print("Files with findings:", len(findings))
print()
for f, hits in findings.items():
    print(f)
    for h in hits:
        print("   -", h)
