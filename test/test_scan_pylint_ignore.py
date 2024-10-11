import unittest
from unittest.mock import patch
from io import StringIO
from pathlib import Path

from scan_pylint_ignore import main


class TestScanPylintIgnore(unittest.TestCase):

    def setUp(self) -> None:
        self.maxDiff = None

    def tearDown(self) -> None:
        Path("test/output/pylint-ignores.csv").unlink(missing_ok=True)

    @patch("sys.stdout", new_callable=StringIO)
    @patch("sys.argv", new=["test/input/py_ignore.py"])
    def test_given_code_4_ignores_generate_valid_stdout(self, mock_stdout):
        self.maxDiff = None
        main()
        test_output = mock_stdout.getvalue().strip()
        with open("test/output/py_result_stdout", encoding="utf8") as file:
            expected_output = file.read().strip()
            self.assertEqual(test_output, expected_output)

    @patch("sys.argv", new=["test/input/py_ignore.py", "-O", "test/output"])
    def test_given_code_4_ignores_generate_valid_report(self):
        self.maxDiff = None
        main()
        with open("test/output/pylint-ignores.csv", encoding="utf8") as file:
            result = file.read().strip()

        with open("test/output/py_result_csv", encoding="utf8") as file:
            expected = file.read().strip()

        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
