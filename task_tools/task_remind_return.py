# 提醒借用用户按时归还设备
from django.db import connection, transaction, close_old_connections
from task_tools.task_utils import CronTaskObj
from equipments.ext_utils import dictfetchall
from utils.email_utils import send_mail

import traceback
import logging

logger = logging.getLogger('django')


class RemindReturnTask:
    def __init__(self):
        self.final_remind_days = 1  # 到期前一天提醒

    def begin_task(self):
        remind_seconds = 2 * 60 * 60
        # query_sql = '''select id, user_id, equipment_id, is_approval, is_return, end_time, is_final_remind,
        #                     is_overtime_remind,round((julianday(strftime('%Y-%m-%d %H:%M:%S',end_time)) -
        #                       julianday(strftime('%Y-%m-%d %H:%M:%S', datetime('now', 'localtime')))) * 86400, 2)
        #                       as delta_seconds
        #                    from equipment_borrow_record where delta_seconds < {}
        #                               and is_approval=1 and is_return=0
        #                               and is_overtime_remind=FALSE and is_delete=FALSE'''.format(remind_seconds)
        query_sql = '''select id, user_id, equipment_id, is_approval, is_return, end_time, is_final_remind, is_overtime_remind,
                           TIMESTAMPDIFF(SECOND, now(), end_time) as delta_seconds
                           from equipment_borrow_record where  TIMESTAMPDIFF(SECOND, now(), end_time) < {}
                                      and is_approval=1 and is_return=0
                                      and is_overtime_remind=0 and is_delete=0'''.format(remind_seconds)
        close_old_connections()
        with connection.cursor() as cursor:
            cursor.execute(query_sql)
            need_remind_qs = dictfetchall(cursor)
        if need_remind_qs:
            from users.models import User, Role
            from equipments.models import EquipmentBorrowRecord
            for q in need_remind_qs:
                borrow_id = q['id']
                user_id = q['user_id']

                equipment_id = q['equipment_id']
                end_time = q['end_time']
                delta_seconds = q['delta_seconds']
                is_final_remind = q['is_final_remind']
                is_overtime_remind = q['is_overtime_remind']
                with transaction.atomic():
                    save_id = transaction.savepoint()
                    try:
                        # 未到期但是小于到期提醒时间,且未提醒过，发送邮件提醒
                        if 0 < delta_seconds < remind_seconds and not is_final_remind:
                            # TODO 发邮件给使用者
                            user = User.objects.get(id=user_id)
                            borrow_qs = EquipmentBorrowRecord.objects.filter(id=borrow_id)
                            info = '即将到期'
                            to = [user.email]
                            send_mail(to, [], info, borrow_qs.first())
                            borrow_qs.update(is_final_remind=True)
                        elif delta_seconds < 0 and not is_overtime_remind:  # 超时
                            # TODO 发邮件给使用者,抄送section manager、下一位借用者、实验室管理员，提示设备仪表超时未还
                            user = User.objects.get(id=user_id)
                            to = [user.email]

                            # 查询下一位用户
                            next_user_qs = EquipmentBorrowRecord.objects.filter(start_time__gte=end_time,
                                                                                equipment_id=equipment_id,
                                                                                is_delete=False,
                                                                                is_approval=0).order_by('id')
                            if next_user_qs:
                                next_user = next_user_qs.first().user
                            borrow_qs = EquipmentBorrowRecord.objects.filter(id=borrow_id)
                            info = '已经逾期'
                            # 查询需要抄送的用户
                            need_cc_users = User.objects.filter(is_delete=False, need_cc=True).values()
                            need_cc_email = [item['email'] for item in list(need_cc_users)]
                            cc = list(set(need_cc_email))
                            send_mail(to, cc, info, borrow_qs.first())
                            borrow_qs.update(is_overtime_remind=True)
                        transaction.savepoint_commit(save_id)
                    except Exception as e:
                        transaction.savepoint_rollback(save_id)
                        logger.error('提醒临期借用者归还设备异常，error: {}'.format(traceback.format_exc()))
                        raise Exception(e)

        logger.info('任务: [提醒临期借用者归还设备] 执行完成')


def init_remind_return():
    remind_obj = RemindReturnTask()
    task = CronTaskObj()
    task.interval_flag = True
    task.interval_minutes = 30
    task.add_job(remind_obj.begin_task, id='定期提醒临期借用者归还设备', trigger='interval')
    task.start()
