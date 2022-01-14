from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework import serializers, validators
from users.models import User, Section, OperationLog, Role
from rest_framework_jwt.serializers import jwt_payload_handler, jwt_encode_handler
from rest_framework.relations import PrimaryKeyRelatedField

import logging

logger = logging.getLogger('django')


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('name', )
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
    group_name = serializers.CharField(source='group.name', label='角色编码', required=True,
                                       error_messages={
                                           'blank': '角色编码[group_name]不能为空',
                                           'required': '角色编码[group_name]为必填项'})

    class Meta:
        model = Role
        fields = ('id', 'name', 'group_name', 'routes')
        extra_kwargs = {
            'name': {
                'validators': [validators.UniqueValidator(queryset=Role.objects.all(), message='该名称已存在')],
                'error_messages': {
                    'blank': '角色名称[name]不能为空',
                    'required': '角色名称[name]为必填项'
                }
            }
        }

    def create(self, validated_data):
        group = validated_data.pop('group')
        group_name = group.get('name')
        existqs = Group.objects.filter(name=group_name)
        if existqs:
            raise serializers.ValidationError('该角色编码已存在')
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                group = Group.objects.create(name=group_name)
                validated_data['group'] = group
                role = Role.objects.create(**validated_data)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.error('存储角色信息失败, error:{}'.format(str(e)))
                raise serializers.ValidationError('存储角色信息失败')
        return role


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
            'telephone': {
                'label': '手机号',
                'required': True,
                # 手机号重复验证
                'validators': [validators.UniqueValidator(queryset=User.objects.filter(is_delete=False).all(), message='该手机号已被注册')],
                'error_messages': {
                    'blank': '手机号[telephone]不能为空',
                    'required': '手机号[telephone]为必填项'
                }
            },
            'employee_no': {
                'label': '工号',
                'required': True,
                # 工号重复验证
                'validators': [validators.UniqueValidator(queryset=User.objects.filter(is_delete=False).all(), message='该工号已存在')],
                'error_messages': {
                    'blank': '工号[employee_no]不能为空',
                    'required': '工号[employee_no]为必填项'
                }
            },
            'email': {
                'label': '邮箱',
                'required': True,
                # 邮箱重复验证
                'validators': [validators.UniqueValidator(queryset=User.objects.filter(is_delete=False).all(), message='该邮箱已被注册')],
                'error_messages': {
                    'blank': '邮箱[email]不能为空',
                    'required': '邮箱[email]为必填项'
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
        # 创建User对象
        user = User.objects.create(**validated_data)
        user.groups.add(Group.objects.filter(name='standardUser').first())
        return user


class UserSerializer(serializers.ModelSerializer):
    employee_no = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ('id', 'username', 'telephone', 'employee_no', 'password', 'email', 'section', 'section_name')

    def update(self, instance, validated_data):
        validated_data['password'] = make_password(validated_data.get('password'))
        return super(UserSerializer, self).update(instance, validated_data)


class OperationLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username')
    user_id = serializers.IntegerField

    class Meta:
        model = OperationLog
        fields = ('id', 'table_name', 'operate', 'user_id', 'user_name', 'reason', 'before',
                  'after', 'change', 'create_time')
