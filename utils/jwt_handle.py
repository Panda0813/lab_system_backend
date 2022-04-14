from users.models import User, Role


def jwt_response_payload_handler(token, user=None, request=None):
    roles = []
    permissions = []
    if user.role_set.values('id', 'role_code'):
        user_roles = user.role_set.values('id', 'role_code')
        roles = [u['role_code'] for u in list(user_roles)]
        permissions = []
        for role in user_roles:
            routes = Role.objects.get(id=role['id']).routes
            if routes:
                permissions.extend(eval(routes))
        permissions = list(set(permissions))
    return {
        'userInfo': {
            'user_id': user.id,
            'username': user.username,
            'employee_no': user.employee_no,
            'is_superuser': user.is_superuser,
            'login_id': user.login_id,
            'pwd_status': user.pwd_status,
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
