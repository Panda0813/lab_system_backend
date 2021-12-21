# coding:utf-8
from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions
from lab_system_backend import settings
from django.utils.translation import ugettext_lazy as _

import datetime

EXPIRE_DAYS = getattr(settings, 'TOKEN_EXPIRE_DAYS')


class ExpiringTokenAuthentication(TokenAuthentication):
    """
    在每次验证token的时候验证是否过期
    """
    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = model.objects.select_related('user').get(key=key)
        except model.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token.')

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed('User inactive or deleted.')

        time_now = datetime.datetime.now()
        if token.created < time_now - datetime.timedelta(hours=24 * EXPIRE_DAYS):
            raise exceptions.AuthenticationFailed('Token has expired')

        return token.user, token
