from equipments.ext_utils import execute_batch_sql
import pandas as pd
import re
import numpy as np
import json
import datetime
from decimal import Decimal
import time

columns_map = {
    '订单号': 'purchase_order_no',
    'Supplier': 'supplier',
    '设备信息': 'name',
    '技术信息': 'specification',
    '品类': 'category',
    'Unit Price': 'price',
    'Qty': 'number',
    '币种': 'currency_id',
    '项目': 'project_id',
    'Location': 'factory_id',
    '固定资产编号': 'fixed_asset_code',
    'Tester': 'used_machine',
    '备注': 'remarks'
}

machine_map = {
    'mask': 1,
    '测试设备': 2,
    'rdl mask': 3,
    'nre': 4
}

tooling_map = {
    '测试配件': 1,
    '测试板': 2,
    '探针卡': 3,
    '探针卡+清针片': 4
}

currency_map = {
    '￥': 1,
    '$': 2,
    'JPY': 10
}

project_map = {'kgd_2g combo': 1, 'moka': 2, 'sed-s210': 3, 'dongqing': 4, 'fuxi': 5, 'giulia': 6, 'guyu': 7, 'hanlu': 8, 'lichun（1glp25）': 9, 'donghu-lp4': 10, 'lpddr5': 11, 'moka2': 12, 'p100': 13, 'p200': 14, 's200': 15, 's210': 16, 's1': 17, 'slx4': 18, 'sram': 19, 'youzi': 20, 'rram': 21, 'xiaoxue（gddr6)': 22, 'youzi2': 23, 'sed-s1': 24, 'sed-s2': 25, 'sed-lp4': 26, 'xiaoman (512m lpddr2)': 27, 'sed-slx4': 28, 'sed-s2.1': 29, 'sed-thu21': 30, 'mcp215': 31, 'pjshang': 32, 'sed-s220': 33}

factory_map = {'xmc': 1, 'psmc': 2, 'taiji': 3, 'ums': 4, '青岛新核心': 5, 'spil-tw': 6, 'spil-sz': 7, 'jscc': 8, 'jcap': 9, 'tpw': 10, 'cms': 11, 'ptn': 12, 'pti': 13, 'sig': 14, 'smic': 15, 'uniic xa': 16, 'gf': 17, '华虹宏力': 18, "ht xi'an": 19, 'unimos': 20, 'htxa': 21, 'htks': 22, 'htnj': 23, 'payton': 24, '新核芯': 25}

used_machine_map = {'T5593': 1, 'T5377': 2, 'T5377HS2': 3, 'T5377S': 4, 'T5503': 5, 'V93000': 6, 'T7702': 7, 'T7748': 8, 'T7792': 9, 'AT504(UMS)': 10, 'AT502': 11, 'AT504': 12, 'T77168': 13, 'T77173': 14, 'T7789': 15, 'T7706': 16, 'T5503HS2': 17, 'V93K': 18}


equipment_sql = '''insert into gc_foundry_equipment(name, purchase_order_no, supplier, category,
                                 number, price, total_amount,specification, fixed_asset_code,
                                 remarks, currency_id, project_id, factory_id, create_time, update_time)
                         values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''

tooling_sql = '''insert into gc_foundry_tooling_info(name, purchase_order_no, supplier, category,
                                 number, price, total_amount,specification, fixed_asset_code, used_machine,
                                 remarks, currency_id, project_id, factory_id, create_time, update_time)
                        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''


def insert_datas(datas, type):
    if type == 'equipments':
        execute_batch_sql(equipment_sql, datas)
    else:
        execute_batch_sql(tooling_sql, datas)


def analy_datas(path, type):
    df = pd.read_excel(path)
    df = df[list(columns_map.keys())]
    df.rename(columns=columns_map, inplace=True)
    ndf = df[['purchase_order_no', 'supplier', 'name', 'specification', 'category', 'price', 'number', 'currency_id',
              'project_id', 'factory_id', 'fixed_asset_code', 'used_machine', 'remarks']]
    ndf = ndf.replace({np.nan: None})
    ndf['purchase_order_no'] = ndf['purchase_order_no'].map(lambda x: x.strip() if x else x)
    ndf['supplier'] = ndf['supplier'].map(lambda x: x.strip() if x else x)
    ndf['name'] = ndf['name'].map(lambda x: x.strip() if x else x)
    ndf['specification'] = ndf['specification'].map(lambda x: x.strip() if x else x)
    ndf['category'] = ndf['category'].map(lambda x: re.sub(r'/r|/n|\n', '', x) if x else x)
    ndf['category'] = ndf['category'].map(lambda x: x.strip() if x else x)
    ndf['price'] = ndf['price'].map(lambda x: float(x) if x else x)
    ndf['number'] = ndf['number'].map(lambda x: int(str(x).strip()) if x else x)
    ndf['total_amount'] = round(ndf['price'] * ndf['number'], 2)
    ndf['price'] = ndf['price'].map(lambda x: Decimal(x) if x else x)
    ndf['total_amount'] = ndf['total_amount'].map(lambda x: Decimal(x) if x else x)
    ndf['currency_id'] = ndf['currency_id'].map(currency_map)
    ndf['project_id'] = ndf['project_id'].map(lambda x: re.sub(r'/r|/n|\n', '', x) if x else x)
    ndf['project_id'] = ndf['project_id'].map(lambda x: x.strip() if x else x)
    ndf['project_id'] = ndf['project_id'].map(lambda x: project_map.get(x.lower(), None) if x else x)
    ndf['factory_id'] = ndf['factory_id'].map(lambda x: re.sub(r'/r|/n|\n', '', x) if x else x)
    ndf['factory_id'] = ndf['factory_id'].map(lambda x: x.strip() if x else x)
    ndf['factory_id'] = ndf['factory_id'].map(lambda x: factory_map.get(x.lower(), None) if x else x)
    ndf['fixed_asset_code'] = ndf['fixed_asset_code'].map(lambda x: re.sub(r'/r|/n|\n', '', x) if x else x)
    ndf['fixed_asset_code'] = ndf['fixed_asset_code'].map(lambda x: x.strip() if x else x)
    ndf['used_machine'] = ndf['used_machine'].map(lambda x: re.sub(r'/r|/n|\n|', '', x) if x else x)
    ndf['used_machine'] = ndf['used_machine'].map(lambda x: x.replace(" ", '') if x else x)
    ndf['remarks'] = ndf['remarks'].map(lambda x: x.strip() if x else x)
    if type == 'equipments':
        ndf = ndf.drop('used_machine', axis=1)
        ndf['category'] = ndf['category'].map(lambda x: machine_map.get(x.lower(), None) if x else x)
        ndf = ndf.replace({np.nan: None})
        datas = ndf.to_dict('records')
        insert_equipment_ls = []
        for data in datas:
            time.sleep(0.01)
            now_ts = datetime.datetime.now()
            project_id = data['project_id']
            if project_id:
                project_id = int(project_id)
            factory_id = data['factory_id']
            if factory_id:
                factory_id = int(factory_id)
            price = data['price']
            if price:
                price = Decimal(price)
            total_amount = data['total_amount']
            if total_amount:
                total_amount = Decimal(total_amount)
            insert_equipment_args = (data['name'], data['purchase_order_no'], data['supplier'], data['category'],
                                     data['number'], price, total_amount, data['specification'],
                                     data['fixed_asset_code'], data['remarks'], data['currency_id'], project_id,
                                     factory_id, now_ts, now_ts)
            insert_equipment_ls.append(insert_equipment_args)
        insert_datas(insert_equipment_ls, type)
        print('设备数据插入完成')
    else:
        ndf['used_machine'] = ndf['used_machine'].map(lambda x: [{'value': used_machine_map.get(i), 'label': i} for i in x.split('/')] if x else x)
        ndf['used_machine'] = ndf['used_machine'].map(lambda x: json.dumps(x) if x else x)
        ndf['category'] = ndf['category'].map(lambda x: tooling_map.get(x.lower(), None) if x else x)
        ndf = ndf.replace({np.nan: None})
        datas = ndf.to_dict('records')
        insert_tooling_ls = []
        for data in datas:
            time.sleep(0.01)
            now_ts = datetime.datetime.now()
            project_id = data['project_id']
            if project_id:
                project_id = int(project_id)
            factory_id = data['factory_id']
            if factory_id:
                factory_id = int(factory_id)
            price = data['price']
            if price:
                price = Decimal(price)
            total_amount = data['total_amount']
            if total_amount:
                total_amount = Decimal(total_amount)
            insert_tooling_args = (data['name'], data['purchase_order_no'], data['supplier'], data['category'],
                                   data['number'], price, total_amount, data['specification'],
                                   data['fixed_asset_code'], data['used_machine'], data['remarks'], data['currency_id'],
                                   project_id, factory_id, now_ts, now_ts)
            insert_tooling_ls.append(insert_tooling_args)
        insert_datas(insert_tooling_ls, type)
        print('配件数据插入完成')


# analy_datas(r'D:\工作需求\商务部\机台.xlsx', 'equipments')

# analy_datas(r'D:\工作需求\商务部\配件.xlsx', 'tooling')