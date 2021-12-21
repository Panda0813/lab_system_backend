from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


class ReqMethodMiddle(MiddlewareMixin):

    def process_response(self, request, response):
        resp_code = response.status_code
        if int(resp_code) == 404:
            response = JsonResponse({'code': 0, 'msg': 'request page not found', 'data': {}})
        return response
