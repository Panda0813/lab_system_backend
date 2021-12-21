"""
自定义返回格式
"""
from rest_framework.renderers import JSONRenderer


class CustomRenderer(JSONRenderer):
    # 重构render方法
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context:
            if isinstance(data, dict):
                msg = data.pop('msg', 'success')
                code = data.pop('code', 1)
            else:
                msg = 'success'
                code = 1

            if data:
                for key in data:
                    # 判断是否有自定义的异常信息
                    if key == 'message':
                        code = 0
                        msg = data[key]
                        data = {}

                for key in data:
                    if key == 'data':
                        data = data[key]

                if isinstance(data, list):
                    new_data = {}
                    new_data['results'] = data
                    data = new_data
                elif isinstance(data, dict):
                    if 'results' not in list(data.keys()) and data:
                        new_data = {}
                        new_data['results'] = [data]
                        data = new_data
            else:
                data = {}

            ret = {
                'code': code,
                'msg': msg,
                'data': data
            }
            return super().render(ret, accepted_media_type, renderer_context)
        else:
            return super().render(data, accepted_media_type, renderer_context)
