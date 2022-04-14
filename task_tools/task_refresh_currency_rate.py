# 定时任务：每日刷新货币汇率
from django.db import transaction, close_old_connections
from task_tools.task_utils import CronTaskObj
from equipments.ext_utils import execute_batch_sql

import requests
import json
import datetime
import traceback
import logging

logger = logging.getLogger('django')


class RefreshCurrencyRate:

    def begin_currency_task(self):
        rate_res = requests.get('https://v6.exchangerate-api.com/v6/13089dcf0bd7c6a574cbcc1e/latest/CNY')
        conversion_rates = json.loads(rate_res.content)['conversion_rates']

        from gc_foundry.models import Currency
        qs = Currency.objects.all()
        update_sql = 'update currency set exchange_rate=%s,update_time=%s where id=%s'
        update_ls = []
        count = 0
        close_old_connections()
        with transaction.atomic():
            save_id = transaction.savepoint()
            try:
                now_ts = datetime.datetime.now()
                for q in qs:
                    count += 1
                    short_name = q.short_name
                    exchange_rate = conversion_rates.get(short_name)
                    if exchange_rate:
                        update_args = (exchange_rate, now_ts, q.id)
                        update_ls.append(update_args)

                    if len(update_ls) >= 50:
                        execute_batch_sql(update_sql, update_ls)
                        update_ls = []

                if len(update_ls) > 0:
                    execute_batch_sql(update_sql, update_ls)
                transaction.savepoint_commit(save_id)
            except Exception as e:
                transaction.savepoint_rollback(save_id)
                logger.error('定期刷新汇率异常，error:{}'.format(traceback.format_exc()))
                raise Exception(e)

        logger.info('成功刷新{}条汇率信息'.format(count))


def init_refresh_currency():
    refresh_obj = RefreshCurrencyRate()
    task = CronTaskObj()
    task.interval_flag = False
    task.cron_hour = 9
    task.add_job(refresh_obj.begin_currency_task, id='定期刷新汇率', trigger='cron')
    task.start()
