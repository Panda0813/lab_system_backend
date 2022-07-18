import datetime
import calendar
from utils.timedelta_utls import get_holiday
import pandas as pd


def get_week_weekday(now_date):
    """本周的第一个工作日和最后一个工作日"""
    first_day = now_date
    one_day = datetime.timedelta(days=1)
    while first_day.weekday() != 0:
        first_day -= one_day
    last_day = first_day + datetime.timedelta(days=4)
    return first_day, last_day


def get_month_weekday(now_date):
    """本月的第一个工作日和最后一个工作日"""
    year = now_date.year
    month = now_date.month
    first_day = datetime.date(year, month, 1)
    total_days = calendar.monthrange(year, month)[1]
    last_day = datetime.date(year, month, total_days)
    list_holiday = get_holiday(year, 'date')
    if first_day in list_holiday:
        while first_day in list_holiday:
            first_day += datetime.timedelta(days=1)
    if last_day in list_holiday:
        while last_day in list_holiday:
            last_day -= datetime.timedelta(days=1)
    return first_day, last_day


def get_year_weekday(now_date):
    """本年的第一个工作日和最后一个工作日"""
    year = now_date.year
    first_day = datetime.date(year, 1, 1)
    last_day = datetime.date(year, 12, 31)
    list_holiday = get_holiday(year, 'date')
    if first_day in list_holiday:
        while first_day in list_holiday:
            first_day += datetime.timedelta(days=1)
    if last_day in list_holiday:
        while last_day in list_holiday:
            last_day -= datetime.timedelta(days=1)
    return first_day, last_day


def get_quarter_weekday(now_date):
    first_day = now_date + pd.tseries.offsets.DateOffset(months=-((now_date.month - 1) % 3), days=1 - now_date.day)
    last_day = now_date + pd.tseries.offsets.DateOffset(months=3-((now_date.month - 1) % 3), days=-now_date.day)
    first_day = first_day.date()
    last_day = last_day.date()
    list_holiday = get_holiday(now_date.year, 'date')
    if first_day in list_holiday:
        while first_day in list_holiday:
            first_day += datetime.timedelta(days=1)
    if last_day in list_holiday:
        while last_day in list_holiday:
            last_day -= datetime.timedelta(days=1)
    return first_day, last_day


def get_start_end(date_type):
    date_type_map = {
        'week': get_week_weekday,
        'month': get_month_weekday,
        'year': get_year_weekday,
        'quarter': get_quarter_weekday
    }

    now_date = datetime.date.today()
    func = date_type_map[date_type]
    first_day, last_day = func(now_date)
    first_day = datetime.datetime.strptime(str(first_day), '%Y-%m-%d') + datetime.timedelta(hours=9)
    last_day = datetime.datetime.strptime(str(last_day), '%Y-%m-%d') + datetime.timedelta(hours=19)
    return first_day, last_day


def get_week_weekday_(now_date):
    """本周的第一个工作日和最后一个工作日"""
    first_day = now_date
    one_day = datetime.timedelta(days=1)
    while first_day.weekday() != 0:
        first_day -= one_day
    last_day = first_day + datetime.timedelta(days=7)
    return first_day, last_day


def get_month_weekday_(now_date):
    """本月的第一个工作日和最后一个工作日"""
    year = now_date.year
    month = now_date.month
    first_day = datetime.date(year, month, 1)
    total_days = calendar.monthrange(year, month)[1]
    last_day = datetime.date(year, month, total_days) + datetime.timedelta(days=1)
    return first_day, last_day


def get_year_weekday_(now_date):
    """本年的第一个工作日和最后一个工作日"""
    year = now_date.year
    first_day = datetime.date(year, 1, 1)
    last_day = datetime.date(year, 12, 31) + datetime.timedelta(days=1)
    return first_day, last_day


def get_quarter_weekday_(now_date):
    first_day = now_date + pd.tseries.offsets.DateOffset(months=-((now_date.month - 1) % 3), days=1 - now_date.day)
    last_day = now_date + pd.tseries.offsets.DateOffset(months=3-((now_date.month - 1) % 3), days=-now_date.day)
    first_day = first_day.date()
    last_day = last_day.date() + datetime.timedelta(days=1)
    return first_day, last_day


def get_start_end_(date_type):
    date_type_map = {
        'week': get_week_weekday_,
        'month': get_month_weekday_,
        'year': get_year_weekday_,
        'quarter': get_quarter_weekday_
    }

    now_date = datetime.date.today()
    func = date_type_map[date_type]
    first_day, last_day = func(now_date)
    first_day = datetime.datetime.strptime(str(first_day), '%Y-%m-%d') + datetime.timedelta(hours=0)
    last_day = datetime.datetime.strptime(str(last_day), '%Y-%m-%d') + datetime.timedelta(hours=0)
    return first_day, last_day
