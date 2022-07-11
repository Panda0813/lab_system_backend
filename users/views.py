from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.http import QueryDict
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework import filters
from rest_framework.decorators import api_view
from rest_framework import generics, serializers, permissions
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework import status
from rest_framework.response import Response
from rest_framework_jwt.views import ObtainJSONWebToken, api_settings, jwt_response_payload_handler

from utils.permission import IsActiveUserOrReadOnly, IsSuperUserOrReadOnly, IsActiveUser
from equipments.ext_utils import REST_SUCCESS, REST_FAIL
from users.serializers import RegisterSerializer, SectionSerializer, UserSerializer, OperationLogSerializer, \
   RoleSerializer, OperateRoleSerializer
from users.models import Section, User, OperationLog, Role
from utils.log_utils import set_update_log, set_delete_log, set_create_log
from utils.pagination import MyPagePagination
from lab_system_backend import settings
from utils.conn_mssql import get_oa_users, get_oa_sections

import re
import traceback
import datetime
import logging

logger = logging.getLogger('django')

EXPIRE_DAYS = getattr(settings, 'TOKEN_EXPIRE_DAYS')


class RoleListGeneric(generics.ListCreateAPIView):
    model = Role
    queryset = model.objects.all().filter(is_active=True)
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name
    serializer_class = RoleSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        distribute = request.GET.get('distribute')
        req_user = request.user
        user_roles = req_user.role_set.values('id', 'role_code')
        user_roles = [item['role_code'] for item in list(user_roles)]
        if not distribute:
            if 'developer' not in user_roles:
                managerRoles = list(set(['gcManager', 'labManager', 'fbaManager', 'pwmManager']) & set(user_roles))
                tag_ls = []
                for role_name in managerRoles:
                    rep = re.findall(r'(.*?)Manager', role_name)
                    if rep:
                        tag_ls.append(rep[0])
                if len(tag_ls) > 0:
                    queryset = queryset.filter(belong_sys__in=tag_ls)
                else:
                    queryset = QueryDict([])
            elif 'developer' in user_roles:
                pass
            else:
                queryset = QueryDict([])

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
        serializer.validated_data.update(data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class RoleDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = Role
    queryset = model.objects.all()
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name
    serializer_class = OperateRoleSerializer

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
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                self.perform_destroy(instance)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.info('删除角色失败, error:{}'.format(str(e)))
                raise serializers.ValidationError('删除失败')
        return REST_SUCCESS({'msg': '删除成功'})


class SectionListGeneric(generics.ListCreateAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [IsActiveUserOrReadOnly]
    filter_backends = [filters.SearchFilter]
    """
    ^ Starts-with search.
    = Exact matches.
    @ Full-text search. (Currently only supported Django's MySQL backend.)
    $ Regex search
    """
    search_fields = ['name']


class SectionDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer


class UserRegisterView(generics.CreateAPIView):
    model = User
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name
    serializer_class = RegisterSerializer
    permission_classes = []

    @set_create_log
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        employee_no = request.data.get('employee_no')
        exist_qs = User.objects.filter(employee_no=employee_no)
        if exist_qs:
            serializer.is_valid(raise_exception=False)
            exist_qs.update(password=make_password(request.data.get('password')), pwd_status=0, is_delete=False)
            new_data = {'id': exist_qs.first().id}
            new_data.update(serializer.data)
            headers = self.get_success_headers(serializer.data)
            return Response(new_data, status=status.HTTP_201_CREATED, headers=headers)
        else:
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data.copy()
            email = data.get('email')
            if email:
                email_pre = email.split('@')[0]
                email = email_pre + '@unisemicon.com'
            data.update({'email': email})
            section_name = data.get('department')
            section_qs = Section.objects.filter(name=section_name)
            if section_qs:
                data.update({'section': section_qs.first()})
            else:
                obj = Section.objects.create(name=section_name)
                data.update({'section': obj})
            serializer.validated_data.update(data)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# 重写登录认证，实现手机号/工号/邮箱均可登录
class CustomBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(Q(username=username) | Q(email=username) | Q(employee_no=username))
            from django.contrib.auth.hashers import make_password
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None


# 重写登录模块
class LoginView(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        try:
            if serializer.is_valid(raise_exception=True):
                user = serializer.validated_data['user']
                token, created = Token.objects.get_or_create(user=user)
                time_now = datetime.datetime.now()
                if not created and token.created < time_now - datetime.timedelta(hours=24 * EXPIRE_DAYS):
                    token.delete()
                    token = Token.objects.create(user=user)
                    token.created = datetime.datetime.utcnow()
                    token.save()
                res_data = {}
                res_data['user_id'] = user.id
                res_data['username'] = user.username
                res_data['employee_no'] = user.employee_no
                res_data['token'] = token.key
                res_data['is_superuser'] = user.is_superuser
                return Response(res_data)
        except:
            return Response({'msg': '账号或密码错误'}, status=status.HTTP_400_BAD_REQUEST)


class JwtLoginView(ObtainJSONWebToken):
    def get_serializer(self, *args, **kwargs):
        """
        Return the serializer instance that should be used for validating and
        deserializing input, and for serializing output.
        """
        data = kwargs.get('data')
        if data:
            if isinstance(data, QueryDict):
                _mutable = data._mutable
                data._mutable = True
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            if serializer.is_valid(raise_exception=True):
                user = serializer.object.get('user') or request.user
                token = serializer.object.get('token')
                response_data = jwt_response_payload_handler(token, user, request)
                response = Response(response_data)
                if api_settings.JWT_AUTH_COOKIE:
                    expiration = (datetime.datetime.utcnow() +
                                  api_settings.JWT_EXPIRATION_DELTA)
                    response.set_cookie(api_settings.JWT_AUTH_COOKIE,
                                        token,
                                        expires=expiration,
                                        httponly=True)
                return response
        except Exception as e:
            logger.error('登录失败, error: {}'.format(str(e)))
            return Response({'msg': '账号或密码错误'}, status=status.HTTP_400_BAD_REQUEST)


# 退出登录
class LogoutView(APIView):

    def get(self, request):
        user = request.user
        return Response({'msg': '退出成功'})


# 查询某个用户名是否存在
@api_view(['GET'])
def query_username_exist(request):
    username = request.GET.get('username')
    if not username:
        return REST_FAIL({'msg': 'username不能为空'})
    qs = User.objects.filter(username=username)
    data = {}
    if qs:
        data = list(qs.values())[0]
    return REST_SUCCESS(data)


# 查看用户列表
class UserListGeneric(generics.ListAPIView):
    queryset = User.objects.all().filter(is_delete=False).order_by('-register_time')
    serializer_class = UserSerializer
    permission_classes = [IsActiveUser]
    # pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        req_user = request.user
        user_roles = req_user.role_set.values('id', 'role_code')
        user_roles = [item['role_code'] for item in list(user_roles)]
        if 'developer' in user_roles:
            pass
        elif list(set(['gcManager', 'labManager', 'fbaManager', 'pwmManager']) & set(user_roles)):
            queryset = queryset.filter(is_superuser=False)
        elif 'labSectionManager' in user_roles:
            section_id = req_user.section_id
            queryset = queryset.filter(is_superuser=False).filter(section_id=section_id)
        else:
            queryset = queryset.filter(is_superuser=False).filter(id=req_user.id)
        employee_no = request.GET.get('employee_no')
        if employee_no:
            queryset = queryset.filter(employee_no=employee_no)  # 精确查询
        section_id = request.GET.get('section')
        if section_id:
            queryset = queryset.filter(section_id=section_id)
        telephone = request.GET.get('telephone')
        if telephone:
            queryset = queryset.filter(telephone=telephone)
        email = request.GET.get('email')
        if email:
            queryset = queryset.filter(email=email)

        fuzzy_params = {}
        fuzzy_params['username'] = request.GET.get('username', '')

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


class UserDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    model = User
    table_name = model._meta.db_table
    verbose_name = model._meta.verbose_name
    queryset = model.objects.filter(is_delete=False).all()
    serializer_class = UserSerializer

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


class ChangePassword(APIView):
    def post(self, request):
        user = request.user
        if user.pwd_status != 0:
            ipassword = request.data['ipassword']
            if not ipassword:
                return REST_FAIL({'msg': '原密码[ipassword]不能为空'})
            if not user.check_password(ipassword):
                return REST_FAIL({"msg": "原密码错误"})
        password = request.data['password']
        if not password:
            return REST_FAIL({'msg': '新密码[password]不能为空'})
        if len(password) < 8:
            return REST_FAIL({'msg': "仅允许至少8位以上密码, 必须同时包含字母、数字和特殊字符"})
        user.set_password(password)
        if user.pwd_status == 0:
            user.pwd_status = 1
        user.save()
        return REST_SUCCESS({"msg": "修改成功"})


class OperationLogGeneric(generics.ListAPIView):
    queryset = OperationLog.objects.all().order_by('-create_time')
    serializer_class = OperationLogSerializer
    pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        operate = request.GET.get('operate')
        if operate:
            queryset = queryset.filter(operate=operate)  # 精确查询

        fuzzy_params = {}
        fuzzy_params['user_name'] = request.GET.get('user_name', '')
        fuzzy_params['table_name'] = request.GET.get('table_name', '')

        filter_params = {}
        for k, v in fuzzy_params.items():
            if v != None and v != '':
                k = k + '__contains'
                filter_params[k] = v

        if filter_params:
            queryset = queryset.filter(**filter_params)

        start_time = request.GET.get('start_time')
        end_time = request.GET.get('end_time')
        if start_time and end_time:
            queryset = queryset.filter(create_time__range=[start_time, end_time])

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# 查询oa用户
@api_view(['GET'])
def query_oa_user_list(request):
    try:
        total, users = get_oa_users(request)
        return REST_SUCCESS({'count': total, 'results': users})
    except Exception as e:
        logger.error('查询失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '查询失败, error: {}'.format(str(e))})


# 查询所有部门
@api_view(['GET'])
def query_oa_sections(request):
    try:
        sections = get_oa_sections()
        return REST_SUCCESS(sections)
    except Exception as e:
        logger.error('查询失败, error: {}'.format(traceback.format_exc()))
        return REST_FAIL({'msg': '查询失败, error: {}'.format(str(e))})
