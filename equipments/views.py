from django.views.generic.base import View
from django.http import QueryDict
from django.db.models import Q
from django.db import connection, close_old_connections, transaction
from rest_framework import generics, serializers
from rest_framework import filters, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.utils.serializer_helpers import ReturnDict
from urllib.parse import unquote

from equipments.serializers import ProjectSerializer, EquipmentSerializer, DepreciationSerializer, \
    ExtendAttribute
from equipments.serializers import BorrowRecordSerializer, OperateBorrowRecordSerializer
from equipments.serializers import ReturnApplySerializer, OperateReturnApplySerializer
from equipments.serializers import BrokenInfoSerializer, OperateBrokenInfoSerializer
from equipments.serializers import CalibrationInfoSerializer, OperateCalibrationSerializer
from equipments.serializers import MaintenanceSerializer, OperateMaintenanceSerializer
from equipments.models import Project, Equipment, EquipmentDepreciationRecord
from equipments.models import EquipmentBorrowRecord, EquipmentReturnRecord, EquipmentBrokenInfo, \
    EquipmentCalibrationInfo, EquipmentMaintenanceRecord
from equipments.ext_utils import analysis_equipment_data, create_excel_resp
from .ext_utils import VIEW_SUCCESS, VIEW_FAIL, execute_batch_sql, REST_FAIL, REST_SUCCESS
from utils.log_utils import set_create_log, set_update_log, set_delete_log, get_differ, save_operateLog
from utils.pagination import MyPagePagination
from utils.timedelta_utls import calculate_datediff, get_holiday, calculate_end_time, calculate_due_date

import re
import datetime
import pandas as pd
import os
import logging

logger = logging.getLogger('django')


# 新增项目
class ProjectListGeneric(generics.ListCreateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class ProjectDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer


# 下载设备上传文件模板
@api_view(['GET'])
def get_import_template(request):
    current_path = os.path.dirname(__file__)
    file_path = os.path.join(current_path, 'template.xlsx')
    return create_excel_resp(file_path, 'template')


# 批量导入附件设备信息
@api_view(['POST'])
def post_EquipmentData(request):
    try:
        file = request.FILES.get('file', '')
        if not file:
            return VIEW_FAIL(msg='上传文件不能为空')
        current_path = os.path.dirname(__file__)
        file_dir_path = os.path.join(current_path, 'temporydata')
        if not os.path.exists(file_dir_path):
            os.mkdir(file_dir_path)
        file_path = os.path.join(file_dir_path, file.name)
        with open(file_path, 'wb') as f:
            for i in file.chunks():
                f.write(i)
    except Exception as e:
        logger.error('解析文件出错, error:{}'.format(str(e)))
        return VIEW_FAIL(msg='解析文件出错, error:{}'.format(str(e)))

    insert_equipment_sql = '''insert into equipment(id, name, number, serial_number, fixed_asset_code,
                                    fixed_asset_name, fixed_asset_category,specification,performance,is_allow_renew,
                                    deposit_position, manufacturer, manufacture_date, custodian,
                                    usage_description,dispose_suggestion, entry_date,
                                    original_cost, estimate_life, net_salvage, create_time, update_time, 
                                    equipment_state, is_delete)
                              values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                                            %s, %s, %s, %s, %s, %s, %s, %s, %s)'''

    update_equipment_sql = '''update equipment set name=%s,number=%s,serial_number=%s,fixed_asset_code=%s,
                                    fixed_asset_name=%s, fixed_asset_category=%s,specification=%s,performance=%s,
                                    is_allow_renew=%s, deposit_position=%s, manufacturer=%s, manufacture_date=%s, 
                                    custodian=%s, usage_description=%s,dispose_suggestion=%s, entry_date=%s,
                                    original_cost=%s, estimate_life=%s, net_salvage=%s,update_time=%s,equipment_state=%s where id=%s'''

    insert_depreciation_sql = '''insert into equipment_depreciation_record(method, periods, depreciated_total,
                                            net_value, net_amount, depreciate_date, create_time, equipment_id)
                                  select %s, %s, %s, %s, %s, %s, %s, %s
                                  where not exists(select equipment_id from equipment_depreciation_record
                                        where equipment_id=%s and periods=%s)'''

    insert_calibration_sql = '''insert into equipment_calibration_info(calibration_time, recalibration_time, due_date, 
                                        certificate, certificate_year, create_time, update_time, equipment_id, state)
                                  values(%s, %s, %s, %s, %s, %s, %s, %s, %s)'''

    update_calibration_sql = '''update equipment_calibration_info set calibration_time=%s,recalibration_time=%s,
                                    due_date=%s,certificate=%s,certificate_year=%s,update_time=%s,state=%s where equipment_id=%s'''

    # datas = req_dic.get('datas', [])
    df = pd.read_excel(file_path, sheet_name='Sheet1')
    datas = df.to_dict('records')
    datas = analysis_equipment_data(datas)
    count = 0
    try:
        insert_equipment_ls = []
        update_equipment_ls = []
        depreciation_ls = []
        calibration_ls = []
        update_calibration_ls = []
        now_ts = datetime.datetime.now()
        for data in datas:
            count += 1
            lineNo = count + 1
            equipment_id = data.get('id')
            if not equipment_id:
                return VIEW_FAIL(msg='设备ID不能为空, 空值所在行: {}'.format(lineNo))
            name = data.get('name')
            if not name:
                return VIEW_FAIL(msg='设备名称不能为空, 空值所在行: {}'.format(lineNo))
            number = data.get('number')
            serial_number = data.get('serial_number')
            # if not serial_number:
            #     serial_number = ''
            #     return VIEW_FAIL(msg='序列号不能为空, 空值所在行: {}'.format(lineNo))
            serial_number = serial_number
            fixed_asset_code = data.get('fixed_asset_code')
            # if not fixed_asset_code:
            #     fixed_asset_code = ''
            #     return VIEW_FAIL(msg='固定资产编码不能为空, 空值所在行: {}'.format(lineNo))
            fixed_asset_name = data.get('fixed_asset_name')
            # if not fixed_asset_name:
            #     fixed_asset_name = ''
            #     return VIEW_FAIL(msg='固定资产名称不能为空, 空值所在行: {}'.format(lineNo))
            fixed_asset_category = data.get('fixed_asset_category')
            specification = data.get('specification')
            # if not specification:
            #     specification = ''
            #     return VIEW_FAIL(msg='规格型号描述不能为空, 空值所在行: {}'.format(lineNo))
            performance = data.get('performance')
            is_allow_renew = data.get('is_allow_renew')
            deposit_position = data.get('deposit_position')
            if not deposit_position:
                return VIEW_FAIL(msg='存放地点不能为空, 空值所在行: {}'.format(lineNo))
            manufacturer = data.get('manufacturer')
            manufacture_date = data.get('manufacture_date')
            custodian = data.get('custodian')
            # if not custodian:
            #     custodian = ''
            #     return VIEW_FAIL(msg='保管人不能为空, 空值所在行: {}'.format(lineNo))
            usage_description = data.get('usage_description')
            dispose_suggestion = data.get('dispose_suggestion')
            entry_date = data.get('entry_date')
            original_cost = data.get('original_cost')
            estimate_life = data.get('estimate_life')
            net_salvage = data.get('net_salvage')
            equipment_state = data.get('equipment_state')

            existqs = Equipment.objects.filter(id=equipment_id)  # 判断设备是否存在，存在则更新
            if existqs:
                update_equipment_args = (name, number, serial_number, fixed_asset_code, fixed_asset_name,
                                  fixed_asset_category, specification, performance, is_allow_renew, deposit_position,
                                  manufacturer, manufacture_date, custodian, usage_description, dispose_suggestion,
                                  entry_date, original_cost, estimate_life, net_salvage, now_ts, equipment_state, equipment_id)
                update_equipment_ls.append(update_equipment_args)
            else:
                insert_equipment_args = (equipment_id, name, number, serial_number, fixed_asset_code, fixed_asset_name,
                                  fixed_asset_category, specification, performance, is_allow_renew, deposit_position,
                                  manufacturer, manufacture_date, custodian, usage_description, dispose_suggestion,
                                  entry_date, original_cost, estimate_life, net_salvage, now_ts, now_ts, equipment_state, False)
                insert_equipment_ls.append(insert_equipment_args)

            method = data.get('method')
            if method:
                periods = data.get('periods')
                depreciated_total = data.get('depreciated_total')
                net_value = data.get('net_value')
                net_amount = data.get('net_amount')
                depreciate_date = data.get('depreciate_date')
                depreciation_args = (method, periods, depreciated_total, net_value, net_amount,
                                     depreciate_date, now_ts, equipment_id, equipment_id, periods)
                depreciation_ls.append(depreciation_args)

            calibration_time = data.get('calibration_time')
            if calibration_time:
                recalibration_time = data.get('recalibration_time')
                due_date = data.get('due_date')
                certificate = data.get('certificate', '')
                if not certificate:
                    certificate = ''
                certificate_year = data.get('certificate_year')
                try:
                    due_date = str(int(due_date))
                    calibration_state = '校验完成'
                except:
                    calibration_state = '待送检'
                calibration_qs = EquipmentCalibrationInfo.objects.filter(equipment_id=equipment_id)
                if calibration_qs:
                    update_calibration_args = (calibration_time, recalibration_time, due_date, certificate,
                                               certificate_year, now_ts, calibration_state, equipment_id)
                    update_calibration_ls.append(update_calibration_args)
                else:
                    calibration_args = (calibration_time, recalibration_time, due_date, certificate, certificate_year,
                                        now_ts, now_ts, equipment_id, calibration_state)
                    calibration_ls.append(calibration_args)

            if len(insert_equipment_ls) + len(update_equipment_ls) >= 10:
                execute_batch_sql(insert_equipment_sql, insert_equipment_ls)
                execute_batch_sql(update_equipment_sql, update_equipment_ls)
                execute_batch_sql(insert_depreciation_sql, depreciation_ls)
                execute_batch_sql(insert_calibration_sql, calibration_ls)
                execute_batch_sql(update_calibration_sql, update_calibration_ls)
                insert_equipment_ls = []
                update_equipment_ls = []
                depreciation_ls = []
                calibration_ls = []
                update_calibration_ls = []

        if len(insert_equipment_ls) + len(update_equipment_ls) > 0:
            execute_batch_sql(insert_equipment_sql, insert_equipment_ls)
            execute_batch_sql(update_equipment_sql, update_equipment_ls)
            execute_batch_sql(insert_depreciation_sql, depreciation_ls)
            execute_batch_sql(insert_calibration_sql, calibration_ls)
            execute_batch_sql(update_calibration_sql, update_calibration_ls)
    except Exception as e:
        logger.error('设备信息插入数据库失败, error:{}'.format(str(e)))
        error_code = e.args[0]
        if error_code == 1062:
            msg = '存在重复导入'
            error = e.args[1]
            reg = re.findall(r"Duplicate entry '(.*)' for key", error)
            if reg:
                msg += '：{}'.format(reg[0])
        elif error_code == 1111:
            msg = e.args[1]
            error = e.args[1]
        else:
            msg = '保存失败'
            error = str(e)
        return VIEW_FAIL(msg=msg, data={'error': error})
    return VIEW_SUCCESS()


# 获取已存在的存放地点
@api_view(['GET'])
def get_deposit_position(request):
    qs = Equipment.objects.values('deposit_position').distinct()
    deposit_positions = []
    if qs:
        deposit_positions = [item['deposit_position'] for item in list(qs)]
    return REST_SUCCESS(deposit_positions)


# 查询设备，新增设备
class EquipmentListGeneric(generics.ListCreateAPIView):
    model = Equipment
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name
    queryset = model.objects.all()
    serializer_class = EquipmentSerializer
    pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        search = request.GET.get('search', '')
        if search:
            queryset = queryset.filter(Q(id=search) | Q(name__contains=search) | Q(fixed_asset_name__contains=search))
        #
        # fuzzy_params = {}
        # fuzzy_params['name'] = request.GET.get('name', '')
        # fuzzy_params['fixed_asset_name'] = request.GET.get('fixed_asset_name', '')
        #
        # filter_params = {}
        # for k, v in fuzzy_params.items():
        #     if v != None and v != '':
        #         k = k + '__contains'
        #         filter_params[k] = v
        # if filter_params:
        #     queryset = queryset.filter(**filter_params)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @set_create_log
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class EquipmentDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# 对设备信息进行操作
class EquipmentDetail(APIView):
    model = Equipment
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def get_object(self, equipment_id):
        try:
            obj = Equipment.objects
            equipment = obj.get(pk=equipment_id)
            return equipment
        except Equipment.DoesNotExist:
            return None

    def get(self, request):
        equipment_id = request.GET.get('id')
        equipment = self.get_object(equipment_id)
        if not equipment:
            return REST_FAIL({'msg': '找不到该设备'})
        serializer = EquipmentSerializer(equipment)
        return Response(serializer.data)

    def put(self, request):
        equipment_id = request.data.get('id')
        equipment = self.get_object(equipment_id)
        if not equipment:
            return REST_FAIL({'msg': '找不到该设备'})
        before = EquipmentSerializer(equipment).data
        extendattribute_set = request.data.pop('extendattribute_set', [])
        serializer = EquipmentSerializer(equipment, data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            if extendattribute_set:
                for _fields in extendattribute_set:
                    attribute_name = _fields['attribute_name']
                    attribute_value = _fields['attribute_value']
                    qs = ExtendAttribute.objects.filter(equipment_id=equipment_id,
                                                        attribute_name=attribute_name)
                    if qs:
                        qs.update(attribute_value=attribute_value)
                    else:
                        ExtendAttribute.objects.create(equipment_id=equipment_id,
                                                       attribute_name=attribute_name,
                                                       attribute_value=attribute_value).save()
            after = serializer.data
            change = get_differ(before, after)
            save_operateLog('update', request.user, self.table_name, self.verbose_name, before, after, change)
            return Response(serializer.data)

    def delete(self, request):
        query_str = QueryDict(request.META.get('QUERY_STRING', ''))
        equipment_id = query_str.get('id')
        equipment = self.get_object(equipment_id)
        if not equipment:
            return REST_FAIL({'msg': '找不到该设备'})
        before = EquipmentSerializer(equipment).data
        equipment.delete()
        save_operateLog('delete', request.user, self.table_name, self.verbose_name, before=before)
        return VIEW_SUCCESS()


# 设备折旧记录
class DepreciationListGeneric(generics.ListCreateAPIView):
    model = EquipmentDepreciationRecord
    queryset = model.objects.all().order_by('-create_time')
    serializer_class = DepreciationSerializer
    pagination_class = MyPagePagination
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('search', '')
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)  # 精确查询

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @set_create_log
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# 操作折旧记录
class DepreciationDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = EquipmentDepreciationRecord
    queryset = model.objects.all()
    serializer_class = DepreciationSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_update_log
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    @set_delete_log
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return VIEW_SUCCESS(msg='删除成功')


# 查询一个设备的可借用时间限制条件
def get_borrow_time_limit(equipment_id):
    equipment_qs = Equipment.objects.filter(id=equipment_id)
    brrow_qs = EquipmentBorrowRecord.objects.filter(equipment__id=equipment_id).order_by('-end_time')
    allow_borrow_days = equipment_qs.first().allow_borrow_days
    last_borrow_end_time = None
    if brrow_qs:
        last_borrow_end_time = brrow_qs.first().end_time
    return {'last_borrow_end_time': last_borrow_end_time, 'allow_borrow_days': allow_borrow_days}


# 申请借用
class BorrowListGeneric(generics.ListCreateAPIView):
    queryset = EquipmentBorrowRecord.objects.all().order_by('-create_time')
    serializer_class = BorrowRecordSerializer
    pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)  # 精确查询

        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            queryset = queryset.filter(Q(start_time__gte=start_time), Q(end_time__lte=end_time))

        fuzzy_params = {}
        fuzzy_params['user__username'] = request.GET.get('user_name', '')
        fuzzy_params['equipment__name'] = request.GET.get('equipment_name', '')
        fuzzy_params['equipment__fixed_asset_name'] = request.GET.get('fixed_asset_name', '')
        fuzzy_params['project__name'] = request.GET.get('project_name', '')
        fuzzy_params['section__name'] = request.GET.get('section_name', '')

        filter_params = {}
        for k, v in fuzzy_params.items():
            if v != None and v != '':
                k = k + '__contains'
                filter_params[k] = v

        if filter_params:
            queryset = queryset.filter(**filter_params)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        data.update({'user': request.user})
        data.update({'section': request.user.section})
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        borrow_type = data.get('borrow_type')

        equipment = data.get('equipment')
        if equipment.equipment_state != 1:
            raise serializers.ValidationError('设备当前状态为{}, 暂时无法借用'.format(equipment.get_equipment_state_display()))
        if borrow_type in ['正常申请', '恢复中断']:  # 判断选择的日期是否在设备可借用时间内
            borrow_time_limit = get_borrow_time_limit(equipment.id)
            last_borrow_end_time = borrow_time_limit['last_borrow_end_time']
            allow_borrow_days = borrow_time_limit['allow_borrow_days']
            if borrow_type == '正常申请':
                if last_borrow_end_time:
                    if last_borrow_end_time > start_time:
                        raise serializers.ValidationError('借用开始时间最早为: {}'.format(last_borrow_end_time))
            if borrow_type == '恢复中断':  # 根据上次剩余时间限制结束时间
                req_borrow_qs = EquipmentBorrowRecord.objects.filter(user=request.user, is_delete=False,
                                                                     is_interrupted=True,
                                                                     is_recovery_interrupt=False).order_by('id').last()
                if not req_borrow_qs:
                    raise serializers.ValidationError('您当前没有可恢复中断的借用申请')
                interrupt_id = req_borrow_qs.id
                surplus_hours = float(req_borrow_qs.expect_usage_time) - float(req_borrow_qs.actual_usage_time)
                if surplus_hours > 0:  # 根据上次中断剩余时间计算最晚借用结束时间
                    end = calculate_end_time(start_time, surplus_hours)
                    allow_end_time = end
                    if allow_end_time < end_time:
                        raise serializers.ValidationError('借用结束时间最晚为: {}'.format(allow_end_time))
                else:
                    raise serializers.ValidationError('您已经没有可借用时长了')
            else:
                if allow_borrow_days:
                    allow_end_time = start_time + datetime.timedelta(days=allow_borrow_days)
                    if allow_end_time < end_time:
                        raise serializers.ValidationError('借用结束时间最晚为: {}'.format(allow_end_time))

        expect_usage_time = calculate_datediff(start_time, end_time)
        data.update({'expect_usage_time': expect_usage_time})
        if borrow_type in ['紧急申请', '恢复中断', '续借']:
            # 先查询当前紧急借用时间段内是否有排队的用户,如果有，所以用户时间往后推迟
            now_range_time_qs = EquipmentBorrowRecord.objects.filter(Q(start_time__range=[start_time, end_time]) |
                                                                     Q(end_time__range=[start_time, end_time]),
                                                                     is_borrow=False, is_delete=False,
                                                                     equipment_id=equipment.id).order_by('id')
            if now_range_time_qs:
                need_delay_qs = EquipmentBorrowRecord.objects.filter(start_time__gte=now_range_time_qs.first().start_time,
                                                                     is_borrow=False, is_delete=False,
                                                                     equipment_id=equipment.id)

                # 对正在排队的用户做时间顺延
                with transaction.atomic():
                    save_id = transaction.savepoint()
                    try:
                        last_end_time = end_time
                        for b_obj in need_delay_qs:
                            if last_end_time > b_obj.start_time:
                                delay_start_time = last_end_time
                            delay_start_time_tofmt = delay_start_time.strftime('%Y-%m-%d %H:%M:%S')
                            list_delay_start = delay_start_time_tofmt.split(' ')
                            start = datetime.datetime.strptime(delay_start_time_tofmt, '%Y-%m-%d %H:%M:%S')
                            start_d = datetime.datetime.strptime(list_delay_start[0], '%Y-%m-%d')
                            if list_delay_start[1] >= '19:00:00':  # 过了下班时间
                                start_d += datetime.timedelta(days=1)
                                start = start_d + datetime.timedelta(hours=9)
                                list_delay_start[1] = '09:00:00'
                            if list_delay_start[1] < '09:00:00':
                                start = start_d + datetime.timedelta(hours=9)
                            # if '12:00:00' <= list_delay_start[1] < '13:00:00':  # 落在午休时间
                            #     start = start_d + datetime.timedelta(hours=13)
                            #     list_delay_start[1] = '13:00:00'
                            # 判断此时的开始时间是否在节假日期间，如果在则继续推后
                            list_holiday = get_holiday(start.year, 'datetime')
                            if start_d in list_holiday:
                                while start_d in list_holiday:
                                    start_d += datetime.timedelta(days=1)
                                    if start_d.year != start.year:  # 跨年
                                        list_holiday = get_holiday(start_d.year, 'datetime')
                                start = start_d + datetime.timedelta(hours=9)
                                list_delay_start[1] = '09:00:00'
                            # 根据开始时间和原预估使用时间计算新的结束时间(跳过非工作时间)
                            end = calculate_end_time(start, float(b_obj.expect_usage_time))
                            list_holiday = get_holiday(end.year, 'datetime')
                            end_d = datetime.datetime.strptime(end.strftime('%Y-%m-%d'), '%Y-%m-%d')
                            # 判断结束时间是否落在节假日，如果在则继续推后
                            if end_d in list_holiday:
                                while end_d in list_holiday:
                                    end_d += datetime.timedelta(days=1)
                                    if end_d.year != end.year:
                                        list_holiday = get_holiday(end_d.year, 'datetime')
                                end = end_d + datetime.timedelta(hours=end.hour, minutes=end.minute, seconds=end.second)
                            b_obj.start_time = start
                            b_obj.end_time = end
                            b_obj.save()
                            last_end_time = end
                        transaction.savepoint_commit(save_id)
                    except Exception as e:
                        transaction.savepoint_rollback(save_id)
                        logger.error('顺延排队用户借用时间失败,error:{}'.format(str(e)))
                        raise serializers.ValidationError('顺延排队用户借用时间失败')

        if borrow_type == '恢复中断':
            EquipmentBorrowRecord.objects.filter(id=interrupt_id).update(is_recovery_interrupt=True)
        data.update({'per_hour_price': equipment.per_hour_price})
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# 操作借用记录
class OperateBorrowRecordGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = EquipmentBorrowRecord
    queryset = model.objects.all()
    serializer_class = OperateBorrowRecordSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_update_log
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        expect_usage_time = calculate_datediff(start_time, end_time)
        data.update({'expect_usage_time': expect_usage_time})
        is_borrow = data.get('is_borrow')
        if is_borrow is True:
            Equipment.objects.filter(id=instance.equipment.id).update(equipment_state=2)
        serializer.validated_data.update(data)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    @set_delete_log
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return VIEW_SUCCESS(msg='删除成功')


# 查询可借用的时间范围
@api_view(['GET'])
def get_AllowBorrowTime(request):
    equipment_id = request.GET.get('equipment')
    borrow_type = request.GET.get('borrow_type')
    if not equipment_id:
        return VIEW_FAIL(msg='设备ID不能为空')
    if not borrow_type:
        return VIEW_FAIL(msg='借用类型不能为空')
    equipment_qs = Equipment.objects.filter(id=equipment_id)
    if not equipment_qs:
        return VIEW_FAIL(msg='找不到该设备')
    equipment_state = equipment_qs.first().equipment_state
    if equipment_state != 1:
        return VIEW_FAIL('设备当前状态为{}, 暂时无法借用'.format(equipment_qs.first().get_equipment_state_display()))
    borrow_time_limit = get_borrow_time_limit(equipment_id)
    last_borrow_end_time = borrow_time_limit['last_borrow_end_time']
    allow_borrow_days = borrow_time_limit['allow_borrow_days']
    allow_start_time = datetime.datetime.now().replace(second=0, microsecond=0)
    allow_end_time = None
    if borrow_type == '正常申请':  # 限制开始时间
        if last_borrow_end_time:
            if last_borrow_end_time > allow_start_time:
                allow_start_time = last_borrow_end_time
    if borrow_type == '恢复中断':  # 根据上次剩余时间限制结束时间
        req_borrow_qs = EquipmentBorrowRecord.objects.filter(user=request.user, is_delete=False, is_interrupted=True).\
                                    order_by('id').last()
        surplus_hours = float(req_borrow_qs.expect_usage_time) - float(req_borrow_qs.actual_usage_time)
        if surplus_hours > 0:
            allow_end_time = allow_start_time + datetime.timedelta(hours=surplus_hours)
        else:
            allow_end_time = allow_start_time
    else:
        if allow_borrow_days:
            allow_end_time = allow_start_time + datetime.timedelta(days=allow_borrow_days)
    return VIEW_SUCCESS(data={'allow_start_time': allow_start_time, 'allow_end_time': allow_end_time})


# 归还设备
class ReturnListGeneric(generics.ListCreateAPIView):
    queryset = EquipmentReturnRecord.objects.all().order_by('-create_time')
    serializer_class = ReturnApplySerializer
    pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            queryset = queryset.filter(borrow_record__equipment__id=equipment_id)  # 精确查询

        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            queryset = queryset.filter(return_time__range=[start_time, end_time])

        fuzzy_params = {}
        fuzzy_params['borrow_record__user__username'] = request.GET.get('user_name', '')
        fuzzy_params['borrow_record__equipment__name'] = request.GET.get('equipment_name', '')
        fuzzy_params['borrow_record__equipment__fixed_asset_name'] = request.GET.get('fixed_asset_name', '')
        fuzzy_params['borrow_record__project__name'] = request.GET.get('project_name', '')
        fuzzy_params['borrow_record__section__name'] = request.GET.get('section_name', '')

        filter_params = {}
        for k, v in fuzzy_params.items():
            if v != None and v != '':
                k = k + '__contains'
                filter_params[k] = v

        if filter_params:
            queryset = queryset.filter(**filter_params)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# 操作归还申请
class OperateReturnApplyGeneric(generics.RetrieveUpdateAPIView):
    model = EquipmentReturnRecord
    queryset = model.objects.all()
    serializer_class = OperateReturnApplySerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_update_log
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        borrow_obj = EquipmentBorrowRecord.objects.filter(id=instance.borrow_record_id)
        equipment_id = instance.borrow_record.equipment_id
        equipment_obj = Equipment.objects.filter(id=equipment_id)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        borrow_record = serializer.validated_data.pop('borrow_record')
        is_interrupted = borrow_record.get('is_interrupted')
        data = serializer.validated_data.copy()
        confirm_state = data.get('confirm_state')
        return_position = data.get('return_position')
        if confirm_state is not None:
            data.update({'is_confirm': True})
            borrow_instance = borrow_obj.first()
            start_time = borrow_instance.start_time
            per_hour_price = borrow_instance.per_hour_price
            actual_end_time = data.get('return_time')
            actual_usage_time = calculate_datediff(start_time, actual_end_time)
            total_amount = None
            if per_hour_price:
                total_amount = round((actual_usage_time * float(per_hour_price)), 2)
            if confirm_state == '正常':
                equipment_state = 1
            elif confirm_state == '损坏':
                equipment_state = 5
            else:
                raise serializers.ValidationError('确认结果不能为空')
            with transaction.atomic():
                save_id = transaction.savepoint()
                try:
                    # 更新借用记录
                    borrow_obj.update(is_return=True,
                                      is_interrupted=is_interrupted,
                                      actual_end_time=actual_end_time,
                                      actual_usage_time=actual_usage_time,
                                      total_amount=total_amount,
                                      update_time=datetime.datetime.now())
                    # 更新设备状态和位置
                    equipment_obj.update(equipment_state=equipment_state,
                                         deposit_position=return_position,
                                         update_time=datetime.datetime.now())
                    serializer.validated_data.update(data)
                    self.perform_update(serializer)

                    if confirm_state == '正常':
                        # TODO 通知下一个预约用户可借用了
                        next_user_qs = EquipmentBorrowRecord.objects.filter(start_time__gte=actual_end_time,
                                                                            equipment_id=equipment_id,
                                                                            is_borrow=False, is_delete=False,
                                                                            is_approval=True).order_by('id')
                        if next_user_qs:
                            next_user = next_user_qs.first().user
                    transaction.savepoint_commit(save_id)
                except Exception as e:
                    transaction.savepoint_rollback(save_id)
                    logger.error('归还信息存储失败,error:{}'.format(str(e)))
                    raise serializers.ValidationError('归还信息存储失败')
        else:
            serializer.validated_data.update(data)
            self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


# 填写设备损坏单
class BrokenInfoGeneric(generics.ListCreateAPIView):
    model = EquipmentBrokenInfo
    queryset = model.objects.all().order_by('-create_time')
    serializer_class = BrokenInfoSerializer
    pagination_class = MyPagePagination
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            queryset = queryset.filter(equipment__id=equipment_id)  # 精确查询

        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            queryset = queryset.filter(broken_time__range=[start_time, end_time])

        fuzzy_params = {}
        fuzzy_params['user__username'] = request.GET.get('user_name', '')
        fuzzy_params['equipment__name'] = request.GET.get('equipment_name', '')
        fuzzy_params['equipment__fixed_asset_name'] = request.GET.get('fixed_asset_name', '')
        fuzzy_params['section__name'] = request.GET.get('section_name', '')

        filter_params = {}
        for k, v in fuzzy_params.items():
            if v != None and v != '':
                k = k + '__contains'
                filter_params[k] = v

        if filter_params:
            queryset = queryset.filter(**filter_params)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @set_create_log
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        broken_user = data.get('user')
        data.update({'section': broken_user.section})
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# 操作损坏记录
class OperateBrokenInfoGeneric(generics.RetrieveUpdateAPIView):
    model = EquipmentBrokenInfo
    queryset = model.objects.all()
    serializer_class = OperateBrokenInfoSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_update_log
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        equipment_id = instance.equipment.id
        is_maintenance = data.get('is_maintenance')
        if is_maintenance is True:
            Equipment.objects.filter(id=equipment_id).update(equipment_state=1)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


# 校验记录
class CalibrationInfoGeneric(generics.ListCreateAPIView):
    model = EquipmentCalibrationInfo
    queryset = model.objects.all().order_by('-create_time')
    serializer_class = CalibrationInfoSerializer
    pagination_class = MyPagePagination
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            queryset = queryset.filter(equipment__id=equipment_id)  # 精确查询

        calibration_start_time = request.GET.get('calibration_start_time')
        calibration_end_time = request.GET.get('calibration_end_time')
        if calibration_start_time and calibration_end_time:
            queryset = queryset.filter(calibration_time__range=[calibration_start_time, calibration_end_time])

        fuzzy_params = {}
        fuzzy_params['equipment__name'] = request.GET.get('equipment_name', '')
        fuzzy_params['equipment__fixed_asset_name'] = request.GET.get('fixed_asset_name', '')

        filter_params = {}
        for k, v in fuzzy_params.items():
            if v != None and v != '':
                k = k + '__contains'
                filter_params[k] = v

        if filter_params:
            queryset = queryset.filter(**filter_params)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @set_create_log
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        recalibration_time = data.get('recalibration_time')
        state = data.get('state')
        equipment = data.get('equipment')
        if state == '已送检':
            if equipment.equipment_state != 3:
                Equipment.objects.filter(id=equipment.id).update(equipment_state=3)
        elif state == '校验完成':
            if equipment.equipment_state == 3:
                Equipment.objects.filter(id=equipment.id).update(equipment_state=1)
        due_date = calculate_due_date(recalibration_time)
        data.update({'due_date': due_date})
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# 更新校验信息
class OperateCalibrationInfoGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = EquipmentCalibrationInfo
    queryset = model.objects.all()
    serializer_class = OperateCalibrationSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_update_log
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        recalibration_time = data.get('recalibration_time')
        state = data.get('state')
        equipment = instance.equipment
        if state == '已送检':
            if equipment.equipment_state != 3:
                Equipment.objects.filter(id=equipment.id).update(equipment_state=3)
        elif state == '校验完成':
            if equipment.equipment_state == 3:
                Equipment.objects.filter(id=equipment.id).update(equipment_state=1)
        due_date = calculate_due_date(recalibration_time)
        data.update({'due_date': due_date})
        serializer.validated_data.update(data)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    @set_delete_log
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return VIEW_SUCCESS(msg='删除成功')


class MaintenanceGeneric(generics.ListCreateAPIView):
    queryset = EquipmentMaintenanceRecord.objects.all().order_by('-create_time')
    serializer_class = MaintenanceSerializer
    pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            queryset = queryset.filter(equipment__id=equipment_id)  # 精确查询

        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            queryset = queryset.filter(Q(down_time__gte=start_time), Q(up_time__lte=end_time))

        fuzzy_params = {}
        fuzzy_params['equipment__name'] = request.GET.get('equipment_name', '')
        fuzzy_params['equipment__fixed_asset_name'] = request.GET.get('fixed_asset_name', '')

        filter_params = {}
        for k, v in fuzzy_params.items():
            if v != None and v != '':
                k = k + '__contains'
                filter_params[k] = v

        if filter_params:
            queryset = queryset.filter(**filter_params)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        equipment = data.get('equipment')
        Equipment.objects.filter(id=equipment.id).update(equipment_state=1)
        data.update({'maintenance_user': request.user.username})
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class OperateMaintenanceGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = EquipmentMaintenanceRecord
    queryset = model.objects.all()
    serializer_class = OperateMaintenanceSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_update_log
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    @set_delete_log
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return VIEW_SUCCESS(msg='删除成功')
