#!/usr/bin/env python3
"""Documentation consistency checks run by CI (and by hand before a PR).

Standard library only. Prints one line per problem and exits 1 if there are any.

  python3 scripts/check_docs.py                     relative links and #anchors in every .md
  python3 scripts/check_docs.py --rfcs              + RFC file naming, headers and README index
  python3 scripts/check_docs.py --skill FILE.md     + skill structure and fenced bash/json syntax
  python3 scripts/check_docs.py --layout CLAUDE.md  + CLAUDE.md layout block matches the tracked files
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
problems = []


def problem(path, msg):
    rel = path.relative_to(ROOT) if isinstance(path, pathlib.Path) and path.is_absolute() else path
    problems.append(f"{rel}: {msg}")


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / line for line in out.splitlines() if line]


def markdown_files():
    return sorted(p for p in tracked_files() if p.suffix == ".md")


FENCE = re.compile(r"^(```|~~~)(.*?)\n(.*?)^\1[ \t]*$", re.S | re.M)


def strip_code(text):
    text = FENCE.sub("", text)
    return re.sub(r"`[^`\n]*`", "", text)


def slugify(heading):
    """GitHub's heading anchor: lowercase, drop punctuation, spaces to hyphens."""
    h = re.sub(r"<[^>]+>", "", heading)
    h = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", h)  # links keep their text
    h = h.replace("`", "").replace("*", "").strip().lower()
    h = re.sub(r"[^\w\- ]", "", h)
    return h.replace(" ", "-")


_anchor_cache = {}


def anchors(path):
    if path not in _anchor_cache:
        seen = {}
        result = set()
        for line in FENCE.sub("", path.read_text(encoding="utf-8")).splitlines():
            m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
            if not m:
                continue
            slug = slugify(m.group(1))
            n = seen.get(slug, 0)
            seen[slug] = n + 1
            result.add(slug if n == 0 else f"{slug}-{n}")
        _anchor_cache[path] = result
    return _anchor_cache[path]


LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")


def check_links():
    for md in markdown_files():
        for target in LINK.findall(strip_code(md.read_text(encoding="utf-8"))):
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue  # http:, https:, mailto: ... are not checked offline
            path_part, _, frag = target.partition("#")
            dest = md if not path_part else (md.parent / path_part).resolve()
            if not dest.exists():
                problem(md, f"broken link -> {target}")
                continue
            if frag and dest.suffix == ".md" and frag.lower() not in anchors(dest):
                problem(md, f"no heading for anchor -> {target}")


# --- RFC repositories ------------------------------------------------------

RFC_NAME = re.compile(r"^rfc_(\d{4})_[a-z0-9]+(?:_[a-z0-9]+)*\.md$")
LIFECYCLE = ("Draft", "Proposed", "Accepted", "Rejected", "Superseded")
PLACEHOLDERS = ("XXXX", "<Title>", "<Your Name>", "<YYYY-MM-DD")


def header_field(text, name):
    m = re.search(rf"^\*\*{re.escape(name)}:\*\*\s*(.*?)\s*$", text, re.M)
    return m.group(1) if m else None


def check_rfcs():
    rfc_dir = ROOT / "rfcs"
    files = {}
    for p in sorted(rfc_dir.iterdir()):
        m = RFC_NAME.match(p.name)
        if not m:
            problem(p, "name does not match rfc_XXXX_short_title.md")
            continue
        num = m.group(1)
        if num in files:
            problem(p, f"number {num} is also used by {files[num].name}")
        files[num] = p
        text = p.read_text(encoding="utf-8")
        for ph in PLACEHOLDERS:
            if ph in text:
                problem(p, f"template placeholder left in: {ph}")
        h1 = re.search(r"^# RFC (\d{4}): (.+?)\s*$", text, re.M)
        if not h1:
            problem(p, "first heading is not '# RFC XXXX: Title'")
        elif h1.group(1) != num:
            problem(p, f"heading says RFC {h1.group(1)} but the file is {num}")
        for field in ("Author", "Date", "Last Updated", "Status", "Version"):
            if header_field(text, field) is None:
                problem(p, f"missing **{field}:** header line")
        status = header_field(text, "Status")
        if status is not None and not status.startswith(LIFECYCLE):
            problem(p, f"Status '{status}' is not one of {', '.join(LIFECYCLE)}")

    readme = ROOT / "README.md"
    rows = re.findall(r"^\|\s*\[(\d{4})\]\((rfcs/[^)]+)\)\s*\|(.*?)\|(.*?)\|\s*$",
                      readme.read_text(encoding="utf-8"), re.M)
    listed = set()
    for num, link, title, status in rows:
        title, status = title.strip(), status.strip()
        p = ROOT / link
        if num in listed:
            problem(readme, f"RFC {num} is listed twice")
        listed.add(num)
        if not p.exists():
            continue  # reported by the link check
        m = RFC_NAME.match(p.name)
        if not m or m.group(1) != num:
            problem(readme, f"row {num} links to {link}")
            continue
        text = p.read_text(encoding="utf-8")
        h1 = re.search(r"^# RFC \d{4}: (.+?)\s*$", text, re.M)
        if h1 and not title.startswith(h1.group(1)):
            problem(readme, f"row {num} title '{title}' does not start with the RFC's title '{h1.group(1)}'")
        file_status = header_field(text, "Status") or ""
        # A compound README status (e.g. a partly superseded RFC) is free text; a plain one must agree.
        if status in LIFECYCLE and not file_status.startswith(status):
            problem(readme, f"row {num} status '{status}' but the RFC says '{file_status}'")
    for num, p in files.items():
        if num not in listed:
            problem(readme, f"RFC index has no row for {p.relative_to(ROOT)}")


# --- skill files ----------------------------------------------------------

def check_skill(name):
    path = ROOT / name
    text = path.read_text(encoding="utf-8")
    if len(re.findall(r"^```", text, re.M)) % 2:
        problem(path, "unbalanced ``` code fences")
    h1 = re.search(r"^# (.+?)\s*$", strip_code(text), re.M)
    if not h1 or h1.group(1) != path.stem:
        problem(path, f"first heading should be '# {path.stem}'")
    steps = [int(n) for n in re.findall(r"^### (\d+) — \S", strip_code(text), re.M)]
    if not steps:
        problem(path, "no '### N — Title' step headings")
    elif steps != list(range(1, len(steps) + 1)):
        problem(path, f"step numbers are not 1..{len(steps)} in order: {steps}")
    if not re.search(r"^## Self-audit\s*$", strip_code(text), re.M):
        problem(path, "missing '## Self-audit' section")
    for m in FENCE.finditer(text):
        lang, body = m.group(2).strip(), m.group(3)
        line = text[: m.start()].count("\n") + 1
        if lang in ("bash", "sh"):
            r = subprocess.run(["bash", "-n"], input=body, capture_output=True, text=True)
            if r.returncode:
                err = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "syntax error"
                problem(path, f"bash block at line {line} does not parse: {err}")
        elif lang == "json":
            try:
                json.loads(body)
            except ValueError as e:
                problem(path, f"json block at line {line} does not parse: {e}")


# --- CLAUDE.md layout block --------------------------------------------------

def check_layout(name):
    path = ROOT / name
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^## Repository layout\s*\n+```[^\n]*\n(.*?)^```", text, re.S | re.M)
    if not m:
        problem(path, "no fenced block under '## Repository layout'")
        return
    named = {line.split()[0].rstrip("/") for line in m.group(1).splitlines() if line.strip()}
    top = {p.relative_to(ROOT).parts[0] for p in tracked_files()}
    for entry in sorted(named - top):
        problem(path, f"layout lists '{entry}', which is not in the repository")
    for entry in sorted(top - named - {name}):
        problem(path, f"layout does not list tracked '{entry}'")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rfcs", action="store_true", help="check rfcs/ naming, headers and the README index")
    ap.add_argument("--skill", action="append", default=[], metavar="FILE", help="check a skill file's structure")
    ap.add_argument("--layout", metavar="FILE", help="check a CLAUDE.md layout block against tracked files")
    a = ap.parse_args()
    check_links()
    if a.rfcs:
        check_rfcs()
    for s in a.skill:
        check_skill(s)
    if a.layout:
        check_layout(a.layout)
    for p in problems:
        print(p)
    n = len(markdown_files())
    print(f"check_docs: {n} markdown files, {len(problems)} problem(s)", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
