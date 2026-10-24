import os
import subprocess
import tempfile
import unittest

import reorder_servers as rs


def item(server_id, name="Name"):
    return (
        f"<ServerItem>\n"
        f"    <id>{server_id}</id>\n"
        f"    <name>{name}</name>\n"
        f"  </ServerItem>"
    )


def document(*items, separator="\n  "):
    body = separator.join(items)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<ArrayOfServerItem>\n  "
        f"{body}\n"
        "</ArrayOfServerItem>\n"
    )


class LatestAddPositionsTests(unittest.TestCase):
    def test_first_appearance_is_recorded(self):
        positions = rs.latest_add_positions([["a", "b"], ["a", "b", "c"]])
        self.assertEqual(positions, {"a": (0, 0), "b": (0, 1), "c": (1, 2)})

    def test_bulk_add_in_one_commit_keeps_file_order(self):
        positions = rs.latest_add_positions([["x", "y", "z"]])
        self.assertLess(positions["x"], positions["y"])
        self.assertLess(positions["y"], positions["z"])

    def test_removal_and_readd_resets_position(self):
        positions = rs.latest_add_positions([["a", "b"], ["b"], ["b", "a"]])
        self.assertEqual(positions["a"], (2, 1))
        self.assertEqual(positions["b"], (0, 1))

    def test_edits_do_not_change_position(self):
        # Same ids in later commits (e.g. description edits) add nothing new.
        positions = rs.latest_add_positions([["a"], ["a"], ["a"]])
        self.assertEqual(positions, {"a": (0, 0)})

    def test_reordering_within_history_does_not_count_as_add(self):
        positions = rs.latest_add_positions([["a", "b"], ["b", "a"]])
        self.assertEqual(positions, {"a": (0, 0), "b": (0, 1)})


class ReorderTextTests(unittest.TestCase):
    def test_blocks_are_sorted_by_position(self):
        text = document(item("b"), item("a"), item("c"))
        positions = {"a": (0, 0), "b": (0, 1), "c": (0, 2)}
        result = rs.reorder_text(text, positions)
        self.assertEqual(rs.ids_in_order(result), ["a", "b", "c"])

    def test_block_contents_are_preserved_byte_for_byte(self):
        original_blocks = [item("b", "Bee"), item("a", "Ay")]
        text = document(*original_blocks)
        positions = {"a": (0, 0), "b": (1, 0)}
        result = rs.reorder_text(text, positions)
        self.assertEqual(result, document(original_blocks[1], original_blocks[0]))

    def test_separators_are_normalized_to_dominant_indentation(self):
        text = document(item("b"), item("a"), item("c"), item("d"))
        # One odd separator (4 spaces) before c; the other separators use 2.
        text = text.replace("</ServerItem>\n  <ServerItem>\n    <id>c", "</ServerItem>\n    <ServerItem>\n    <id>c", 1)
        positions = {"a": (0, 0), "b": (0, 1), "c": (0, 2), "d": (0, 3)}
        result = rs.reorder_text(text, positions)
        self.assertEqual(result, document(item("a"), item("b"), item("c"), item("d")))

    def test_header_footer_and_separators_stay_put(self):
        text = document(item("b"), item("a"), separator="\n\n  ")
        positions = {"a": (0, 0), "b": (1, 0)}
        result = rs.reorder_text(text, positions)
        self.assertTrue(result.startswith('<?xml version="1.0" encoding="utf-8"?>\n<ArrayOfServerItem>\n  '))
        self.assertTrue(result.endswith("\n</ArrayOfServerItem>\n"))
        self.assertIn("</ServerItem>\n\n  <ServerItem>", result)

    def test_reorder_is_a_fixed_point(self):
        text = document(item("c"), item("a"), item("b"))
        positions = {"a": (0, 0), "b": (0, 1), "c": (0, 2)}
        once = rs.reorder_text(text, positions)
        twice = rs.reorder_text(once, positions)
        self.assertEqual(once, twice)

    def test_missing_position_raises(self):
        text = document(item("a"), item("unknown"))
        with self.assertRaises(ValueError):
            rs.reorder_text(text, {"a": (0, 0)})

    def test_empty_document_raises(self):
        with self.assertRaises(ValueError):
            rs.reorder_text('<?xml version="1.0"?><ArrayOfServerItem/>', {})


class IdsByCommitTests(unittest.TestCase):
    """Uses a real git repository so the history reading is exercised end to end."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = self._tmp.name
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        # Isolate from global git settings such as GPG signing and hooks.
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", os.devnull)

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True
        ).stdout

    def commit_text(self, message, text):
        path = os.path.join(self.repo, "Servers.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self.git("add", "Servers.xml")
        self.git("commit", "-q", "-m", message)

    def commit(self, message, *server_ids):
        self.commit_text(message, document(*(item(i) for i in server_ids)))

    def history(self):
        return rs.ids_by_commit("Servers.xml", cwd=self.repo)

    def test_reads_each_commit_oldest_first(self):
        self.commit("first", "a", "b")
        self.commit("second", "a", "b", "c")
        self.commit("third", "c", "a")
        self.assertEqual(self.history(), [["a", "b"], ["a", "b", "c"], ["c", "a"]])

    def test_malformed_xml_commit_is_still_counted(self):
        # Some real history has invalid XML; its servers must not be skipped.
        self.commit("first", "a")
        self.commit_text("malformed", document(item("b")).replace("</ServerItem>", "</ServerItem"))
        self.commit("third", "a", "b")
        self.assertEqual(self.history(), [["a"], ["b"], ["a", "b"]])

    def test_end_to_end_removal_and_readd(self):
        self.commit("add a and b", "a", "b")
        self.commit("remove a", "b")
        self.commit("re-add a", "b", "a")
        positions = rs.latest_add_positions(self.history())
        self.assertEqual(positions["a"], (2, 1))
        self.assertEqual(positions["b"], (0, 1))


if __name__ == "__main__":
    unittest.main()
