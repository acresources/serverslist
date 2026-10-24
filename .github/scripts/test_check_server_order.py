import os
import tempfile
import textwrap
import unittest

import check_server_order as cso


def server_xml(server_id, name="Name"):
    return textwrap.dedent(f"""\
        <ServerItem>
          <id>{server_id}</id>
          <name>{name}</name>
        </ServerItem>
        """)


def server_list(*server_ids):
    body = "".join(server_xml(i) for i in server_ids)
    return f'<?xml version="1.0" encoding="utf-8"?>\n<ArrayOfServerItem>\n{body}</ArrayOfServerItem>\n'


class FindErrorsTests(unittest.TestCase):
    def test_unchanged_list_is_valid(self):
        self.assertEqual(cso.find_errors(["a", "b", "c"], ["a", "b", "c"]), [])

    def test_appending_one_server_is_valid(self):
        self.assertEqual(cso.find_errors(["a", "b"], ["a", "b", "c"]), [])

    def test_appending_several_servers_is_valid(self):
        self.assertEqual(cso.find_errors(["a", "b"], ["a", "b", "c", "d"]), [])

    def test_empty_base_allows_any_new_list(self):
        self.assertEqual(cso.find_errors([], ["x", "y"]), [])

    def test_inserting_at_top_is_rejected(self):
        errors = cso.find_errors(["a", "b"], ["new", "a", "b"])
        self.assertEqual(len(errors), 1)
        self.assertIn("new server new was inserted above", errors[0])

    def test_inserting_in_middle_is_rejected(self):
        errors = cso.find_errors(["a", "b"], ["a", "new", "b"])
        self.assertEqual(len(errors), 1)
        self.assertIn("new server new was inserted above", errors[0])

    def test_swapping_two_existing_servers_is_rejected(self):
        errors = cso.find_errors(["a", "b", "c"], ["b", "a", "c"])
        self.assertTrue(any("reordered or moved" in e for e in errors))

    def test_moving_existing_server_to_bottom_is_rejected(self):
        errors = cso.find_errors(["a", "b", "c"], ["b", "c", "a"])
        self.assertTrue(any("reordered or moved" in e for e in errors))

    def test_removing_a_server_is_valid(self):
        self.assertEqual(cso.find_errors(["a", "b", "c"], ["a", "c"]), [])

    def test_removing_last_server_then_appending_is_valid(self):
        self.assertEqual(cso.find_errors(["a", "b", "c"], ["a", "b", "d"]), [])

    def test_removing_and_inserting_above_remaining_is_rejected(self):
        errors = cso.find_errors(["a", "b", "c"], ["new", "a", "c"])
        self.assertTrue(any("inserted above" in e for e in errors))

    def test_multiple_new_servers_inserted_above_are_each_reported(self):
        errors = cso.find_errors(["a"], ["n1", "n2", "a"])
        self.assertEqual(len([e for e in errors if "inserted above" in e]), 2)


class FindDuplicatesTests(unittest.TestCase):
    def test_no_duplicates(self):
        self.assertEqual(cso.find_duplicates(["a", "b", "c"]), [])

    def test_empty_list(self):
        self.assertEqual(cso.find_duplicates([]), [])

    def test_single_duplicate(self):
        self.assertEqual(cso.find_duplicates(["a", "b", "a"]), ["a"])

    def test_triple_occurrence_reported_once(self):
        self.assertEqual(cso.find_duplicates(["a", "a", "a"]), ["a"])

    def test_multiple_duplicates_are_sorted(self):
        self.assertEqual(cso.find_duplicates(["c", "b", "a", "b", "c"]), ["b", "c"])


class ReadIdsTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def write(self, content):
        path = os.path.join(self._tmpdir.name, "Servers.xml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_returns_ids_in_document_order(self):
        path = self.write(server_list("b", "a", "c"))
        self.assertEqual(cso.read_ids(path), ["b", "a", "c"])

    def test_trims_whitespace_around_ids(self):
        path = self.write(server_list("  abc  "))
        self.assertEqual(cso.read_ids(path), ["abc"])

    def test_missing_id_raises(self):
        path = self.write(
            '<?xml version="1.0"?><ArrayOfServerItem><ServerItem><name>x</name></ServerItem></ArrayOfServerItem>'
        )
        with self.assertRaises(ValueError):
            cso.read_ids(path)

    def test_empty_id_raises(self):
        path = self.write(
            '<?xml version="1.0"?><ArrayOfServerItem><ServerItem><id>  </id></ServerItem></ArrayOfServerItem>'
        )
        with self.assertRaises(ValueError):
            cso.read_ids(path)


class MainTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def write(self, name, content):
        path = os.path.join(self._tmpdir.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_description_edit_without_reordering_passes(self):
        base = self.write("base.xml", server_list("a", "b"))
        head = self.write("head.xml", server_list("a", "b").replace("Name", "Renamed", 1))
        self.assertEqual(cso.main(["check", base, head]), 0)

    def test_append_passes(self):
        base = self.write("base.xml", server_list("a", "b"))
        head = self.write("head.xml", server_list("a", "b", "c"))
        self.assertEqual(cso.main(["check", base, head]), 0)

    def test_insert_above_fails_with_exit_code_1(self):
        base = self.write("base.xml", server_list("a", "b"))
        head = self.write("head.xml", server_list("c", "a", "b"))
        self.assertEqual(cso.main(["check", base, head]), 1)

    def test_duplicate_in_head_fails(self):
        base = self.write("base.xml", server_list("a"))
        head = self.write("head.xml", server_list("a", "b", "b"))
        self.assertEqual(cso.main(["check", base, head]), 1)

    def test_duplicate_in_base_fails_even_if_head_is_fine(self):
        base = self.write("base.xml", server_list("a", "a"))
        head = self.write("head.xml", server_list("a"))
        self.assertEqual(cso.main(["check", base, head]), 1)

    def test_malformed_head_returns_exit_code_2(self):
        base = self.write("base.xml", server_list("a"))
        head = self.write("head.xml", "<ArrayOfServerItem><ServerItem>")
        self.assertEqual(cso.main(["check", base, head]), 2)

    def test_wrong_argument_count_returns_exit_code_2(self):
        self.assertEqual(cso.main(["check"]), 2)


if __name__ == "__main__":
    unittest.main()
