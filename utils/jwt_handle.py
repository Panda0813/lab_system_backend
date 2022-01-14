from users.models import User
from django.contrib.auth.models import Group


def jwt_response_payload_handler(token, user=None, request=None):
    groups = Group.objects.filter(user=user)
    roles = [group.name for group in groups]
    permissions = []
    for group in groups:
        routes = group.role_set.first().routes
        if routes:
            permissions.extend(eval(routes))
    permissions = list(set(permissions))
    return {
        'userInfo': {
            'user_id': user.id,
            'username': user.username,
            'employee_no': user.employee_no,
            'is_superuser': user.is_superuser,
        },
        'token': 'JWT ' + token,
        'roles': roles,
        'permissions': permissions
    }


def jwt_response_payload_error_handler(serializer, request=None):
    return {
        "msg": "用户名或者密码错误",
        "status": 400,
        "detail": serializer.errors
    }
