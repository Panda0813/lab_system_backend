from django.views.generic.base import View
from django.http import QueryDict
from django.db.models import Q, Count
from django.db import connection, close_old_connections, transaction
from rest_framework import generics, serializers
from rest_framework import filters, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.utils.serializer_helpers import ReturnDict
from urllib.parse import unquote
from dateutil.relativedelta import relativedelta

from equipments.serializers import ProjectSerializer, EquipmentSerializer, DepreciationSerializer, \
    ExtendAttribute
from equipments.serializers import BorrowRecordSerializer, OperateBorrowRecordSerializer
from equipments.serializers import ReturnApplySerializer, OperateReturnApplySerializer
from equipments.serializers import BrokenInfoSerializer, OperateBrokenInfoSerializer
from equipments.serializers import CalibrationInfoSerializer, OperateCalibrationSerializer
from equipments.serializers import MaintenanceSerializer, OperateMaintenanceSerializer, \
    MaintainInfoSerializer, OperateMaintainInfoSerializer
from equipments.models import Project, Equipment, EquipmentDepreciationRecord
from equipments.models import EquipmentBorrowRecord, EquipmentReturnRecord, EquipmentBrokenInfo, \
    EquipmentCalibrationInfo, EquipmentMaintenanceRecord, EquipmentMaintainInfo, EquipmentCalibrationCertificate
from equipments.serializers import CalibrationCertificateSerializer
from equipments.ext_utils import analysis_equipment_data, create_excel_resp, \
    analysis_calibration, analysis_maintain, analysis_certificate
from .ext_utils import VIEW_SUCCESS, VIEW_FAIL, execute_batch_sql, REST_FAIL, REST_SUCCESS
from utils.log_utils import set_create_log, set_update_log, set_delete_log, get_differ, save_operateLog
from utils.pagination import MyPagePagination
from utils.timedelta_utls import calculate_datediff, get_holiday, calculate_end_time, calculate_due_date, \
    calculate_recalibration_time, calculate_pm_time

import json
import re
import datetime
import pandas as pd
import os
import logging

logger = logging.getLogger('django')


# ????????????
class ProjectListGeneric(generics.ListCreateAPIView):
    queryset = Project.objects.all().order_by('name')
    serializer_class = ProjectSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class ProjectDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer


# ??????????????????
@api_view(['GET'])
def get_map_options(request):
    equipment_state = [
        {'value': 1, 'label': '??????'},
        {'value': 2, 'label': '?????????'},
        {'value': 3, 'label': '?????????'},
        {'value': 4, 'label': '??????'},
        {'value': 5, 'label': '??????'},
        {'value': 6, 'label': '??????'}]
    service_type = [
        {'value': 1, 'label': '?????????'},
        {'value': 2, 'label': '??????'},
        {'value': 3, 'label': '??????'},
        {'value': 4, 'label': '??????'},
        {'value': 5, 'label': '??????'},
    ]
    manage_type = [
        {'value': 1, 'label': 'PM'},
        {'value': 2, 'label': 'Check'},
        {'value': 3, 'label': 'Inspection'}
    ]
    return REST_SUCCESS({
        'equipment_state': equipment_state,
        'service_type': service_type,
        'manage_type': manage_type
    })


# ??????????????????
@api_view(['GET'])
def get_category(request):
    categoryBase = [
        {'id': 1, 'name': 'ATE Tester'},
        {'id': 2, 'name': 'Tester Cell Machine'},
        {'id': 3, 'name': 'Reliability & Environment'},
        {'id': 4, 'name': 'Measurement & Intrumentation'},
        {'id': 5, 'name': 'Probe, Tip & Assembly'},
        {'id': 6, 'name': 'Device Test Tooling'},
        {'id': 7, 'name': 'Inspection & Rework'},
        {'id': 8, 'name': 'Other Tool, Jig & Kit'},
        {'id': 9, 'name': 'Facility Equipment & Tool'},
        {'id': 10, 'name': 'APT MB & SLT System'}]
    df1 = pd.DataFrame(categoryBase)
    obj = Equipment.objects.filter(is_delete=False)
    search = request.GET.get('search', '')
    if search:
        obj = obj.filter(Q(id=search) | Q(name__contains=search))
    equipment_state = request.GET.get('equipment_state')
    if equipment_state:
        equipment_state_ls = equipment_state.split(',')
        obj = obj.filter(equipment_state__in=equipment_state_ls)
    countqs = obj.values('fixed_asset_category').annotate(count=Count('id')).all()
    if countqs:
        countqs = list(countqs)
        df2 = pd.DataFrame(countqs)
        df2.rename(columns={'fixed_asset_category': 'id'}, inplace=True)
        df = pd.merge(df1, df2, on='id', how='left')
        df.fillna(0, inplace=True)
    else:
        df = df1.copy()
        df['count'] = 0
    df['count'] = df['count'].astype('int')
    category = df.to_dict('records')
    return REST_SUCCESS(category)


# ??????????????????????????????
@api_view(['GET'])
def get_upload_template(request):
    current_path = os.path.dirname(__file__)
    file_name = request.GET.get('file_name')
    if not file_name:
        return REST_FAIL({'msg': 'file_name????????????'})
    file_path = os.path.join(current_path, '{}.xlsx'.format(file_name))
    return create_excel_resp(file_path, file_name)


# ??????????????????????????????
@api_view(['POST'])
def post_EquipmentData(request):
    try:
        try:
            file = request.FILES.get('file', '')
            if not file:
                return VIEW_FAIL(msg='????????????????????????')
            current_path = os.path.dirname(__file__)
            file_dir_path = os.path.join(current_path, 'temporydata')
            if not os.path.exists(file_dir_path):
                os.mkdir(file_dir_path)
            file_path = os.path.join(file_dir_path, 'UniIC_Equipment_Resource_Management_System_v1.xlsx')
            with open(file_path, 'wb') as f:
                for i in file.chunks():
                    f.write(i)
        except Exception as e:
            logger.error('??????????????????, error:{}'.format(str(e)))
            return VIEW_FAIL(msg='??????????????????, error:{}'.format(str(e)))

        insert_equipment_sql = '''insert into equipment(id, name, number, serial_number, fixed_asset_code,
                                        fixed_asset_category, custodian, equipment_state, service_type,specification,
                                        performance, assort_material,deposit_position, install_date, manage_type,manager,
                                        application_specialist, manufacturer, manufacture_date, origin_place,
                                        create_time, update_time, is_delete)
                                  values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                                                    %s, %s, %s, %s, %s, %s, %s, %s)'''

        update_equipment_sql = '''update equipment set name=%s,number=%s,serial_number=%s,fixed_asset_code=%s,
                                        fixed_asset_category=%s,custodian=%s,equipment_state=%s,service_type=%s,
                                        specification=%s,performance=%s,assort_material=%s,deposit_position=%s,
                                        install_date=%s,manage_type=%s,manager=%s,application_specialist=%s,
                                        manufacturer=%s, manufacture_date=%s,origin_place=%s,update_time=%s where id=%s'''

        # datas = req_dic.get('datas', [])
        df = pd.read_excel(file_path, sheet_name='Sheet1')
        datas = df.to_dict('records')
        datas = analysis_equipment_data(datas)
        count = 0
        try:
            insert_equipment_ls = []
            update_equipment_ls = []
            for data in datas:
                now_ts = datetime.datetime.now()
                count += 1
                lineNo = count + 1
                equipment_id = data.get('id')
                if not equipment_id:
                    return VIEW_FAIL(msg='ID????????????, ???????????????: {}'.format(lineNo))
                name = data.get('name')
                number = data.get('number')
                serial_number = data.get('serial_number')
                fixed_asset_code = data.get('fixed_asset_code')
                fixed_asset_category = data.get('fixed_asset_category')
                custodian = data.get('custodian')
                equipment_state = data.get('equipment_state')
                service_type = data.get('service_type')
                specification = data.get('specification')
                performance = data.get('performance')
                assort_material = data.get('assort_material')
                deposit_position = data.get('deposit_position')
                install_date = data.get('install_date')
                manage_type = data.get('manage_type')
                manager = data.get('manager')
                application_specialist = data.get('application_specialist')
                manufacturer = data.get('manufacturer')
                manufacture_date = data.get('manufacture_date')
                origin_place = data.get('origin_place')

                existqs = Equipment.objects.filter(id=equipment_id)  # ??????????????????????????????????????????
                if existqs:
                    update_equipment_args = (name, number, serial_number, fixed_asset_code, fixed_asset_category,
                                             custodian, equipment_state, service_type, specification, performance,
                                             assort_material, deposit_position, install_date, manage_type, manager,
                                             application_specialist, manufacturer, manufacture_date, origin_place,
                                             now_ts, equipment_id)
                    update_equipment_ls.append(update_equipment_args)
                else:
                    insert_equipment_args = (equipment_id, name, number, serial_number, fixed_asset_code,
                                             fixed_asset_category, custodian, equipment_state, service_type,
                                             specification, performance, assort_material, deposit_position, install_date,
                                             manage_type, manager, application_specialist, manufacturer, manufacture_date,
                                             origin_place, now_ts, now_ts, False)
                    insert_equipment_ls.append(insert_equipment_args)

                if len(insert_equipment_ls) + len(update_equipment_ls) >= 10:
                    execute_batch_sql(insert_equipment_sql, insert_equipment_ls)
                    execute_batch_sql(update_equipment_sql, update_equipment_ls)
                    insert_equipment_ls = []
                    update_equipment_ls = []

            if len(insert_equipment_ls) + len(update_equipment_ls) > 0:
                execute_batch_sql(insert_equipment_sql, insert_equipment_ls)
                execute_batch_sql(update_equipment_sql, update_equipment_ls)
        except Exception as e:
            logger.error('?????????????????????????????????, error:{}'.format(str(e)))
            error_code = e.args[0]
            if error_code == 1111:
                msg = e.args[1]
                error = e.args[1]
            else:
                msg = '????????????'
                error = str(e)
            return VIEW_FAIL(msg=msg, data={'error': error})
        return VIEW_SUCCESS(msg='????????????')
    except Exception as e:
        logger.error('????????????????????????, error:{}'.format(str(e)))
        return VIEW_FAIL(msg='????????????????????????', data={'error': str(e)})


# ??????????????????????????????
@api_view(['GET'])
def get_deposit_position(request):
    qs = Equipment.objects.values('deposit_position').distinct()
    deposit_positions = []
    if qs:
        deposit_positions = [item['deposit_position'] for item in list(qs) if item['deposit_position']]
    return REST_SUCCESS(deposit_positions)


# ???????????????????????????
class EquipmentListGeneric(generics.ListCreateAPIView):
    model = Equipment
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name
    queryset = model.objects.filter(is_delete=False).all().order_by('create_time')
    serializer_class = EquipmentSerializer
    # pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        search = request.GET.get('search', '')
        if search:
            queryset = queryset.filter(Q(id__contains=search) | Q(name__contains=search))
        equipment_state = request.GET.get('equipment_state')
        if equipment_state:
            equipment_state_ls = equipment_state.split(',')
            queryset = queryset.filter(equipment_state__in=equipment_state_ls)
        borrow_tag = request.GET.get('borrow_tag')
        if borrow_tag:
            queryset = queryset.filter(equipment_state__in=[1, 2])
        calibration_state = request.GET.get('calibration_state')
        if calibration_state:
            calibration_qs = EquipmentCalibrationInfo.objects.all().values('equipment_id')
            calibration_qs = [q['equipment_id'] for q in calibration_qs]
            queryset = queryset.exclude(id__in=calibration_qs)
        maintain_tag = request.GET.get('maintain_tag')
        if maintain_tag:
            maintain_qs = EquipmentMaintainInfo.objects.all().values('equipment_id')
            maintain_qs = [q['equipment_id'] for q in maintain_qs]
            queryset = queryset.exclude(id__in=maintain_qs)
        fixed_asset_category = request.GET.get('fixed_asset_category')
        if fixed_asset_category:
            queryset = queryset.filter(fixed_asset_category=int(fixed_asset_category))

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
    queryset = Equipment.objects.filter(is_delete=False).all()
    serializer_class = EquipmentSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# ???????????????????????????????????????
@api_view(['GET'])
def query_equip_exist(request):
    equipment_id = request.GET.get('equipment_id')
    if not equipment_id:
        return REST_FAIL({'msg': '??????ID????????????'})
    qs = Equipment.objects.filter(id=equipment_id)
    data = {}
    if qs:
        data = list(qs.values())[0]
    return REST_SUCCESS(data)


# ???????????????????????????
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
            return REST_FAIL({'msg': '??????????????????'})
        serializer = EquipmentSerializer(equipment)
        return Response(serializer.data)

    def put(self, request):
        equipment_id = request.data.get('id')
        equipment = self.get_object(equipment_id)
        if not equipment:
            return REST_SUCCESS({'msg': '??????????????????'})
        before = EquipmentSerializer(equipment).data
        extendattribute_set = request.data.pop('extendattribute_set', [])
        equipment_state = request.data.get('equipment_state', 0)
        serializer = EquipmentSerializer(equipment, data=request.data)
        if serializer.is_valid(raise_exception=True):
            if Equipment.objects.filter(pk=equipment_id).first().is_delete:
                data = serializer.validated_data.copy()
                data.update({'is_delete': False})
                data.update({'create_time': datetime.datetime.now()})
                serializer.validated_data.update(data)
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
            if equipment_state != equipment.equipment_state and int(equipment_state) == 4:
                EquipmentMaintainInfo.objects.filter(equipment_id=equipment_id).update(calibration_time=None,
                                                                                       recalibration_time=None,
                                                                                       due_date=None,
                                                                                       pm_q1=None,
                                                                                       pm_q2=None,
                                                                                       pm_q3=None,
                                                                                       pm_q4=None,
                                                                                       update_time=datetime.datetime.now())
            after = serializer.data
            change = get_differ(before, after)
            save_operateLog('update', request.user, self.table_name, self.verbose_name, before, after, change)
            return Response(serializer.data)

    def delete(self, request):
        query_str = QueryDict(request.META.get('QUERY_STRING', ''))
        equipment_id = query_str.get('id')
        equipment = self.get_object(equipment_id)
        if not equipment:
            return REST_FAIL({'msg': '??????????????????'})
        before = EquipmentSerializer(equipment).data
        equipment.delete()
        save_operateLog('delete', request.user, self.table_name, self.verbose_name, before=before)
        return REST_SUCCESS({'msg': '????????????'})


# ??????????????????
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
            queryset = queryset.filter(equipment_id=equipment_id)  # ????????????

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


# ??????????????????
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
        return REST_SUCCESS({'msg': '????????????'})


# ????????????????????????????????????????????????
def get_borrow_time_limit(equipment_id):
    equipment_qs = Equipment.objects.filter(id=equipment_id)
    brrow_qs = EquipmentBorrowRecord.objects.filter(equipment__id=equipment_id, is_approval=1, is_delete=False).order_by('-end_time')
    allow_borrow_days = equipment_qs.first().allow_borrow_days
    last_borrow_end_time = None
    if brrow_qs:
        last_borrow_end_time = brrow_qs.first().end_time
        last_actual_end_time = brrow_qs.first().actual_end_time
        if last_actual_end_time:
            last_borrow_end_time = last_actual_end_time
    return {'last_borrow_end_time': last_borrow_end_time, 'allow_borrow_days': allow_borrow_days}


# ????????????
class BorrowListGeneric(generics.ListCreateAPIView):
    queryset = EquipmentBorrowRecord.objects.all().order_by('-create_time')
    serializer_class = BorrowRecordSerializer
    pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        search = request.GET.get('search', '')
        if search:
            queryset = queryset.filter(Q(equipment__id__contains=search) | Q(equipment__name__contains=search))
        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            queryset = queryset.filter(Q(start_time__gte=start_time), Q(end_time__lte=end_time))

        fuzzy_params = {}
        fuzzy_params['user__username'] = request.GET.get('user_name', '')
        fuzzy_params['equipment__fixed_asset_name'] = request.GET.get('fixed_asset_name', '')
        fuzzy_params['project__name'] = request.GET.get('project_name', '')
        fuzzy_params['user__section_name'] = request.GET.get('section_name', '')

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
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        if start_time > end_time:
            raise serializers.ValidationError('????????????????????????????????????')
        borrow_type = data.get('borrow_type')

        equipment = data.get('equipment')
        if equipment.equipment_state not in [1, 2]:
            raise serializers.ValidationError('?????????????????????{}, ??????????????????'.format(equipment.get_equipment_state_display()))
        interrupt_borrow_qs = EquipmentBorrowRecord.objects.filter(user=request.user, is_delete=False,
                                                                   is_interrupted=True, equipment_id=equipment,
                                                                   is_recovery_interrupt=False).order_by('id').last()
        if borrow_type in ['????????????', '????????????']:  # ??????????????????????????????????????????????????????
            borrow_time_limit = get_borrow_time_limit(equipment.id)
            last_borrow_end_time = borrow_time_limit['last_borrow_end_time']
            allow_borrow_days = borrow_time_limit['allow_borrow_days']
            if borrow_type == '????????????':
                if last_borrow_end_time:
                    if last_borrow_end_time > start_time:
                        raise serializers.ValidationError('?????????????????????: {}'.format(last_borrow_end_time))
            if borrow_type == '????????????':  # ??????????????????????????????????????????
                if not interrupt_borrow_qs:
                    raise serializers.ValidationError('??????????????????????????????')
                surplus_hours = float(interrupt_borrow_qs.expect_usage_time) - float(interrupt_borrow_qs.actual_usage_time)
                if surplus_hours > 0:  # ??????????????????????????????????????????????????????
                    end = calculate_end_time(start_time, surplus_hours)
                    allow_end_time = end
                    if allow_end_time < end_time:
                        raise serializers.ValidationError('?????????????????????: {}'.format(allow_end_time))
                else:
                    raise serializers.ValidationError('??????????????????????????????')
            else:
                if allow_borrow_days:
                    allow_end_time = start_time + datetime.timedelta(days=allow_borrow_days)
                    if allow_end_time < end_time:
                        raise serializers.ValidationError('?????????????????????: {}'.format(allow_end_time))

        expect_usage_time = calculate_datediff(start_time, end_time)
        data.update({'expect_usage_time': expect_usage_time})
        if borrow_type in ['????????????', '????????????', '??????']:
            # ???????????????????????????????????????????????????????????????,??????????????????????????????????????????
            now_range_time_qs = EquipmentBorrowRecord.objects.filter(Q(start_time__range=[start_time, end_time]) |
                                                                     Q(end_time__range=[start_time, end_time]),
                                                                     is_approval=0, is_delete=False,
                                                                     equipment_id=equipment.id).order_by('id')
            if now_range_time_qs:
                need_delay_qs = EquipmentBorrowRecord.objects.filter(start_time__gte=now_range_time_qs.first().start_time,
                                                                     is_approval=0, is_delete=False,
                                                                     equipment_id=equipment.id)

                # ???????????????????????????????????????
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
                            if list_delay_start[1] >= '19:00:00':  # ??????????????????
                                start_d += datetime.timedelta(days=1)
                                start = start_d + datetime.timedelta(hours=9)
                                list_delay_start[1] = '09:00:00'
                            if list_delay_start[1] < '09:00:00':
                                start = start_d + datetime.timedelta(hours=9)
                            # if '12:00:00' <= list_delay_start[1] < '13:00:00':  # ??????????????????
                            #     start = start_d + datetime.timedelta(hours=13)
                            #     list_delay_start[1] = '13:00:00'
                            # ??????????????????????????????????????????????????????????????????????????????
                            list_holiday = get_holiday(start.year, 'datetime')
                            if start_d in list_holiday:
                                while start_d in list_holiday:
                                    start_d += datetime.timedelta(days=1)
                                    if start_d.year != start.year:  # ??????
                                        list_holiday = get_holiday(start_d.year, 'datetime')
                                start = start_d + datetime.timedelta(hours=9)
                                list_delay_start[1] = '09:00:00'
                            # ??????????????????????????????????????????????????????????????????(?????????????????????)
                            end = calculate_end_time(start, float(b_obj.expect_usage_time))
                            list_holiday = get_holiday(end.year, 'datetime')
                            end_d = datetime.datetime.strptime(end.strftime('%Y-%m-%d'), '%Y-%m-%d')
                            # ??????????????????????????????????????????????????????????????????
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
                            if interrupt_borrow_qs:
                                EquipmentBorrowRecord.objects.filter(id=interrupt_borrow_qs.id).\
                                    update(is_recovery_interrupt=True)
                        transaction.savepoint_commit(save_id)
                    except Exception as e:
                        transaction.savepoint_rollback(save_id)
                        logger.error('????????????????????????????????????,error:{}'.format(str(e)))
                        raise serializers.ValidationError('????????????????????????????????????')

        data.update({'per_hour_price': equipment.per_hour_price})
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# ??????????????????
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
        old_is_approval = instance.is_approval
        old_confirm_state = instance.return_confirm_state
        old_is_return = instance.is_return
        per_hour_price = instance.per_hour_price
        equipment_id = instance.equipment_id
        equipment_obj = Equipment.objects.filter(id=equipment_id)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        expect_usage_time = calculate_datediff(start_time, end_time)
        data.update({'expect_usage_time': expect_usage_time})
        is_approval = data.get('is_approval')
        if is_approval == 1 and old_is_approval == 0:
            if Equipment.objects.get(id=equipment_id).equipment_state == 2:
                raise serializers.ValidationError('?????????????????????????????????????????????')
            Equipment.objects.filter(id=equipment_id).update(equipment_state=2)
            start_time = datetime.datetime.now()
            end_time = calculate_end_time(start_time, expect_usage_time)
            data.update({'start_time': start_time})
            data.update({'end_time': end_time})
        return_confirm_state = data.get('return_confirm_state')
        return_position = data.get('return_position')
        is_return = data.get('is_return')
        if is_return == 1 and old_is_return == 0:
            actual_end_time = datetime.datetime.now()
            data.update({'actual_end_time': actual_end_time})
        if return_confirm_state is not None and old_confirm_state is None:
            data.update({'is_return': 2})
            actual_end_time = data.get('actual_end_time')
            actual_usage_time = calculate_datediff(start_time, actual_end_time)
            data.update({'actual_usage_time': actual_usage_time})
            if per_hour_price:
                total_amount = round((actual_usage_time * float(per_hour_price)), 2)
                data.update({'total_amount': total_amount})
            if return_confirm_state == '??????':
                equipment_state = 1
            elif return_confirm_state == '??????':
                equipment_state = 3
            else:
                raise serializers.ValidationError('????????????????????????')
            with transaction.atomic():
                save_id = transaction.savepoint()
                try:
                    # ???????????????????????????
                    equipment_obj.update(equipment_state=equipment_state,
                                         deposit_position=return_position,
                                         update_time=datetime.datetime.now())
                    serializer.validated_data.update(data)
                    self.perform_update(serializer)

                    if return_confirm_state == '??????':
                        # TODO ???????????????????????????????????????
                        next_user_qs = EquipmentBorrowRecord.objects.filter(start_time__gte=actual_end_time,
                                                                            equipment_id=equipment_id,
                                                                            is_delete=False,
                                                                            is_approval=0).order_by('id')
                        if next_user_qs:
                            next_user = next_user_qs.first().user
                    transaction.savepoint_commit(save_id)
                except Exception as e:
                    transaction.savepoint_rollback(save_id)
                    logger.error('????????????????????????,error:{}'.format(str(e)))
                    raise serializers.ValidationError('????????????????????????')
        else:
            with transaction.atomic():
                save_id = transaction.savepoint()
                try:
                    if is_approval == 1 and old_is_approval == 0:
                        Equipment.objects.filter(id=equipment_id).update(equipment_state=2)
                    serializer.validated_data.update(data)
                    self.perform_update(serializer)
                    transaction.savepoint_commit(save_id)
                except Exception as e:
                    transaction.savepoint_rollback(save_id)
                    logger.error('????????????,error:{}'.format(str(e)))
                    raise serializers.ValidationError('????????????')

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    @set_delete_log
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return REST_SUCCESS({'msg': '????????????'})


# ??????????????????????????????
@api_view(['GET'])
def get_AllowBorrowTime(request):
    equipment_id = request.GET.get('equipment')
    borrow_type = request.GET.get('borrow_type')
    if not equipment_id:
        return REST_FAIL({'msg': '??????ID????????????'})
    if not borrow_type:
        return REST_FAIL({'msg': '????????????????????????'})
    equipment_qs = Equipment.objects.filter(id=equipment_id)
    if not equipment_qs:
        return REST_FAIL({'msg': '??????????????????'})
    equipment_state = equipment_qs.first().equipment_state
    if equipment_state not in [1, 2]:
        return REST_FAIL({'msg': '?????????????????????{}, ??????????????????'.format(equipment_qs.first().get_equipment_state_display())})
    borrow_time_limit = get_borrow_time_limit(equipment_id)
    last_borrow_end_time = borrow_time_limit['last_borrow_end_time']
    allow_borrow_days = borrow_time_limit['allow_borrow_days']
    allow_start_time = datetime.datetime.now().replace(second=0, microsecond=0)
    allow_end_time = None
    if borrow_type == '????????????':  # ??????????????????
        if last_borrow_end_time:
            if last_borrow_end_time > allow_start_time:
                allow_start_time = (last_borrow_end_time + datetime.timedelta(minutes=1)).replace(second=0, microsecond=0)
    if borrow_type == '????????????':  # ??????????????????????????????????????????
        interrupt_borrow_qs = EquipmentBorrowRecord.objects.filter(user=request.user, is_delete=False, is_interrupted=True,
                                                             is_recovery_interrupt=False, equipment_id=equipment_id).\
                                    order_by('id').last()
        surplus_hours = 0
        if interrupt_borrow_qs:
            surplus_hours = float(interrupt_borrow_qs.expect_usage_time) - float(interrupt_borrow_qs.actual_usage_time)
        if surplus_hours > 0:
            allow_end_time = allow_start_time + datetime.timedelta(hours=surplus_hours)
        else:
            return REST_SUCCESS(data={'allow_start_time': None, 'allow_end_time': None})
    else:
        if borrow_type == '????????????':
            no_approval = EquipmentBorrowRecord.objects.filter(is_approval=1, is_return=0, is_delete=False,
                                                               equipment_id=equipment_id).order_by('-end_time').first()
            if no_approval:
                if no_approval.end_time > allow_start_time:
                    allow_start_time = (no_approval.end_time + datetime.timedelta(minutes=1)).\
                                            replace(second=0, microsecond=0)
        if allow_borrow_days:
            allow_end_time = allow_start_time + datetime.timedelta(days=allow_borrow_days)
    return REST_SUCCESS(data={'allow_start_time': allow_start_time, 'allow_end_time': allow_end_time})


# ????????????
class ReturnListGeneric(generics.ListCreateAPIView):
    queryset = EquipmentReturnRecord.objects.all().order_by('-create_time')
    serializer_class = ReturnApplySerializer
    pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            queryset = queryset.filter(borrow_record__equipment__id=equipment_id)  # ????????????

        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            queryset = queryset.filter(return_time__range=[start_time, end_time])

        fuzzy_params = {}
        fuzzy_params['borrow_record__user__username'] = request.GET.get('user_name', '')
        fuzzy_params['borrow_record__equipment__name'] = request.GET.get('equipment_name', '')
        fuzzy_params['borrow_record__equipment__fixed_asset_name'] = request.GET.get('fixed_asset_name', '')
        fuzzy_params['borrow_record__project__name'] = request.GET.get('project_name', '')
        fuzzy_params['borrow_record__section_name'] = request.GET.get('section_name', '')

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


# ??????????????????
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
        old_confirm_state = instance.confirm_state
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
        if confirm_state is not None and old_confirm_state is None:
            data.update({'is_confirm': True})
            borrow_instance = borrow_obj.first()
            start_time = borrow_instance.start_time
            per_hour_price = borrow_instance.per_hour_price
            actual_end_time = data.get('return_time')
            actual_usage_time = calculate_datediff(start_time, actual_end_time)
            total_amount = None
            if per_hour_price:
                total_amount = round((actual_usage_time * float(per_hour_price)), 2)
            if confirm_state == '??????':
                equipment_state = 1
            elif confirm_state == '??????':
                equipment_state = 5
            else:
                raise serializers.ValidationError('????????????????????????')
            with transaction.atomic():
                save_id = transaction.savepoint()
                try:
                    # ??????????????????
                    borrow_obj.update(is_return=2,
                                      is_interrupted=is_interrupted,
                                      actual_end_time=actual_end_time,
                                      actual_usage_time=actual_usage_time,
                                      total_amount=total_amount,
                                      update_time=datetime.datetime.now())
                    # ???????????????????????????
                    equipment_obj.update(equipment_state=equipment_state,
                                         deposit_position=return_position,
                                         update_time=datetime.datetime.now())
                    serializer.validated_data.update(data)
                    self.perform_update(serializer)

                    if confirm_state == '??????':
                        # TODO ???????????????????????????????????????
                        next_user_qs = EquipmentBorrowRecord.objects.filter(start_time__gte=actual_end_time,
                                                                            equipment_id=equipment_id,
                                                                            is_delete=False,
                                                                            is_approval=0).order_by('id')
                        if next_user_qs:
                            next_user = next_user_qs.first().user
                    transaction.savepoint_commit(save_id)
                except Exception as e:
                    transaction.savepoint_rollback(save_id)
                    logger.error('????????????????????????,error:{}'.format(str(e)))
                    raise serializers.ValidationError('????????????????????????')
        else:
            serializer.validated_data.update(data)
            self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


# ?????????????????????
class BrokenInfoGeneric(generics.ListCreateAPIView):
    model = EquipmentBrokenInfo
    queryset = model.objects.all().order_by('-create_time')
    serializer_class = BrokenInfoSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            queryset = queryset.filter(equipment__id=equipment_id)  # ????????????

        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            queryset = queryset.filter(broken_time__range=[start_time, end_time])

        fuzzy_params = {}
        fuzzy_params['user__username'] = request.GET.get('user_name', '')
        fuzzy_params['equipment__name'] = request.GET.get('equipment_name', '')
        fuzzy_params['equipment__fixed_asset_name'] = request.GET.get('fixed_asset_name', '')
        fuzzy_params['user__section_name'] = request.GET.get('section_name', '')

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
        evaluation_result = data.get('evaluation_result')
        equipment = data.get('equipment')
        if evaluation_result:
            if evaluation_result == '??????':
                Equipment.objects.filter(id=equipment.id).update(equipment_state=3)
            elif evaluation_result == '??????':
                Equipment.objects.filter(id=equipment.id).update(equipment_state=4)
            elif evaluation_result == '??????':
                Equipment.objects.filter(id=equipment.id).update(equipment_state=6)
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# ??????????????????
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
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)


# ????????????????????????
@api_view(['POST'])
def post_calibration(request):
    try:
        try:
            file = request.FILES.get('file', '')
            if not file:
                return VIEW_FAIL(msg='????????????????????????')
            current_path = os.path.dirname(__file__)
            file_dir_path = os.path.join(current_path, 'temporydata')
            if not os.path.exists(file_dir_path):
                os.mkdir(file_dir_path)
            file_path = os.path.join(file_dir_path, 'UniIC_Equipment_Calibration.xlsx')
            with open(file_path, 'wb') as f:
                for i in file.chunks():
                    f.write(i)
        except Exception as e:
            logger.error('??????????????????, error:{}'.format(str(e)))
            return VIEW_FAIL(msg='??????????????????, error:{}'.format(str(e)))

        insert_calibration_sql = '''insert into equipment_calibration_info(specification, environment, calibration_cycle,
                                                    calibration_time, recalibration_time, due_date, 
                                                    create_time, update_time, equipment_id, state)
                                      values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''

        update_calibration_sql = '''update equipment_calibration_info set specification=%s,environment=%s,
                                            calibration_cycle=%s,calibration_time=%s,recalibration_time=%s,
                                            due_date=%s,update_time=%s,state=%s where equipment_id=%s'''
        df = pd.read_excel(file_path, sheet_name='Sheet1')
        datas = df.to_dict('records')
        datas = analysis_calibration(datas)
        count = 0
        try:
            insert_calibration_ls = []
            update_calibration_ls = []
            for data in datas:
                now_ts = datetime.datetime.now()
                count += 1
                lineNo = count + 1
                equipment_id = data.get('equipment_id')
                if not equipment_id:
                    return VIEW_FAIL(msg='ID????????????, ???????????????: {}'.format(lineNo))
                specification = data.get('specification')
                environment = data.get('environment')
                calibration_cycle = data.get('calibration_cycle')
                calibration_time = data.get('calibration_time')
                if calibration_cycle and calibration_time:
                    recalibration_time = calculate_recalibration_time(calibration_time, calibration_cycle)
                    due_date = calculate_due_date(recalibration_time, 'calibration')
                    try:
                        due_date = str(int(due_date))
                        calibration_state = '????????????'
                    except:
                        calibration_state = '?????????'
                else:
                    calibration_time = None
                    recalibration_time = None
                    due_date = None
                    calibration_state = None
                calibration_qs = EquipmentCalibrationInfo.objects.filter(equipment_id=equipment_id)
                if calibration_qs:
                    update_calibration_args = (specification, environment, calibration_cycle, calibration_time,
                                               recalibration_time, due_date, now_ts, calibration_state, equipment_id)
                    update_calibration_ls.append(update_calibration_args)
                else:
                    insert_calibration_args = (specification, environment, calibration_cycle,
                                               calibration_time, recalibration_time, due_date,
                                               now_ts, now_ts, equipment_id, calibration_state)
                    insert_calibration_ls.append(insert_calibration_args)

                if len(insert_calibration_ls) + len(update_calibration_ls) >= 10:
                    execute_batch_sql(insert_calibration_sql, insert_calibration_ls)
                    execute_batch_sql(update_calibration_sql, update_calibration_ls)
                    insert_calibration_ls = []
                    update_calibration_ls = []

            if len(insert_calibration_ls) + len(update_calibration_ls) > 0:
                execute_batch_sql(insert_calibration_sql, insert_calibration_ls)
                execute_batch_sql(update_calibration_sql, update_calibration_ls)
        except Exception as e:
            logger.error('?????????????????????????????????, error:{}'.format(str(e)))
            error_code = e.args[0]
            if error_code == 1111:
                msg = e.args[1]
                error = e.args[1]
            else:
                msg = '????????????'
                error = str(e)
            return VIEW_FAIL(msg=msg, data={'error': error})
        return VIEW_SUCCESS(msg='????????????')
    except Exception as e:
        logger.error('????????????????????????, error:{}'.format(str(e)))
        return VIEW_FAIL(msg='????????????????????????', data={'error': str(e)})


# ????????????
class CalibrationInfoGeneric(generics.ListCreateAPIView):
    model = EquipmentCalibrationInfo
    queryset = model.objects.all().order_by('create_time')
    serializer_class = CalibrationInfoSerializer
    # pagination_class = MyPagePagination
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            queryset = queryset.filter(equipment__id=equipment_id)  # ????????????

        calibration_start_time = request.GET.get('calibration_start_time')
        calibration_end_time = request.GET.get('calibration_end_time')
        if calibration_start_time and calibration_end_time:
            queryset = queryset.filter(calibration_time__range=[calibration_start_time, calibration_end_time])

        fuzzy_params = {}
        fuzzy_params['equipment__name'] = request.GET.get('equipment_name', '')

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
        calibration_cycle = data.get('calibration_cycle')
        calibration_time = data.get('calibration_time')
        recalibration_time = calculate_recalibration_time(calibration_time, calibration_cycle)
        data.update({'recalibration_time': recalibration_time})
        state = data.get('state')
        equipment = data.get('equipment')
        if state == '?????????':
            if equipment.equipment_state != 3:
                Equipment.objects.filter(id=equipment.id).update(equipment_state=3)
        elif state == '????????????':
            if equipment.equipment_state == 3:
                Equipment.objects.filter(id=equipment.id).update(equipment_state=1)
        due_date = calculate_due_date(recalibration_time, 'calibration')
        data.update({'due_date': due_date})
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# ??????????????????
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
        old_state = instance.state
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        calibration_cycle = data.get('calibration_cycle')
        calibration_time = data.get('calibration_time')
        recalibration_time = calculate_recalibration_time(calibration_time, calibration_cycle)
        data.update({'recalibration_time': recalibration_time})
        state = data.get('state')
        equipment = instance.equipment
        if state == '?????????' and old_state == '?????????':
            if equipment.equipment_state != 3:
                Equipment.objects.filter(id=equipment.id).update(equipment_state=3)
        elif state == '????????????' and old_state == '?????????':
            if equipment.equipment_state == 3:
                Equipment.objects.filter(id=equipment.id).update(equipment_state=1)
        due_date = calculate_due_date(recalibration_time, 'calibration')
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
        return REST_SUCCESS({'msg': '????????????'})


# ????????????????????????
def insert_certificate(datas):
    insert_certificate_sql = '''insert into equipment_calibration_certificate(certificate_year, certificate, 
                                    create_time, update_time, equipment_id)
                                    values(%s, %s, %s, %s, %s)'''
    update_certificate_sql = '''update equipment_calibration_certificate set certificate_year=%s,certificate=%s,
                                    update_time=%s where id=%s'''
    insert_certificate_ls = []
    update_certificate_ls = []
    count = 0
    for data in datas:
        now_ts = datetime.datetime.now()
        count += 1
        lineNo = count + 1
        equipment_id = data.get('equipment_id')
        if not equipment_id:
            return VIEW_FAIL(msg='ID????????????, ???????????????: {}'.format(lineNo))
        certificate_year = data.get('certificate_year')
        if not certificate_year:
            return VIEW_FAIL(msg='????????????????????????, ???????????????: {}'.format(lineNo))
        certificate = data.get('certificate')
        id = data.get('id', '')
        if id:
            certificate_qs = EquipmentCalibrationCertificate.objects.filter(id=id)
        else:
            certificate_qs = EquipmentCalibrationCertificate.objects.filter(equipment_id=equipment_id,
                                                                            certificate_year=certificate_year.strip())
        if certificate_qs:
            update_certificate_args = (certificate_year, certificate, now_ts, certificate_qs.first().id)
            update_certificate_ls.append(update_certificate_args)
        else:
            insert_certificate_args = (certificate_year, certificate, now_ts, now_ts, equipment_id)
            insert_certificate_ls.append(insert_certificate_args)

        if len(insert_certificate_ls) + len(update_certificate_ls) >= 10:
            execute_batch_sql(insert_certificate_sql, insert_certificate_ls)
            execute_batch_sql(update_certificate_sql, update_certificate_ls)
            insert_certificate_ls = []
            update_certificate_ls = []

    if len(insert_certificate_ls) + len(update_certificate_ls) > 0:
        execute_batch_sql(insert_certificate_sql, insert_certificate_ls)
        execute_batch_sql(update_certificate_sql, update_certificate_ls)


# ????????????????????????
@api_view(['POST'])
def post_batch_certificate(request):
    try:
        try:
            file = request.FILES.get('file', '')
            if not file:
                return VIEW_FAIL(msg='????????????????????????')
            current_path = os.path.dirname(__file__)
            file_dir_path = os.path.join(current_path, 'temporydata')
            if not os.path.exists(file_dir_path):
                os.mkdir(file_dir_path)
            file_path = os.path.join(file_dir_path, 'UniIC_Calibration_Certificate.xlsx')
            with open(file_path, 'wb') as f:
                for i in file.chunks():
                    f.write(i)
        except Exception as e:
            logger.error('??????????????????, error:{}'.format(str(e)))
            return VIEW_FAIL(msg='??????????????????, error:{}'.format(str(e)))

        df = pd.read_excel(file_path, sheet_name='Sheet1')
        datas = df.to_dict('records')
        datas = analysis_certificate(datas)
        try:
            insert_certificate(datas)
        except Exception as e:
            logger.error('?????????????????????????????????, error:{}'.format(str(e)))
            error_code = e.args[0]
            if error_code == 1111:
                msg = e.args[1]
                error = e.args[1]
            else:
                msg = '????????????'
                error = str(e)
            return VIEW_FAIL(msg=msg, data={'error': error})
        return VIEW_SUCCESS(msg='????????????')
    except Exception as e:
        logger.error('????????????????????????, error:{}'.format(str(e)))
        return VIEW_FAIL(msg='????????????????????????', data={'error': str(e)})


# ??????????????????
@api_view(['POST'])
def add_certificate(request):
    try:
        try:
            req_dic = json.loads(request.body)
        except Exception as e:
            return REST_FAIL({'msg': '????????????????????????,??????????????????????????????', 'error': str(e)})
        del_ls = req_dic.get('del_ls', [])
        certificate_ls = req_dic.get('certificate_ls', [])
        if not certificate_ls:
            return REST_FAIL({'msg': '????????????????????????'})
        close_old_connections()
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                if del_ls:
                    EquipmentCalibrationCertificate.objects.filter(id__in=del_ls).delete()
                insert_certificate(certificate_ls)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.error('?????????????????????????????????, error:{}'.format(str(e)))
                error_code = e.args[0]
                if error_code == 1111:
                    msg = e.args[1]
                    error = e.args[1]
                else:
                    msg = '????????????'
                    error = str(e)
                return REST_FAIL({'msg': msg, 'error': error})
        return REST_SUCCESS({'msg': '????????????'})
    except Exception as e:
        logger.error('????????????????????????, error:{}'.format(str(e)))
        return REST_FAIL({'msg': '????????????????????????', 'error': str(e)})


# ????????????
class CertificateGeneric(generics.ListCreateAPIView):
    model = EquipmentCalibrationCertificate
    queryset = model.objects.all().order_by('certificate_year')
    serializer_class = CalibrationCertificateSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            queryset = queryset.filter(equipment__id=equipment_id)  # ????????????

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class OperateCertificateGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = EquipmentCalibrationCertificate
    queryset = model.objects.all().order_by('certificate_year')
    serializer_class = CalibrationCertificateSerializer
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
        return REST_SUCCESS({'msg': '????????????'})


class MaintenanceGeneric(generics.ListCreateAPIView):
    model = EquipmentMaintenanceRecord
    queryset = model.objects.all().order_by('-create_time')
    serializer_class = MaintenanceSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name
    # pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            queryset = queryset.filter(equipment__id=equipment_id)  # ????????????

        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            queryset = queryset.filter(Q(down_time__gte=start_time), Q(up_time__lte=end_time))

        fuzzy_params = {}
        fuzzy_params['equipment__name'] = request.GET.get('equipment_name', '')

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
        equipment = data.get('equipment')
        Equipment.objects.filter(id=equipment.id).update(equipment_state=1)
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
        return REST_SUCCESS({'msg': '????????????'})


# ????????????????????????
@api_view(['POST'])
def post_maintain(request):
    try:
        try:
            file = request.FILES.get('file', '')
            if not file:
                return VIEW_FAIL(msg='????????????????????????')
            current_path = os.path.dirname(__file__)
            file_dir_path = os.path.join(current_path, 'temporydata')
            if not os.path.exists(file_dir_path):
                os.mkdir(file_dir_path)
            file_path = os.path.join(file_dir_path, 'UniIC_Equipment_Maintain.xlsx')
            with open(file_path, 'wb') as f:
                for i in file.chunks():
                    f.write(i)
        except Exception as e:
            logger.error('??????????????????, error:{}'.format(str(e)))
            return VIEW_FAIL(msg='??????????????????, error:{}'.format(str(e)))

        insert_maintain_sql = '''insert into equipment_maintain_info(calibration_time, recalibration_time, due_date, 
                                                    pm_q1, pm_q2, pm_q3, pm_q4,
                                                    create_time, update_time, equipment_id)
                                      values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''

        update_maintain_sql = '''update equipment_maintain_info set calibration_time=%s,recalibration_time=%s,
                                            due_date=%s,pm_q1=%s,pm_q2=%s,pm_q3=%s,pm_q4=%s,
                                            update_time=%s where equipment_id=%s'''
        df = pd.read_excel(file_path, sheet_name='Sheet1')
        datas = df.to_dict('records')
        datas = analysis_maintain(datas)
        count = 0
        try:
            insert_maintain_ls = []
            update_maintain_ls = []
            for data in datas:
                now_ts = datetime.datetime.now()
                count += 1
                lineNo = count + 1
                equipment_id = data.get('equipment_id')
                if not equipment_id:
                    return VIEW_FAIL(msg='ID????????????, ???????????????: {}'.format(lineNo))
                calibration_time = data.get('calibration_time')
                recalibration_time = data.get('recalibration_time')
                if calibration_time and recalibration_time:
                    due_date = calculate_due_date(recalibration_time, 'maintain')
                    pm_q1, pm_q2, pm_q3, pm_q4 = calculate_pm_time(recalibration_time)
                else:
                    calibration_time = None
                    recalibration_time = None
                    due_date = None
                    pm_q1, pm_q2, pm_q3, pm_q4 = None, None, None, None
                maintain_qs = EquipmentMaintainInfo.objects.filter(equipment_id=equipment_id)
                if maintain_qs:
                    update_maintain_args = (calibration_time, recalibration_time, due_date,
                                            pm_q1, pm_q2, pm_q3, pm_q4, now_ts, equipment_id)
                    update_maintain_ls.append(update_maintain_args)
                else:
                    insert_maintain_args = (calibration_time, recalibration_time, due_date,
                                            pm_q1, pm_q2, pm_q3, pm_q4,
                                            now_ts, now_ts, equipment_id)
                    insert_maintain_ls.append(insert_maintain_args)

                if len(insert_maintain_ls) + len(update_maintain_ls) >= 10:
                    execute_batch_sql(insert_maintain_sql, insert_maintain_ls)
                    execute_batch_sql(update_maintain_sql, update_maintain_ls)
                    insert_maintain_ls = []
                    update_maintain_ls = []

            if len(insert_maintain_ls) + len(update_maintain_ls) > 0:
                execute_batch_sql(insert_maintain_sql, insert_maintain_ls)
                execute_batch_sql(update_maintain_sql, update_maintain_ls)
        except Exception as e:
            logger.error('?????????????????????????????????, error:{}'.format(str(e)))
            error_code = e.args[0]
            if error_code == 1111:
                msg = e.args[1]
                error = e.args[1]
            else:
                msg = '????????????'
                error = str(e)
            return VIEW_FAIL(msg=msg, data={'error': error})
        return VIEW_SUCCESS(msg='????????????')
    except Exception as e:
        logger.error('????????????????????????, error:{}'.format(str(e)))
        return VIEW_FAIL(msg='????????????????????????', data={'error': str(e)})


# ??????????????????
class MaintainInfoGeneric(generics.ListCreateAPIView):
    model = EquipmentMaintainInfo
    queryset = model.objects.all().order_by('create_time')
    serializer_class = MaintainInfoSerializer
    # pagination_class = MyPagePagination
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        equipment_id = request.GET.get('equipment', '')
        if equipment_id:
            queryset = queryset.filter(equipment__id=equipment_id)  # ????????????

        fuzzy_params = {}
        fuzzy_params['equipment__name'] = request.GET.get('equipment_name', '')

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
        if recalibration_time:
            due_date = calculate_due_date(recalibration_time, 'maintain')
            data.update({'due_date': due_date})
            pm_q1, pm_q2, pm_q3, pm_q4 = calculate_pm_time(recalibration_time)
            data.update({'pm_q1': pm_q1})
            data.update({'pm_q2': pm_q2})
            data.update({'pm_q3': pm_q3})
            data.update({'pm_q4': pm_q4})
            serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# ??????????????????
class OperateMaintainInfoGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = EquipmentMaintainInfo
    queryset = model.objects.all()
    serializer_class = OperateMaintainInfoSerializer
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
        if recalibration_time:
            due_date = calculate_due_date(recalibration_time, 'maintain')
            data.update({'due_date': due_date})
            pm_q1, pm_q2, pm_q3, pm_q4 = calculate_pm_time(recalibration_time)
            data.update({'pm_q1': pm_q1})
            data.update({'pm_q2': pm_q2})
            data.update({'pm_q3': pm_q3})
            data.update({'pm_q4': pm_q4})
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
        return REST_SUCCESS({'msg': '????????????'})
