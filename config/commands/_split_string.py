#!/usr/bin/env python3

"""This helper command is used to print flake8 output"""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass
class Flake8Error:
    """A class to represent a single flake8 error"""

    filename: str
    line_number: int
    col_number: int
    problem: str

    @classmethod
    def from_line(cls, line: str):
        prefix, _sep, problem = line.partition(": ")
        filename, line_number, col_number = prefix.split(":")
        return cls(filename, int(line_number), int(col_number), problem)


def _update_previous_errors(
    previous_errors: list[Flake8Error], replacement_window: tuple[int, int], replacement_n_lines: int
) -> list[Flake8Error]:
    """Update the line numbers of the previous errors to what they would be after the edit window.
    This is a helper function for `_filter_previous_errors`.

    All previous errors that are inside of the edit window should not be ignored,
    so they are removed from the previous errors list.

    Args:
        previous_errors: list of errors with old line numbers
        replacement_window: the window of the edit/lines that will be replaced
        replacement_n_lines: the number of lines that will be used to replace the text

    Returns:
        list of errors with updated line numbers
    """
    updated = []
    lines_added = replacement_n_lines - (replacement_window[1] - replacement_window[0] + 1)
    for error in previous_errors:
        if error.line_number < replacement_window[0]:
            # no need to adjust the line number
            updated.append(error)
            continue
        if replacement_window[0] <= error.line_number <= replacement_window[1]:
            # The error is within the edit window, so let's not ignore it
            # either way (we wouldn't know how to adjust the line number anyway)
            continue
        # We're out of the edit window, so we need to adjust the line number
        updated.append(Flake8Error(error.filename, error.line_number + lines_added, error.col_number, error.problem))
    return updated


def format_flake8_output(
    input_string: str,
    show_line_numbers: bool = False,
    *,
    previous_errors_string: str = "",
    replacement_window: tuple[int, int] | None = None,
    replacement_n_lines: int | None = None,
) -> str:
    """Filter flake8 output for previous errors and print it for a given file.

    Args:
        input_string: The flake8 output as a string
        show_line_numbers: Whether to show line numbers in the output
        previous_errors_string: The previous errors as a string
        replacement_window: The window of the edit (lines that will be replaced)
        replacement_n_lines: The number of lines used to replace the text

    Returns:
        The filtered flake8 output as a string
    """
    errors = [Flake8Error.from_line(line.strip()) for line in input_string.split("\n") if line.strip()]
    lines = []
    if previous_errors_string:
        assert replacement_window is not None
        assert replacement_n_lines is not None
        previous_errors = [
            Flake8Error.from_line(line.strip()) for line in previous_errors_string.split("\n") if line.strip()
        ]
        previous_errors = _update_previous_errors(previous_errors, replacement_window, replacement_n_lines)
        errors = [error for error in errors if error not in previous_errors]
    for error in errors:
        if not show_line_numbers:
            line = f"- {error.problem}"
        else:
            line = f"- {error.line_number}:{error.col_number} {error.problem}"
        if line not in lines:
            # Make sure we don't have duplicates
            lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_string", type=str, help="The flake8 output as a string")
    parser.add_argument("--previous", type=str, default="", help="The previous errors as a string")
    parser.add_argument("--window", type=int, nargs=2, default=None, help="The window of the edit")
    parser.add_argument("--n-lines", type=int, default=None, help="The number of lines used to replace the text")
    parser.add_argument("--line-numbers", action="store_true", help="Whether to show line numbers in the output")
    args = parser.parse_args()

    if not args.previous:
        print(format_flake8_output(args.input_string))
    else:
        print(
            format_flake8_output(
                args.input_string,
                previous_errors_string=args.previous,
                replacement_window=args.window,
                replacement_n_lines=args.n_lines,
                show_line_numbers=args.line_numbers,
            )
        )
