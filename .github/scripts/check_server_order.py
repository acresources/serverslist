#!/usr/bin/env python3
"""Enforce that changes to Servers.xml only append new servers to the bottom.

Servers are identified by their ``<id>``, not their ``<name>``, because names
may change but ids must not. A change is allowed when:

* servers that existed in the base file keep their relative order
  (in-place edits such as description or status changes are fine, and
  servers may be removed), and
* every server that is new in the head file comes after all of the
  servers that were retained from the base file.

Within any file, each id must be unique.

Usage
-----
check_server_order.py <base-Servers.xml> <head-Servers.xml>

Exit codes
----------
0
    The change is valid.
1
    A duplicate id or an ordering violation was found.
2
    An input file could not be read or parsed, or the arguments are wrong.
"""

import sys
import xml.etree.ElementTree as ET


def read_ids(path):
    """Return the server ids in document order.

    Parameters
    ----------
    path : str
        Path to a Servers.xml file.

    Returns
    -------
    list of str
        The stripped ``<id>`` text of each ``ServerItem``, in document order.
        Duplicates are preserved.

    Raises
    ------
    ValueError
        If a ``ServerItem`` has no ``<id>`` or the id is empty.
    xml.etree.ElementTree.ParseError
        If the file is not well-formed XML.
    OSError
        If the file cannot be read.
    """
    root = ET.parse(path).getroot()
    ids = []
    for item in root.iter("ServerItem"):
        id_element = item.find("id")
        if id_element is None or not (id_element.text or "").strip():
            raise ValueError(f"{path}: ServerItem is missing a non-empty <id>")
        ids.append(id_element.text.strip())
    return ids


def find_duplicates(ids):
    """Return the ids that appear more than once.

    Parameters
    ----------
    ids : list of str
        Server ids in document order.

    Returns
    -------
    list of str
        Each duplicated id exactly once, sorted.
    """
    seen = set()
    duplicates = set()
    for server_id in ids:
        if server_id in seen:
            duplicates.add(server_id)
        seen.add(server_id)
    return sorted(duplicates)


def find_errors(base_ids, head_ids):
    """Return the ordering problems between a base and a head server list.

    Parameters
    ----------
    base_ids : list of str
        Server ids in the base file, in document order.
    head_ids : list of str
        Server ids in the head file, in document order.

    Returns
    -------
    list of str
        Human-readable descriptions of each violation. An empty list means
        the order is valid. Duplicate ids are not checked here; see
        `find_duplicates`.
    """
    errors = []

    base_set = set(base_ids)
    head_set = set(head_ids)

    retained_in_base_order = [i for i in base_ids if i in head_set]
    retained_in_head_order = [i for i in head_ids if i in base_set]
    if retained_in_base_order != retained_in_head_order:
        errors.append(
            "existing servers were reordered or moved; "
            "new servers must be appended to the bottom of the list"
        )

    last_retained_index = max(
        (index for index, i in enumerate(head_ids) if i in base_set), default=-1
    )
    for index, server_id in enumerate(head_ids):
        if server_id not in base_set and index < last_retained_index:
            errors.append(
                f"new server {server_id} was inserted above existing entries; "
                "new servers must be appended to the bottom of the list"
            )

    return errors


def main(argv):
    """Run the check from the command line.

    Parameters
    ----------
    argv : list of str
        Command-line arguments, where ``argv[0]`` is the program name.

    Returns
    -------
    int
        The process exit code (0, 1, or 2). See the module docstring.
    """
    if len(argv) != 3:
        print("usage: check_server_order.py <base-Servers.xml> <head-Servers.xml>", file=sys.stderr)
        return 2

    base_path, head_path = argv[1], argv[2]
    try:
        base_ids = read_ids(base_path)
        head_ids = read_ids(head_path)
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"::error::Could not read server list: {exc}")
        return 2

    duplicate_errors = [
        (path, f"duplicate server id {server_id}")
        for path, ids in ((base_path, base_ids), (head_path, head_ids))
        for server_id in find_duplicates(ids)
    ]
    for path, error in duplicate_errors:
        print(f"::error file={path}::{error}")
    if duplicate_errors:
        return 1

    errors = find_errors(base_ids, head_ids)
    for error in errors:
        print(f"::error file={head_path}::{error}")

    if errors:
        return 1

    print("Server order check passed: new servers are appended to the bottom.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
