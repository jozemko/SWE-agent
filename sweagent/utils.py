
import datetime
from inspect import currentframe


_LAST_TIME = datetime.datetime.now()


def debug_time(name=""):
    """Display time delta at line number"""
    cf = currentframe()
    line_no = cf.f_back.f_lineno
    global _LAST_TIME
    time_delta = datetime.datetime.now() - _LAST_TIME
    _LAST_TIME = datetime.datetime.now()
    print(f"Time: {time_delta} at line {line_no} ({name=})") 