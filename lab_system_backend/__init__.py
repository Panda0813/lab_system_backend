from task_tools.task_refresh_calibration_state import init_refresh_task
from task_tools.task_remind_return import init_remind_return
from task_tools.task_refresh_currency_rate import init_refresh_currency
from utils.conn_mssql import get_mssql_conn

import platform

mssql_conn = None


def init_public_var():
    global mssql_conn
    mssql_conn = get_mssql_conn()


# init_public_var()


def init_uniq():
    """
    只初始化一次的任务
    """
    init_refresh_task()
    init_remind_return()
    init_refresh_currency()


if platform.system() == "Windows":
    init_uniq()
    pass
else:
    import fcntl
    import atexit
    f = open("scheduler.lock", "wb")

    def unlock():
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
    atexit.register(unlock)

    def init_ok():
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            init_uniq()
        except:
            pass
        pass
    init_ok()
