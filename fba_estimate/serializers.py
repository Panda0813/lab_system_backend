from rest_framework import serializers, validators

from fba_estimate.models import FirstService, SecondService, Company, EstimateOption, CapitalSurplus, \
    EstimateMonthDetail, EstimateMonthFuture


class FirstServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FirstService
        fields = ('id', 'name', 'is_active')
        extra_kwargs = {
            'name': {
                'validators': [validators.UniqueValidator(queryset=FirstService.objects.all(), message='该业务名称已存在')],
                'error_messages': {
                    'blank': '业务名称[name]不能为空',
                    'required': '业务名称[name]为必填项'
                }
            }
        }


class SecondServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecondService
        fields = ('id', 'first_service', 'first_service_name', 'name', 'is_active')
        extra_kwargs = {
            'name': {
                'validators': [validators.UniqueValidator(queryset=FirstService.objects.all(), message='该业务名称已存在')],
                'error_messages': {
                    'blank': '业务名称[name]不能为空',
                    'required': '业务名称[name]为必填项'
                }
            }
        }


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ('id', 'name', 'is_active')
        extra_kwargs = {
            'name': {
                'validators': [validators.UniqueValidator(queryset=FirstService.objects.all(), message='该公司名称已存在')],
                'error_messages': {
                    'blank': '公司名称[name]不能为空',
                    'required': '公司名称[name]为必填项'
                }
            }
        }


class EstimateOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstimateOption
        fields = '__all__'


class CapitalSurplusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapitalSurplus
        fields = '__all__'


class EstimateMonthDetailSerializer(serializers.ModelSerializer):
    writer_user = serializers.ReadOnlyField()
    is_allow_update = serializers.ReadOnlyField()
    close_time = serializers.ReadOnlyField()

    class Meta:
        model = EstimateMonthDetail
        fields = ('id', 'first_service', 'first_service_name', 'second_service', 'second_service_name', 'company',
                  'data_type', 'write_date', 'year', 'month', 'day', 'in_usd', 'in_cny', 'out_usd',
                  'out_cny', 'writer_user', 'is_allow_update', 'close_time', 'remarks', 'create_time')


class EstimateMonthFutureSerializer(serializers.ModelSerializer):
    writer_user = serializers.ReadOnlyField()
    is_allow_update = serializers.ReadOnlyField()
    close_time = serializers.ReadOnlyField()

    class Meta:
        model = EstimateMonthFuture
        fields = ('id', 'first_service', 'first_service_name', 'second_service', 'second_service_name', 'company',
                  'data_type', 'write_date', 'year', 'month', 'in_usd', 'in_cny', 'out_usd', 'out_cny',
                  'writer_user', 'is_allow_update', 'close_time', 'remarks', 'create_time')
