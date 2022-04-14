from django.utils.http import urlquote
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse, HttpResponse
from xlrd import xldate_as_tuple
from django.db import connection

import os
import re
import pandas as pd
import numpy as np
import datetime
import time


def VIEW_SUCCESS(msg=None, data={}):
    res_dict = {'code': 1, 'msg': 'success', 'data': data}
    if msg:
        res_dict['msg'] = msg
    return JsonResponse(res_dict)


def VIEW_FAIL(msg=None, data={}):
    res_dict = {'code': 0, 'msg': 'fail', 'data': data}
    if msg:
        res_dict['msg'] = msg
    return JsonResponse(res_dict)


def REST_SUCCESS(data={}):
    return Response(data)


def REST_FAIL(data={}):
    return Response(data, status=status.HTTP_400_BAD_REQUEST)


def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


FIXED_ASSET_CATEGORYS = {
    'ATE Tester': 1,
    'Tester Cell Machine': 2,
    'Reliability & Environment': 3,
    'Measurement & Intrumentation': 4,
    'Probe, Tip & Assembly': 5,
    'Device Test Tooling': 6,
    'Inspection & Rework': 7,
    'Other Tool, Jig & Kit': 8,
    'Facility Equipment & Tool': 9,
    'APT MB & SLT System': 10
}

EQUIPMENT_STATES = {
    '待用': 1,
    '使用中': 2,
    '维护中': 3,
    '闲置': 4,
    '代管': 5,
    '报废': 6
}

service_type_map = {
    '不可用': 1,
    '领用': 2,
    '随用': 3,
    '预约': 4,
    '专用': 5
}

manage_type_map = {
    'PM': 1,
    'Check': 2,
    'Inspection': 3
}

columns_map = {
    'ID': 'id',
    '设备器材型号名称': 'name',
    '数量': 'number',
    '序列号': 'serial_number',
    '固定资产编号': 'fixed_asset_code',
    '类别': 'fixed_asset_category',
    '固定资产保管人': 'custodian',
    '当前状态': 'equipment_state',
    '服务方式': 'service_type',
    '技术指标': 'specification',
    '主要功能和应用领域': 'performance',
    '配套设备器材': 'assort_material',
    '存放地点': 'deposit_position',
    '安装日期': 'install_date',
    '管理方式': 'manage_type',
    '管理人': 'manager',
    '应用技术专家': 'application_specialist',
    '制造商': 'manufacturer',
    '生产日期': 'manufacture_date',
    '原产地': 'origin_place'
}

is_allow_renew_map = {
    '能': True,
    '否': False,
    None: False
}

def trans_type(x):
    if x:
        try:
            x = str(int(x))
        except:
            x = x
        return x


def trans_float_ts(ts, infmt, outfmt):
    """
    转换日期格式
    """
    try:
        if not ts:
            return ''
        if isinstance(ts, pd._libs.tslibs.timestamps.Timestamp):
            ts = ts.to_pydatetime()
        if isinstance(ts, str):
            if re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d+|\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}|\d{4}-\d{2}-\d{2}', ts):
                return ts
            try:
                dt = datetime.datetime.strptime(ts, infmt)
            except:
                dt = datetime.datetime(*xldate_as_tuple(ts, 0))
        elif isinstance(ts, datetime.datetime):
            dt = ts
        return dt.strftime(outfmt)
    except:
        return ts


def analysis_equipment_data(datas):
    if not datas:
        return []
    df = pd.DataFrame(datas)
    df = df[list(columns_map.keys())]
    df.rename(columns=columns_map, inplace=True)
    df['number'] = df['number'].fillna(1)
    df = df.replace({np.nan: None})
    ndf = df.copy()
    ndf['manufacture_date'] = ndf['manufacture_date'].map(trans_type)
    ndf['manufacture_date'] = ndf['manufacture_date'].apply(trans_float_ts, args=('%Y', '%Y'))
    ndf['install_date'] = ndf['install_date'].apply(trans_float_ts, args=('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S'))
    # ndf['calibration_time'] = ndf['calibration_time'].apply(trans_float_ts, args=('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'))
    # ndf['recalibration_time'] = ndf['recalibration_time'].apply(trans_float_ts, args=('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'))
    ndf['name'] = ndf['name'].map(lambda x: re.sub(r'/r|/n|\n', '', x) if x else x)
    ndf['serial_number'] = ndf['serial_number'].map(lambda x: re.sub(r' |/r|/n|\n', '', str(x)) if x else x)
    ndf['deposit_position'] = ndf['deposit_position'].map(lambda x: re.sub(r' |/r|/n|\n', '', x) if x else x)
    ndf['fixed_asset_code'] = ndf['fixed_asset_code'].map(lambda x: re.sub(r' |/r|/n|\n', '', str(x)) if x else x)

    ndf['equipment_state'] = ndf['equipment_state'].map(lambda x: re.sub(r' |/r|/n|\n', '', x) if x else x)
    ndf['equipment_state'] = ndf['equipment_state'].map(
        lambda x: EQUIPMENT_STATES[x] if EQUIPMENT_STATES.get(x) else None)

    ndf['fixed_asset_category'] = ndf['fixed_asset_category'].map(lambda x: re.sub(r'/r|/n|\n', '', x) if x else x)
    ndf['fixed_asset_category'] = ndf['fixed_asset_category'].map(lambda x: str(x).strip() if x else x)
    ndf['fixed_asset_category'] = ndf['fixed_asset_category'].map(
        lambda x: FIXED_ASSET_CATEGORYS[x] if FIXED_ASSET_CATEGORYS.get(x) else None)

    ndf['service_type'] = ndf['service_type'].map(lambda x: re.sub(r' |/r|/n|\n', '', x) if x else x)
    ndf['service_type'] = ndf['service_type'].map(lambda x: service_type_map[x] if service_type_map.get(x) else None)

    ndf['manage_type'] = ndf['manage_type'].map(lambda x: re.sub(r' |/r|/n|\n', '', x) if x else x)
    ndf['manage_type'] = ndf['manage_type'].map(lambda x: manage_type_map[x] if manage_type_map.get(x) else None)
    ndf['id'] = ndf['id'].map(lambda x: str(x).strip() if x else x)
    ndf['name'] = ndf['name'].map(lambda x: x.strip() if x else x)
    ndf['number'] = ndf['number'].map(lambda x: str(int(x)).strip() if x else x)
    ndf['fixed_asset_code'] = ndf['fixed_asset_code'].map(lambda x: x.strip() if x else x)
    ndf = ndf.replace({np.nan: None})
    datas = ndf.to_dict('records')
    return datas


calibration_columns_map = {
    'ID': 'equipment_id',
    '校准规范': 'specification',
    '环境要求': 'environment',
    '校准周期(月)': 'calibration_cycle',
    '校准日期': 'calibration_time'
}


def analysis_calibration(datas):
    if not datas:
        return []
    df = pd.DataFrame(datas)
    df = df[list(calibration_columns_map.keys())]
    df.rename(columns=calibration_columns_map, inplace=True)
    df = df.replace({np.nan: None})
    ndf = df.copy()
    ndf['equipment_id'] = ndf['equipment_id'].map(lambda x: str(x).strip() if x else x)
    ndf['equipment_id'] = ndf['equipment_id'].map(lambda x: re.sub(r'|/r|/n|\n', '', x) if x else x)
    ndf['calibration_cycle'] = ndf['calibration_cycle'].map(lambda x: int(re.sub(r' |/r|/n|\n', '', str(x))) if x else x)
    ndf['calibration_time'] = ndf['calibration_time'].apply(trans_float_ts, args=('%Y-%m-%d', '%Y-%m-%d'))
    ndf['calibration_time'] = ndf['calibration_time'].map(lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date() if x else x)
    ndf = ndf.replace({np.nan: None})
    datas = ndf.to_dict('records')
    return datas


certificate_columns_map = {
    'ID': 'equipment_id',
    '校准年份': 'certificate_year',
    '校准报告': 'certificate'
}


def analysis_certificate(datas):
    if not datas:
        return []
    df = pd.DataFrame(datas)
    df = df[list(certificate_columns_map.keys())]
    df.rename(columns=certificate_columns_map, inplace=True)
    df = df.replace({np.nan: None})
    ndf = df.copy()
    ndf['equipment_id'] = ndf['equipment_id'].map(lambda x: str(x).strip() if x else x)
    ndf['equipment_id'] = ndf['equipment_id'].map(lambda x: re.sub(r'|/r|/n|\n', '', x) if x else x)
    ndf['certificate_year'] = ndf['certificate_year'].map(lambda x: str(int(x)).strip() if x else '')
    ndf = ndf.replace({np.nan: None})
    datas = ndf.to_dict('records')
    return datas


maintain_columns_map = {
    'ID': 'equipment_id',
    '校准日期': 'calibration_time',
    '再校准日期': 'recalibration_time'
}


def analysis_maintain(datas):
    if not datas:
        return []
    df = pd.DataFrame(datas)
    df = df[list(maintain_columns_map.keys())]
    df.rename(columns=maintain_columns_map, inplace=True)
    df = df.replace({np.nan: None})
    ndf = df.copy()
    ndf['calibration_time'] = ndf['calibration_time'].apply(trans_float_ts, args=('%Y-%m-%d', '%Y-%m-%d'))
    ndf['calibration_time'] = ndf['calibration_time'].map(lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date() if x else x)
    ndf['recalibration_time'] = ndf['recalibration_time'].apply(trans_float_ts, args=('%Y-%m-%d', '%Y-%m-%d'))
    ndf['recalibration_time'] = ndf['recalibration_time'].map(lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date() if x else x)
    ndf = ndf.replace({np.nan: None})
    datas = ndf.to_dict('records')
    return datas


def execute_batch_sql(sql, datas):
    if not datas:
        return None
    with connection.cursor() as cursor:
        res = cursor.executemany(sql, datas)
    return res


def create_suffix():
    ts = time.time()
    suffix = str(int(round(ts, 5) * 10**5))[:15]
    return suffix


def create_excel_resp(file_path, filename):
    with open(file_path, 'rb') as f:
        result = f.read()
    response = HttpResponse(result)
    response['Content-Type'] = 'application/vnd.ms-excel;charset=UTF-8'
    response['Content-Disposition'] = 'attachment;filename="' + urlquote(filename) + '.xlsx"'
    return response


def get_file_path(prefix, dir_name='report_files'):
    current_path = os.path.dirname(__file__)
    file_dir = os.path.join(current_path, dir_name)
    if not os.path.exists(file_dir):
        os.mkdir(file_dir)

    file_name = '{}-{}'.format(prefix, create_suffix())
    file_path = os.path.join(file_dir, file_name)
    return file_path
