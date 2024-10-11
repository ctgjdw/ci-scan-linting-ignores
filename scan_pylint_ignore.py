import csv
import re
import sys
from argparse import ArgumentParser
from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import List, Optional


logger = Logger("scan-pylint-ignore")
PYLINT_IGNORE_PATTERN = re.compile(
    r".*#\s*pylint\s*:\s*disable(?:-next)?\s*=\s*([a-zA-Z-]+)(?: (.+))?$"
)
PYTHON_COMMENT_PATTERN = re.compile(r"#\s*(.+)$")


@dataclass
class Ignore:
    filepath: Path
    start: int
    end: int
    issue: str
    reason: List[str]

    @property
    def keys(self) -> tuple[str, str, str, str]:
        return ("File", "Line section", "Pylint issue", "Reason")

    @property
    def values(self) -> dict[str, str]:
        reason = " ".join(self.reason) if self.reason else "(No reason provided)"
        return {
            "File": str(self.filepath),
            "Line section": f"{self.start}-{self.end}",
            "Pylint issue": self.issue,
            "Reason": reason,
        }


def parse_args():
    parser = ArgumentParser(
        description="Helper script to detect pylint ignores within all Python files within"
        " a directory, and formats it as a report"
    )

    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Path to a Python file, or a directory of python files. Defaults to the current directory.",
    )

    parser.add_argument(
        "-O",
        "--output-dir",
        type=Path,
        help="The directory to save the generated report. Omit this flag if you want to print the results in the console.",
    )

    parser.add_argument(
        "-I",
        "--ignore-dirs",
        type=str,
        help="The list of directories to ignore. The application will not search. The list should be comma-seperated.",
    )

    parser.add_argument(
        "-v",
        "--verify",
        action="store_true",
        help="Enable to only verify that all Pylint ignores is accompanied by a reason. (Default: False)",
    )

    return parser.parse_args()


def get_reason(rematch: re.Match, line_number: int, lines: List[str]) -> List[str]:
    reasons: List[str] = []
    previous_line = lines[line_number - 2]

    if comment_match := PYTHON_COMMENT_PATTERN.match(previous_line):
        reasons.append(comment_match.group(1).strip())

    if reason := rematch.group(2):
        reasons.append(reason.strip())

    return reasons


def find_ignores(filepath: Path) -> List[Ignore]:
    ignores: List[Ignore] = []
    ignore: Optional[Ignore] = None
    with filepath.open("r", encoding="utf-8") as file:
        lines = file.readlines()

    gen = enumerate(lines, start=1)

    while True:
        try:
            line_number, line = next(gen)
            line = line.strip()
            if rematch := PYLINT_IGNORE_PATTERN.match(line):
                if ignore is not None:
                    # add current buffered ignore into list
                    # before handling the newly detected ignore
                    ignores.append(ignore)

                ignore = Ignore(
                    filepath,
                    line_number,
                    line_number,
                    rematch.group(1),
                    get_reason(rematch, line_number, lines),
                )

            elif (rematch := PYTHON_COMMENT_PATTERN.match(line)) and ignore is not None:
                # If justification continues below the original ignore stub
                ignore.end = line_number
                ignore.reason.append(rematch.group(1).strip())

            elif ignore is not None:
                ignores.append(ignore)
                ignore = None

        except StopIteration:
            if ignore is not None:
                ignores.append(ignore)
            break

    return ignores


def catch_bad_ignores(ignores: List[Ignore]):
    bad_ignores: List[Ignore] = [
        ignore
        for ignore in ignores
        if ignore.values["Reason"] == "(No reason provided)"
    ]

    if not bad_ignores:
        return

    logger.error(
        "ERROR: The following Pylint ignores were detected without any reasons for justification. "
        "Please ensure that a reason is given either in the same comment line, or in comments immediately below the original ignore."
    )

    for idx, ignore in enumerate(bad_ignores, start=1):
        logger.error(
            "%d. %s, lines %s",
            idx,
            ignore.values["File"],
            ignore.values["Line section"],
        )
    sys.exit(1)


def export(export_dir: Optional[Path], ignores: List[Ignore]):
    if export_dir is None:
        for ignore in ignores:
            values = ignore.values
            print(f"File: {values['File']}, lines {values['Line section']}")
            print(f"Pylint issue: {values['Pylint issue']}")
            print(f"Reason: {values['Reason']}")
            print()

    else:
        export_path = export_dir / "pylint-ignores.csv"
        with export_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, ignores[0].keys)
            writer.writeheader()

            for ignore in ignores:
                writer.writerow(ignore.values)


def main():
    args = parse_args()
    path: Path = args.path
    export_dir: Optional[Path] = args.output_dir
    ignore_dirs: List[Path] = []

    if (ignore_dirs_str := args.ignore_dirs) is not None:
        ignore_dirs = [Path(string.strip()) for string in ignore_dirs_str.split(",")]

    if export_dir is None:
        logger.warning(
            "WARNING: No output directory was specified, issues will be printed in the console."
        )
    if export_dir and not export_dir.exists():
        logger.info("Creating export directory: %s", export_dir.resolve())
        export_dir.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        logger.error("ERROR: Specified path '%s' does not exist", path.resolve())
        sys.exit(1)

    ignores: List[Ignore] = []
    file_count = 0

    if path.is_file():
        ignores.extend(find_ignores(path))
        file_count += 1
    else:
        for filepath in path.glob("**/*.py"):
            if any([filepath.is_relative_to(path) for path in ignore_dirs]):
                continue
            ignores.extend(find_ignores(filepath))
            file_count += 1

    if not ignores:
        logger.info("INFO: No pylint ignores detected.")
        sys.exit(0)

    logger.warning(
        "WARNING: %d instance%s of Pylint ignores were detected across %d file%s, please assess if they are still relevant.",
        len(ignores),
        "" if len(ignores) == 1 else "s",
        file_count,
        "" if file_count == 1 else "s",
    )

    if args.verify:
        catch_bad_ignores(ignores)

    export(export_dir, ignores)


if __name__ == "__main__":
    main()
