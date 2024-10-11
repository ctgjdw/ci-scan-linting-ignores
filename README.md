# Detect Code Ignores

This CLI script can be used in the `CI` pipeline to detect and report on ignores/inline ignores inserted via comments or config files. Reviewers can then review the report and factor this report into their MR/PR approvals.

## What is supported

1. `Python` projects, detects the following:
    - `pylint: disable`
    - `pylint: disable-next`
2. `TS/JS` projects, detects the following:
    - ignores in `.eslintignore`
    - `eslint-disable`
    - `eslint-disable-next-line`

## To run

For `Python`: `python scan_pylint_ignore.py`

For `TS/JS`: `python ./scan_eslint_ignore.py -E .eslintignore`

> Refer to `python scan_pylint_ignore.py --help` or `python scan_pylint_ignore.py --help` for more options
