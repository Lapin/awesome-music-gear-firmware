#!/usr/bin/env python3
"""Rebuild CHANGELOG.md from the history of README.md on the current branch."""
import re
import subprocess
from collections import OrderedDict
from pathlib import Path

ENTRY = re.compile(r"^\s*- \[([^\]]+)\]\((https?://[^\s)]+)\)(.*)$")
HEADING = re.compile(r"^(#{2,4}) (.+)$")
SKIP_SECTIONS = {"Contents"}
HEADER = """# Changelog

Every entry added, removed, moved or reworded in the list, newest first. This file is generated from the history of `README.md`, so don't edit it by hand.
"""


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def entries(readme):
    """Map each link to its text and section."""
    found, trail = {}, {}
    for line in readme.splitlines():
        heading = HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            trail = {k: v for k, v in trail.items() if k < level}
            trail[level] = heading.group(2).strip()
            continue
        match = ENTRY.match(line)
        if match and not set(trail.values()) & SKIP_SECTIONS:
            key = match.group(2).rstrip("/").lower()
            found.setdefault(key, {
                "line": line.strip()[2:],
                "section": " > ".join(trail[k] for k in sorted(trail)),
            })
    return found


def compare(old, new):
    changes = {"Added": [], "Removed": [], "Moved": [], "Changed": []}
    for key, entry in new.items():
        before = old.get(key)
        if before is None:
            changes["Added"].append(f"{entry['line']} ({entry['section']})")
        elif before["section"] != entry["section"]:
            changes["Moved"].append(f"{entry['line']} (from {before['section']} to {entry['section']})")
        elif before["line"] != entry["line"]:
            changes["Changed"].append(f"{entry['line']} ({entry['section']})")
    for key, entry in old.items():
        if key not in new:
            changes["Removed"].append(f"{entry['line']} ({entry['section']})")
    return changes


def build():
    log = git("log", "--first-parent", "--reverse", "--date=short", "--format=%H %ad", "--", "README.md")
    days, previous, first = OrderedDict(), None, None
    for row in log.splitlines():
        commit, day = row.split()
        current = entries(git("show", f"{commit}:README.md"))
        if previous is None:
            first = (day, len(current))
        else:
            bucket = days.setdefault(day, {"Added": [], "Removed": [], "Moved": [], "Changed": []})
            for kind, items in compare(previous, current).items():
                bucket[kind].extend(items)
        previous = current

    output = [HEADER]
    for day, bucket in reversed(days.items()):
        if not any(bucket.values()):
            continue
        output.append(f"## {day}\n")
        for kind, items in bucket.items():
            if items:
                output.append(f"### {kind}\n")
                output.extend(f"- {item}" for item in items)
                output.append("")
    if first:
        output.append(f"## {first[0]}\n\nThe list started with {first[1]} entries.\n")
    return "\n".join(output).rstrip() + "\n"


if __name__ == "__main__":
    Path("CHANGELOG.md").write_text(build())
