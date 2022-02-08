from django.db import connection, close_old_connections, transaction
from django.db.models import Q
from django.utils.http import urlquote
from django.views.generic.base import View
from decimal import Decimal
from rest_framework.decorators import api_view
from rest_framework.response import Response

from equipments.models import EquipmentBorrowRecord, EquipmentMaintenanceRecord, EquipmentBrokenInfo
from reports.time_utils import get_start_end
from utils.timedelta_utls import calculate_datediff
from equipments.ext_utils import REST_SUCCESS, REST_FAIL, create_suffix, create_excel_resp
from utils.permission import IsSuperUser

import pandas as pd
import matplotlib.pyplot as plt
import datetime
import time
import hashlib
import os
import traceback
import logging

logger = logging.getLogger('django')


def get_file_path(prefix):
    current_path = os.path.dirname(__file__)
    file_dir = os.path.join(current_path, 'report_files')
    if not os.path.exists(file_dir):
        os.mkdir(file_dir)

    file_name = '{}-{}'.format(prefix, create_suffix())
    file_path = os.path.join(file_dir, file_name)
    return file_path


# 根据开始结束时间，得出记录在此区间内的使用时长
def get_usagetime(ndf, start_time, end_time):
    # 找出记录开始时间位于查询开始时间之前的记录
    last_ls = list(ndf.loc[ndf['start_time'] < start_time].index)
    for index in last_ls:
        usage_time = calculate_datediff(start_time, ndf['end_time'].iloc[index].to_pydatetime())
        ndf['usage_time'].iloc[index] = usage_time
        if 'total_amount' in ndf:
            ndf['total_amount'].iloc[index] = ndf['per_hour_price'].iloc[index] * usage_time
        ndf['start_time'].iloc[index] = start_time
    # 找出记录结束时间位于查询结束时间之后的记录
    next_ls = list(ndf.loc[ndf['end_time'] > end_time].index)
    for index in next_ls:
        usage_time = calculate_datediff(ndf['start_time'].iloc[index].to_pydatetime(), end_time)
        ndf['usage_time'].iloc[index] = usage_time
        if 'total_amount' in ndf:
            ndf['total_amount'].iloc[index] = ndf['per_hour_price'].iloc[index] * usage_time
        ndf['end_time'].iloc[index] = end_time
    return ndf


# 查询设备使用率
@api_view(['GET'])
def get_usage_rate(request):
    try:
        obj = EquipmentBorrowRecord.objects.filter(is_borrow=True, is_return=2)
        user_name = request.GET.get('user_name')
        if user_name:
            obj = obj.filter(user__username__contains=user_name)
        equipment_id = request.GET.get('equipment')
        if equipment_id:
            obj = obj.filter(equipment_id=equipment_id)
        equipment_name = request.GET.get('equipment_name')
        if equipment_name:
            obj = obj.filter(equipment__name__contains=equipment_name)
        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            start_time = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            end_time = datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            total_weekday = calculate_datediff(start_time, end_time)  # 总工时
        else:
            total_weekday_map = {
                'week': 50,
                'month': 208,
                'year': 2500
            }
            date_type = request.GET.get('date_type', 'week')  # week, month, year
            start_time, end_time = get_start_end(date_type)
            total_weekday = total_weekday_map[date_type]
        obj = obj.filter(Q(start_time__gte=start_time, actual_end_time__lte=end_time) |
                         Q(start_time__range=[start_time, end_time]) | Q(actual_end_time__range=[start_time, end_time]))
        borrow_record_qs = obj.values('id', 'user_id', 'user__username', 'equipment_id', 'equipment__name',
                                      'start_time', 'actual_end_time', 'actual_usage_time')
        if not borrow_record_qs:
            return REST_SUCCESS({})
        df = pd.DataFrame(list(borrow_record_qs))
        ndf = df.rename({'actual_end_time': 'end_time', 'actual_usage_time': 'usage_time',
                         'user__username': 'user_name', 'equipment__name': 'equipment_name'}, axis=1)
        ndf['usage_time'] = ndf['usage_time'].map(lambda x: float(x))
        ndf = get_usagetime(ndf, start_time, end_time)

        # 按设备统计明细
        mdf = ndf[['equipment_id', 'equipment_name', 'user_name', 'start_time', 'end_time', 'usage_time']]
        mdf.sort_values('start_time', inplace=True)
        equipment_id_ls = [equipment_id for equipment_id in list(mdf['equipment_id'].unique())]
        equipment_id_ls.sort()

        final_df = pd.DataFrame(columns=['equipment_id', 'equipment_name', 'user_name', 'start_time', 'end_time', 'usage_time'],
                                dtype=object)
        for equipment_id in equipment_id_ls:
            ldf = mdf[mdf['equipment_id'] == equipment_id]
            ldf.loc['total'] = ldf[['usage_time']].apply(lambda x: x.sum())
            ldf.fillna('', inplace=True)
            final_df = pd.concat([final_df, ldf], axis=0)
        final_df['start_time'] = final_df['start_time'].map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if x else x)
        final_df['end_time'] = final_df['end_time'].map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if x else x)
        final_df['usage_time'] = final_df['usage_time'].map(lambda x: round(x, 2))
        usage_df = final_df

        # 计算使用率
        total_df = ndf[['equipment_id', 'usage_time']]
        total_df = total_df.groupby('equipment_id').sum().reset_index()
        total_df['total_weekday'] = total_weekday
        total_df['percentage'] = total_df['usage_time'] / total_df['total_weekday']
        total_df['percentage'] = total_df['percentage'].map(lambda x: round(x, 4))
        total_df['usage_time'] = total_df['usage_time'].map(lambda x: round(x, 2))
        rate_df = total_df

        operate = request.GET.get('operate', 'list')
        if operate == 'export':
            # 绘制使用率图
            def autolabel(rects):
                """显示柱状上的数值"""
                for rect in rects:
                    height = rect.get_height()
                    plt.text(rect.get_x() + rect.get_width() / n - 0.1, height + 1, '%s' % float(height))

            total_width, n = 0.4, 2
            width = total_width / n
            plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
            plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号
            x = total_df.index.tolist()
            fig = plt.figure()
            plt.grid(axis='y', alpha=0.2)
            for i in range(len(x)):
                x[i] = x[i] + width
            total_weekday_label = 'Total Weekday({}H)'.format(total_weekday)
            t1 = plt.bar(x, total_df['total_weekday'], width=width, label=total_weekday_label, fc='r')
            for i in range(len(x)):
                x[i] = x[i] + width
            t2 = plt.bar(x, total_df['usage_time'], width=width, tick_label=total_df['equipment_id'],
                         label='Total Usage Time(H)', fc='b')
            autolabel(t2)
            plt.xticks(rotation=45)
            plt.legend(bbox_to_anchor=(1.0, 0.7), prop={'size': 12})
            current_path = os.path.dirname(__file__)
            image_dir = os.path.join(current_path, 'report_images')
            if not os.path.exists(image_dir):
                os.mkdir(image_dir)
            image_name = hashlib.md5(str(time.time()).encode()).hexdigest() + '.jpg'
            image_path = os.path.join(image_dir, image_name)
            plt.savefig(image_path, dpi=150, bbox_inches='tight')

            # 保存成excel文件
            file_path = get_file_path('usage')
            writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
            workbook = writer.book
            border_format = workbook.add_format({'border': 1})
            note_fmt = workbook.add_format({'bold': True, 'font_size': 10, 'font_color': 'red',
                                            'font_name': '微软雅黑', 'align': 'left', 'valign': 'vcenter'})
            date_fmt = workbook.add_format({'bold': False, 'num_format': 'yyyy-mm-dd hh:mm:ss'})
            percent_fmt = workbook.add_format({'num_format': '0.00%'})
            float_fmt = workbook.add_format({'num_format': '#,##0.00'})
            amt_fmt = workbook.add_format({'num_format': '#,##0'})
            title_fmt = workbook.add_format(
                {'bold': True, 'font_size': 11, 'font_name': '微软雅黑', 'num_format': 'yyyy-mm-dd hh:mm:ss',
                 'bg_color': '#9FC3D1', 'valign': 'vcenter', 'align': 'center'})
            blank_fmt = workbook.add_format({'bold': False, 'bg_color': 'white'})

            final_df = final_df.rename({'equipment_id': 'Tester', 'user_name': 'User', 'start_time': 'Begin Time',
                                        'end_time': 'End Time', 'usage_time': 'Usaged Time'}, axis=1)
            final_df.to_excel(writer, sheet_name='使用明细', header=False, index=False, startcol=0, startrow=2)
            worksheet = writer.sheets['使用明细']
            l_end = len(final_df.index) + 2
            for col_num, value in enumerate(final_df.columns.values):
                worksheet.write(1, col_num, value, title_fmt)
            worksheet.merge_range('A1:E1', 'Begin: {}  End: {}'.format(start_time, end_time), note_fmt)
            worksheet.set_column('A:A', 15)
            worksheet.set_column('B:B', 10)
            worksheet.set_column('C:C', 22)
            worksheet.set_column('D:D', 22)
            worksheet.set_column('E:E', 14, float_fmt)
            # 加边框
            worksheet.conditional_format('A3:E%d' % l_end, {'type': 'no_blanks', 'format': border_format})
            worksheet.conditional_format('A1:E%d' % l_end, {'type': 'blanks', 'format': blank_fmt})

            total_df = total_df.rename({'equipment_id': 'Tester', 'usage_time': 'Total Usage Time(H)',
                                        'total_weekday': total_weekday_label, 'percentage': 'Percenge'}, axis=1)
            total_df.to_excel(writer, sheet_name='使用率', header=False, index=False, startcol=0, startrow=2)
            worksheet1 = writer.sheets['使用率']
            l1_end = len(total_df.index) + 2
            for col_num, value in enumerate(total_df.columns.values):
                worksheet1.write(1, col_num, value, title_fmt)
            worksheet1.merge_range('A1:D1', 'Begin: {}  End: {}'.format(start_time, end_time), note_fmt)
            worksheet1.set_column('A:A', 15)
            worksheet1.set_column('B:B', 21, float_fmt)
            worksheet1.set_column('C:C', 21, amt_fmt)
            worksheet1.set_column('D:D', 14)
            worksheet1.conditional_format('D3:D%d' % l1_end, {'type': 'cell', 'criteria': '>=', 'value': 0,
                                                              'format': percent_fmt})
            worksheet1.conditional_format('A1:D%d' % l1_end, {'type': 'no_blanks', 'format': border_format})
            worksheet2 = writer.book.add_worksheet('统计图')
            worksheet2.merge_range('A1:G1', 'Begin: {}  End: {}'.format(start_time, end_time), note_fmt)
            worksheet2.insert_image(1, 0, image_path)
            writer.save()
            return create_excel_resp(file_path, '设备使用率统计表')

        data = {}
        # data['image_name'] = image_name
        usage_df.rename({'equipment_id': 'equipment'}, axis=1, inplace=True)
        data['usage_detail'] = usage_df.to_dict('records')
        rate_df.rename({'equipment_id': 'equipment'}, axis=1, inplace=True)
        data['total_rate'] = rate_df.to_dict('records')
        return REST_SUCCESS(data)
    except Exception as e:
        logger.error('查询失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '查询失败, error: {}'.format(str(e))})


# 查询设备使用记录
@api_view(['GET'])
def get_use_detail(request):
    try:
        obj = EquipmentBorrowRecord.objects.filter(is_borrow=True, is_return=2)
        user_name = request.GET.get('user_name')
        if user_name:
            obj = obj.filter(user__username__contains=user_name)
        equipment_id = request.GET.get('equipment')
        if equipment_id:
            obj = obj.filter(equipment_id=equipment_id)
        equipment_name = request.GET.get('equipment_name')
        if equipment_name:
            obj = obj.filter(equipment__name__contains=equipment_name)
        project_id = request.GET.get('project')
        if project_id:
            obj = obj.filter(project_id=project_id)
        project_name = request.GET.get('project_name')
        if project_name:
            obj = obj.filter(project__name__contains=project_name)
        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')

        if start_time and end_time:
            start_time = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            end_time = datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            obj = obj.filter(Q(start_time__gte=start_time, actual_end_time__lte=end_time) |
                             Q(start_time__range=[start_time, end_time]) | Q(actual_end_time__range=[start_time, end_time]))
        borrow_record_qs = obj.order_by('-id').values('user__username', 'equipment_id', 'equipment__name', 'project__name',
                                                      'start_time', 'actual_end_time', 'actual_usage_time')
        if not borrow_record_qs:
            return REST_SUCCESS([])
        df = pd.DataFrame(list(borrow_record_qs))
        ndf = df.rename({'actual_end_time': 'end_time', 'actual_usage_time': 'usage_time',
                         'user__username': 'user_name', 'equipment__name': 'equipment_name',
                         'project__name': 'project_name'}, axis=1)
        ndf['usage_time'] = ndf['usage_time'].map(lambda x: float(x))
        if start_time and end_time:
            ndf = get_usagetime(ndf, start_time, end_time)
        ndf['start_time'] = ndf['start_time'].map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if x else x)
        ndf['end_time'] = ndf['end_time'].map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if x else x)
        ndf = ndf[['user_name', 'project_name', 'equipment_id', 'equipment_name', 'start_time', 'end_time', 'usage_time']]
        operate = request.GET.get('operate', 'list')
        if operate == 'export':
            file_path = get_file_path('detail')
            writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
            workbook = writer.book
            fmt = workbook.add_format({'font_size': 11})
            border_format = workbook.add_format({'border': 1})
            float_fmt = workbook.add_format({'num_format': '#,##0.00'})
            amt_fmt = workbook.add_format({'num_format': '#,##0'})
            title_fmt = workbook.add_format(
                {'bold': True, 'font_size': 11, 'font_name': '微软雅黑', 'num_format': 'yyyy-mm-dd hh:mm:ss',
                 'bg_color': '#9FC3D1', 'valign': 'vcenter', 'align': 'center'})
            blank_fmt = workbook.add_format({'bold': False, 'bg_color': 'white'})

            ndf = ndf.rename({'user_name': '使用人', 'project_name': '项目', 'equipment_id': '设备ID',
                              'equipment_name': '设备名称', 'start_time': '开始时间',
                              'end_time': '结束时间', 'usage_time': '使用时长'}, axis=1)
            ndf.to_excel(writer, sheet_name='使用记录', header=False, index=False, startcol=0, startrow=1)
            worksheet = writer.sheets['使用记录']
            l_end = len(ndf.index) + 1
            for col_num, value in enumerate(ndf.columns.values):
                worksheet.write(0, col_num, value, title_fmt)
            worksheet.set_column('A:D', 17, fmt)
            worksheet.set_column('E:F', 22, fmt)
            worksheet.set_column('G:G', 16, float_fmt)
            worksheet.conditional_format('A1:G%d' % l_end, {'type': 'no_blanks', 'format': border_format})
            writer.save()
            return create_excel_resp(file_path, '使用记录表')
        ndf.rename({'equipment_id': 'equipment'}, axis=1, inplace=True)
        datas = ndf.to_dict('records')
        return REST_SUCCESS(datas)
    except Exception as e:
        logger.error('查询失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '查询失败, error: {}'.format(str(e))})


# 查询设备维修时间
@api_view(['GET'])
def get_maintenance_time(request):
    try:
        obj = EquipmentMaintenanceRecord.objects
        maintenance_user = request.GET.get('maintenance_user')
        if maintenance_user:
            obj = obj.filter(maintenance_user=maintenance_user)
        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            start_time = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            end_time = datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            total_weekday = calculate_datediff(start_time, end_time)  # 总工时
        else:
            start_time, end_time = get_start_end('quarter')  # 按季度导出
            total_weekday = 625
        obj = obj.filter(Q(down_time__gte=start_time, up_time__lte=end_time) |
                         Q(down_time__range=[start_time, end_time]) | Q(up_time__range=[start_time, end_time]))
        qs = obj.order_by('-create_time').values('maintenance_user', 'down_time', 'up_time', 'maintenance_hours',
                                                 'equipment_id', 'equipment__name')
        if not qs:
            return REST_SUCCESS([])
        df = pd.DataFrame(list(qs))
        ndf = df.rename({'equipment__name': 'equipment_name'}, axis=1)
        ndf['maintenance_hours'] = ndf['maintenance_hours'].map(lambda x: float(x))
        last_ls = list(ndf.loc[ndf['down_time'] < start_time].index)
        for index in last_ls:
            ndf['down_time'].iloc[index] = start_time
        next_ls = list(ndf.loc[ndf['up_time'] > end_time].index)
        for index in next_ls:
            ndf['up_time'].iloc[index] = end_time
        if maintenance_user:
            total_df = ndf[['maintenance_user', 'equipment_id', 'maintenance_hours']]
            total_df = total_df.groupby(['maintenance_user', 'equipment_id']).sum().reset_index()
        else:
            total_df = ndf[['equipment_id', 'maintenance_hours']]
            total_df = total_df.groupby('equipment_id').sum().reset_index()
        total_df['total_weekday'] = total_weekday
        total_df['percentage'] = total_df['maintenance_hours'] / total_df['total_weekday']
        total_df['maintenance_hours'] = total_df['maintenance_hours'].map(lambda x: round(x, 2))
        operate = request.GET.get('operate', 'list')
        if operate == 'export':
            file_path = get_file_path('maintenance')
            writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
            workbook = writer.book
            fmt = workbook.add_format({'font_size': 11})
            border_format = workbook.add_format({'border': 1})
            percent_fmt = workbook.add_format({'num_format': '0.00%'})
            float_fmt = workbook.add_format({'num_format': '#,##0.00'})
            amt_fmt = workbook.add_format({'num_format': '#,##0'})
            note_fmt = workbook.add_format({'bold': True, 'font_size': 10, 'font_color': 'red',
                                            'font_name': '微软雅黑', 'align': 'left', 'valign': 'vcenter'})
            title_fmt = workbook.add_format(
                {'bold': True, 'font_size': 11, 'font_name': '微软雅黑', 'num_format': 'yyyy-mm-dd hh:mm:ss',
                 'bg_color': '#9FC3D1', 'valign': 'vcenter', 'align': 'center'})
            blank_fmt = workbook.add_format({'bold': False, 'bg_color': 'white'})

            total_df = total_df.rename({'maintenance_user': '维修人', 'equipment_id': '设备ID',
                                        'maintenance_hours': '维修时长', 'total_weekday': '有效工作时间',
                                        'percentage': '百分比'}, axis=1)
            total_df.to_excel(writer, sheet_name='维修记录', header=False, index=False, startcol=0, startrow=2)
            worksheet = writer.sheets['维修记录']
            l_end = len(total_df.index) + 2
            for col_num, value in enumerate(total_df.columns.values):
                worksheet.write(1, col_num, value, title_fmt)
            worksheet.merge_range('A1:E1', 'Begin: {}  End: {}'.format(start_time, end_time), note_fmt)
            worksheet.set_column('A:E', 15.5, fmt)
            worksheet.conditional_format('C3:C%d' % l_end, {'type': 'no_blanks', 'format': float_fmt})
            worksheet.conditional_format('D3:D%d' % l_end, {'type': 'no_blanks', 'format': amt_fmt})
            worksheet.conditional_format('E3:E%d' % l_end, {'type': 'cell', 'criteria': '>=', 'value': 0,
                                                            'format': percent_fmt})
            worksheet.conditional_format('A1:E%d' % l_end, {'type': 'no_blanks', 'format': border_format})
            writer.save()
            return create_excel_resp(file_path, '维修记录表')
        total_df.rename({'equipment_id': 'equipment'}, axis=1, inplace=True)
        result = total_df.to_dict('records')
        return REST_SUCCESS(result)
    except Exception as e:
        logger.error('查询失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '查询失败, error: {}'.format(str(e))})


# 导出设备损坏信息
@api_view(['GET'])
def get_broken_record(request):
    try:
        obj = EquipmentBrokenInfo.objects
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            obj = obj.filter(equipment_id=equipment_id)
        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            obj = obj.filter(broken_time__range=[start_time, end_time])
        qs = obj.order_by('-create_time').values('equipment_id', 'user__username', 'section__name',
                                                 'broken_reason', 'broken_time')
        if not qs:
            return REST_SUCCESS([])
        df = pd.DataFrame(list(qs))
        ndf = df.rename({'user__username': 'user_name', 'section__name': 'section_name'}, axis=1)
        ndf['broken_time'] = ndf['broken_time'].map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
        operate = request.GET.get('operate', 'list')
        if operate == 'export':
            file_path = get_file_path('broken')
            writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
            workbook = writer.book
            fmt = workbook.add_format({'font_size': 11})
            border_format = workbook.add_format({'border': 1})
            float_fmt = workbook.add_format({'num_format': '#,##0.00'})
            amt_fmt = workbook.add_format({'num_format': '#,##0'})
            title_fmt = workbook.add_format(
                {'bold': True, 'font_size': 11, 'font_name': '微软雅黑', 'num_format': 'yyyy-mm-dd hh:mm:ss',
                 'bg_color': '#9FC3D1', 'valign': 'vcenter', 'align': 'center'})
            blank_fmt = workbook.add_format({'bold': False, 'bg_color': 'white'})

            ndf = ndf.rename({'equipment_id': '设备ID', 'user_name': '损坏人', 'section_name': '部门',
                              'broken_reason': '损坏原因', 'broken_time': '损坏时间'}, axis=1)
            ndf.to_excel(writer, sheet_name='损坏信息', header=False, index=False, startcol=0, startrow=1)
            worksheet = writer.sheets['损坏信息']
            l_end = len(ndf.index) + 1
            for col_num, value in enumerate(ndf.columns.values):
                worksheet.write(0, col_num, value, title_fmt)
            worksheet.set_column('A:C', 17, fmt)
            worksheet.set_column('D:D', 25, fmt)
            worksheet.set_column('E:E', 22, float_fmt)
            worksheet.conditional_format('A1:E%d' % l_end, {'type': 'no_blanks', 'format': border_format})
            writer.save()
            return create_excel_resp(file_path, '损坏信息表')

        ndf.rename({'equipment_id': 'equipment'}, axis=1, inplace=True)
        data = ndf.to_dict('records')
        return REST_SUCCESS(data)
    except Exception as e:
        logger.error('查询失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '查询失败, error: {}'.format(str(e))})


# 导出项目计费
@api_view(['GET'])
def get_equipment_fee(request):
    try:
        obj = EquipmentBorrowRecord.objects.filter(~Q(total_amount=None), is_borrow=True, is_return=2)
        project_id = request.GET.get('project')
        if project_id:
            obj = obj.filter(project_id=project_id)
        section_id = request.GET.get('section')
        if section_id:
            obj = obj.filter(section_id=section_id)
        equipment_id = request.GET.get('equipment')
        if equipment_id:
            obj = obj.filter(equipment_id=equipment_id)
        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            start_time = datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            end_time = datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
        else:
            date_type = request.GET.get('date_type', 'week')  # week, month, year
            start_time, end_time = get_start_end(date_type)
        obj = obj.filter(Q(start_time__gte=start_time, actual_end_time__lte=end_time) |
                         Q(start_time__range=[start_time, end_time]) | Q(
            actual_end_time__range=[start_time, end_time]))
        qs = obj.values('project__name', 'section__name', 'equipment_id', 'start_time', 'actual_end_time',
                        'actual_usage_time', 'per_hour_price', 'total_amount')
        if not qs:
            return REST_SUCCESS([])
        df = pd.DataFrame(list(qs))
        ndf = df.rename({'project__name': 'project_name', 'section__name': 'section_name',
                         'actual_end_time': 'end_time', 'actual_usage_time': 'usage_time'}, axis=1)
        ndf['usage_time'] = ndf['usage_time'].map(lambda x: float(x))
        ndf['per_hour_price'] = ndf['per_hour_price'].map(lambda x: float(x))
        ndf['total_amount'] = ndf['total_amount'].map(lambda x: float(x))
        ndf = get_usagetime(ndf, start_time, end_time)
        tdf = ndf[['project_name', 'section_name', 'equipment_id', 'total_amount']]
        tdf = tdf.groupby(['project_name', 'section_name', 'equipment_id']).sum().reset_index()
        project_name_ls = [project_name for project_name in list(tdf['project_name'].unique())]
        project_name_ls.sort()

        final_df = pd.DataFrame(columns=['project_name', 'section_name', 'equipment_id', 'total_amount'],
                                dtype=object)
        for project_name in project_name_ls:
            ldf = tdf[tdf['project_name'] == project_name]
            ldf.loc['总计'] = ldf[['total_amount']].apply(lambda x: x.sum())
            ldf.fillna('', inplace=True)
            final_df = pd.concat([final_df, ldf], axis=0)
        final_df['total_amount'] = final_df['total_amount'].map(lambda x: round(x, 2))
        excel_df = final_df.rename({'project_name': '项目', 'section_name': '部门', 'equipment_id': '设备ID',
                                    'total_amount': '费用'}, axis=1)

        operate = request.GET.get('operate', 'list')
        if operate == 'export':
            file_path = get_file_path('fee')
            writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
            workbook = writer.book
            fmt = workbook.add_format({'font_size': 11})
            border_format = workbook.add_format({'border': 1})
            note_fmt = workbook.add_format({'bold': True, 'font_size': 10, 'font_color': 'red',
                                            'font_name': '微软雅黑', 'align': 'left', 'valign': 'vcenter'})
            amt_fmt = workbook.add_format({'num_format': '#,##0.00'})
            title_fmt = workbook.add_format(
                {'bold': True, 'font_size': 11, 'font_name': '微软雅黑', 'num_format': 'yyyy-mm-dd hh:mm:ss',
                 'bg_color': '#9FC3D1', 'valign': 'vcenter', 'align': 'center'})
            blank_fmt = workbook.add_format({'bold': False, 'bg_color': 'white'})
            l_end = len(excel_df.index) + 2
            excel_df.to_excel(writer, sheet_name='项目费用', header=False, index=False, startcol=0, startrow=2)
            worksheet = writer.sheets['项目费用']
            for col_num, value in enumerate(excel_df.columns.values):
                worksheet.write(1, col_num, value, title_fmt)
            worksheet.merge_range('A1:D1', 'Begin: {}  End: {}'.format(start_time, end_time), note_fmt)
            worksheet.set_column('A:D', 16.5, fmt)
            worksheet.conditional_format('D3:D%d' % l_end, {'type': 'no_blanks', 'format': amt_fmt})
            # 加边框
            worksheet.conditional_format('A1:D%d' % l_end, {'type': 'no_blanks', 'format': border_format})
            worksheet.conditional_format('A1:D%d' % l_end, {'type': 'blanks', 'format': blank_fmt})
            writer.save()
            return create_excel_resp(file_path, '设备使用计费表')
        final_df.rename({'equipment_id': 'equipment'}, axis=1, inplace=True)
        data = final_df.to_dict('records')
        return REST_SUCCESS(data)
    except Exception as e:
        logger.error('查询失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '查询失败, error: {}'.format(str(e))})
