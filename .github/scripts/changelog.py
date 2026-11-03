#!/usr/bin/env python3
"""Rebuild CHANGELOG.md from the history of README.md on the current branch."""
import re
import subprocess
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


def name_of(entry):
    return ENTRY.match("- " + entry["line"]).group(1)


def compare(old, new):
    changes = {"Added": [], "Removed": [], "Moved": [], "Changed": []}
    removed = {key: entry for key, entry in old.items() if key not in new}
    relinked = {name_of(entry): entry for entry in removed.values()}
    for key, entry in new.items():
        before = old.get(key)
        if before is None:
            previous = relinked.pop(name_of(entry), None)
            if previous is None:
                changes["Added"].append(f"{entry['line']} ({entry['section']})")
            else:
                removed = {k: e for k, e in removed.items() if e is not previous}
                changes["Changed"].append(f"{entry['line']} ({entry['section']}, link updated)")
        elif before["section"] != entry["section"]:
            reworded = ", reworded" if before["line"] != entry["line"] else ""
            changes["Moved"].append(f"{entry['line']} (from {before['section']} to {entry['section']}{reworded})")
        elif before["line"] != entry["line"]:
            changes["Changed"].append(f"{entry['line']} ({entry['section']})")
    changes["Removed"] = [f"{entry['line']} ({entry['section']})" for entry in removed.values()]
    return changes


def snapshots():
    """The list as it stood at the end of each day, so each day shows its net change."""
    log = git("log", "--first-parent", "--reverse", "--date=short", "--format=%H %cd", "--", "README.md")
    days, latest = {}, ""
    for row in log.splitlines():
        commit, day = row.split()
        latest = max(latest, day)  # A commit dated earlier than its parent still counts as the latest day.
        days[latest] = entries(git("show", f"{commit}:README.md"))
    return list(days.items())


def build():
    days = snapshots()
    output = [HEADER]
    for (_, old), (day, new) in reversed(list(zip(days, days[1:]))):
        changes = compare(old, new)
        if not any(changes.values()):
            continue
        output.append(f"## {day}\n")
        for kind, items in changes.items():
            if items:
                output.append(f"### {kind}\n")
                output.extend(f"- {item}" for item in items)
                output.append("")
    if days:
        output.append(f"## {days[0][0]}\n\nThe list started with {len(days[0][1])} entries.\n")
    return "\n".join(output).rstrip() + "\n"


if __name__ == "__main__":
    Path("CHANGELOG.md").write_text(build())
