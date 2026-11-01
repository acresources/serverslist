#!/usr/bin/env python3
"""Reorder Servers.xml by when each server was most recently added.

A server's position comes from its latest "add": the commit in which its
<id> first appeared in the file, or in which it reappeared after being absent
from the previous version. Within a commit, servers keep the order they had
in that commit's file.

Only the order of the <ServerItem> blocks changes. Each block's bytes and the
whitespace between blocks stay where they are.

Usage
-----
reorder_servers.py <path-to-Servers.xml>

Run from inside the git repository. The file is rewritten in place.
"""

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter

ITEM_RE = re.compile(r"<ServerItem>.*?</ServerItem>", re.DOTALL)
ID_RE = re.compile(r"<id>\s*([^<]*?)\s*</id>")


def ids_in_order(xml_text):
    """Return the server ids in document order.

    Parameters
    ----------
    xml_text : str
        A Servers.xml document, or a single ``<ServerItem>`` fragment.

    Returns
    -------
    list of str
        The stripped ``<id>`` text of each ``ServerItem``.
    """
    root = ET.fromstring(xml_text)
    return [item.find("id").text.strip() for item in root.iter("ServerItem")]


def latest_add_positions(versions):
    """Return each server's position from its latest add.

    Parameters
    ----------
    versions : list of list of str
        The server ids of each committed version of the file, oldest first.

    Returns
    -------
    dict of str to tuple of (int, int)
        Maps each id to ``(commit_index, position_in_that_commit)`` for the
        commit where it was most recently added.
    """
    positions = {}
    previous = set()
    for commit_index, ids in enumerate(versions):
        for position, server_id in enumerate(ids):
            if server_id not in previous:
                positions[server_id] = (commit_index, position)
        previous = set(ids)
    return positions


def ids_by_commit(path, cwd=None):
    """Return the server ids of each commit that touched ``path``, oldest first.

    Ids are read with a regular expression rather than an XML parser because
    some historical versions of the file are not well-formed XML. Skipping
    them would misattribute the servers added in those commits.

    Parameters
    ----------
    path : str
        Path of the file, relative to the repository root.
    cwd : str, optional
        Repository directory. Defaults to the current directory.

    Returns
    -------
    list of list of str
        One id list per commit, in document order.

    Raises
    ------
    subprocess.CalledProcessError
        If git fails, e.g. if a commit does not contain the file.
    """
    shas = subprocess.run(
        ["git", "log", "--reverse", "--format=%H", "--", path],
        cwd=cwd, capture_output=True, text=True, check=True,
    ).stdout.split()
    versions = []
    for sha in shas:
        content = subprocess.run(
            ["git", "show", f"{sha}:{path}"],
            cwd=cwd, capture_output=True, text=True, check=True,
        ).stdout
        versions.append(ID_RE.findall(content))
    return versions


def reorder_text(text, positions):
    """Return ``text`` with its ``<ServerItem>`` blocks sorted by ``positions``.

    Parameters
    ----------
    text : str
        A Servers.xml document.
    positions : dict of str to tuple
        Sort key for each server id, as returned by `latest_add_positions`.

    Returns
    -------
    str
        The reordered document. Block contents are preserved exactly. The
        separators between blocks are replaced with the most common separator
        in the input, so indentation is consistent in the output.

    Raises
    ------
    ValueError
        If the document has no servers, or a server has no position.
    """
    matches = list(ITEM_RE.finditer(text))
    if not matches:
        raise ValueError("no ServerItem blocks found")

    blocks = []
    for match in matches:
        (server_id,) = ids_in_order(match.group(0))
        if server_id not in positions:
            raise ValueError(f"no add history for server {server_id}")
        blocks.append((positions[server_id], match.group(0)))

    separators = [
        text[a.end():b.start()] for a, b in zip(matches, matches[1:])
    ]
    if separators:
        dominant = Counter(separators).most_common(1)[0][0]
        separators = [dominant] * len(separators)
    ordered = [block for _, block in sorted(blocks, key=lambda pair: pair[0])]

    out = [text[: matches[0].start()]]
    for index, block in enumerate(ordered):
        out.append(block)
        if index < len(separators):
            out.append(separators[index])
    out.append(text[matches[-1].end():])
    return "".join(out)


def main(argv):
    """Reorder the file given on the command line.

    Parameters
    ----------
    argv : list of str
        Command-line arguments, where ``argv[0]`` is the program name.

    Returns
    -------
    int
        0 on success, 2 on bad arguments or unusable input.
    """
    if len(argv) != 2:
        print("usage: reorder_servers.py <path-to-Servers.xml>", file=sys.stderr)
        return 2

    path = argv[1]
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()

    try:
        positions = latest_add_positions(ids_by_commit(path))
        reordered = reorder_text(text, positions)
    except (ValueError, subprocess.CalledProcessError, ET.ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(reordered)

    print(f"Reordered {len(ITEM_RE.findall(text))} servers in {path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
