from __future__ import annotations

from sweagent.agent.history_processors import (
    DefaultHistoryProcessor,
    LastNObservations,
    MaxNObservations,
    StripFailedEdits,
)


def string_to_history(string: str) -> list[dict]:
    history = []
    for line in string.split("\n"):
        line = line.strip()
        if not line:
            continue
        role = "user"
        is_demo = False
        content = line
        for _role in ["system", "assistant"]:
            if line.startswith(_role):
                role = _role
                content = line.removeprefix(_role).strip()
        if line.startswith("demo:"):
            is_demo = True
            content = line.removeprefix("demo:").strip()
        history.append({"role": role, "content": content, "is_demo": is_demo})
    return history


HISTORY_1 = string_to_history("""
system:Welcome to the SWE-Agent!
demo: This is a demo message
1
2
3
4
5
6
7
8
9
10
""")

HISTORY_2 = string_to_history("""
system:Welcome to the SWE-Agent!
demo: This is a demo message
1 VERY LONG
assistant: VERY LONG
3
4 VERY LONG
5
6 VERY LONG
7
8 VERY LONG
9
10 VERY LONG
""")


HISTORY_3 = string_to_history("""
system:Welcome to the SWE-Agent!
demo: This is a demo message
1 VERY LONG
assistant: VERY LONG
3
4 VERY LONG
5
6 VERY LONG
7 Your proposed edit has introduced new syntax error
8 Your proposed edit has introduced new syntax error
9
10 Your proposed edit has introduced new syntax error
""")

ALL_HISTORIES = [HISTORY_1, HISTORY_2, HISTORY_3]


def test_default_hp():
    hp = DefaultHistoryProcessor()
    for h in ALL_HISTORIES:
        assert hp(h) == h


def test_only_n_outputs():
    one = MaxNObservations(n=2, max_age=5, long_output_char_thld=4)
    assert one(HISTORY_1) == HISTORY_1
    assert one(HISTORY_2) == string_to_history("""
        system:Welcome to the SWE-Agent!
        demo: This is a demo message
        1 VERY LONG
        assistant: VERY LONG
        3
        Old output omitted (1 lines)
        5
        Old output omitted (1 lines)
        7
        8 VERY LONG
        9
        10 VERY LONG
        """)


def test_only_n_outputs_young():
    one = MaxNObservations(n=5, max_age=2, long_output_char_thld=4)
    assert one(HISTORY_1) == HISTORY_1
    assert one(HISTORY_2) == string_to_history("""
        system:Welcome to the SWE-Agent!
        demo: This is a demo message
        1 VERY LONG
        assistant: VERY LONG
        3
        Old output omitted (1 lines)
        5
        Old output omitted (1 lines)
        7
        8 VERY LONG
        9
        10 VERY LONG
        """)


def test_only_n_outputs_long_long():
    one = MaxNObservations(n=5, max_age=5, long_output_char_thld=100)
    for h in ALL_HISTORIES:
        assert one(h) == h


def test_strip_failed_edits():
    sfe = StripFailedEdits()
    assert sfe(HISTORY_1) == HISTORY_1
    assert sfe(HISTORY_2) == HISTORY_2
    assert sfe(HISTORY_3) == string_to_history("""
        system:Welcome to the SWE-Agent!
        demo: This is a demo message
        1 VERY LONG
        assistant: VERY LONG
        3
        4 VERY LONG
        5
        6 VERY LONG
        Output of failed edit omitted.
        Output of failed edit omitted.
        9
        10 Your proposed edit has introduced new syntax error
        """)


def test_last_n_observations():
    lno = LastNObservations(n=5)
    print(lno(HISTORY_1))
    assert lno(HISTORY_1) == string_to_history("""
        system:Welcome to the SWE-Agent!
        demo: This is a demo message
        1
        Old output omitted (1 lines)
        Old output omitted (1 lines)
        Old output omitted (1 lines)
        Old output omitted (1 lines)
        6
        7
        8
        9
        10
    """)
