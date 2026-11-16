import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mock_detector import analyze


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "logic.py").write_text("def total(): return 1\ndef helper(): return 2\n")
        (self.root / "consumer.py").write_text("from logic import total as calculate\n")

    def inspect(self, text, **kwargs):
        path = self.root / "test_sample.py"
        path.write_text(text)
        return analyze(path, targets=["logic.total"], source_root=self.root, **kwargs)

    def test_decorator_alias_and_where_used(self):
        rows = self.inspect('from unittest.mock import patch as p\n@p("consumer.calculate")\ndef test_x(): pass\n')
        self.assertEqual(rows[0]["rule_id"], "OM001")
        self.assertEqual(rows[0]["resolved_target"], "logic.total")
        self.assertEqual(rows[0]["test"], "test_x")

    def test_object_and_mocker(self):
        rows = self.inspect('import logic as l\ndef test_x(mocker):\n mocker.patch.object(l, "total")\n mocker.patch("logic.helper")\n')
        self.assertEqual([r["rule_id"] for r in rows], ["OM001", "OM002"])

    def test_keyword_arguments(self):
        rows = self.inspect('from unittest import mock\nimport logic\nmock.patch(target="logic.total")\nmock.patch.object(target=logic, attribute="helper")\n')
        self.assertEqual([r["rule_id"] for r in rows], ["OM001", "OM002"])

    def test_boundary_and_unknown(self):
        rows = self.inspect('from unittest.mock import patch\npatch("logic.helper")\npatch("requests.get")\npatch(dynamic_name)\n', boundaries=["logic.helper"])
        self.assertEqual([r["status"] for r in rows], ["allowed", "unknown", "unknown"])

    def test_boundary_cannot_hide_declared_target(self):
        rows = self.inspect('from unittest.mock import patch\npatch("logic.total")\n', boundaries=["logic"])
        self.assertEqual(rows[0]["rule_id"], "OM001")

    def test_multiple_and_dict(self):
        rows = self.inspect('from unittest.mock import patch\npatch.multiple("logic", total=None, helper=None)\npatch.dict("os.environ", {"X": "1"})\n')
        self.assertEqual({r["rule_id"] for r in rows}, {"OM001", "OM002", "STATE_PATCH"})

    def test_local_object_unknown(self):
        rows = self.inspect('from unittest.mock import patch\ndef test_x():\n obj = factory()\n patch.object(obj, "total")\n')
        self.assertEqual(rows[0]["status"], "unknown")

    def test_no_mock_and_unrelated_patch(self):
        self.assertEqual(self.inspect('def test_x():\n assert 1 == 1\n'), [])
        self.assertEqual(self.inspect('from other import patch\npatch("logic.total")\n'), [])

    def test_async_and_local_import(self):
        rows = self.inspect('async def test_x():\n from unittest.mock import patch\n patch("logic.total")\n')
        self.assertEqual(rows[0]["rule_id"], "OM001")

    def test_cli_json_and_exit_codes(self):
        path = self.root / "test_cli.py"
        path.write_text('from unittest.mock import patch\npatch("logic.total")\n')
        result = subprocess.run([sys.executable, "-m", "mock_detector", str(path), "--target", "logic.total", "--format", "json", "--fail-on", "warning"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["findings"][0]["rule_id"], "OM001")
        path.write_text("def broken(\n")
        result = subprocess.run([sys.executable, "-m", "mock_detector", str(path), "--format", "json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(json.loads(result.stdout)["errors"])


if __name__ == "__main__":
    unittest.main()
