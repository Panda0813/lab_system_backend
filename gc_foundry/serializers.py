from rest_framework import serializers, validators

from gc_foundry.models import Currency, Factory, MachineModel, FoundryEquipment, FoundryTooling, FoundryTransfer

import logging

logger = logging.getLogger('django')


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ('id', 'name', 'short_name', 'exchange_rate', 'opt_group')
        extra_kwargs = {
            'name': {
                'validators': [validators.UniqueValidator(queryset=Currency.objects.all(), message='该货币名称已存在')],
                'error_messages': {
                    'blank': '货币名称[name]不能为空',
                    'required': '货币名称[name]为必填项'
                }
            }
        }


class FactorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Factory
        fields = ('id', 'name', 'is_active')
        extra_kwargs = {
            'name': {
                'validators': [validators.UniqueValidator(queryset=Factory.objects.all(), message='该工厂名称已存在')],
                'error_messages': {
                    'blank': '工厂名称[name]不能为空',
                    'required': '工厂名称[name]为必填项'
                }
            }
        }


class MachineModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineModel
        fields = ('id', 'name', 'is_active')
        extra_kwargs = {
            'name': {
                'validators': [validators.UniqueValidator(queryset=Factory.objects.all(), message='该机台型号已存在')],
                'error_messages': {
                    'blank': '机台型号[name]不能为空',
                    'required': '机台型号[name]为必填项'
                }
            }
        }


class FoundryEquipmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = FoundryEquipment
        fields = ('id', 'name', 'purchase_order_no', 'supplier', 'category', 'is_fixed_asset', 'project', 'project_name',
                  'number', 'unit', 'price', 'currency', 'currency_name', 'currency_exchange_rate', 'total_amount',
                  'base_total_amount', 'factory', 'factory_name', 'specification', 'serial_number', 'fixed_asset_code',
                  'assort_material', 'custodian', 'image_path', 'image_ls', 'remarks')
        extra_kwargs = {
            'currency': {
                'error_messages': {
                    'blank': '币种[currency]不能为空',
                    'required': '币种[currency]为必填项'
                }
            }
        }


class FoundryToolingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoundryTooling
        fields = ('id', 'name', 'purchase_order_no', 'supplier', 'category', 'is_fixed_asset', 'project', 'project_name',
                  'number', 'unit', 'price', 'currency', 'currency_name', 'currency_exchange_rate', 'total_amount',
                  'base_total_amount', 'factory', 'factory_name', 'specification', 'serial_number', 'fixed_asset_code',
                  'used_machine', 'custodian', 'image_path', 'image_ls', 'remarks')
        extra_kwargs = {
            'currency': {
                'error_messages': {
                    'blank': '币种[currency]不能为空',
                    'required': '币种[currency]为必填项'
                }
            }
        }


class FoundryTransferSerializer(serializers.ModelSerializer):
    operate_user = serializers.ReadOnlyField()

    class Meta:
        model = FoundryTransfer
        fields = ('id', 'foundry_equipment', 'equipment_name', 'equipment_order_no', 'foundry_tooling', 'tooling_name',
                  'tooling_order_no', 'number', 'before_factory', 'after_factory', 'before_project', 'after_project',
                  'transfer_time', 'operate_user', 'remarks')
        extra_kwargs = {
            'number': {
                'error_messages': {
                    'blank': '数量[number]不能为空',
                    'required': '数量[number]为必填项'
                }
            },
            'transfer_time': {
                'error_messages': {
                    'blank': '转移时间[transfer_time]不能为空',
                    'required': '转移时间[transfer_time]为必填项'
                }
            }
        }
