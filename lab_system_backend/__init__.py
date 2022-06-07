import pymysql
pymysql.install_as_MySQLdb()

from task_tools.task_refresh_calibration_state import init_refresh_task
from task_tools.task_remind_return import init_remind_return
from task_tools.task_refresh_currency_rate import init_refresh_currency

import platform
import portalocker


def init_uniq():
    """
    只初始化一次的任务
    """
    init_refresh_task()
    init_remind_return()
    # init_refresh_currency()


if platform.system() == "Windows":
    f = open('lock.txt', 'w')
    try:
        portalocker.lock(f, portalocker.LOCK_EX | portalocker.LOCK_NB)  # 加锁
        init_uniq()
    except:
        print('lock have another instance running')
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
