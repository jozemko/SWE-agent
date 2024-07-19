from __future__ import annotations

import copy
import re
from abc import abstractmethod
from dataclasses import dataclass


class FormatError(Exception):
    pass


# ABSTRACT BASE CLASSES


class HistoryProcessorMeta(type):
    _registry = {}

    def __new__(cls, name, bases, attrs):
        new_cls = super().__new__(cls, name, bases, attrs)
        if name != "HistoryProcessor":
            cls._registry[name] = new_cls
        return new_cls


@dataclass
class HistoryProcessor(metaclass=HistoryProcessorMeta):
    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    def __call__(self, history: list[dict]) -> list[dict]:
        raise NotImplementedError

    @classmethod
    def get(cls, name, *args, **kwargs):
        try:
            return cls._registry[name](*args, **kwargs)
        except KeyError:
            msg = f"Model output parser ({name}) not found."
            raise ValueError(msg)


# DEFINE NEW PARSING FUNCTIONS BELOW THIS LINE
class DefaultHistoryProcessor(HistoryProcessor):
    def __call__(self, history):
        """This history processor returns the identical history"""
        return history


class StripFailedEdits(HistoryProcessor):
    def __init__(self):
        """Strip output from failed edits"""

    def _is_failed_edit(self, entry: dict) -> bool:
        if entry["role"] != "user":
            return False
        if entry.get("demo", False):
            return False
        if "Your proposed edit has introduced new syntax error" in entry["content"]:
            return True
        return False

    def _process_entry(self, entry: dict) -> dict:
        if self._is_failed_edit(entry):
            entry["content"] = "Output of failed edit omitted."
        return entry

    def __call__(
        self,
        history: list[dict],
    ) -> list[dict]:
        history = copy.deepcopy(history)
        # Never strip the last failed edit
        return [self._process_entry(entry) for entry in history[:-1]] + [history[-1]]


class MaxNObservations(HistoryProcessor):
    def __init__(self, n: int, *, max_age: int, long_output_char_thld: int = 200):
        """This is similar to the `LastNObservations`, except that we do not touch any
        "short" outputs (anything shorter than `long_output_char_thld` characters).

        Starting from the last step, we will keep the output if

        1) We have kept less than `n` outputs so far
        2) The step is within the last `max_age` steps
        """
        self.n = n
        self.max_age = max_age
        self.long_output_char_thld = long_output_char_thld

    def _strip_observation(self, entry: dict) -> dict:
        entry["content"] = f'Old output omitted ({len(entry["content"].splitlines())} lines)'
        return entry

    def __call__(self, history: list[dict]) -> list[dict]:
        history = copy.deepcopy(history)
        new_history = list()
        user_messages = [entry for entry in history if (entry["role"] == "user" and not entry.get("is_demo", False))]
        n_user_messages = len(user_messages)
        n_long_ums = len([entry for entry in user_messages if len(entry["content"]) > self.long_output_char_thld])
        user_msg_idx = 0
        n_long_added = 0
        for entry in history:
            data = entry.copy()
            if data["role"] != "user":
                new_history.append(entry)
                continue
            if data.get("is_demo", False):
                new_history.append(entry)
                continue
            else:
                user_msg_idx += 1
            if user_msg_idx == 1:
                # Issue text
                new_history.append(entry)
                continue
            # Will be 0 for last user message, because user_msg_idx is 1-based
            age = n_user_messages - user_msg_idx
            n_remaining = n_long_ums - n_long_added
            if (n_remaining > self.n or age > self.max_age) and len(entry["content"]) > self.long_output_char_thld:
                self._strip_observation(entry)
            else:
                n_long_added += 1
            new_history.append(entry)
        return new_history


def last_n_history(history: list[dict], n: int) -> list[dict]:
    """Strip all observations except for the last n messages"""
    if n <= 0:
        msg = "n must be a positive integer"
        raise ValueError(msg)
    new_history = list()
    user_messages = len([entry for entry in history if (entry["role"] == "user" and not entry.get("is_demo", False))])
    user_msg_idx = 0
    for entry in history:
        data = entry.copy()
        if data["role"] != "user":
            new_history.append(entry)
            continue
        if data.get("is_demo", False):
            new_history.append(entry)
            continue
        else:
            user_msg_idx += 1
        # user_msg_idx 1 is the issue template
        if user_msg_idx == 1 or user_msg_idx in range(user_messages - n + 1, user_messages + 1):
            new_history.append(entry)
        else:
            data["content"] = f'Old output omitted ({len(entry["content"].splitlines())} lines)'
            new_history.append(data)
    return new_history


class Max5ObservationsNoFE(HistoryProcessor):
    def __call__(self, history: list[dict]) -> list[dict]:
        return MaxNObservations(n=5, max_age=10, long_output_char_thld=200)(StripFailedEdits()(history))


class LastNObservations(HistoryProcessor):
    def __init__(self, n):
        self.n = n

    def __call__(self, history):
        return last_n_history(history, self.n)


class Last2Observations(HistoryProcessor):
    def __call__(self, history):
        return last_n_history(history, 2)


class Last5Observations(HistoryProcessor):
    def __call__(self, history):
        return last_n_history(history, 5)


class Last5ObservationsNoFE(HistoryProcessor):
    def __call__(self, history):
        return last_n_history(StripFailedEdits()(history), 5)


class ClosedWindowHistoryProcessor(HistoryProcessor):
    pattern = re.compile(r"^(\d+)\:.*?(\n|$)", re.MULTILINE)
    file_pattern = re.compile(r"\[File:\s+(.*)\s+\(\d+\s+lines\ total\)\]")

    def __call__(self, history):
        new_history = list()
        # For each value in history, keep track of which windows have been shown.
        # We want to mark windows that should stay open (they're the last window for a particular file)
        # Then we'll replace all other windows with a simple summary of the window (i.e. number of lines)
        windows = set()
        for entry in reversed(history):
            data = entry.copy()
            if data["role"] != "user":
                new_history.append(entry)
                continue
            if data.get("is_demo", False):
                new_history.append(entry)
                continue
            matches = list(self.pattern.finditer(entry["content"]))
            if len(matches) >= 1:
                file_match = self.file_pattern.search(entry["content"])
                if file_match:
                    file = file_match.group(1)
                else:
                    continue
                if file in windows:
                    start = matches[0].start()
                    end = matches[-1].end()
                    data["content"] = (
                        entry["content"][:start]
                        + f"Outdated window with {len(matches)} lines omitted...\n"
                        + entry["content"][end:]
                    )
                windows.add(file)
            new_history.append(data)
        return list(reversed(new_history))
