from rest_framework import serializers, validators
from django.db import connection, close_old_connections, transaction

from equipments.models import Project, Equipment, EquipmentDepreciationRecord, ExtendAttribute
from equipments.models import EquipmentBorrowRecord, EquipmentReturnRecord, EquipmentBrokenInfo, \
    EquipmentCalibrationInfo, EquipmentMaintenanceRecord

import logging

logger = logging.getLogger('django')


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ('id', 'name')
        extra_kwargs = {
            'name': {
                'validators': [validators.UniqueValidator(queryset=Project.objects.all(), message='该名称已存在')],
                'error_messages': {
                    'blank': '项目名称[name]不能为空',
                    'required': '项目名称[name]为必填项'
                }
            }
        }


class ExtendAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtendAttribute
        fields = ('attribute_name', 'attribute_value')


class EquipmentSerializer(serializers.ModelSerializer):
    extendattribute_set = ExtendAttributeSerializer(label='扩展属性', many=True, required=False)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # data.update(equipment_state=instance.get_equipment_state_display())
        # data.update(fixed_asset_category=instance.get_fixed_asset_category_display())
        return data

    class Meta:
        model = Equipment
        # fields = '__all__'
        fields = ('id', 'name', 'number', 'serial_number', 'fixed_asset_code', 'fixed_asset_category', 'custodian',
                  'equipment_state', 'service_type', 'specification', 'performance', 'assort_material',
                  'allow_borrow_days', 'per_hour_price', 'deposit_position', 'install_date', 'manage_type', 'manager',
                  'application_specialist', 'manufacturer', 'manufacture_date', 'origin_place',
                  'user_manual', 'license', 'extendattribute_set', 'is_delete', 'create_time')
        extra_kwargs = {
            'id': {
                'label': '设备仪器ID',
                'required': True,
                'validators': [validators.UniqueValidator(queryset=Equipment.objects.all(), message='该设备仪器ID已存在')],
                'error_messages': {
                    'blank': '设备仪器ID[id]不能为空',
                    'required': '设备仪器ID[id]为必填项'
                }
            },
            'name': {
                'error_messages': {
                    'blank': '设备名称[name]不能为空',
                    'required': '设备名称[name]为必填项'
                }
            }
        }

    def create(self, validated_data):
        extendattribute_set = validated_data.pop('extendattribute_set', [])
        equipment = Equipment.objects.create(**validated_data)
        if extendattribute_set:
            with transaction.atomic():
                save_id = transaction.savepoint()
                try:
                    for _fields in extendattribute_set:
                        attribute_name = _fields['attribute_name']
                        attribute_value = _fields['attribute_value']
                        ExtendAttribute.objects.create(equipment=equipment,
                                                       attribute_name=attribute_name,
                                                       attribute_value=attribute_value)
                    transaction.savepoint_commit(save_id)
                except Exception as e:
                    transaction.savepoint_rollback(save_id)
                    logger.error('扩展属性存储失败,error:{}'.format(str(e)))
                    raise serializers.ValidationError('扩展属性存储失败')
        return equipment


class DepreciationSerializer(serializers.ModelSerializer):

    class Meta:
        model = EquipmentDepreciationRecord
        fields = ('id', 'equipment', 'equipment_name', 'method', 'periods', 'depreciated_total', 'net_value',
                  'net_amount', 'depreciate_date', 'create_time')
        extra_kwargs = {
            'method': {
                'error_messages': {
                    'blank': '折旧方法[method]不能为空',
                    'required': '折旧方法[method]为必填项'
                }
            },
            'periods': {
                'error_messages': {
                    'blank': '已折旧期间数[periods]不能为空',
                    'required': '已折旧期间数[periods]为必填项'
                }
            },
            'depreciated_total': {
                'error_messages': {
                    'blank': '累计折旧值[depreciated_total]不能为空',
                    'required': '累计折旧值[depreciated_total]为必填项'
                }
            },
            'net_value': {
                'error_messages': {
                    'blank': '净值[net_value]不能为空',
                    'required': '净值[net_value为必填项'
                }
            },
            'net_amount': {
                'error_messages': {
                    'blank': '净额[net_amount]不能为空',
                    'required': '净额[net_amount]为必填项'
                }
            },
            'depreciate_date': {
                'error_messages': {
                    'blank': '折旧日期[depreciate_date]不能为空',
                    'required': '折旧日期[depreciate_date]为必填项'
                }
            }
        }


class ReturnApplySerializer(serializers.ModelSerializer):
    borrow_record_id = serializers.IntegerField(label='借用记录ID', required=True,
                                                validators=[validators.UniqueValidator(queryset=EquipmentReturnRecord.objects.all(),
                                                          message='该条借用记录已申请归还，无需再申请')],
                                                error_messages={
                                                    'blank': '借用记录ID[borrow_record_id]不能为空',
                                                    'required': '借用记录ID[borrow_record_id]为必填项'})
    is_confirm = serializers.ReadOnlyField()
    confirm_state = serializers.ReadOnlyField()
    remarks = serializers.ReadOnlyField()
    is_interrupted = serializers.BooleanField(label='借用是否被中断', source='borrow_record.is_interrupted', required=False)
    user = serializers.IntegerField(label='申请人', source='borrow_record.user.id', read_only=True)

    class Meta:
        model = EquipmentReturnRecord
        # TODO 后面正式环境申请归还时，return_time为只读，已提交时间为准
        fields = ('id', 'borrow_record_id', 'user', 'user_name', 'section_name', 'project_name', 'equipment', 'equipment_name',
                  'return_time', 'return_position', 'is_interrupted', 'is_confirm', 'confirm_state', 'remarks')
        extra_kwargs = {
            'borrow_record_id ': {
                'label': '借用记录ID',
                'help_text': '借用记录ID',
                'required': True,
                # 归还记录重复验证
                'validators': [validators.UniqueValidator(queryset=EquipmentReturnRecord.objects.all(),
                                                          message='该条借用记录已申请归还，无需再申请')],
                'error_messages': {
                    'blank': '借用记录ID[borrow_record_id]不能为空',
                    'required': '借用记录ID[borrow_record_id]为必填项'
                }
            },
        }

    def create(self, validated_data):
        borrow_record_id = validated_data.get('borrow_record_id')
        borrow_record = validated_data.pop('borrow_record', {})
        return_record = EquipmentReturnRecord.objects.create(**validated_data)
        is_interrupted = borrow_record.get('is_interrupted', False)
        if is_interrupted is True:
            EquipmentBorrowRecord.objects.filter(id=borrow_record_id).update(is_interrupted=is_interrupted)
        return return_record


class OperateReturnApplySerializer(serializers.ModelSerializer):
    borrow_record_id = serializers.ReadOnlyField()
    is_confirm = serializers.ReadOnlyField()
    is_interrupted = serializers.BooleanField(label='借用是否被中断', source='borrow_record.is_interrupted', required=False)
    user = serializers.IntegerField(label='申请人', source='borrow_record.user.id', read_only=True)

    class Meta:
        model = EquipmentReturnRecord
        fields = ('id', 'borrow_record_id', 'user', 'user_name', 'section_name', 'project_name', 'equipment', 'equipment_name',
                  'return_time', 'return_position', 'is_interrupted', 'is_confirm', 'confirm_state', 'remarks')


class BorrowRecordSerializer(serializers.ModelSerializer):
    is_approval = serializers.ReadOnlyField()
    refuse_reason = serializers.ReadOnlyField()
    is_borrow = serializers.ReadOnlyField()
    remarks = serializers.ReadOnlyField()
    is_return = serializers.ReadOnlyField()
    actual_end_time = serializers.ReadOnlyField()
    expect_usage_time = serializers.ReadOnlyField()
    actual_usage_time = serializers.ReadOnlyField()
    is_interrupted = serializers.ReadOnlyField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(borrow_type=instance.get_borrow_type_display())
        return data

    class Meta:
        model = EquipmentBorrowRecord
        fields = ('id', 'user', 'user_name', 'section_name', 'project', 'project_name', 'equipment', 'equipment_name',
                  'borrow_type', 'start_time', 'end_time', 'expect_usage_time', 'is_approval', 'refuse_reason', 'is_borrow',
                  'is_return', 'is_interrupted', 'actual_end_time', 'actual_usage_time', 'remarks',
                  'return_confirm_state', 'return_position')

        extra_kwargs = {
            'user': {
                'read_only': True
            },
            'project': {
                'error_messages': {
                    'blank': '项目[project]不能为空',
                    'required': '项目[project]为必填项'
                }
            },
            'equipment': {
                'error_messages': {
                    'blank': '设备[equipment]不能为空',
                    'required': '设备[equipment]为必填项'
                }
            },
            'start_time': {
                'error_messages': {
                    'blank': '借用开始时间[start_time]不能为空',
                    'required': '借用开始时间[start_time]为必填项'
                }
            },
            'end_time': {
                'error_messages': {
                    'blank': '借用结束时间[end_time]不能为空',
                    'required': '借用结束时间[end_time]为必填项'
                }
            }
        }


class OperateBorrowRecordSerializer(serializers.ModelSerializer):
    expect_usage_time = serializers.ReadOnlyField()
    is_interrupted = serializers.ReadOnlyField()
    borrow_type = serializers.ReadOnlyField()

    class Meta:
        model = EquipmentBorrowRecord
        fields = ('id', 'user_name', 'section_name', 'project', 'project_name', 'equipment', 'equipment_name', 'borrow_type',
                  'start_time', 'end_time', 'expect_usage_time', 'is_approval', 'refuse_reason', 'is_borrow',
                  'is_return', 'is_interrupted', 'actual_end_time', 'actual_usage_time', 'remarks',
                  'return_confirm_state', 'return_position')
        extra_kwargs = {
            'project': {
                'read_only': True,
            },
            'equipment': {
                'read_only': True,
            },
        }


class BrokenInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentBrokenInfo
        fields = ('id', 'user', 'user_name', 'section_name', 'equipment', 'equipment_name', 'broken_time', 'broken_reason',
                  'image_path', 'evaluation_result', 'maintenance_plan', 'is_maintenance', 'remarks')


class OperateBrokenInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentBrokenInfo
        fields = ('id', 'user', 'user_name', 'section_name', 'equipment', 'equipment_name', 'broken_time',
                  'broken_reason', 'image_path', 'evaluation_result', 'maintenance_plan', 'is_maintenance', 'remarks')
        extra_kwargs = {
            'user': {
                'read_only': True
            },
            'equipment': {
                'read_only': True
            }
        }


class CalibrationInfoSerializer(serializers.ModelSerializer):
    due_date = serializers.ReadOnlyField()

    class Meta:
        model = EquipmentCalibrationInfo
        fields = ('id', 'equipment', 'equipment_name', 'calibration_time', 'recalibration_time', 'due_date',
                  'certificate', 'certificate_year', 'state', 'remarks')
        extra_kwargs = {
            'equipment': {
                'label': '设备',
                'required': True,
                'validators': [validators.UniqueValidator(queryset=EquipmentCalibrationInfo.objects.all(),
                                                          message='该设备已存在校验信息')],
                'error_messages': {
                    'blank': '设备[equipment]不能为空',
                    'required': '设备[equipment]为必填项'
                }
            }
        }


class OperateCalibrationSerializer(serializers.ModelSerializer):
    due_date = serializers.ReadOnlyField()

    class Meta:
        model = EquipmentCalibrationInfo
        fields = ('id', 'equipment', 'equipment_name', 'calibration_time', 'recalibration_time', 'due_date',
                  'certificate', 'certificate_year', 'state', 'remarks')
        extra_kwargs = {
            'equipment': {
                'read_only': True
            }
        }


class MaintenanceSerializer(serializers.ModelSerializer):
    create_time = serializers.ReadOnlyField()

    class Meta:
        model = EquipmentMaintenanceRecord
        fields = ('id', 'user', 'user_name', 'equipment', 'equipment_name', 'fault_description', 'reason_measure',
                  'down_time', 'up_time', 'maintenance_hours', 'maintenance_user', 'remarks', 'create_time')


class OperateMaintenanceSerializer(serializers.ModelSerializer):
    maintenance_user = serializers.ReadOnlyField()

    class Meta:
        model = EquipmentMaintenanceRecord
        fields = ('id', 'user', 'user_name', 'equipment', 'equipment_name', 'fault_description', 'reason_measure',
                  'down_time', 'up_time', 'maintenance_hours', 'maintenance_user', 'remarks')
        extra_kwargs = {
            'user': {
                'read_only': True
            },
            'equipment': {
                'read_only': True
            }
        }
