from django.utils.http import urlquote
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse, HttpResponse
from xlrd import xldate_as_tuple
from django.db import connection

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
    '机器设备': 1,
    '电子设备': 2,
    '其他设备': 3,
    None: 3
}

EQUIPMENT_STATES = {
    '可借用': 1,
    '已借出': 2,
    '已送检': 3,
    '已调拨': 4,
    '故障': 5,
    '闲置': 6,
    '报废': 7,
    None: 1
}

columns_map = {
    'ID': 'id',
    '名称': 'name',
    '资产数量': 'number',
    '序列号': 'serial_number',
    '固定资产编码': 'fixed_asset_code',
    '固定资产名称': 'fixed_asset_name',
    '固定资产类别': 'fixed_asset_category',
    '规格型号描述': 'specification',
    '主要性能': 'performance',
    '能否续借': 'is_allow_renew',
    '状态': 'equipment_state',
    '存放地点': 'deposit_position',
    '校准日期': 'calibration_time',
    '再校准日期': 'recalibration_time',
    '到期日': 'due_date',
    '校准报告': 'certificate',
    '校准报告版本': 'certificate_year',
    '制造商': 'manufacturer',
    '制造日期': 'manufacture_date',
    '保管人': 'custodian',
    '使用/故障说明': 'usage_description',
    '处理建议': 'dispose_suggestion',
    '财务入账日期': 'entry_date',
    '资产原值': 'original_cost',
    '预计使用期间数': 'estimate_life',
    '预计净残值': 'net_salvage',
    '折旧方法': 'method',
    '已折旧期间数': 'periods',
    '累计折旧': 'depreciated_total',
    '净值': 'net_value',
    '净额': 'net_amount',
    '折旧日期': 'depreciate_date'
}

is_allow_renew_map = {
    '能': True,
    '否': False,
    None: False
}


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
        raise Exception('日期[{}]格式错误，请传入正确格式:[年-月-日 时:分:秒]或[年/月/日 时:分:秒]或者不传'.format(ts))


def analysis_equipment_data(datas):
    if not datas:
        return []
    df = pd.DataFrame(datas)
    df = df[list(columns_map.keys())]
    df.rename(columns=columns_map, inplace=True)
    df['number'] = df['number'].fillna(1)
    df = df.replace({np.nan: None})
    ndf = df.copy()
    ndf['manufacture_date'] = ndf['manufacture_date'].map(lambda x: str(int(x)) if x else '')
    ndf['manufacture_date'] = ndf['manufacture_date'].apply(trans_float_ts, args=('%Y', '%Y'))
    ndf['entry_date'] = ndf['entry_date'].apply(trans_float_ts, args=('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'))
    ndf['depreciate_date'] = ndf['depreciate_date'].apply(trans_float_ts, args=('%Y/%m', '%Y-%m'))
    ndf['calibration_time'] = ndf['calibration_time'].apply(trans_float_ts, args=('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'))
    ndf['recalibration_time'] = ndf['recalibration_time'].apply(trans_float_ts, args=('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'))
    ndf['certificate_year'] = ndf['certificate_year'].map(lambda x: str(int(x)) if x else '')
    ndf['equipment_state'] = ndf['equipment_state'].map(EQUIPMENT_STATES)
    ndf['fixed_asset_category'] = ndf['fixed_asset_category'].map(FIXED_ASSET_CATEGORYS)
    ndf['is_allow_renew'] = ndf['is_allow_renew'].map(is_allow_renew_map)
    ndf['id'] = ndf['id'].map(lambda x: str(x).strip() if x else x)
    ndf['name'] = ndf['name'].map(lambda x: x.strip() if x else x)
    ndf['number'] = ndf['number'].map(lambda x: str(int(x)).strip() if x else x)
    ndf['fixed_asset_code'] = ndf['fixed_asset_code'].map(lambda x: x.strip() if x else x)
    ndf['fixed_asset_name'] = ndf['fixed_asset_name'].map(lambda x: x.strip() if x else x)
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
