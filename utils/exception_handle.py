from rest_framework.views import exception_handler
from rest_framework.views import Response
from rest_framework import status

import logging

logger = logging.getLogger('django')


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        logger.error('请求异常, error:{}'.format(exc))
        return Response({'message': '服务器错误'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR, exception=True)
    else:
        # 取第一个错误的提示用于渲染
        for index, value in enumerate(response.data):
            if index == 0:
                key = value
                value = response.data[key]

                if isinstance(value, str):
                    message = value
                else:
                    message = value[0]
        return Response({'message': message}, status=response.status_code, exception=True)
