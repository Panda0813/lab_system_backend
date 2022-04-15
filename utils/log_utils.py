from users.models import OperationLog

import re


def get_differ(before, after):
    differ = before.keys() & after
    differ_vals = [{'column': k, 'before': before[k], 'after': after[k]} for k in differ if before[k] != after[k]]
    return differ_vals


def save_operateLog(operate, user, table_name, verbose_name, before=None, after=None, change=None):
    log_dic = {}
    log_dic['user'] = user
    log_dic['table_name'] = table_name
    log_dic['operate'] = operate
    if re.findall(r'表', verbose_name):
        msg = re.findall(r'(.*?)表', verbose_name)[0]
    else:
        msg = verbose_name
    if operate == 'add':
        reason = '新增' + msg
    elif operate == 'update':
        reason = '修改' + msg
    elif operate == 'delete':
        reason = '删除' + msg
    else:
        return '操作类型不正确'
    log_dic['reason'] = reason
    log_dic['before'] = before
    log_dic['after'] = after
    log_dic['change'] = change
    OperationLog.objects.create(**log_dic)
    return 'success'


def set_create_log(func):
    def wrapper(self, request, *args, **kwargs):
        res = func(self, request, *args, **kwargs)
        after = res.data
        save_operateLog('add', request.user, self.table_name, self.verbose_name, after=after)
        return res
    return wrapper


def set_update_log(func):
    def wrapper(self, request, *args, **kwargs):
        before_instance = self.get_object()
        before = self.get_serializer(before_instance).data
        res = func(self, request, *args, **kwargs)
        after_instance = self.get_object()
        after = self.get_serializer(after_instance).data
        change = get_differ(before, after)

        if change:
            save_operateLog('update', request.user, self.table_name, self.verbose_name, before, after, change)
        return res
    return wrapper


def set_delete_log(func):
    def wrapper(self, request, *args, **kwargs):
        before_instance = self.get_object()
        before = self.get_serializer(before_instance).data
        res = func(self, request, *args, **kwargs)
        save_operateLog('delete', request.user, self.table_name, self.verbose_name, before=before)
        return res
    return wrapper
