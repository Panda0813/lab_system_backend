from rest_framework import serializers, validators
from django.db import transaction

from pwm_cost.models import WaferInfo, WaferBom, GrainInfo, GrainBom, WaferPrice, UploadRecord, GrainYield, \
    GrainUnitPrice

import logging

logger = logging.getLogger('django')


class WaferBomSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaferBom
        fields = ('id', 'wafer_source', 'count', 'remarks')


class WaferInfoSerializer(serializers.ModelSerializer):
    belong_wafer = WaferBomSerializer(label='bom详情', many=True, required=False)

    class Meta:
        model = WaferInfo
        fields = ('id', 'project', 'project_name', 'general', 'subdivision', 'technology', 'gross_die', 'has_bom',
                  'remarks', 'create_time', 'belong_wafer')

    def create(self, validated_data):
        belong_wafer = validated_data.pop('belong_wafer', [])
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                wafer = WaferInfo.objects.create(**validated_data)
                if belong_wafer:
                    for _fields in belong_wafer:
                        wafer_source = _fields['wafer_source']
                        count = _fields['count']
                        remarks = _fields['remarks']
                        WaferBom.objects.create(belong_wafer=wafer, wafer_source=wafer_source,
                                                count=count, remarks=remarks)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.error('wafer信息新增失败,error:{}'.format(str(e)))
                raise serializers.ValidationError('wafer信息新增失败')
        return wafer

    def update(self, instance, validated_data):
        has_bom = validated_data.get('has_bom')
        belong_wafer = validated_data.pop('belong_wafer', [])
        new_source_id = []
        if belong_wafer:
            new_source_id = [item['wafer_source'].id for item in belong_wafer]
        old_source = instance.belong_wafer.values('id', 'wafer_source_id')
        old_source_id = []
        if old_source:
            old_source_id = [item['wafer_source_id'] for item in list(old_source)]
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                if has_bom == False:
                    instance.belong_wafer.all().delete()
                else:
                    if list(set(old_source_id) ^ set(new_source_id)):
                        instance.belong_wafer.all().delete()
                        for _fields in belong_wafer:
                            wafer_source = _fields['wafer_source']
                            count = _fields['count']
                            remarks = _fields['remarks']
                            WaferBom.objects.create(belong_wafer=instance, wafer_source=wafer_source,
                                                    count=count, remarks=remarks)
                    else:
                        for _fields in belong_wafer:
                            wafer_source = _fields['wafer_source']
                            count = _fields['count']
                            remarks = _fields['remarks']
                            WaferBom.objects.filter(belong_wafer=instance, wafer_source=wafer_source).\
                                update(count=count, remarks=remarks)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.error('wafer信息更新失败,error:{}'.format(str(e)))
                raise serializers.ValidationError('wafer信息更新失败')
        return super(WaferInfoSerializer, self).update(instance, validated_data)


class GrainBomSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrainBom
        fields = ('id', 'grain_source', 'count', 'remarks')


class GrainInfoSerializer(serializers.ModelSerializer):
    belong_grain = GrainBomSerializer(label='bom详情', many=True, required=False)

    class Meta:
        model = GrainInfo
        fields = ('id', 'wafer', 'project', 'project_name', 'gross_die', 'general', 'subdivision', 'technology', 'package_mode',
                  'package_size', 'grade', 'type', 'sub_con', 'has_bom', 'remarks', 'create_time', 'belong_grain')

    def create(self, validated_data):
        belong_grain = validated_data.pop('belong_grain', [])
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                grain = GrainInfo.objects.create(**validated_data)
                if belong_grain:
                    for _fields in belong_grain:
                        grain_source = _fields['grain_source']
                        count = _fields['count']
                        remarks = _fields['remarks']
                        GrainBom.objects.create(belong_grain=grain, grain_source=grain_source,
                                                count=count, remarks=remarks)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.error('grain信息新增失败,error:{}'.format(str(e)))
                raise serializers.ValidationError('grain信息新增失败')
        return grain

    def update(self, instance, validated_data):
        has_bom = validated_data.get('has_bom')
        belong_grain = validated_data.pop('belong_grain', [])
        new_source_id = []
        if belong_grain:
            new_source_id = [item['grain_source'].id for item in belong_grain]
        old_source = instance.belong_grain.values('id', 'grain_source_id')
        old_source_id = []
        if old_source:
            old_source_id = [item['grain_source_id'] for item in list(old_source)]
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                if has_bom == False:
                    instance.belong_grain.all().delete()
                else:
                    if list(set(old_source_id) ^ set(new_source_id)):
                        instance.belong_grain.all().delete()
                        for _fields in belong_grain:
                            grain_source = _fields['grain_source']
                            count = _fields['count']
                            remarks = _fields['remarks']
                            GrainBom.objects.create(belong_grain=instance, grain_source=grain_source,
                                                    count=count, remarks=remarks)
                    else:
                        for _fields in belong_grain:
                            grain_source = _fields['grain_source']
                            count = _fields['count']
                            remarks = _fields['remarks']
                            GrainBom.objects.filter(belong_grain=instance, grain_source=grain_source).\
                                update(count=count, remarks=remarks)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.error('grain信息更新失败,error:{}'.format(str(e)))
                raise serializers.ValidationError('grain信息更新失败')
        return super(GrainInfoSerializer, self).update(instance, validated_data)


class UploadRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadRecord
        fields = ('id', 'user', 'user_name', 'data_type', 'file_path', 'create_time')


class WaferPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaferPrice
        fields = ('id', 'wafer_id', 'upload_id', 'user_id', 'user_name', 'price_source', 'supplier', 'purchase_price', 'order_date',
                  'wafer_price', 'create_time', 'remarks', 'project_name', 'general', 'subdivision', 'technology', 'gross_die')


class GrainYieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrainYield
        fields = ('id', 'grain_id', 'wafer_id', 'upload_id', 'user_id', 'user_name', 'hb_yld', 'cp_yld', 'rdl_yld',
                  'bp_yld', 'wafer_yld', 'ap_yld', 'bi_yld', 'ft1_yld', 'ft2_yld', 'ft3_yld', 'ft4_yld', 'ft5_yld',
                  'ft6_yld', 'ft_yld', 'create_time', 'remarks', 'subdivision')


class GrainPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrainUnitPrice
        fields = ('id', 'grain_id', 'wafer_id', 'upload_id', 'user_id', 'user_name', 'wafer_price', 'purchase_price', 'hb_up', 'cp_up',
                  'rdl_up', 'bp_up', 'wafer_amt', 'ap_up', 'ap_amt', 'bi_up', 'bi_amt', 'ft1_up', 'ft1_amt', 'ft2_up',
                  'ft2_amt', 'ft3_up', 'ft3_amt', 'ft4_up', 'ft4_amt', 'ft5_up', 'ft5_amt', 'ft6_up', 'ft6_amt',
                  'msp_up', 'msp_amt', 'ft_amt', 'ic_up', 'die_up', 'ft_up', 'create_time', 'remarks', 'subdivision')

