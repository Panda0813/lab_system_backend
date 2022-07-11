from xlrd import xldate_as_tuple
from pandas._libs.tslibs.timestamps import Timestamp

import time
import os
import pandas as pd
import numpy as np
import re
import datetime



def create_suffix():
    ts = time.time()
    suffix = str(int(round(ts, 5) * 10**5))[:15]
    return suffix


def get_file_path(prefix, dir_name):
    current_path = os.path.dirname(__file__)
    file_dir = os.path.join(current_path, dir_name)
    if not os.path.exists(file_dir):
        os.mkdir(file_dir)

    file_name = '{}-{}'.format(prefix, create_suffix())
    file_path = os.path.join(file_dir, file_name)
    return file_path, file_name


def trans_time(ts, infmt, outfmt):
    try:
        if not ts:
            return ''
        if isinstance(ts, Timestamp):
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


wafer_price_map = {
    'Wafer 型号': 'wafer_id',
    '价格来源': 'price_source',
    '供应商': 'supplier',
    '采购单价': 'purchase_price',
    '下单日期': 'order_date'
}


def analysis_wafer_price(datas):
    if not datas:
        return pd.DataFrame([])
    df = pd.DataFrame(datas)
    df = df[list(wafer_price_map.keys())]
    df.rename(columns=wafer_price_map, inplace=True)
    df = df.replace({np.nan: None})
    ndf = df.copy()
    ndf['order_date'] = ndf['order_date'].apply(trans_time, args=('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'))
    ndf['purchase_price'] = ndf['purchase_price'].map(lambda x: float(x) if x else x)
    return ndf


grain_yield_map = {
    'PN': 'grain_id',
    'HB YLD': 'hb_yld',
    'CP YLD': 'cp_yld',
    'RDL YLD': 'rdl_yld',
    'BP YLD': 'bp_yld',
    'AP YLD': 'ap_yld',
    'BI YLD': 'bi_yld',
    'FT1 YLD': 'ft1_yld',
    'FT2 YLD': 'ft2_yld',
    'FT3 YLD': 'ft3_yld',
    'FT4 YLD': 'ft4_yld',
    'FT5 YLD': 'ft5_yld',
    'FT6 YLD': 'ft6_yld',
}


def analysis_grain_yield(datas):
    if not datas:
        return pd.DataFrame([])
    df = pd.DataFrame(datas)
    df = df[list(grain_yield_map.keys())]
    df.rename(columns=grain_yield_map, inplace=True)
    df = df.replace({np.nan: None})
    ndf = df.copy()
    return ndf


grain_price_map = {
    'PN': 'grain_id',
    '采购单价': 'purchase_price',
    'HB U/P': 'hb_up',
    'CP U/P': 'cp_up',
    'RDL U/P': 'rdl_up',
    'BP U/P': 'bp_up',
    'AP U/P': 'ap_up',
    'BI U/P': 'bi_up',
    'FT1 U/P': 'ft1_up',
    'FT2 U/P': 'ft2_up',
    'FT3 U/P': 'ft3_up',
    'FT4 U/P': 'ft4_up',
    'FT5 U/P': 'ft5_up',
    'FT6 U/P': 'ft6_up',
    'MSP U/P': 'msp_up'
}


def analysis_grain_price(datas):
    if not datas:
        return pd.DataFrame([])
    df = pd.DataFrame(datas)
    df = df[list(grain_price_map.keys())]
    df.rename(columns=grain_price_map, inplace=True)
    df = df.replace({np.nan: None})
    ndf = df.copy()
    return ndf
