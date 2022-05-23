from dateutil.relativedelta import relativedelta

import datetime
import time
import os


def get_last_month():
    now_date = datetime.datetime.now().date()
    last_month = now_date + relativedelta(months=-1)
    return last_month.year, last_month.month


def create_suffix():
    ts = time.time()
    suffix = str(int(round(ts, 5) * 10**5))[:15]
    return suffix


def get_file_path(prefix, dir_name='report_files'):
    current_path = os.path.dirname(__file__)
    file_dir = os.path.join(current_path, dir_name)
    if not os.path.exists(file_dir):
        os.mkdir(file_dir)

    file_name = '{}-{}'.format(prefix, create_suffix())
    file_path = os.path.join(file_dir, file_name)
    return file_path
