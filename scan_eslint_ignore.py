import csv
import re
import sys
from argparse import ArgumentParser
from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import List, Optional
from enum import Enum


logger = Logger("scan-eslint-ignore")

TS_COMMENT_PATTERN = re.compile(r".*//\s*(.+)")

ESLINT_IGNORE_ENTIRE_FILE_PATTERN = re.compile(
    r"^/\*\s*eslint-disable\s*([a-zA-Z@\-,\s\/]*)\s*\*/$"
)

ESLINT_INLINE_IGNORE_PATTERN = re.compile(
    r".*//\s*eslint-disable(?:-next)?-line\s*([a-zA-Z@\-,\s\/]*)\s*$"
)

TS_INLINE_IGNORE = re.compile(r"^//\s*\@ts-(?:ignore)?(?:expect-error)?")


class IgnoreType(Enum):
    ESLINT_IGNORE_ESLINTIGNORE = "ignore from .eslintignore"
    ESLINT_IGNORE_ENTIRE_FILE = "eslint-ignore (entire file)"
    ESLINT_IGNORE_SINGLE_LINE = "eslint-ignore (single line)"
    TSLINT_IGNORE_SINGLE_LINE = "ts-ignore (single line)"


SEARCH_IGNORE_TYPE_TUPLES = [
    ("/\\*\\s*eslint-disable", IgnoreType.ESLINT_IGNORE_ENTIRE_FILE),
    (
        ".*//\\s*eslint-disable",
        IgnoreType.ESLINT_IGNORE_SINGLE_LINE,
    ),
    ("@ts-", IgnoreType.TSLINT_IGNORE_SINGLE_LINE),
]


@dataclass
class Ignore:
    filepath: Path
    start: int
    end: int
    rule: Optional[str]
    reason: List[str]
    type: Optional[IgnoreType]

    @property
    def keys(self) -> tuple[str, str, str, str, str]:
        return ("File", "Line section", "Type", "Rule", "Reason")

    @property
    def values(self) -> dict[str, str]:
        if self.type is None:
            logger.error("Invalid Ignore.type")
            sys.exit(1)

        reason = " ".join(self.reason) if self.reason else "(No reason provided)"
        return {
            "File": str(self.filepath),
            "Line section": f"{self.start}-{self.end}",
            "Type": self.type.value,
            "Rule": self.rule if self.rule else "NA",
            "Reason": reason,
        }


def parse_args():
    parser = ArgumentParser(
        description="Helper script to detect eslint and ts ignores within all js/ts files within"
        " a directory, and formats it as a report"
    )

    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Path to a file, or a directory. Defaults to the current directory.",
    )

    parser.add_argument(
        "-E",
        "--eslint-ignore-path",
        type=Path,
        default=Path(".eslintignore"),
        help="Path to the .eslintignore file to scan for, if it exists.",
    )

    parser.add_argument(
        "-O",
        "--output-dir",
        type=Path,
        help="The directory to save the generated report. Omit this flag if you want to print the results in the console.",
    )

    parser.add_argument(
        "-F",
        "--file-ext",
        type=str,
        help="The list of extensions to search for ignores. The list should be comma-seperated.",
        default=".mjs,.js,.ts,.jsx,.tsx",
    )

    parser.add_argument(
        "-I",
        "--ignore-dirs",
        type=str,
        help="The list of directories to ignore. The application will not search. The list should be comma-seperated.",
        default="node_modules",
    )

    parser.add_argument(
        "-v",
        "--verify",
        action="store_true",
        help="Enable to only verify that all ignores is accompanied by a reason. (Default: False)",
    )

    return parser.parse_args()


def get_reason(line_number: int, lines: List[str]) -> List[str]:
    reasons: List[str] = []
    previous_line = lines[line_number - 2]

    if comment_match := TS_COMMENT_PATTERN.match(previous_line):
        reasons.append(comment_match.group(1).strip())

    return reasons


def get_ignore_type(match: re.Match[str]):
    for search_str, result in SEARCH_IGNORE_TYPE_TUPLES:
        if search_str in match.re.pattern:
            return result


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
            if rematch := (
                ESLINT_IGNORE_ENTIRE_FILE_PATTERN.match(line)
                or ESLINT_INLINE_IGNORE_PATTERN.match(line)
                or TS_INLINE_IGNORE.match(line)
            ):
                if ignore is not None:
                    # add current buffered ignore into list
                    # before handling the newly detected ignore
                    ignores.append(ignore)

                rule = None
                try:
                    rule: str = rematch.group(1).strip()
                except IndexError as err:
                    logger.debug("Unable to retrieve rule matching group: %s", str(err))

                ignore = Ignore(
                    filepath,
                    line_number,
                    line_number,
                    rule,
                    get_reason(line_number, lines),
                    get_ignore_type(rematch),
                )

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
        "ERROR: The following ignores were detected without any reasons for justification. "
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
            print(f"File: {values['File']}")
            print(f"Lines: {values['Line section']}")
            print(f"Type: {values['Type']}")
            print(f"Rule: {values['Rule']}")
            print(f"Reason: {values['Reason']}")
            print()

    else:
        export_path = export_dir / "eslint-ignores.csv"
        with export_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, ignores[0].keys)
            writer.writeheader()

            for ignore in ignores:
                writer.writerow(ignore.values)


def scan_eslint_ignore_file(ignore_file_path: Path) -> List[Ignore]:
    comment_pattern = re.compile(r"#\s*(.+)$")

    def get_reason_for_ignore_file(line_number: int, lines: List[str]):
        if line_number < 1:
            return []

        previous_line = lines[line_number - 1]
        if result := comment_pattern.match(previous_line):
            return [result.group(1).strip()]

    ignores = []
    if not ignore_file_path.exists():
        return ignores

    with ignore_file_path.open(encoding="utf8") as file:
        lines = [input.strip() for input in file.readlines()]

    for line_number, line in enumerate(lines):
        if comment_pattern.match(line) or not line:
            continue
        ignores.append(
            Ignore(
                line,
                line_number + 1,
                line_number + 1,
                None,
                get_reason_for_ignore_file(line_number, lines),
                IgnoreType.ESLINT_IGNORE_ESLINTIGNORE,
            )
        )

    return ignores


def main():
    args = parse_args()
    path: Path = args.path
    extensions = [ext.strip() for ext in args.file_ext.split(",")]
    export_dir: Optional[Path] = args.output_dir
    eslint_ignore_file_path: Path = args.eslint_ignore_path
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

    ignores_in_file = scan_eslint_ignore_file(eslint_ignore_file_path)
    ignores.extend(ignores_in_file)

    if path.is_file():
        ignores.extend(find_ignores(path))
        file_count += 1
    else:
        paths = [
            filepath for filepath in path.glob("**/*") if filepath.suffix in extensions
        ]
        for file in paths:
            if any([file.is_relative_to(path) for path in ignore_dirs]):
                continue
            ignores.extend(find_ignores(file))
            file_count += 1

    if not ignores:
        logger.info("INFO: No ignores detected.")
        sys.exit(0)

    logger.warning(
        "WARNING: %d instance%s of ignores were detected across %d file%s, please assess if they are still relevant.",
        len(ignores) - len(ignores_in_file),
        "" if len(ignores) == 1 else "s",
        file_count,
        "" if file_count == 1 else "s",
    )

    if args.verify:
        catch_bad_ignores(ignores)

    export(export_dir, ignores)


if __name__ == "__main__":
    main()
