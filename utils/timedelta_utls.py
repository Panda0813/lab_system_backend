from chinese_calendar import is_holiday
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta


def get_holiday(year, date_type):
    """得到某一年所有假期日"""
    list_holiday = []
    year = int(year)
    for month in range(1, 13):
        for day in range(1, 32):
            try:
                dt = date(year, month, day)
            except:
                break
            if is_holiday(dt):
                list_holiday.append('{}-{:02d}-{:02d}'.format(year, month, day))
    if date_type == 'datetime':
        list_holiday = list(map(lambda x: datetime.strptime(x, '%Y-%m-%d'), list_holiday))
    elif date_type == 'date':
        list_holiday = list(map(lambda x: datetime.strptime(x, '%Y-%m-%d').date(), list_holiday))
    return list_holiday


# 计算两个时间点中间的工作时间
def calculate_datediff_(start, end):
    delta_seconds = (end - start).total_seconds()
    hours = round((delta_seconds / 3600), 2)
    return hours


# 计算两个时间点中间的工作时间， 跳过非工作时间
def calculate_datediff(start, end):
    """
    计算两个时间点中间的工作时间
    每日工作时间：9:00-19:00
    """
    if isinstance(start, datetime):
        start = start.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(end, datetime):
        end = end.strftime('%Y-%m-%d %H:%M:%S')
    if start[:4] == end[:4]:
        list_holiday = get_holiday(end[:4], 'datetime')  # 后续从数据库查
    else:
        list_holiday = []
        for year in range(int(start[:4]), int(end[:4]) + 1):
            list_holiday = list_holiday + get_holiday(str(year), 'datetime')  # 后续从数据库查
    result = 0
    list_start = start.split(' ')
    start = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
    start_d = datetime.strptime(list_start[0], '%Y-%m-%d')
    list_end = end.split(' ')
    end = datetime.strptime(end, '%Y-%m-%d %H:%M:%S')
    end_d = datetime.strptime(list_end[0], '%Y-%m-%d')
    # 判断开始时间，如果大于今天下班时间，则转到后一天开始计算
    if list_start[1] >= '19:00:00':
        start_d += timedelta(days=1)
        start = start_d + timedelta(hours=9)
        list_start[1] = '09:00:00'
    # 结束时间小于上班时间，转到前一天计算
    if list_end[1] <= '09:00:00':
        end_d += timedelta(days=-1)
        end = end_d + timedelta(hours=19)
        list_end[1] = '19:00:00'
    # 判断是否在节假日中,如果在，则转换成假期结束后第一天上班时间
    if start_d in list_holiday:
        while start_d in list_holiday:
            start_d += timedelta(days=1)
        start = start_d + timedelta(hours=9)
        list_start[1] = '09:00:00'
    if end_d in list_holiday:
        while end_d in list_holiday:
            end_d += timedelta(days=1)
        end = end_d + timedelta(hours=9)
        list_end[1] = '09:00:00'
    if list_start[1] < '09:00:00':
        start = start_d + timedelta(hours=9)
    # 开始时间在午休，从下午13点开始
    # if '12:00:00' < list_start[1] < '13:00:00':
    #     start = start_d + timedelta(hours=13)
    #     list_start[1] = '13:00:00'
    # 结束时间在午休，截止到上午12点
    # if '12:00:00' < list_end[1] < '13:00:00':
    #     end = end_d + timedelta(hours=12)
    #     list_end[1] = '12:00:00'
    if start >= end:
        return 0
    # 开始结束在同一天
    if start_d == end_d:
        result = (end-start).total_seconds()
        # if list_start[1] <= '12:00:00':
        #     if list_end[1] >= '13:00:00':
        #         result -= 3600
    # 开始结束不在一天，排除中间的节假日
    else:
        # if list_start[1] <= '12:00:00':
        #     result -= 3600
        result += (start_d + timedelta(hours=19) - start).total_seconds()  # 今天下班时间-开始时间
        start_d += timedelta(days=1)  # 下一日开始算
        while start_d < end_d:
            if start_d not in list_holiday:
                result += 10 * 60 * 60  # 不是休息日，则加上每日工作时长
            start_d += timedelta(days=1)
        result += (end - (end_d + timedelta(hours=9))).total_seconds()  # 结束日减去上班前的时间
        # if list_end[1] >= '13:00:00':
        #     result -= 3600
    delta_seconds = result if result > 0 else 0
    hours = round((delta_seconds/3600), 2)
    return hours


# 根据预计工作时长和开始时间计算出合理的结束时间(跳过非工作时间)
def calculate_end_time(start_time, hours):
    allow_end_time = start_time + timedelta(hours=hours)
    allow_end_time_tofmt = allow_end_time.strftime('%Y-%m-%d %H:%M:%S')
    list_allow_end = allow_end_time_tofmt.split(' ')
    end = datetime.strptime(allow_end_time_tofmt, '%Y-%m-%d %H:%M:%S')
    end_d = datetime.strptime(list_allow_end[0], '%Y-%m-%d')
    if list_allow_end[0] == start_time.strftime('%Y-%m-%d'):  # 允许的结束时间和开始时间在同一天
        if list_allow_end[1] > '19:00:00':  # 允许的结束时间超过下班时间，顺延到第二天
            extra_hours = round((end - (end_d + timedelta(hours=19))).total_seconds() / 3600, 2)
            end_d += timedelta(days=1)
            end = end_d + timedelta(hours=(9 + extra_hours))
    else:  # 允许的结束时间和开始时间不在一天
        extra_hours = round((end - start_time.replace(hour=19, minute=0, second=0)).total_seconds() / 3600, 2)
        weekdays = int(extra_hours // 10)
        remainder_hours = extra_hours % 10
        if weekdays > 0:
            list_holiday = get_holiday(end.year, 'datetime')
            for i in range(1, weekdays + 1):
                if end_d in list_holiday:
                    while end_d in list_holiday:
                        end_d += timedelta(days=1)
                        if end_d.year != end.year:
                            list_holiday = get_holiday(end_d.year, 'datetime')
                end_d += timedelta(days=1)
            end = end_d + timedelta(hours=(9 + remainder_hours))
        else:
            end = end_d + timedelta(hours=(9 + remainder_hours))
    return end


# 计算再校准日期
def calculate_recalibration_time(calibration_time, months):
    recalibration_time = calibration_time + relativedelta(months=months) + timedelta(days=-1)
    return recalibration_time


# 计算校准到期日
def calculate_due_date(recalibration_time, module):
    today_date = datetime.today().date()
    recalibration_date = recalibration_time
    delta_days = (recalibration_date - today_date).days
    if delta_days < 30:
        if module == 'calibration':
            due_date = 'Please perform calibration ASAP'
        elif module == 'maintain':
            due_date = 'Please perform PM-Y and external Cal ASAP'
        else:
            return None
    else:
        due_date = str(delta_days)
    return due_date


# 计算校准日期
def calculate_pm_time(recalibration_time):
    recalibration_month = recalibration_time.month
    if recalibration_month <= 3:
        qm_q1 = recalibration_time
    elif recalibration_month <= 6:
        qm_q1 = recalibration_time + relativedelta(months=-3)
    elif recalibration_month <= 9:
        qm_q1 = recalibration_time + relativedelta(months=-6)
    elif recalibration_month <= 12:
        qm_q1 = recalibration_time + relativedelta(months=-9)
    else:
        qm_q1 = recalibration_time
    qm_q2 = (qm_q1 + relativedelta(months=3)).strftime('%Y-%m-%d')
    qm_q3 = (qm_q1 + relativedelta(months=6)).strftime('%Y-%m-%d')
    qm_q4 = (qm_q1 + relativedelta(months=9)).strftime('%Y-%m-%d')
    qm_q1 = qm_q1.strftime('%Y-%m-%d')
    return qm_q1, qm_q2, qm_q3, qm_q4
