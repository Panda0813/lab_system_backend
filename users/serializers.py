from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework import serializers, validators
from users.models import User, Section, OperationLog, Role
from rest_framework_jwt.serializers import jwt_payload_handler, jwt_encode_handler
from rest_framework.relations import PrimaryKeyRelatedField

from decimal import Decimal
import datetime
import json
import logging

logger = logging.getLogger('django')


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('id', 'name', )
        extra_kwargs = {
            'name': {
                'validators': [validators.UniqueValidator(queryset=Group.objects.all(), message='该名称已存在')],
                'error_messages': {
                    'blank': '角色编码不能为空',
                    'required': '角色编码为必填项'
                }
            }
        }


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ('id', 'name', 'role_code', 'routes')
        extra_kwargs = {
            'name': {
                'validators': [validators.UniqueValidator(queryset=Role.objects.all(), message='该名称已存在')],
                'error_messages': {
                    'blank': '角色名称[name]不能为空',
                    'required': '角色名称[name]为必填项'
                }
            },
            'role_code': {
                'validators': [validators.UniqueValidator(queryset=Role.objects.all(), message='该编码已存在')],
                'error_messages': {
                    'blank': '角色编码[code]不能为空',
                    'required': '角色编码[code]为必填项'
                }
            }
        }


class OperateRoleSerializer(serializers.ModelSerializer):
    group_name = serializers.ReadOnlyField()

    class Meta:
        model = Role
        fields = ('id', 'name', 'group_name', 'routes')


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ('id', 'name')
        extra_kwargs = {
            'name': {
                'validators': [validators.UniqueValidator(queryset=Section.objects.all(), message='该名称已存在')],
                'error_messages': {
                    'blank': '部门名称[name]不能为空',
                    'required': '部门名称[name]为必填项'
                }
            }
        }


class RegisterSerializer(serializers.ModelSerializer):
    password_confirm = serializers.CharField(label='确认密码',
                                             min_length=6, max_length=20,
                                             write_only=True,
                                             error_messages={
                                                 'min_length': '仅允许6~20个字符的确认密码',
                                                 'max_length': '仅允许6~20个字符的确认密码'
                                             })

    class Meta:
        model = User
        fields = ('id', 'username', 'telephone', 'employee_no', 'email', 'password', 'password_confirm', 'section', 'section_name')
        extra_kwargs = {
            'username': {
                'error_messages': {
                    'blank': '用户名称[username]不能为空',
                    'required': '用户名称[username]为必填项'
                }
            },
            'password': {
                'label': '密码',
                'write_only': True,
                'min_length': 6,
                'max_length': 20,
                'error_messages': {
                    'min_length': '仅允许6~20个字符的确认密码',
                    'max_length': '仅允许6~20个字符的确认密码'
                }
            }
        }

    # 多字段校验：直接使用validate，但是必须返回attrs
    def validate_password_confirm(self, password_confirm):
        if self._kwargs['data'].get('password') != password_confirm:
            raise serializers.ValidationError('确认密码与密码不一致')
        return password_confirm

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        validated_data['password'] = make_password(validated_data.get('password'))
        standard_role = Role.objects.get(role_code='standardUser')
        # 创建User对象
        user = User.objects.create(**validated_data)
        standard_role.users.add(user)
        return user


class UserSerializer(serializers.ModelSerializer):
    employee_no = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ('id', 'username', 'telephone', 'employee_no', 'password', 'email', 'section', 'section_name', 'role_set')

    def update(self, instance, validated_data):
        role_set = validated_data.pop('role_set', [])
        new_role_id = []
        if role_set:
            new_role_id = [r.id for r in role_set]
        old_role = instance.role_set.values('id')
        old_role_id = []
        if old_role:
            old_role_id = [r['id'] for r in list(old_role)]
        if list(set(old_role_id) ^ set(new_role_id)):
            with transaction.atomic():
                save_id = transaction.savepoint()
                try:
                    instance.role_set.clear()
                    instance.role_set.add(*new_role_id)
                    transaction.savepoint_commit(save_id)
                except Exception as e:
                    transaction.savepoint_rollback(save_id)
                    logger.error('角色存储失败,error:{}'.format(str(e)))
                    raise serializers.ValidationError('角色存储失败')
        if instance.password != validated_data.get('password'):
            validated_data['password'] = make_password(validated_data.get('password'))
        return super(UserSerializer, self).update(instance, validated_data)


class OperationLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username')
    user_id = serializers.IntegerField

    class Meta:
        model = OperationLog
        fields = ('id', 'table_name', 'operate', 'user_id', 'user_name', 'reason', 'before',
                  'after', 'change', 'create_time')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['before'] = eval(data['before']) if data['before'] else data['before']
        data['after'] = eval(data['after']) if data['after'] else data['after']
        data['change'] = eval(data['change']) if data['change'] else data['change']
        return data
