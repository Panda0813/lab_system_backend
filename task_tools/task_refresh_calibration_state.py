# 定时任务：每日刷新设备最校验到期日
from django.db import transaction, close_old_connections

from task_tools.task_utils import CronTaskObj
from utils.timedelta_utls import calculate_due_date
from equipments.ext_utils import execute_batch_sql

import traceback
import logging

logger = logging.getLogger('django')


class RefreshCalibrationState:

    def begin_task(self):
        from equipments.models import EquipmentCalibrationInfo
        qs = EquipmentCalibrationInfo.objects.all()
        update_sql = 'update equipment_calibration_info set due_date=%s,state=%s where id=%s'
        update_ls = []
        count = 0
        close_old_connections()
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                for q in qs:
                    count += 1
                    _id = q.id
                    state = q.state
                    recalibration_time = q.recalibration_time
                    old_due_date = q.due_date
                    new_due_date = calculate_due_date(recalibration_time)
                    if new_due_date == 'Please perform calibration ASAP':
                        state = '待送检'
                    if old_due_date != new_due_date:
                        update_args = (new_due_date, state, _id)
                        update_ls.append(update_args)

                    if len(update_ls) >= 50:
                        execute_batch_sql(update_sql, update_ls)
                        update_ls = []

                if len(update_ls) > 0:
                    execute_batch_sql(update_sql, update_ls)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.error('定期刷新校验到期日异常，error:{}'.format(traceback.format_exc()))
                raise Exception(e)

        logger.info('成功刷新{}条设备校验到期日'.format(count))


def init_refresh_task():
    refresh_obj = RefreshCalibrationState()
    task = CronTaskObj()
    task.interval_flag = False
    task.add_job(refresh_obj.begin_task, id='定期刷新校验到期日', trigger='cron')
    task.start()
