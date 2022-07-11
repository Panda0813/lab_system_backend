from django.shortcuts import render
from django.db.models import Q
from rest_framework import generics, serializers
from rest_framework import filters, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import connection, close_old_connections, transaction
from utils.pagination import MyPagePagination

from pwm_cost.serializers import WaferInfoSerializer, WaferBomSerializer, GrainBomSerializer, GrainInfoSerializer, \
    UploadRecordSerializer, WaferPriceSerializer, GrainYieldSerializer, GrainPriceSerializer
from pwm_cost.models import WaferInfo, WaferBom, GrainInfo, GrainBom, UploadRecord, WaferPrice, GrainYield, \
    GrainUnitPrice
from equipments.ext_utils import REST_FAIL, REST_SUCCESS, VIEW_FAIL, VIEW_SUCCESS, \
    create_excel_resp, execute_batch_sql, dictfetchall
from utils.log_utils import set_create_log, set_update_log, set_delete_log
from pwm_cost.ext_utils import get_file_path, analysis_wafer_price, analysis_grain_yield, analysis_grain_price
from decimal import Decimal
from users.models import User

import pandas as pd
import numpy as np
import datetime
import traceback
import json
import os
import logging


logger = logging.getLogger('django')


# 获取wafer对应关系
@api_view(['GET'])
def get_wafer_maps(request):
    general_base = ['晶圆']
    subdivision_base = ['Dram', 'Logic']
    technology_base = ['25nm', '38nm', '45nm', '55nm', '63nm']
    wafer_maps = {'general_type': general_base, 'subdivision_type': subdivision_base, 'technology_type': technology_base}
    # general_qs = WaferInfo.objects.values('general').distinct()
    # if general_qs:
    #     general_qs = [item['general'] for item in list(general_qs) if item['general']]
    #     general_base.extend(general_qs)
    #     wafer_maps['general_type'] = list(set(general_base))
    subdivision_qs = WaferInfo.objects.values('subdivision').distinct()
    if subdivision_qs:
        subdivision_qs = [item['subdivision'] for item in list(subdivision_qs) if item['subdivision']]
        subdivision_base.extend(subdivision_qs)
        wafer_maps['subdivision_type'] = list(set(subdivision_base))
        wafer_maps['subdivision_type'].sort()
    technology_qs = WaferInfo.objects.values('technology').distinct()
    if technology_qs:
        technology_qs = [item['technology'] for item in list(technology_qs) if item['technology']]
        technology_base.extend(technology_qs)
        wafer_maps['technology_type'] = list(set(technology_base))
        wafer_maps['technology_type'].sort()
    return REST_SUCCESS(wafer_maps)


class WaferInfoGeneric(generics.ListCreateAPIView):
    model = WaferInfo
    queryset = model.objects.all()
    serializer_class = WaferInfoSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name
    filter_backends = [filters.OrderingFilter, ]
    ordering_fields = ['create_time']
    ordering = ['-create_time']

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        wafer_id = request.GET.get('id', '')
        if wafer_id:
            queryset = queryset.filter(id=wafer_id)  # 精确查询
        project_id = request.GET.get('project', '')
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        fuzzy_params = {}
        fuzzy_params['general'] = request.GET.get('general', '')
        fuzzy_params['subdivision'] = request.GET.get('subdivision', '')
        fuzzy_params['technology'] = request.GET.get('technology', '')

        filter_params = {}
        for k, v in fuzzy_params.items():
            if v != None and v != '':
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
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class WaferDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = WaferInfo
    queryset = model.objects.all()
    serializer_class = WaferInfoSerializer
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


class WaferBomGeneric(generics.ListCreateAPIView):
    model = WaferBom
    queryset = model.objects.all()
    serializer_class = WaferBomSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_create_log
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class WaferBomDetailGeneric(generics.RetrieveUpdateAPIView):
    model = WaferBom
    queryset = model.objects.all()
    serializer_class = WaferBomSerializer
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


# 获取颗粒对应关系
@api_view(['GET'])
def get_grain_maps(request):
    general_base = ['颗粒']
    subdivision_base = ['KGD', 'DRAM', 'ASIC']
    technology_base = ['25nm', '38nm', '45nm', '55nm', '63nm']
    grain_maps = {'general_type': general_base, 'subdivision_type': subdivision_base, 'technology_type': technology_base}
    # general_qs = GrainInfo.objects.values('general').distinct()
    # if general_qs:
    #     general_qs = [item['general'] for item in list(general_qs) if item['general']]
    #     general_base.extend(general_qs)
    #     grain_maps['general_type'] = list(set(general_base))
    subdivision_qs = GrainInfo.objects.values('subdivision').distinct()
    if subdivision_qs:
        subdivision_qs = [item['subdivision'] for item in list(subdivision_qs) if item['subdivision']]
        subdivision_base.extend(subdivision_qs)
        grain_maps['subdivision_type'] = list(set(subdivision_base))
    technology_qs = GrainInfo.objects.values('technology').distinct()
    if technology_qs:
        technology_qs = [item['technology'] for item in list(technology_qs) if item['technology']]
        technology_base.extend(technology_qs)
        grain_maps['technology_type'] = list(set(technology_base))
        grain_maps['technology_type'].sort()
    return REST_SUCCESS(grain_maps)


class GrainInfoGeneric(generics.ListCreateAPIView):
    model = GrainInfo
    queryset = model.objects.all().order_by('-create_time')
    serializer_class = GrainInfoSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        grain_id = request.GET.get('id', '')
        if grain_id:
            queryset = queryset.filter(id=grain_id)  # 精确查询
        wafer_id = request.GET.get('wafer', '')
        if wafer_id:
            queryset = queryset.filter(wafer_id=wafer_id)  # 精确查询
        project_id = request.GET.get('project', '')
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        fuzzy_params = {}
        fuzzy_params['general'] = request.GET.get('general', '')
        fuzzy_params['subdivision'] = request.GET.get('subdivision', '')
        fuzzy_params['technology'] = request.GET.get('technology', '')

        filter_params = {}
        for k, v in fuzzy_params.items():
            if v != None and v != '':
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
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class GrainDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = GrainInfo
    queryset = model.objects.all()
    serializer_class = GrainInfoSerializer
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


class GrainBomGeneric(generics.ListCreateAPIView):
    model = GrainBom
    queryset = model.objects.all()
    serializer_class = GrainBomSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_create_log
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class GrainBomDetailGeneric(generics.RetrieveUpdateAPIView):
    model = GrainBom
    queryset = model.objects.all()
    serializer_class = GrainBomSerializer
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


class UploadRecordGeneric(generics.ListCreateAPIView):
    queryset = UploadRecord.objects.all().order_by('-create_time')
    serializer_class = UploadRecordSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        req_user = request.user
        queryset = queryset.filter(user=req_user)
        user_id = request.GET.get('user', '')
        if user_id:
            queryset = queryset.filter(user_id=user_id)  # 精确查询
        data_type = request.GET.get('data_type', '')
        if data_type:
            queryset = queryset.filter(data_type=data_type)
        start_createTime = request.GET.get('start_createTime', '')
        end_createTime = request.GET.get('end_createTime', '')
        if start_createTime and end_createTime:
            queryset = queryset.filter(create_time__range=[start_createTime + ' 00:00:00', end_createTime + ' 23:59:59'])

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class UploadRecordOperate(generics.DestroyAPIView):
    model = UploadRecord
    queryset = model.objects.all()
    serializer_class = UploadRecordSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_delete_log
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        del_id = instance.id
        data_type = instance.data_type
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                if data_type == 1:
                    WaferPrice.objects.filter(upload_id=del_id).delete()
                elif data_type == 2:
                    GrainYield.objects.filter(upload_id=del_id).delete()
                elif data_type == 3:
                    GrainUnitPrice.objects.filter(upload_id=del_id).delete()
                self.perform_destroy(instance)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.info('删除上传记录失败, error:{}'.format(str(e)))
                raise serializers.ValidationError('删除失败')
        return REST_SUCCESS({'msg': '删除成功'})


class WaferPriceGeneric(generics.ListCreateAPIView):
    queryset = WaferPrice.objects.all().order_by('-create_time')
    serializer_class = WaferPriceSerializer
    pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        user_id = request.GET.get('user', '')
        if user_id:
            queryset = queryset.filter(user_id=user_id)  # 精确查询
        wafer_id = request.GET.get('wafer', '')
        if wafer_id:
            queryset = queryset.filter(wafer_id=wafer_id)  # 精确查询
        project_id = request.GET.get('project', '')
        if project_id:
            queryset = queryset.filter(wafer__project_id=project_id)
        start_orderTime = request.GET.get('start_orderTime', '')
        end_orderTime = request.GET.get('end_orderTime')
        if start_orderTime and end_orderTime:
            queryset = queryset.filter(order_date__range=[start_orderTime, end_orderTime])
        start_createTime = request.GET.get('start_createTime', '')
        end_createTime = request.GET.get('end_createTime', '')
        if start_createTime and end_createTime:
            queryset = queryset.filter(create_time__range=[start_createTime + ' 00:00:00', end_createTime + ' 23:59:59'])

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
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class WaferPriceOperate(generics.RetrieveUpdateDestroyAPIView):
    model = WaferPrice
    queryset = model.objects.all()
    serializer_class = WaferPriceSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_delete_log
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return REST_SUCCESS({'msg': '删除成功'})


# 下载上传文件模板
@api_view(['GET'])
def get_upload_template(request):
    current_path = os.path.dirname(__file__)
    file_name = request.GET.get('file_name')
    if not file_name:
        return REST_FAIL({'msg': 'file_name不能为空'})
    dir_ = os.path.join(current_path, 'download_template')
    file_path = os.path.join(dir_, '{}.xlsx'.format(file_name))
    return create_excel_resp(file_path, file_name)


# 导入wafer成本
@api_view(['POST'])
def upload_wafer_price(request):
    try:
        try:
            file = request.FILES.get('file', '')
            if not file:
                return VIEW_FAIL(msg='上传文件不能为空')
            upload_path, file_name = get_file_path('wafer', 'upload_files')
            with open(upload_path, 'wb') as f:
                for i in file.chunks():
                    f.write(i)
        except Exception as e:
            logger.error('文件解析出错, error:{}'.format(str(e)))
            return VIEW_FAIL(msg='文件解析出错, error:{}'.format(str(e)))
        res_data = {'upload_file_name': file_name}
        df = pd.read_excel(upload_path, sheet_name='Sheet1')
        datas = df.to_dict('records')
        ndf = analysis_wafer_price(datas)
        if ndf.empty:
            res_data['datas'] = []
            return VIEW_SUCCESS(msg='导入成功', data=res_data)
        # 追加有bom的wafer
        bom_qs = WaferInfo.objects.filter(has_bom=True).values('id')
        if bom_qs:
            base_bom_df = pd.DataFrame(list(bom_qs))
            base_bom_df.rename(columns={'id': 'wafer_id'}, inplace=True)
            ndf = pd.concat([ndf, base_bom_df], axis=0)
        wafer_id_ls = list(ndf['wafer_id'].unique())
        wafer_qs = WaferInfo.objects.filter(id__in=wafer_id_ls).values('id', 'project__name', 'general', 'subdivision',
                                                                       'technology', 'gross_die', 'has_bom')
        info_df = pd.DataFrame(list(wafer_qs))
        info_df.rename(columns={'id': 'wafer_id', 'project__name': 'project_name'}, inplace=True)
        mdf = pd.merge(ndf, info_df, how='outer', on='wafer_id')
        mdf = mdf.replace({np.nan: None})
        datas = mdf.to_dict('records')
        for d in datas:
            if d['has_bom']:
                wafer_obj = WaferInfo.objects.get(id=d['wafer_id']).belong_wafer.values('wafer_source_id', 'count')
                source_df = pd.DataFrame(list(wafer_obj))
                source_df.rename(columns={'wafer_source_id': 'wafer_id'}, inplace=True)
                bom_df = pd.merge(source_df, mdf, how='left', on='wafer_id')
                bom_df['sum'] = bom_df['purchase_price'] * bom_df['count']
                d['wafer_price'] = round(bom_df['sum'].sum(), 2)
            else:
                d['wafer_price'] = d['purchase_price']
        res_data['datas'] = datas
        return VIEW_SUCCESS(msg='导入成功', data=res_data)
    except Exception as e:
        logger.error('文件解析出错, error:{}'.format(str(e)))
        return VIEW_FAIL(msg='文件解析出错, 请按照导入模板导入数据', data={'error': str(e)})


# 重新测算成本
@api_view(['POST'])
def recalculate_wafer_price(request):
    try:
        try:
            req_dic = json.loads(request.body)
        except Exception as e:
            return REST_FAIL({'msg': '请求参数解析错误,请确认格式正确后上传', 'error': str(e)})
        datas = req_dic.get('datas', [])
        if not datas:
            return REST_FAIL({'msg': '提交数据不能为空'})
        ndf = pd.DataFrame(datas)
        mdf = ndf[['wafer_id', 'project_name', 'general', 'subdivision', 'technology', 'gross_die', 'has_bom',
                   'price_source', 'supplier', 'purchase_price', 'order_date']]
        ndf['purchase_price'] = ndf['purchase_price'].map(lambda x: float(x) if x else x)
        mdf = mdf.replace({np.nan: None})
        datas = mdf.to_dict('records')
        for d in datas:
            if d['has_bom']:
                wafer_obj = WaferInfo.objects.get(id=d['wafer_id']).belong_wafer.values('wafer_source_id', 'count')
                source_df = pd.DataFrame(list(wafer_obj))
                source_df.rename(columns={'wafer_source_id': 'wafer_id'}, inplace=True)
                bom_df = pd.merge(source_df, mdf, how='left', on='wafer_id')
                bom_df['purchase_price'] = bom_df['purchase_price'].map(lambda x: float(x) if x else x)
                bom_df['sum'] = bom_df['purchase_price'] * bom_df['count']
                d['wafer_price'] = round(bom_df['sum'].sum(), 2)
            else:
                d['wafer_price'] = d['purchase_price']
        return REST_SUCCESS(data=datas)
    except Exception as e:
        logger.error('测算出错, error:{}'.format(str(e)))
        return REST_FAIL({'msg': '测算出错', 'error': str(e)})


# 保存导入的数据
@api_view(['POST'])
def save_upload_wafer_price(request):
    try:
        try:
            req_dic = json.loads(request.body)
        except Exception as e:
            return REST_FAIL({'msg': '请求参数解析错误,请确认格式正确后上传', 'error': str(e)})
        user = request.user
        file_path = req_dic.get('upload_file_name')
        maintain_period = datetime.datetime.now().strftime('%Y-%m')
        datas = req_dic.get('datas', [])
        if not datas:
            return REST_FAIL({'msg': '提交数据不能为空'})
        insert_sql = '''insert into pwm_cost_wafer_price(price_source, supplier, purchase_price, order_date,wafer_price, 
                                    maintain_period, create_time, update_time, is_delete, upload_id, wafer_id, user_id)
                                    values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
        close_old_connections()
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                if file_path:
                    upload_obj = UploadRecord.objects.create(user=user, data_type=1, file_path=file_path)
                    upload_id = upload_obj.id
                else:
                    upload_id = None
                count = 0
                now_ts = datetime.datetime.now()
                insert_ls = []
                for data in datas:
                    count += 1
                    wafer_id = data.get('wafer_id')
                    if not wafer_id:
                        return REST_SUCCESS({'msg': 'wafer型号不能为空, 空值所在行: {}'.format(count)})
                    insert_args = (data.get('price_source'), data.get('supplier'), data.get('purchase_price'),
                                   data.get('order_date'), data.get('wafer_price'), maintain_period, now_ts, now_ts,
                                   False, upload_id, wafer_id, user.id)
                    insert_ls.append(insert_args)
                    if len(insert_ls) >= 50:
                        execute_batch_sql(insert_sql, insert_ls)
                        insert_ls = []
                if len(insert_ls) > 0:
                    execute_batch_sql(insert_sql, insert_ls)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.error('wafer价格数据保存失败, error:{}'.format(str(e)))
                return REST_FAIL({'msg': '数据保存失败', 'error': str(e)})
        return REST_SUCCESS({'msg': '提交成功'})
    except Exception as e:
        logger.error('wafer价格数据保存失败, error:{}'.format(str(e)))
        return REST_FAIL({'msg': '数据保存失败', 'error': str(e)})


# 导出wafer成本信息
@api_view(['GET'])
def export_wafer_price(request):
    try:
        queryset = WaferPrice.objects
        wafer_id = request.GET.get('wafer', '')
        if wafer_id:
            queryset = queryset.filter(wafer_id=wafer_id)
        project_id = request.GET.get('project', '')
        if project_id:
            queryset = queryset.filter(wafer__project_id=project_id)
        start_orderTime = request.GET.get('start_orderTime', '')
        end_orderTime = request.GET.get('end_orderTime')
        if start_orderTime and end_orderTime:
            queryset = queryset.filter(order_date__range=[start_orderTime, end_orderTime])
        start_createTime = request.GET.get('start_createTime', '')
        end_createTime = request.GET.get('end_createTime', '')
        if start_createTime and end_createTime:
            queryset = queryset.filter(create_time__range=[start_createTime + ' 00:00:00', end_createTime + ' 23:59:59'])
        qs = queryset.order_by('create_time').values('wafer_id', 'wafer__project__name', 'wafer__general',
                                                      'wafer__subdivision', 'wafer__technology', 'wafer__gross_die',
                                                      'price_source', 'supplier', 'purchase_price', 'order_date',
                                                      'wafer_price', 'create_time')
        blank_path = os.path.dirname(__file__) + '/blank_files/Wafer成本信息.xlsx'
        if not qs:
            return create_excel_resp(blank_path, 'Wafer成本信息')
        df = pd.DataFrame(list(qs))
        df['purchase_price'] = df['purchase_price'].map(lambda x: float(x) if x else x)
        df['wafer_price'] = df['wafer_price'].map(lambda x: float(x) if x else x)
        df['create_time'] = df['create_time'].map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
        ndf = df[['wafer_id', 'wafer__project__name', 'wafer__general', 'wafer__subdivision', 'wafer__technology',
                  'wafer__gross_die', 'price_source', 'supplier', 'purchase_price', 'order_date', 'create_time',
                  'wafer_price']]
        rename_maps = {
            'wafer_id': 'Wafer 型号',
            'wafer__project__name': '项目',
            'wafer__general': '产品大类',
            'wafer__subdivision': '产品细分',
            'wafer__technology': '工艺',
            'wafer__gross_die': 'Gross die数量',
            'price_source': '价格来源',
            'supplier': '供应商',
            'purchase_price': '采购单价',
            'order_date': '下单日期',
            'create_time': '提交日期',
            'wafer_price': 'Wafer U/P'
        }
        ndf.rename(rename_maps, axis=1, inplace=True)
        file_path, file_name = get_file_path('wafer', 'export_files')
        writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
        workbook = writer.book
        fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'text_wrap': True, 'valign': 'vcenter'})
        center_fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'text_wrap': True,
                                          'valign': 'vcenter', 'align': 'center'})
        right_fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'text_wrap': True,
                                          'valign': 'vcenter', 'align': 'right'})
        border_format = workbook.add_format({'border': 1})
        float_fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'num_format': '#,##0.00', 'valign': 'vcenter'})
        ts_fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'num_format': 'yyyy/m/d',
                                      'valign': 'vcenter', 'align': 'right'})
        title_fmt = workbook.add_format(
            {'bold': True, 'font_size': 10, 'font_name': 'Arial Unicode MS', 'valign': 'vcenter', 'align': 'center'})
        ndf.to_excel(writer, sheet_name='Sheet1', header=False, index=False, startcol=0, startrow=1)
        worksheet = writer.sheets['Sheet1']
        l_end = len(ndf.index) + 1
        for col_num, value in enumerate(ndf.columns.values):
            worksheet.write(0, col_num, value, title_fmt)
        worksheet.conditional_format('A1:F1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#5b9bd5'})})
        worksheet.conditional_format('G1:K1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#ffc000'})})
        worksheet.conditional_format('L1:L1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#ff0000'})})
        worksheet.set_column('A:B', 15.5, fmt)
        worksheet.set_column('C:E', 10, center_fmt)
        worksheet.set_column('F:H', 12, fmt)
        worksheet.set_column('I:I', 9, float_fmt)
        worksheet.set_column('J:J', 10, ts_fmt)
        worksheet.set_column('K:K', 18, right_fmt)
        worksheet.set_column('L:L', 11, float_fmt)
        worksheet.conditional_format('A1:L%d' % l_end, {'type': 'blanks', 'format': border_format})
        worksheet.conditional_format('A1:L%d' % l_end, {'type': 'no_blanks', 'format': border_format})
        writer.save()
        return create_excel_resp(file_path, 'Wafer成本信息')
    except Exception as e:
        logger.error('导出失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '导出失败, error: {}'.format(str(e))})


class GrainYieldGeneric(generics.ListCreateAPIView):
    queryset = GrainYield.objects.all().order_by('-create_time')
    serializer_class = GrainYieldSerializer
    pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        user_id = request.GET.get('user', '')
        if user_id:
            queryset = queryset.filter(user_id=user_id)  # 精确查询
        grain_id = request.GET.get('grain', '')
        if grain_id:
            queryset = queryset.filter(grain_id=grain_id)  # 精确查询
        subdivision = request.GET.get('subdivision', '')
        if subdivision:
            queryset = queryset.filter(grain__subdivision=subdivision)
        start_createTime = request.GET.get('start_createTime', '')
        end_createTime = request.GET.get('end_createTime', '')
        if start_createTime and end_createTime:
            queryset = queryset.filter(create_time__range=[start_createTime + ' 00:00:00', end_createTime + ' 23:59:59'])

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
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class GrainYieldOperate(generics.RetrieveUpdateDestroyAPIView):
    model = GrainYield
    queryset = model.objects.all()
    serializer_class = GrainYieldSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_delete_log
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return REST_SUCCESS({'msg': '删除成功'})


class GrainPriceGeneric(generics.ListCreateAPIView):
    queryset = GrainUnitPrice.objects.all().order_by('-create_time')
    serializer_class = GrainPriceSerializer
    pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        user_id = request.GET.get('user', '')
        if user_id:
            queryset = queryset.filter(user_id=user_id)  # 精确查询
        grain_id = request.GET.get('grain', '')
        if grain_id:
            queryset = queryset.filter(grain_id=grain_id)  # 精确查询
        subdivision = request.GET.get('subdivision', '')
        if subdivision:
            queryset = queryset.filter(grain__subdivision=subdivision)
        start_createTime = request.GET.get('start_createTime', '')
        end_createTime = request.GET.get('end_createTime', '')
        if start_createTime and end_createTime:
            queryset = queryset.filter(create_time__range=[start_createTime + ' 00:00:00', end_createTime + ' 23:59:59'])

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
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class GrainPriceOperate(generics.RetrieveUpdateDestroyAPIView):
    model = GrainUnitPrice
    queryset = model.objects.all()
    serializer_class = GrainPriceSerializer
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name

    @set_delete_log
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return REST_SUCCESS({'msg': '删除成功'})


# 查询本月是否已上传wafer成本
@api_view(['GET'])
def exist_wafer_price(request):
    now_period = datetime.datetime.now().strftime('%Y-%m')
    wafer_price_qs = WaferPrice.objects.filter(maintain_period=now_period)
    if wafer_price_qs:
        exist_tag = True
    else:
        exist_tag = False
    return REST_SUCCESS(data={'exist_tag': exist_tag})


# 计算良率
def calculate_yield(ydf):
    ydf.fillna(1, inplace=True)
    ydf['wafer_yld'] = round(ydf['hb_yld'] * ydf['cp_yld'] * ydf['rdl_yld'] * ydf['bp_yld'], 4)
    ydf['ft_yld'] = round(ydf['ap_yld'] * ydf['bi_yld'] * ydf['ft1_yld'] * ydf['ft2_yld']
                          * ydf['ft3_yld'] * ydf['ft4_yld'] * ydf['ft5_yld'] * ydf['ft6_yld'], 4)
    grain_id_ls = list(ydf['grain_id'].unique())
    grain_qs = GrainInfo.objects.filter(id__in=grain_id_ls).values('id', 'wafer_id', 'has_bom')
    info_df = pd.DataFrame(list(grain_qs))
    info_df.rename(columns={'id': 'grain_id'}, inplace=True)
    ydf = pd.merge(ydf, info_df, how='outer', on='grain_id')
    y_datas = ydf.to_dict('records')
    for d in y_datas:
        if d['has_bom']:
            ydf.loc[ydf['grain_id'] == d['grain_id'], ['hb_yld', 'cp_yld', 'rdl_yld', 'bp_yld', 'wafer_yld']] = 1
    ydf[ydf.columns.difference(['grain_id', 'has_bom', 'wafer_id'])] \
        = round(ydf[ydf.columns.difference(['grain_id', 'has_bom', 'wafer_id'])], 4)
    return ydf.to_dict('records')


# 导入颗粒良率
@api_view(['POST'])
def upload_grain_yield(request):
    try:
        try:
            file = request.FILES.get('file', '')
            if not file:
                return VIEW_FAIL(msg='上传文件不能为空')
            upload_path, file_name = get_file_path('yield', 'upload_files')
            with open(upload_path, 'wb') as f:
                for i in file.chunks():
                    f.write(i)
        except Exception as e:
            logger.error('文件解析出错, error:{}'.format(str(e)))
            return VIEW_FAIL(msg='文件解析出错, error:{}'.format(str(e)))
        res_data = {'upload_file_name': file_name}
        df = pd.read_excel(upload_path, sheet_name='Sheet1')
        datas = df.to_dict('records')
        ndf = analysis_grain_yield(datas)
        if ndf.empty:
            res_data['datas'] = []
            return VIEW_SUCCESS(msg='导入成功', data=res_data)
        res_data['datas'] = calculate_yield(ndf)
        return VIEW_SUCCESS(msg='导入成功', data=res_data)
    except Exception as e:
        logger.error('文件解析出错, error:{}'.format(str(e)))
        return VIEW_FAIL(msg='文件解析出错, 请按照导入模板导入数据', data={'error': str(e)})


# 查询wafer最新成本
def query_wafer_price(ids):
    sql = '''select a.wafer_id, b.id as grain_id, wafer_price, a.create_time
                from (select * from pwm_cost_wafer_price order by create_time desc) a
                inner join pwm_cost_grain_info b on a.wafer_id = b.wafer_id
                where b.id {}
                group by a.wafer_id, b.id'''
    if len(ids) == 1:
        fmt = "= '{}'".format(ids[0])
    else:
        fmt = 'in {}'.format(tuple(ids))
    with connection.cursor() as cursor:
        cursor.execute(sql.format(fmt))
        qs = dictfetchall(cursor)
    return qs


# 计算测试费
def calculate_grain_price(pdf, ydf):
    grain_id_ls = list(pdf['grain_id'].unique())
    # 拼接wafer信息
    grain_qs = GrainInfo.objects.filter(id__in=grain_id_ls).values('id', 'wafer_id', 'wafer__gross_die', 'has_bom')
    info_df = pd.DataFrame(list(grain_qs))
    info_df.rename(columns={'id': 'grain_id', 'wafer__gross_die': 'gross_die'}, inplace=True)
    pdf = pd.merge(pdf, info_df, how='outer', on='grain_id')  # 合并wafer信息和测试费
    pdf['gross_die'] = pdf['gross_die'].fillna(1)
    # 拼接wafer成本
    wafer_grain_id_ls = [item['id'] for item in list(grain_qs) if item['wafer_id']]  # 关联wafer的颗粒
    wafer_price_qs = query_wafer_price(wafer_grain_id_ls)
    if wafer_price_qs:
        wp_df = pd.DataFrame(wafer_price_qs)
        wp_df = wp_df[['grain_id', 'wafer_price']]
        pdf = pd.merge(pdf, wp_df, how='outer', on='grain_id')  # 合并成本和测试费
    else:
        pdf['wafer_price'] = 0
    pdf[['purchase_price', 'wafer_price']] = pdf[['purchase_price', 'wafer_price']].astype(float)
    pdf[['purchase_price', 'wafer_price']] = pdf[['purchase_price', 'wafer_price']].fillna(0)
    pdf = pd.merge(pdf, ydf, how='left', on='grain_id')  # 合并测试费和良率
    pdf[['wafer_yld', 'ft_yld', 'ap_yld', 'bi_yld', 'ft1_yld', 'ft2_yld', 'ft3_yld', 'ft4_yld', 'ft5_yld', 'ft6_yld']] = \
        pdf[['wafer_yld', 'ft_yld', 'ap_yld', 'bi_yld', 'ft1_yld', 'ft2_yld', 'ft3_yld', 'ft4_yld', 'ft5_yld', 'ft6_yld']].fillna(1)
    pdf['wafer_amt'] = round(pdf['hb_up'] + pdf['cp_up'] + pdf['rdl_up'] + pdf['bp_up'], 2)  # 计算前段费用
    # 先计算各段成本
    pdf['ap_amt'] = round(pdf['ap_up'] * pdf['ap_yld'] * pdf['wafer_yld'] * pdf['gross_die'], 2)
    pdf['bi_amt'] = round(pdf['bi_up'] * pdf['ap_yld'] * pdf['wafer_yld'] * pdf['gross_die'], 2)
    pdf['ft1_amt'] = round(pdf['ft1_up'] * pdf['ap_yld'] * pdf['bi_yld'] * pdf['wafer_yld'] * pdf['gross_die'], 2)
    pdf['ft2_amt'] = round(pdf['ft2_up'] * pdf['ap_yld'] * pdf['bi_yld'] * pdf['ft1_yld'] * pdf['wafer_yld'] *
                           pdf['gross_die'], 2)
    pdf['ft3_amt'] = round(pdf['ft3_up'] * pdf['ap_yld'] * pdf['bi_yld'] * pdf['ft1_yld'] * pdf['ft2_yld'] *
                           pdf['wafer_yld'] * pdf['gross_die'], 2)
    pdf['ft4_amt'] = round(pdf['ft4_up'] * pdf['ap_yld'] * pdf['bi_yld'] * pdf['ft1_yld'] * pdf['ft2_yld'] *
                           pdf['ft3_yld'] * pdf['wafer_yld'] * pdf['gross_die'], 2)
    pdf['ft5_amt'] = round(pdf['ft5_up'] * pdf['ap_yld'] * pdf['bi_yld'] * pdf['ft1_yld'] * pdf['ft2_yld'] *
                           pdf['ft3_yld'] * pdf['ft4_yld'] * pdf['wafer_yld'] * pdf['gross_die'], 2)
    pdf['ft6_amt'] = round(pdf['ft6_up'] * pdf['ap_yld'] * pdf['bi_yld'] * pdf['ft1_yld'] * pdf['ft2_yld'] *
                           pdf['ft3_yld'] * pdf['ft4_yld'] * pdf['ft5_yld'] * pdf['wafer_yld'] * pdf['gross_die'], 2)
    pdf['msp_amt'] = round(pdf['msp_up'] * pdf['ft_yld'] * pdf['wafer_yld'] * pdf['gross_die'], 2)
    pdf['ft_amt'] = pdf['ap_amt'] + pdf['bi_amt'] + pdf['ft1_amt'] + pdf['ft2_amt'] + \
                    pdf['ft3_amt'] + pdf['ft4_amt'] + pdf['ft5_amt'] + pdf['ft6_amt'] + pdf['msp_amt']
    pdf['ic_up'] = round(pdf['purchase_price'] + ((pdf['wafer_price'] + pdf['wafer_amt'] + pdf['ft_amt']) /
                         (pdf['wafer_yld'] * pdf['ft_yld'] * pdf['gross_die'])), 2)
    pdf['die_up'] = round(pdf['purchase_price'] + ((pdf['wafer_price'] + pdf['wafer_amt']) /
                                                   (pdf['wafer_yld'] * pdf['ft_yld'] * pdf['gross_die'])), 2)
    pdf['ft_up'] = round(pdf['ft_amt'] / (pdf['wafer_yld'] * pdf['ft_yld'] * pdf['gross_die']), 2)
    nb_df = pdf[pdf['has_bom'] == False]  # 无bom
    eb_df = pdf[pdf['has_bom'] == True]  # 有bom
    eb_datas = eb_df.to_dict('records')
    # 计算有bom的颗粒的采购单价
    for d in eb_datas:
        grain_obj = GrainInfo.objects.get(id=d['grain_id']).belong_grain.values('grain_source_id', 'count')
        source_df = pd.DataFrame(list(grain_obj))
        source_df.rename(columns={'grain_source_id': 'grain_id'}, inplace=True)
        nb_df_ = nb_df.copy()
        bom_df = pd.merge(source_df, nb_df_, how='left', on='grain_id')
        bom_df = bom_df[['grain_id', 'wafer_price', 'ic_up', 'count']]
        bom_df['wafer_price_sum'] = bom_df['wafer_price'] * bom_df['count']
        bom_df['purchase_price_sum'] = bom_df['ic_up'] * bom_df['count']
        d['wafer_price'] = round(bom_df['wafer_price'].sum(), 2)
        d['purchase_price'] = round(bom_df['purchase_price_sum'].sum(), 2)
        d['ft_amt'] = d['ap_amt'] + d['bi_amt'] + d['ft1_amt'] + d['ft2_amt'] + \
                      d['ft3_amt'] + d['ft4_amt'] + d['ft5_amt'] + d['ft6_amt'] + d['msp_amt']
        d['ic_up'] = round(d['purchase_price'] + ((d['wafer_price'] + d['wafer_amt'] + d['ft_amt']) /
                                                  (d['wafer_yld'] * d['ft_yld'] * d['gross_die'])), 2)
        d['die_up'] = round(d['purchase_price'] + ((d['wafer_price'] + d['wafer_amt']) /
                                                   (d['wafer_yld'] * d['ft_yld'] * d['gross_die'])), 2)
        d['ft_up'] = round(d['ft_amt'] / (d['wafer_yld'] * d['ft_yld'] * d['gross_die']), 2)
    f_eb_df = pd.DataFrame(eb_datas)
    f_df = pd.concat([nb_df, f_eb_df], axis=0)
    left_df = ydf[['grain_id']]
    f_df = pd.merge(left_df, f_df, how='outer', on='grain_id')
    return f_df.to_dict('records')


# 导入颗粒测试费
@api_view(['POST'])
def upload_grain_price(request):
    try:
        try:
            file = request.FILES.get('file', '')
            if not file:
                return VIEW_FAIL(msg='上传文件不能为空')
            upload_path, file_name = get_file_path('price', 'upload_files')
            with open(upload_path, 'wb') as f:
                for i in file.chunks():
                    f.write(i)
        except Exception as e:
            logger.error('文件解析出错, error:{}'.format(str(e)))
            return VIEW_FAIL(msg='文件解析出错, error:{}'.format(str(e)))
        res_data = {'upload_file_name': file_name}
        yield_data = request.POST.get('yield_data')
        df = pd.read_excel(upload_path, sheet_name='Sheet1')
        datas = df.to_dict('records')
        ndf = analysis_grain_price(datas)
        if ndf.empty:
            res_data['datas'] = []
            return VIEW_SUCCESS(msg='导入成功', data=res_data)
        ndf.fillna(0, inplace=True)  # 无加工费默认0
        pdf = ndf.copy()
        ydf = pd.DataFrame(json.loads(yield_data))  # 良率
        ydf = ydf[['grain_id', 'wafer_yld', 'ft_yld', 'ap_yld', 'bi_yld', 'ft1_yld', 'ft2_yld', 'ft3_yld', 'ft4_yld',
                   'ft5_yld', 'ft6_yld']]
        res_data['datas'] = calculate_grain_price(pdf, ydf)
        return VIEW_SUCCESS(msg='导入成功', data=res_data)
    except Exception as e:
        logger.error('文件解析出错, error:{}'.format(str(e)))
        return VIEW_FAIL(msg='文件解析出错, 请按照导入模板导入数据', data={'error': str(e)})


# 重新测算数据
@api_view(['POST'])
def recalculate_grain_data(request):
    try:
        try:
            req_dic = json.loads(request.body)
        except Exception as e:
            return REST_FAIL({'msg': '请求参数解析错误,请确认格式正确后上传', 'error': str(e)})
        yield_data = req_dic.get('yield_data')
        if not yield_data:
            return REST_FAIL({'msg': '提交数据不能为空'})
        price_data = req_dic.get('price_data', [])
        res_data = {}
        # 重新测算良率
        ydf = pd.DataFrame(yield_data)
        y_base_df = pd.DataFrame(columns=['grain_id', 'hb_yld', 'cp_yld', 'rdl_yld', 'bp_yld', 'ap_yld', 'bi_yld',
                                          'ft1_yld', 'ft2_yld', 'ft3_yld', 'ft4_yld', 'ft5_yld', 'ft6_yld'], dtype=object)
        ydf = pd.concat([y_base_df, ydf], axis=0)
        ydf = ydf[['grain_id', 'hb_yld', 'cp_yld', 'rdl_yld', 'bp_yld', 'ap_yld', 'bi_yld', 'ft1_yld', 'ft2_yld',
                   'ft3_yld', 'ft4_yld', 'ft5_yld', 'ft6_yld']]
        ydf.fillna(1, inplace=True)
        ydf[['hb_yld', 'cp_yld', 'rdl_yld', 'bp_yld', 'ap_yld', 'bi_yld', 'ft1_yld', 'ft2_yld',
            'ft3_yld', 'ft4_yld', 'ft5_yld', 'ft6_yld']] = \
            ydf[['hb_yld', 'cp_yld', 'rdl_yld', 'bp_yld', 'ap_yld', 'bi_yld', 'ft1_yld', 'ft2_yld',
                'ft3_yld', 'ft4_yld', 'ft5_yld', 'ft6_yld']].astype(float)
        yield_data = calculate_yield(ydf)
        res_data['yield_data'] = yield_data
        # 重新测算成本
        if price_data:
            ydf = pd.DataFrame(yield_data)
            ydf = ydf[['grain_id', 'wafer_yld', 'ft_yld', 'ap_yld', 'bi_yld', 'ft1_yld', 'ft2_yld', 'ft3_yld', 'ft4_yld',
                       'ft5_yld', 'ft6_yld']]
            pdf = pd.DataFrame(price_data)
            p_base_df = pd.DataFrame(columns=['grain_id', 'purchase_price', 'hb_up', 'cp_up', 'rdl_up', 'bp_up', 'ap_up',
                                              'bi_up', 'ft1_up', 'ft2_up', 'ft3_up', 'ft4_up', 'ft5_up', 'ft6_up',
                                              'msp_up'], dtype=object)
            pdf = pd.concat([p_base_df, pdf], axis=0)
            pdf = pdf[['grain_id', 'purchase_price', 'hb_up', 'cp_up', 'rdl_up', 'bp_up', 'ap_up',
                       'bi_up', 'ft1_up', 'ft2_up', 'ft3_up', 'ft4_up', 'ft5_up', 'ft6_up', 'msp_up']]
            pdf.fillna(0, inplace=True)
            pdf[['hb_up', 'cp_up', 'rdl_up', 'bp_up', 'ap_up', 'bi_up', 'ft1_up',
                 'ft2_up', 'ft3_up', 'ft4_up', 'ft5_up', 'ft6_up', 'msp_up']] = \
                pdf[['hb_up', 'cp_up', 'rdl_up', 'bp_up', 'ap_up', 'bi_up', 'ft1_up',
                     'ft2_up', 'ft3_up', 'ft4_up', 'ft5_up', 'ft6_up', 'msp_up']].astype(float)
            price_data = calculate_grain_price(pdf, ydf)
        res_data['price_data'] = price_data
        return REST_SUCCESS(data=res_data)
    except Exception as e:
        logger.error('测算出错, error:{}'.format(str(e)))
        return REST_FAIL({'msg': '测算出错', 'error': str(e)})


# 保存导入的颗粒测算信息
@api_view(['POST'])
def save_upload_grain_data(request):
    try:
        try:
            req_dic = json.loads(request.body)
        except Exception as e:
            return REST_FAIL({'msg': '请求参数解析错误,请确认格式正确后上传', 'error': str(e)})
        user = request.user
        yield_file_name = req_dic.get('yield_file_name')
        yield_data = req_dic.get('yield_data', [])
        price_file_name = req_dic.get('price_file_name')
        price_data = req_dic.get('price_data', [])
        if not yield_data or not price_data:
            return REST_FAIL({'msg': '提交数据不能为空'})
        yield_sql = '''insert into pwm_cost_grain_yld(hb_yld, cp_yld, rdl_yld, bp_yld, wafer_yld, ap_yld, bi_yld, 
                                ft1_yld, ft2_yld, ft3_yld,ft4_yld, ft5_yld, ft6_yld, ft_yld, period, create_time, 
                                update_time,is_delete, grain_id, upload_id, user_id, wafer_id)
                      values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
        price_sql = '''insert into pwm_cost_grain_price(wafer_price, purchase_price, hb_up, cp_up, rdl_up, bp_up, wafer_amt, 
                                 ap_up, ap_amt, bi_up, bi_amt, ft1_up, ft1_amt, ft2_up, ft2_amt, ft3_up, 
                                 ft3_amt, ft4_up, ft4_amt, ft5_up, ft5_amt, ft6_up, ft6_amt, msp_up, msp_amt, 
                                 ft_amt, ic_up, die_up, ft_up, period, create_time, update_time, 
                                 is_delete, grain_id, upload_id, user_id, wafer_id)
                            values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                             %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
        period = datetime.datetime.now().strftime('%Y-%m')
        close_old_connections()
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                now_ts = datetime.datetime.now()
                # 保存良率数据
                if yield_file_name:
                    yield_upload_obj = UploadRecord.objects.create(user=user, data_type=2, file_path=yield_file_name)
                    yield_upload_id = yield_upload_obj.id
                else:
                    yield_upload_id = None
                yield_count = 0
                yield_ls = []
                for d in yield_data:
                    yield_count += 1
                    grain_id = d.get('grain_id')
                    if not grain_id:
                        return REST_SUCCESS({'msg': '良率数据中料号不能为空, 空值所在行: {}'.format(yield_count)})
                    args = (d.get('hb_yld'), d.get('cp_yld'), d.get('rdl_yld'), d.get('bp_yld'), d.get('wafer_yld'),
                            d.get('ap_yld'), d.get('bi_yld'), d.get('ft1_yld'), d.get('ft2_yld'), d.get('ft3_yld'),
                            d.get('ft4_yld'), d.get('ft5_yld'), d.get('ft6_yld'), d.get('ft_yld'), period,
                            now_ts, now_ts, False, grain_id, yield_upload_id, user.id, d.get('wafer_id'))
                    yield_ls.append(args)
                    if len(yield_ls) >= 50:
                        execute_batch_sql(yield_sql, yield_ls)
                        yield_ls = []
                if len(yield_ls) > 0:
                    execute_batch_sql(yield_sql, yield_ls)
                # 保存测试费数据
                if price_file_name:
                    price_upload_obj = UploadRecord.objects.create(user=user, data_type=3, file_path=price_file_name)
                    price_upload_id = price_upload_obj.id
                else:
                    price_upload_id = None
                price_count = 0
                price_ls = []
                for d in price_data:
                    price_count += 1
                    grain_id = d.get('grain_id')
                    if not grain_id:
                        return REST_SUCCESS({'msg': '测试费数据中料号不能为空, 空值所在行: {}'.format(yield_count)})
                    args = (d.get('wafer_price'), d.get('purchase_price'), d.get('hb_up'), d.get('cp_up'), d.get('rdl_up'),
                            d.get('bp_up'), d.get('wafer_amt'), d.get('ap_up'), d.get('ap_amt'), d.get('bi_up'),
                            d.get('bi_amt'), d.get('ft1_up'), d.get('ft1_amt'), d.get('ft2_up'), d.get('ft2_amt'),
                            d.get('ft3_up'), d.get('ft3_amt'), d.get('ft4_up'), d.get('ft4_amt'), d.get('ft5_up'),
                            d.get('ft5_amt'), d.get('ft6_up'), d.get('ft6_amt'), d.get('msp_up'), d.get('msp_amt'),
                            d.get('ft_amt'), d.get('ic_up'), d.get('die_up'), d.get('ft_up'), period,
                            now_ts, now_ts, False, grain_id, price_upload_id, user.id, d.get('wafer_id'))
                    price_ls.append(args)
                    if len(price_ls) >= 50:
                        execute_batch_sql(price_sql, price_ls)
                        price_ls = []
                if len(price_ls) > 0:
                    execute_batch_sql(price_sql, price_ls)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.error('grain测算数据保存失败, error:{}'.format(str(e)))
                return REST_FAIL({'msg': '数据保存失败', 'error': str(e)})
        return REST_SUCCESS({'msg': '提交成功'})
    except Exception as e:
        logger.error('grain测算数据保存失败, error:{}'.format(str(e)))
        return REST_FAIL({'msg': '数据保存失败', 'error': str(e)})


# 导出颗粒良率
@api_view(['GET'])
def export_grain_yield(request):
    try:
        queryset = GrainYield.objects
        grain_id = request.GET.get('grain', '')
        if grain_id:
            queryset = queryset.filter(grain_id=grain_id)  # 精确查询
        subdivision = request.GET.get('subdivision', '')
        if subdivision:
            queryset = queryset.filter(grain__subdivision=subdivision)
        start_createTime = request.GET.get('start_createTime', '')
        end_createTime = request.GET.get('end_createTime', '')
        if start_createTime and end_createTime:
            queryset = queryset.filter(create_time__range=[start_createTime + ' 00:00:00', end_createTime + ' 23:59:59'])
        qs = queryset.order_by('create_time').values('wafer_id', 'wafer__gross_die', 'grain_id', 'grain__project__name',
                                                     'grain__general', 'grain__subdivision', 'grain__technology',
                                                     'grain__package_mode', 'grain__package_size', 'grain__grade',
                                                     'grain__type', 'grain__sub_con', 'hb_yld', 'cp_yld', 'rdl_yld',
                                                     'bp_yld', 'wafer_yld', 'ap_yld', 'bi_yld', 'ft1_yld', 'ft2_yld',
                                                     'ft3_yld', 'ft4_yld', 'ft5_yld', 'ft6_yld', 'ft_yld', 'create_time')
        blank_path = os.path.dirname(__file__) + '/blank_files/颗粒良率数据.xlsx'
        if not qs:
            return create_excel_resp(blank_path, '颗粒良率数据')
        df = pd.DataFrame(list(qs))
        df[['hb_yld', 'cp_yld', 'rdl_yld', 'bp_yld', 'wafer_yld', 'ap_yld', 'bi_yld', 'ft1_yld', 'ft2_yld',
            'ft3_yld', 'ft4_yld', 'ft5_yld', 'ft6_yld', 'ft_yld']] = \
            df[['hb_yld', 'cp_yld', 'rdl_yld', 'bp_yld', 'wafer_yld', 'ap_yld', 'bi_yld', 'ft1_yld', 'ft2_yld',
                'ft3_yld', 'ft4_yld', 'ft5_yld', 'ft6_yld', 'ft_yld']].astype(float)
        df['create_time'] = df['create_time'].map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
        ndf = df[['wafer_id', 'wafer__gross_die', 'grain_id', 'grain__project__name', 'grain__general',
                  'grain__subdivision', 'grain__technology', 'grain__package_mode', 'grain__package_size', 'grain__grade',
                  'grain__type', 'grain__sub_con', 'hb_yld', 'cp_yld', 'rdl_yld','bp_yld', 'wafer_yld', 'ap_yld',
                  'bi_yld', 'ft1_yld', 'ft2_yld','ft3_yld', 'ft4_yld', 'ft5_yld', 'ft6_yld', 'ft_yld', 'create_time']]
        rename_maps = {
            'wafer_id': 'Wafer 型号',
            'wafer__gross_die': 'Gross die数量',
            'grain_id': 'PN',
            'grain__project__name': '项目',
            'grain__general': '产品大类',
            'grain__subdivision': '产品细分',
            'grain__technology': '工艺',
            'grain__package_mode': 'Package',
            'grain__package_size': 'Package size',
            'grain__grade': 'Grade',
            'grain__type': 'Type',
            'grain__sub_con': 'Sub-con',
            'hb_yld': 'HB YLD',
            'cp_yld': 'CP YLD',
            'rdl_yld': 'RDL YLD',
            'bp_yld': 'BP YLD',
            'wafer_yld': 'TTL Wafer YLD',
            'ap_yld': 'AP YLD',
            'bi_yld': 'BI YLD',
            'ft1_yld': 'FT1 YLD',
            'ft2_yld': 'FT2 YLD',
            'ft3_yld': 'FT3 YLD',
            'ft4_yld': 'FT4 YLD',
            'ft5_yld': 'FT5 YLD',
            'ft6_yld': 'FT6 YLD',
            'ft_yld': 'TTL FT YLD',
            'create_time': '提交日期'
        }
        ndf.rename(rename_maps, axis=1, inplace=True)
        file_path, file_name = get_file_path('yield', 'export_files')
        writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
        workbook = writer.book
        fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'text_wrap': True, 'valign': 'vcenter'})
        center_fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'text_wrap': True,
                                          'valign': 'vcenter', 'align': 'center'})
        right_fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'text_wrap': True,
                                          'valign': 'vcenter', 'align': 'right'})
        border_format = workbook.add_format({'border': 1})
        percent_fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'num_format': '0.00%', 'valign': 'vcenter'})
        title_fmt = workbook.add_format(
            {'bold': True, 'font_size': 10, 'font_name': 'Arial Unicode MS', 'text_wrap': True, 'valign': 'vcenter', 'align': 'center'})
        ndf.to_excel(writer, sheet_name='Sheet1', header=False, index=False, startcol=0, startrow=1)
        worksheet = writer.sheets['Sheet1']
        l_end = len(ndf.index) + 1
        for col_num, value in enumerate(ndf.columns.values):
            worksheet.write(0, col_num, value, title_fmt)
        worksheet.conditional_format('A1:L1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#5b9bd5'})})
        worksheet.conditional_format('M1:P1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#92d050'})})
        worksheet.conditional_format('Q1:Q1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#ffff00'})})
        worksheet.conditional_format('R1:Y1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#5b9bd5'})})
        worksheet.conditional_format('Z1:Z1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#ffff00'})})
        worksheet.conditional_format('AA1:AA1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#5b9bd5'})})
        worksheet.set_column('A:A', 15.5, fmt)
        worksheet.set_column('B:B', 12, fmt)
        worksheet.set_column('C:C', 18, fmt)
        worksheet.set_column('D:D', 15.5, fmt)
        worksheet.set_column('E:H', 10, center_fmt)
        worksheet.set_column('I:I', 11.5, fmt)
        worksheet.set_column('J:L', 9, fmt)
        worksheet.set_column('M:Z', 9, percent_fmt)
        worksheet.set_column('AA:AA', 18, right_fmt)
        worksheet.conditional_format('A1:AA%d' % l_end, {'type': 'blanks', 'format': border_format})
        worksheet.conditional_format('A1:AA%d' % l_end, {'type': 'no_blanks', 'format': border_format})
        writer.save()
        return create_excel_resp(file_path, '颗粒良率数据')
    except Exception as e:
        logger.error('良率导出失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '良率导出失败, error: {}'.format(str(e))})


# 导出颗粒测试费
@api_view(['GET'])
def export_grain_price(request):
    try:
        queryset = GrainUnitPrice.objects
        grain_id = request.GET.get('grain', '')
        if grain_id:
            queryset = queryset.filter(grain_id=grain_id)  # 精确查询
        subdivision = request.GET.get('subdivision', '')
        if subdivision:
            queryset = queryset.filter(grain__subdivision=subdivision)
        start_createTime = request.GET.get('start_createTime', '')
        end_createTime = request.GET.get('end_createTime', '')
        if start_createTime and end_createTime:
            queryset = queryset.filter(create_time__range=[start_createTime + ' 00:00:00', end_createTime + ' 23:59:59'])
        qs = queryset.order_by('create_time').values('wafer_id', 'wafer__gross_die', 'grain_id', 'grain__project__name',
                                                     'grain__general', 'grain__subdivision', 'grain__technology',
                                                     'grain__package_mode', 'grain__package_size', 'grain__grade',
                                                     'grain__type', 'grain__sub_con', 'wafer_price', 'purchase_price', 'hb_up', 'cp_up',
                                                     'rdl_up', 'bp_up', 'wafer_amt', 'ap_up', 'ap_amt', 'bi_up', 'bi_amt',
                                                     'ft1_up', 'ft1_amt', 'ft2_up', 'ft2_amt', 'ft3_up', 'ft3_amt',
                                                     'ft4_up', 'ft4_amt', 'ft5_up', 'ft5_amt', 'ft6_up', 'ft6_amt',
                                                     'msp_up', 'msp_amt', 'ft_amt', 'ic_up', 'die_up', 'ft_up', 'create_time')
        blank_path = os.path.dirname(__file__) + '/blank_files/颗粒测试费数据.xlsx'
        if not qs:
            return create_excel_resp(blank_path, '颗粒测试费数据')
        df = pd.DataFrame(list(qs))
        df[['wafer_price', 'purchase_price', 'hb_up', 'cp_up', 'rdl_up', 'bp_up', 'wafer_amt', 'ap_up', 'ap_amt', 'bi_up', 'bi_amt',
            'ft1_up', 'ft1_amt', 'ft2_up', 'ft2_amt', 'ft3_up', 'ft3_amt', 'ft4_up', 'ft4_amt', 'ft5_up', 'ft5_amt',
            'ft6_up', 'ft6_amt','msp_up', 'msp_amt', 'ft_amt', 'ic_up', 'die_up', 'ft_up']] = \
            df[['wafer_price', 'purchase_price', 'hb_up', 'cp_up', 'rdl_up', 'bp_up', 'wafer_amt', 'ap_up', 'ap_amt', 'bi_up', 'bi_amt',
               'ft1_up', 'ft1_amt', 'ft2_up', 'ft2_amt', 'ft3_up', 'ft3_amt', 'ft4_up', 'ft4_amt', 'ft5_up', 'ft5_amt',
               'ft6_up', 'ft6_amt','msp_up', 'msp_amt', 'ft_amt', 'ic_up', 'die_up', 'ft_up']].astype(float)
        df['create_time'] = df['create_time'].map(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
        ndf = df[['wafer_id', 'wafer__gross_die', 'grain_id', 'grain__project__name', 'grain__general', 'grain__subdivision',
                  'grain__technology', 'grain__package_mode', 'grain__package_size', 'grain__grade', 'grain__type',
                  'grain__sub_con', 'wafer_price', 'purchase_price', 'hb_up', 'cp_up', 'rdl_up', 'bp_up', 'wafer_amt', 'ap_up', 'ap_amt',
                  'bi_up', 'bi_amt', 'ft1_up', 'ft1_amt', 'ft2_up', 'ft2_amt', 'ft3_up', 'ft3_amt', 'ft4_up', 'ft4_amt',
                  'ft5_up', 'ft5_amt', 'ft6_up', 'ft6_amt', 'msp_up', 'msp_amt', 'ft_amt', 'ic_up', 'die_up', 'ft_up', 'create_time']]
        rename_maps = {
            'wafer_id': 'Wafer 型号',
            'wafer__gross_die': 'Gross die数量',
            'grain_id': 'PN',
            'grain__project__name': '项目',
            'grain__general': '产品大类',
            'grain__subdivision': '产品细分',
            'grain__technology': '工艺',
            'grain__package_mode': 'Package',
            'grain__package_size': 'Package size',
            'grain__grade': 'Grade',
            'grain__type': 'Type',
            'grain__sub_con': 'Sub-con',
            'wafer_price': 'Wafer U/P',
            'purchase_price': '采购单价',
            'hb_up': 'HB U/P',
            'cp_up': 'CP U/P',
            'rdl_up': 'RDL U/P',
            'bp_up': 'BP U/P',
            'wafer_amt': 'TTL Wafer 加工费',
            'ap_up': 'AP U/P',
            'ap_amt': 'AP AMT',
            'bi_up': 'BI U/P',
            'bi_amt': 'BI AMT',
            'ft1_up': 'FT1 U/P',
            'ft1_amt': 'FT1 AMT',
            'ft2_up': 'FT2 U/P',
            'ft2_amt': 'FT2 AMT',
            'ft3_up': 'FT3 U/P',
            'ft3_amt': 'FT3 AMT',
            'ft4_up': 'FT4 U/P',
            'ft4_amt': 'FT4 AMT',
            'ft5_up': 'FT5 U/P',
            'ft5_amt': 'FT5 AMT',
            'ft6_up': 'FT6 U/P',
            'ft6_amt': 'FT6 AMT',
            'msp_up': 'MSP U/P',
            'msp_amt': 'MSP AMT',
            'ft_amt': 'TTL FT 加工费',
            'ic_up': 'IC U/P',
            'die_up': 'Die U/P',
            'ft_up ': 'FT U/P',
            'create_time': '提交日期'
        }
        ndf.rename(rename_maps, axis=1, inplace=True)
        file_path, file_name = get_file_path('price', 'export_files')
        writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
        workbook = writer.book
        fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'text_wrap': True, 'valign': 'vcenter'})
        center_fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'text_wrap': True,
                                          'valign': 'vcenter', 'align': 'center'})
        right_fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'text_wrap': True,
                                          'valign': 'vcenter', 'align': 'right'})
        border_format = workbook.add_format({'border': 1})
        float_fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'num_format': '#,##0.00', 'valign': 'vcenter'})
        percent_fmt = workbook.add_format({'font_size': 10, 'font_name': 'Arial Unicode MS', 'num_format': '0.00%', 'valign': 'vcenter'})
        title_fmt = workbook.add_format(
            {'bold': True, 'font_size': 10, 'font_name': 'Arial Unicode MS', 'text_wrap': True, 'valign': 'vcenter', 'align': 'center'})
        ndf.to_excel(writer, sheet_name='Sheet1', header=False, index=False, startcol=0, startrow=1)
        worksheet = writer.sheets['Sheet1']
        l_end = len(ndf.index) + 1
        for col_num, value in enumerate(ndf.columns.values):
            worksheet.write(0, col_num, value, title_fmt)
        worksheet.conditional_format('A1:L1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#5b9bd5'})})
        worksheet.conditional_format('M1:N1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#ffff00'})})
        worksheet.conditional_format('O1:R1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#92d050'})})
        worksheet.conditional_format('S1:S1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#ffff00'})})
        worksheet.conditional_format('T1:AK1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#5b9bd5'})})
        worksheet.conditional_format('AL1:AO1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#ffff00'})})
        worksheet.conditional_format('AP1:AP1', {'type': 'no_blanks', 'format': workbook.add_format({'bg_color': '#5b9bd5'})})
        worksheet.set_column('A:A', 15.5, fmt)
        worksheet.set_column('B:B', 12, fmt)
        worksheet.set_column('C:C', 18, fmt)
        worksheet.set_column('D:D', 15.5, fmt)
        worksheet.set_column('E:H', 10, center_fmt)
        worksheet.set_column('I:I', 11.5, fmt)
        worksheet.set_column('J:L', 9, fmt)
        worksheet.set_column('M:AO', 9, float_fmt)
        worksheet.set_column('AP:AP', 18, right_fmt)
        worksheet.conditional_format('A1:AP%d' % l_end, {'type': 'blanks', 'format': border_format})
        worksheet.conditional_format('A1:AP%d' % l_end, {'type': 'no_blanks', 'format': border_format})
        writer.save()
        return create_excel_resp(file_path, '颗粒测试费数据')
    except Exception as e:
        logger.error('测试费导出失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '测试费导出失败, error: {}'.format(str(e))})


# 查询拥有成本测算系统的用户
@api_view(['GET'])
def query_system_user(request):
    qs = User.objects.all().filter(role__belong_sys='pwm').values('id', 'username')
    user_ls = []
    if qs:
        user_ls = [{'value': item['id'], 'label': item['username']} for item in list(qs)]
    return REST_SUCCESS(user_ls)


# 下载上传的测试数据原文件
@api_view(['GET'])
def download_source_file(request):
    file_name = request.GET.get('file_path')
    current_path = os.path.dirname(__file__)
    file_dir = os.path.join(current_path, 'upload_files')
    whole_path = os.path.join(file_dir, file_name)
    return create_excel_resp(whole_path, file_name)


@api_view(['GET'])
def get_data(request):
    # res_data = [{'grain_id': 'SCKU4BL256160AAA1', 'hb_yld': '84.48%', 'cp_yld': '84.56%', 'rdl_yld': '66.99%', 'bp_yld': '96.76%', 'ap_yld': '90.04%', 'bi_yld': '82.5%', 'ft1_yld': '69.76%', 'ft2_yld': '77.91%', 'ft3_yld': '73.1%', 'ft4_yld': '86.45%', 'ft5_yld': '92.22%', 'ft6_yld': '82.5%', 'wafer_yld': '46.3%', 'ft_yld': '19.41%', 'wafer_id': '256M LP38', 'has_bom': False}, {'grain_id': 'B PN', 'hb_yld': '85.34%', 'cp_yld': '88.68%', 'rdl_yld': '76.25%', 'bp_yld': '82.37%', 'ap_yld': '85.86%', 'bi_yld': '87.88%', 'ft1_yld': '79.84%', 'ft2_yld': '75.88%', 'ft3_yld': '83.11%', 'ft4_yld': '88.63%', 'ft5_yld': '89.52%', 'ft6_yld': '86.28%', 'wafer_yld': '47.53%', 'ft_yld': '26.01%', 'wafer_id': '2G D3', 'has_bom': False}, {'grain_id': 'MCP PN', 'hb_yld': '100.0%', 'cp_yld': '100.0%', 'rdl_yld': '100.0%', 'bp_yld': '100.0%', 'ap_yld': '89.63%', 'bi_yld': '82.33%', 'ft1_yld': '81.56%', 'ft2_yld': '82.55%', 'ft3_yld': '79.72%', 'ft4_yld': '83.49%', 'ft5_yld': '88.41%', 'ft6_yld': '89.67%', 'wafer_yld': '100.0%', 'ft_yld': '26.22%', 'wafer_id': None, 'has_bom': True}]
    yield_data = [{'grain_id': 'SCKU4BL256160AAA1', 'hb_yld': 0.8448, 'cp_yld': 0.8456, 'rdl_yld': 0.6699, 'bp_yld': 0.9676, 'ap_yld': 0.9004, 'bi_yld': 0.825, 'ft1_yld': 0.6976, 'ft2_yld': 0.7791, 'ft3_yld': 0.731, 'ft4_yld': 0.8645, 'ft5_yld': 0.9222, 'ft6_yld': 0.825, 'wafer_yld': 0.463, 'ft_yld': 0.1941, 'wafer_id': '256M LP38', 'has_bom': False}, {'grain_id': 'B PN', 'hb_yld': 0.8534, 'cp_yld': 0.8868, 'rdl_yld': 0.7625, 'bp_yld': 0.8237, 'ap_yld': 0.8586, 'bi_yld': 0.8788, 'ft1_yld': 0.7984, 'ft2_yld': 0.7588, 'ft3_yld': 0.8311, 'ft4_yld': 0.8863, 'ft5_yld': 0.8952, 'ft6_yld': 0.8628, 'wafer_yld': 0.4753, 'ft_yld': 0.2601, 'wafer_id': '2G D3', 'has_bom': False}, {'grain_id': 'MCP PN', 'hb_yld': 1.0, 'cp_yld': 1.0, 'rdl_yld': 1.0, 'bp_yld': 1.0, 'ap_yld': 0.8963, 'bi_yld': 0.8233, 'ft1_yld': 0.8156, 'ft2_yld': 0.8255, 'ft3_yld': 0.7972, 'ft4_yld': 0.8349, 'ft5_yld': 0.8841, 'ft6_yld': 0.8967, 'wafer_yld': 1.0, 'ft_yld': 0.2622, 'wafer_id': None, 'has_bom': True}]
    price_data = [{'grain_id': 'SCKU4BL256160AAA1', 'hb_up': 1.72, 'cp_up': 1.59, 'rdl_up': 1.65, 'bp_up': 2.08, 'ap_up': 1.53, 'bi_up': 1.33, 'ft1_up': 1.39, 'ft2_up': 2.99, 'ft3_up': 1.66, 'ft4_up': 2.18, 'ft5_up': 2.95, 'ft6_up': 1.78, 'msp_up': 3.26, 'wafer_id': '256M LP38', 'gross_die': 8945.0, 'has_bom': False, 'purchase_price': 2.18, 'wafer_yld': 0.463, 'ft_yld': 0.1941, 'ap_yld': 0.9004, 'bi_yld': 0.825, 'ft1_yld': 0.6976, 'ft2_yld': 0.7791, 'ft3_yld': 0.731, 'ft4_yld': 0.8645, 'ft5_yld': 0.9222, 'ft6_yld': 0.825, 'wafer_amt': 7.04, 'ap_amt': 6336.549, 'bi_amt': 4959.621, 'ft1_amt': 4276.274, 'ft2_amt': 6416.947, 'ft3_amt': 2775.611, 'ft4_amt': 2664.553, 'ft5_amt': 3117.129, 'ft6_amt': 1734.515, 'msp_amt': 2620.623, 'ft_amt': 34904.002, 'ic_up': 43.429, 'die_up': 0.009, 'ft_up': 43.42}, {'grain_id': 'B PN', 'hb_up': 1.65, 'cp_up': 2.99, 'rdl_up': 4.18, 'bp_up': 2.32, 'ap_up': 1.33, 'bi_up': 1.62, 'ft1_up': 2.15, 'ft2_up': 1.69, 'ft3_up': 1.4, 'ft4_up': 1.84, 'ft5_up': 2.02, 'ft6_up': 1.9, 'msp_up': 1.86, 'wafer_id': '2G D3', 'gross_die': 1580.0, 'has_bom': False, 'purchase_price': 1.51, 'wafer_yld': 0.4753, 'ft_yld': 0.2601, 'ap_yld': 0.8586, 'bi_yld': 0.8788, 'ft1_yld': 0.7984, 'ft2_yld': 0.7588, 'ft3_yld': 0.8311, 'ft4_yld': 0.8863, 'ft5_yld': 0.8952, 'ft6_yld': 0.8628, 'wafer_amt': 11.14, 'ap_amt': 998.795, 'bi_amt': 1044.554, 'ft1_amt': 1218.272, 'ft2_amt': 764.563, 'ft3_amt': 480.598, 'ft4_amt': 524.958, 'ft5_amt': 510.786, 'ft6_amt': 430.092, 'msp_amt': 363.311, 'ft_amt': 6337.438999999999, 'ic_up': 32.502, 'die_up': 0.057, 'ft_up': 32.445}, {'grain_id': 'MCP PN', 'hb_up': 0.0, 'cp_up': 0.0, 'rdl_up': 0.0, 'bp_up': 0.0, 'ap_up': 1.87, 'bi_up': 2.08, 'ft1_up': 1.59, 'ft2_up': 1.73, 'ft3_up': 3.26, 'ft4_up': 2.08, 'ft5_up': 1.39, 'ft6_up': 1.57, 'msp_up': 2.95, 'wafer_id': None, 'gross_die': 1.0, 'has_bom': True, 'purchase_price': 108.433, 'wafer_yld': 1.0, 'ft_yld': 0.2622, 'ap_yld': 0.8963, 'bi_yld': 0.8233, 'ft1_yld': 0.8156, 'ft2_yld': 0.8255, 'ft3_yld': 0.7972, 'ft4_yld': 0.8349, 'ft5_yld': 0.8841, 'ft6_yld': 0.8967, 'wafer_amt': 0.0, 'ap_amt': 1.87, 'bi_amt': 1.864, 'ft1_amt': 1.173, 'ft2_amt': 1.041, 'ft3_amt': 1.62, 'ft4_amt': 0.824, 'ft5_amt': 0.46, 'ft6_amt': 0.459, 'msp_amt': 0.773, 'ft_amt': 118.51700000000001, 'ic_up': 452.01, 'die_up': 0.0, 'ft_up': 452.01}]
    res_data = {'yield_data': yield_data, 'price_data': price_data}
    return REST_SUCCESS(data=res_data)
