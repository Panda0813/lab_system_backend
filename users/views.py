from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from django.db import transaction
from django.http import QueryDict
from django.utils import timezone
from django.contrib.auth.models import Group
from rest_framework.views import APIView
from rest_framework import filters
from rest_framework import generics, serializers
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework import status
from rest_framework.response import Response
from rest_framework_jwt.views import ObtainJSONWebToken, api_settings, jwt_response_payload_handler

from utils.permission import IsActiveUserOrReadOnly, IsSuperUserOrReadOnly
from equipments.ext_utils import REST_SUCCESS, REST_FAIL
from users.serializers import RegisterSerializer, SectionSerializer, UserSerializer, OperationLogSerializer, \
    GroupSerializer, RoleSerializer, OperateRoleSerializer
from users.models import Section, User, OperationLog, Role
from utils.pagination import MyPagePagination
from utils.log_utils import set_delete_log
from lab_system_backend import settings

import datetime
import logging

logger = logging.getLogger('django')

EXPIRE_DAYS = getattr(settings, 'TOKEN_EXPIRE_DAYS')


class GroupListGeneric(generics.ListCreateAPIView):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class RoleListGeneric(generics.ListCreateAPIView):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer


class RoleDetailGeneric(generics.RetrieveUpdateDestroyAPIView):
    queryset = Role.objects.all()
    serializer_class = OperateRoleSerializer

    @set_delete_log
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        group = instance.group
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                Group.objects.filter(id=group.id).delete()
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
    serializer_class = RegisterSerializer
    permission_classes = []


# 重写登录认证，实现手机号/工号/邮箱均可登录
class CustomBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            if not username:
                username = kwargs.get('login_name')
            user = User.objects.get(Q(login_name=username) | Q(telephone=username) |
                                    Q(employee_no=username) | Q(email=username))
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
                groups = Group.objects.filter(user=user)
                roles = [group.name for group in groups]
                res_data = {}
                res_data['user_id'] = user.id
                res_data['username'] = user.username
                res_data['employee_no'] = user.employee_no
                res_data['token'] = token.key
                res_data['is_superuser'] = user.is_superuser
                res_data['roles'] = roles
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
            if not data.get('login_name'):
                data['login_name'] = data['username']
                if isinstance(data, QueryDict):
                    data._mutable = _mutable
                kwargs['data'] = data
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


# 查看用户列表
class UserListGeneric(generics.ListAPIView):
    queryset = User.objects.all().filter(is_delete=False).order_by('-register_time')
    serializer_class = UserSerializer
    pagination_class = MyPagePagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        employee_no = request.GET.get('employee_no')
        if employee_no:
            queryset = queryset.filter(employee_no=employee_no)  # 精确查询
        section_id = request.GET.get('section')
        if section_id:
            queryset = queryset.filter(section_id=section_id)

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


class UserDetailGeneric(generics.RetrieveUpdateAPIView):
    queryset = User.objects.filter(is_delete=False).all()
    serializer_class = UserSerializer


class ChangePassword(APIView):
    def post(self, request):
        user = request.user
        ipassword = request.data['ipassword']
        password = request.data['password']
        if not ipassword:
            return REST_FAIL({'msg': '原密码[ipassword]不能为空'})
        if not password:
            return REST_FAIL({'msg': '新密码[password]不能为空'})
        if user.check_password(ipassword):
            if len(password) > 20 or len(password) < 6:
                return REST_FAIL({'msg': "仅允许6~20个字符的新密码"})
            user.set_password(password)
            user.save()
            return REST_SUCCESS({"msg": "修改成功"})
        else:
            return REST_FAIL({"msg": "原密码错误"})


class OperationLogGeneric(generics.ListAPIView):
    queryset = OperationLog.objects.all().order_by('-create_time')
    serializer_class = OperationLogSerializer
    pagination_class = MyPagePagination
