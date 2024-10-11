import unittest
from unittest.mock import patch
from io import StringIO
from pathlib import Path

from scan_eslint_ignore import main


class TestScanEslintIgnore(unittest.TestCase):

    def setUp(self) -> None:
        self.maxDiff = None

    def tearDown(self) -> None:
        Path("test/output/eslint-ignores.csv").unlink(missing_ok=True)

    @patch("sys.stdout", new_callable=StringIO)
    @patch(
        "sys.argv", new=["test/input/ts_ignore.ts", "-E", "./test/input/.eslintignore"]
    )
    def test_given_code_4_ignores_generate_valid_stdout(self, mock_stdout):
        main()
        test_output = mock_stdout.getvalue().strip()
        with open("test/output/ts_result_stdout", encoding="utf8") as file:
            expected_output = file.read().strip()
            self.assertEqual(test_output, expected_output)

    @patch(
        "sys.argv",
        new=[
            "test/input/ts_ignore.py",
            "-O",
            "test/output",
            "-E",
            "./test/input/.eslintignore",
        ],
    )
    def test_given_code_4_ignores_generate_valid_report(self):
        main()
        with open("test/output/eslint-ignores.csv", encoding="utf8") as file:
            result = file.read().strip()

        with open("test/output/ts_result_csv", encoding="utf8") as file:
            expected = file.read().strip()

        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
