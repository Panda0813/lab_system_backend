from django.shortcuts import render
from django.db import close_old_connections, transaction
from django.db.models import Q
from rest_framework import generics, serializers
from rest_framework import filters, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from gc_foundry.serializers import CurrencySerializer, FactorySerializer, FoundryEquipmentSerializer, \
    FoundryToolingSerializer, MachineModelSerializer, FoundryTransferSerializer
from gc_foundry.models import Currency, Factory, FoundryEquipment, FoundryTooling, MachineModel, FoundryTransfer
from equipments.models import Project
from equipments.ext_utils import REST_FAIL, REST_SUCCESS, get_file_path, create_excel_resp
from utils.log_utils import set_create_log, set_update_log, set_delete_log
from lab_system_backend.settings import MEDIA_ROOT, MEDIA_URL, BASE_DIR
from decimal import Decimal

import traceback
import os
import uuid
import random
import string
import time
import logging
import pandas as pd

logger = logging.getLogger('django')


# 获取对应关系
@api_view(['GET'])
def get_map_options(request):
    machine_category = [
        {'value': 1, 'label': 'Mask'},
        {'value': 2, 'label': '测试设备'},
        {'value': 3, 'label': 'RDL Mask'},
        {'value': 4, 'label': 'NRE'}
    ]
    tooling_category = [
        {'value': 1, 'label': '测试配件'},
        {'value': 2, 'label': '测试板'},
        {'value': 3, 'label': '探针卡'},
        {'value': 4, 'label': '探针卡+清针片'}
    ]
    fixed_asset = [
        {'value': 1, 'label': '是'},
        {'value': 2, 'label': '否'},
        {'value': 3, 'label': '财务账上报废'}
    ]
    unit_type = [
        {'value': 1, 'label': '套'},
        {'value': 2, 'label': '个'},
        {'value': 3, 'label': '台'},
        {'value': 4, 'label': '块'}
    ]
    return REST_SUCCESS({
        'machine_category': machine_category,
        'tooling_category': tooling_category,
        'fixed_asset': fixed_asset,
        'unit_type': unit_type
    })


# 新增货币种类
class CurrencyListGeneric(generics.ListCreateAPIView):
    model = Currency
    queryset = model.objects.all()
    serializer_class = CurrencySerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'short_name']

    @set_create_log
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class CurrencyDetailGeneric(generics.RetrieveUpdateAPIView):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer


# 新增工厂
class FactoryListGeneric(generics.ListCreateAPIView):
    model = Factory
    queryset = model.objects.all()
    serializer_class = FactorySerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        is_active = request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

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


class FactoryDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = Factory
    queryset = model.objects.all()
    serializer_class = FactorySerializer
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
        return REST_SUCCESS({'msg': '删除成功'})


class ModelListGeneric(generics.ListCreateAPIView):
    model = MachineModel
    queryset = model.objects.all()
    serializer_class = MachineModelSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    @set_create_log
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class ModelDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = MachineModel
    queryset = model.objects.all()
    serializer_class = MachineModelSerializer
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
        return REST_SUCCESS({'msg': '删除成功'})


def create_pathname():
    ts = str(int(time.time()))
    num = string.ascii_letters+string.digits
    pathname = ts + "".join(random.sample(num, 6))
    return pathname


# 上传图片
@api_view(['POST'])
def upload_image(request):
    save_dir = request.POST.get('save_dir')
    if save_dir:
        dir_ = os.path.join(MEDIA_ROOT, save_dir)
    else:
        save_dir = create_pathname()
        dir_ = os.path.join(MEDIA_ROOT, save_dir)
    if not os.path.exists(dir_):
        os.makedirs(dir_)
    files = request.FILES.getlist('image')
    image_name_ls = []
    for file in files:
        image_name = str(uuid.uuid4()) + '.jpg'
        image_save_path = os.path.join(dir_, image_name)
        with open(image_save_path, 'wb') as f:
            for part in file.chunks():
                f.write(part)
                f.flush()
        image_name_ls.append(image_name)
    del_ls = request.POST.get('delImageLs')
    if del_ls:
        del_ls = del_ls.split(',')
        for item in del_ls:
            remove_path = os.path.join(dir_, item)
            if os.path.exists(remove_path):
                os.remove(remove_path)

    return REST_SUCCESS({'save_dir': save_dir})


# 新增测试机台
class FoundryEquipmentList(generics.ListCreateAPIView):
    model = FoundryEquipment
    queryset = model.objects.all().order_by('-create_time')
    serializer_class = FoundryEquipmentSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        project_id = request.GET.get('project', '')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        category = request.GET.get('category', '')
        if category:
            queryset = queryset.filter(category=category)
        factory = request.GET.get('factory', '')
        if factory:
            queryset = queryset.filter(factory=factory)

        fuzzy_params = {}
        fuzzy_params['purchase_order_no'] = request.GET.get('purchase_order_no', '')
        fuzzy_params['name'] = request.GET.get('name', '')
        fuzzy_params['supplier'] = request.GET.get('supplier', '')

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
        number = data.get('number')
        price = data.get('price')
        currency = data.get('currency')
        exchange_rate = currency.exchange_rate
        if number and price:
            total_amount = int(number) * float(price)
            base_total_amount = round(total_amount / float(exchange_rate), 2)
            data.update({'total_amount': total_amount})
            data.update({'base_total_amount': base_total_amount})
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# 修改机台信息
class FoundryEquipmentDetail(generics.RetrieveUpdateDestroyAPIView):
    model = FoundryEquipment
    queryset = model.objects.all()
    serializer_class = FoundryEquipmentSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_update_log
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        number = data.get('number')
        price = data.get('price')
        if number and price:
            total_amount = int(number) * float(price)
            data.update({'total_amount': total_amount})
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
        return REST_SUCCESS({'msg': '删除成功'})


# 新增器材配件
class FoundryToolingList(generics.ListCreateAPIView):
    model = FoundryTooling
    queryset = model.objects.all().order_by('-create_time')
    serializer_class = FoundryToolingSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        project_id = request.GET.get('project', '')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        category = request.GET.get('category', '')
        if category:
            queryset = queryset.filter(category=category)
        factory = request.GET.get('factory', '')
        if factory:
            queryset = queryset.filter(factory=factory)

        fuzzy_params = {}
        fuzzy_params['purchase_order_no'] = request.GET.get('purchase_order_no', '')
        fuzzy_params['name'] = request.GET.get('name', '')
        fuzzy_params['supplier'] = request.GET.get('supplier', '')

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
        number = data.get('number')
        price = data.get('price')
        currency = data.get('currency')
        exchange_rate = currency.exchange_rate
        if number and price:
            total_amount = int(number) * float(price)
            base_total_amount = round(total_amount / float(exchange_rate), 2)
            data.update({'total_amount': total_amount})
            data.update({'base_total_amount': base_total_amount})
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# 修改器材配件
class FoundryToolingDetail(generics.RetrieveUpdateDestroyAPIView):
    model = FoundryTooling
    queryset = model.objects.all()
    serializer_class = FoundryToolingSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_update_log
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        number = data.get('number')
        price = data.get('price')
        if number and price:
            total_amount = int(number) * float(price)
            data.update({'total_amount': total_amount})
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
        return REST_SUCCESS({'msg': '删除成功'})


# 转移设备
class FoundryTransferList(generics.ListCreateAPIView):
    model = FoundryTransfer
    queryset = model.objects.all().order_by('-create_time')
    serializer_class = FoundryTransferSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        foundry_equipment = request.GET.get('foundry_equipment', '')
        if foundry_equipment:
            queryset = queryset.filter(foundry_equipment_id=foundry_equipment)
        foundry_tooling = request.GET.get('foundry_tooling', '')
        if foundry_tooling:
            queryset = queryset.filter(foundry_tooling_id=foundry_tooling)

        factory = request.GET.get('factory', '')
        if factory:
            factory_name = Factory.objects.get(id=factory).name
            queryset = queryset.filter(Q(before_factory=factory_name) | Q(after_factory=factory_name))
        project = request.GET.get('project', '')
        if project:
            project_name = Project.objects.get(id=project).name
            queryset = queryset.filter(Q(before_project=project_name) | Q(after_project=project_name))
        purchase_order_no = request.GET.get('purchase_order_no', '')
        if purchase_order_no:
            queryset = queryset.filter(Q(foundry_equipment__purchase_order_no__contains=purchase_order_no) |
                                       Q(foundry_tooling__purchase_order_no__contains=purchase_order_no))

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
        operate_user = request.user.username
        foundry_equipment = data.get('foundry_equipment')
        foundry_tooling = data.get('foundry_tooling')
        obj = foundry_equipment if foundry_equipment else foundry_tooling
        number = data.get('number')
        factory = data.get('after_factory')
        project = data.get('after_project')
        exchange_rate = obj.currency.exchange_rate
        price = obj.price
        obj_number = obj.number
        if number > obj_number:
            return REST_FAIL({'msg': '转移数量不能超出现有数量'})
        before_factory = obj.factory_name
        before_project = obj.project_name
        after_factory = Factory.objects.get(id=int(factory)).name if factory else None
        after_project = Project.objects.get(id=int(project)).name if project else None
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                if int(obj_number) == int(number):  # 数量一样，不用拆分
                    if project:
                        obj.project_id = int(project)
                    if factory:
                        obj.factory_id = int(factory)
                    obj.save()
                else:
                    surplus_number = obj_number - number  # 剩余数量
                    # 更新剩余数量和总计
                    total_amount = int(surplus_number) * float(price)
                    base_total_amount = round(total_amount / float(exchange_rate), 2)
                    obj.number = surplus_number
                    obj.total_amount = total_amount
                    obj.base_total_amount = base_total_amount
                    obj.save()

                    # 创建新的设备或器材数据
                    new_total_amount = int(number) * float(price)
                    new_base_total_amount = round(new_total_amount / float(exchange_rate), 2)
                    new_obj = obj
                    new_obj.pk = None
                    new_obj.save()
                    new_obj.number = number
                    new_obj.total_amount = new_total_amount
                    new_obj.base_total_amount = new_base_total_amount
                    if factory:
                        new_obj.factory_id = int(factory)
                    if project:
                        new_obj.project_id = int(project)
                    new_obj.save()
                data.update({'before_factory': before_factory})
                data.update({'before_project': before_project})
                data.update({'after_factory': after_factory})
                data.update({'after_project': after_project})
                data.update({'operate_user': operate_user})
                serializer.validated_data.update(data)
                self.perform_create(serializer)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.error('归还信息存储失败,error:{}'.format(str(e)))
                raise serializers.ValidationError('归还信息存储失败')

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class FoundryTransferDetail(generics.RetrieveUpdateAPIView):
    model = FoundryTransfer
    queryset = model.objects.all()
    serializer_class = FoundryTransferSerializer
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


# 导出机台信息
@api_view(['GET'])
def export_equipment_list(request):
    try:
        obj = FoundryEquipment.objects
        project_id = request.GET.get('project', '')
        if project_id:
            obj = obj.filter(project_id=project_id)
        category = request.GET.get('category', '')
        if category:
            obj = obj.filter(category=category)
        factory = request.GET.get('factory', '')
        if factory:
            obj = obj.filter(factory=factory)

        fuzzy_params = {}
        fuzzy_params['purchase_order_no'] = request.GET.get('purchase_order_no', '')
        fuzzy_params['name'] = request.GET.get('name', '')
        fuzzy_params['supplier'] = request.GET.get('supplier', '')

        filter_params = {}
        for k, v in fuzzy_params.items():
            if v != None and v != '':
                k = k + '__contains'
                filter_params[k] = v
        if filter_params:
            obj = obj.filter(**filter_params)
        qs = obj.order_by('-create_time').values('purchase_order_no', 'supplier', 'name', 'category',
                                                 'project__name', 'number', 'unit', 'price', 'total_amount',
                                                 'currency__name', 'currency__exchange_rate', 'factory__name',
                                                 'assort_material', 'fixed_asset_code')
        blank_path = os.path.dirname(__file__) + '/blank_files/机台信息表.xlsx'
        if not qs:
            return create_excel_resp(blank_path, '机台信息表')
        df = pd.DataFrame(list(qs))
        df['price'] = df['price'].map(lambda x: float(x) if x else x)
        df['total_amount'] = df['total_amount'].map(lambda x: float(x) if x else x)
        df['currency__exchange_rate'] = df['currency__exchange_rate'].map(lambda x: float(x) if x else x)
        df['base_total_amount'] = round(df['total_amount'] / df['currency__exchange_rate'], 2)
        ndf = df[['purchase_order_no', 'supplier', 'name', 'category', 'project__name', 'number', 'unit', 'price',
                  'total_amount', 'currency__name', 'base_total_amount', 'factory__name', 'assort_material',
                  'fixed_asset_code']]
        machine_category = {
            1: 'Mask',
            2: '测试设备',
            3: 'RDL Mask',
            4: 'NRE'
        }
        unit_type = {
            1: '套',
            2: '个',
            3: '台',
            4: '块'
        }
        ndf['category'] = ndf['category'].map(machine_category)
        ndf['unit'] = ndf['unit'].map(unit_type)
        order_list = ndf['purchase_order_no'].unique().tolist()
        if None in order_list:
            order_list.remove(None)
        order_count = len(order_list)
        base_amount_sum = ndf['base_total_amount'].sum()
        rename_maps = {
            'purchase_order_no': '采购订单编号',
            'supplier': '供应商',
            'name': '系统级应用测试设备型号名称',
            'category': '类别',
            'project__name': '项目',
            'number': '数量',
            'unit': '单位',
            'price': '单价',
            'total_amount': '总价',
            'currency__name': '币种',
            'base_total_amount': '本位币总价（¥）',
            'factory__name': '存放地点',
            'assort_material': '配套设备器材',
            'fixed_asset_code': '固定资产编号'
        }
        ndf.rename(rename_maps, axis=1, inplace=True)
        file_path = get_file_path('detail', 'export_files')
        writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
        workbook = writer.book
        fmt = workbook.add_format({'font_size': 10, 'text_wrap': True, 'valign': 'vcenter'})
        center_fmt = workbook.add_format({'font_size': 10, 'text_wrap': True, 'valign': 'vcenter', 'align': 'center'})
        border_format = workbook.add_format({'border': 1})
        float_fmt = workbook.add_format({'font_size': 10, 'num_format': '#,##0.00', 'valign': 'vcenter'})
        total_fmt = workbook.add_format({'font_size': 10, 'align': 'center'})
        title_fmt = workbook.add_format(
            {'bold': True, 'font_size': 10, 'font_name': '宋体', 'font_color': 'white',
             'bg_color': '#821e78', 'valign': 'vcenter', 'align': 'center'})
        ndf.to_excel(writer, sheet_name='各工厂资产', header=False, index=False, startcol=0, startrow=1)
        worksheet = writer.sheets['各工厂资产']
        l_end = len(ndf.index) + 1
        for col_num, value in enumerate(ndf.columns.values):
            worksheet.write(0, col_num, value, title_fmt)
        total_no = l_end + 1
        worksheet.write(l_end, 0, '订单数量：', title_fmt)
        worksheet.write(l_end, 1, order_count, total_fmt)
        worksheet.merge_range('C{}:J{}'.format(total_no, total_no), '')
        worksheet.write(l_end, 10, '合计金额：', title_fmt)
        worksheet.write(l_end, 11, base_amount_sum, float_fmt)
        worksheet.merge_range('M{}:N{}'.format(total_no, total_no), '')
        worksheet.set_column('A:B', 14, fmt)
        worksheet.set_column('C:C', 24, fmt)
        worksheet.set_column('D:F', 11, fmt)
        worksheet.set_column('G:G', 6, center_fmt)
        worksheet.set_column('H:I', 14, float_fmt)
        worksheet.set_column('J:J', 8, fmt)
        worksheet.set_column('K:K', 14, float_fmt)
        worksheet.set_column('L:L', 14, center_fmt)
        worksheet.set_column('M:N', 18, fmt)
        worksheet.set_row(0, 16.5)
        worksheet.conditional_format('A1:N%d' % total_no, {'type': 'blanks', 'format': border_format})
        worksheet.conditional_format('A1:N%d' % total_no, {'type': 'no_blanks', 'format': border_format})
        writer.save()
        return create_excel_resp(file_path, '机台信息表')
    except Exception as e:
        logger.error('查询失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '查询失败, error: {}'.format(str(e))})


# 导出器材信息
@api_view(['GET'])
def export_tooling_list(request):
    try:
        obj = FoundryTooling.objects
        project_id = request.GET.get('project', '')
        if project_id:
            obj = obj.filter(project_id=project_id)
        category = request.GET.get('category', '')
        if category:
            obj = obj.filter(category=category)
        factory = request.GET.get('factory', '')
        if factory:
            obj = obj.filter(factory=factory)

        fuzzy_params = {}
        fuzzy_params['purchase_order_no'] = request.GET.get('purchase_order_no', '')
        fuzzy_params['name'] = request.GET.get('name', '')
        fuzzy_params['supplier'] = request.GET.get('supplier', '')

        filter_params = {}
        for k, v in fuzzy_params.items():
            if v != None and v != '':
                k = k + '__contains'
                filter_params[k] = v
        if filter_params:
            obj = obj.filter(**filter_params)
        qs = obj.order_by('-create_time').values('purchase_order_no', 'supplier', 'name', 'category',
                                                 'project__name', 'number', 'unit', 'price', 'total_amount',
                                                 'currency__name', 'currency__exchange_rate', 'factory__name',
                                                 'used_machine', 'fixed_asset_code')
        blank_path = os.path.dirname(__file__) + '/blank_files/设备器材表.xlsx'
        if not qs:
            return create_excel_resp(blank_path, '设备器材表')
        df = pd.DataFrame(list(qs))
        df['price'] = df['price'].map(lambda x: float(x) if x else x)
        df['total_amount'] = df['total_amount'].map(lambda x: float(x) if x else x)
        df['currency__exchange_rate'] = df['currency__exchange_rate'].map(lambda x: float(x) if x else x)
        df['base_total_amount'] = round(df['total_amount'] / df['currency__exchange_rate'], 2)
        ndf = df[['purchase_order_no', 'supplier', 'name', 'category', 'project__name', 'number', 'unit', 'price',
                  'total_amount', 'currency__name', 'base_total_amount', 'factory__name', 'used_machine',
                  'fixed_asset_code']]
        machine_category = {
            1: '测试配件',
            2: '测试板',
            3: '探针卡'
        }
        unit_type = {
            1: '套',
            2: '个',
            3: '台',
            4: '块'
        }
        ndf['category'] = ndf['category'].map(machine_category)
        ndf['unit'] = ndf['unit'].map(unit_type)

        def join_used_machine(x):
            if x:
                x = eval(x)
                return ','.join([item['label'] for item in x])
            else:
                return None
        ndf['used_machine'] = ndf['used_machine'].map(join_used_machine)
        order_list = ndf['purchase_order_no'].unique().tolist()
        if None in order_list:
            order_list.remove(None)
        order_count = len(order_list)
        base_amount_sum = ndf['base_total_amount'].sum()
        rename_maps = {
            'purchase_order_no': '采购订单编号',
            'supplier': '供应商',
            'name': '设备器材型号名称',
            'category': '类别',
            'project__name': '项目',
            'number': '数量',
            'unit': '单位',
            'price': '单价',
            'total_amount': '总价',
            'currency__name': '币种',
            'base_total_amount': '本位币总价（¥）',
            'factory__name': '存放地点',
            'used_machine': '配套机台型号',
            'fixed_asset_code': '固定资产编号'
        }
        ndf.rename(rename_maps, axis=1, inplace=True)
        file_path = get_file_path('detail', 'export_files')
        writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
        workbook = writer.book
        fmt = workbook.add_format({'font_size': 10, 'text_wrap': True, 'valign': 'vcenter'})
        center_fmt = workbook.add_format({'font_size': 10, 'text_wrap': True, 'valign': 'vcenter', 'align': 'center'})
        border_format = workbook.add_format({'border': 1})
        float_fmt = workbook.add_format({'font_size': 10, 'num_format': '#,##0.00', 'valign': 'vcenter'})
        total_fmt = workbook.add_format({'font_size': 10, 'align': 'center'})
        title_fmt = workbook.add_format(
            {'bold': True, 'font_size': 10, 'font_name': '宋体', 'font_color': 'white',
             'bg_color': '#821e78', 'valign': 'vcenter', 'align': 'center'})
        ndf.to_excel(writer, sheet_name='各工厂资产', header=False, index=False, startcol=0, startrow=1)
        worksheet = writer.sheets['各工厂资产']
        l_end = len(ndf.index) + 1
        for col_num, value in enumerate(ndf.columns.values):
            worksheet.write(0, col_num, value, title_fmt)
        total_no = l_end + 1
        worksheet.write(l_end, 0, '订单数量：', title_fmt)
        worksheet.write(l_end, 1, order_count, total_fmt)
        worksheet.merge_range('C{}:J{}'.format(total_no, total_no), '')
        worksheet.write(l_end, 10, '合计金额：', title_fmt)
        worksheet.write(l_end, 11, base_amount_sum, float_fmt)
        worksheet.merge_range('M{}:N{}'.format(total_no, total_no), '')
        worksheet.set_column('A:B', 14, fmt)
        worksheet.set_column('C:C', 24, fmt)
        worksheet.set_column('D:F', 11, fmt)
        worksheet.set_column('G:G', 6, center_fmt)
        worksheet.set_column('H:I', 14, float_fmt)
        worksheet.set_column('J:J', 8, fmt)
        worksheet.set_column('K:K', 14, float_fmt)
        worksheet.set_column('L:L', 14, center_fmt)
        worksheet.set_column('M:N', 18, fmt)
        worksheet.set_row(0, 16.5)
        worksheet.conditional_format('A1:N%d' % total_no, {'type': 'blanks', 'format': border_format})
        worksheet.conditional_format('A1:N%d' % total_no, {'type': 'no_blanks', 'format': border_format})
        writer.save()
        return create_excel_resp(file_path, '设备器材表')
    except Exception as e:
        logger.error('查询失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '查询失败, error: {}'.format(str(e))})
