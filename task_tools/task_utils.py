from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.triggers.interval import IntervalTrigger
from lab_system_backend.settings import INTERVAL_TIME, CRON_DATE, ERROR_WAIT

import datetime
import logging

logger = logging.getLogger('django')


class CronTaskObj:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        self.cron_hour = CRON_DATE['hour']
        self.interval_minutes = INTERVAL_TIME['minutes']
        self.error_seconds = ERROR_WAIT * 60
        self.job_exc_dict = {}
        self.interval_flag = None  # 轮询标志

    def change_trigger(self, job_id, trigger='interval', **trigger_args):
        """
        修改定时任务触发器
        """
        self.scheduler.reschedule_job(job_id, trigger=trigger, **trigger_args)

    def get_trigger(self, job_id):
        """
        获取定时任务触发器
        """
        return self.scheduler.get_job(job_id).trigger

    def add_job(self, func, trigger, id=None, args=None, kwargs=None, **trigger_args):
        # if self.interval_flag:
        #     minutes = 0.1
        #     self.scheduler.add_job(func, trigger=trigger, id=id, args=args, kwargs=kwargs,
        #                            minutes=minutes, **trigger_args)
        # else:
        #     self.scheduler.add_job(func, trigger=trigger, id=id, args=args, kwargs=kwargs,
        #                            hour=self.cron_hour, **trigger_args)
        if id == '定期刷新校验到期日':
            minutes = 0.3
        else:
            minutes = 0.5

        self.scheduler.add_job(func, trigger='interval', id=id, args=args, kwargs=kwargs,
                               minutes=minutes, **trigger_args)
        self.job_exc_dict[id] = 0

    def start(self):
        """
        开启任务，增加监听器，监听正常及异常
        """
        self.scheduler.add_listener(self._listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        if self.scheduler.state == 0:
            self.scheduler.start()

    def _listener(self, event):
        """
        监听器
        """
        if event.exception:
            self.job_exc_dict[event.job_id] += 1

            # 出现异常进入异常执行周期，正常后恢复原间隔
            if self.job_exc_dict[event.job_id] >= 1:
                logger.error('任务: [%s]出现异常，任务运行间隔暂时修改为[%s]s，ERROR: %s, \n, %s' % (event.job_id,
                                                                                self.error_seconds, event.traceback,
                                                                                str(event.exception)))
                self.change_trigger(event.job_id, seconds=self.error_seconds)
                self.job_exc_dict[event.job_id] = 0
        else:
            self.job_exc_dict[event.job_id] = 0
            # 无异常后，恢复原间隔
            trigger = self.get_trigger(event.job_id)
            if isinstance(trigger, IntervalTrigger):
                if trigger.interval < datetime.timedelta(seconds=self.interval_minutes * 60):
                    if self.interval_flag:
                        self.change_trigger(event.job_id, minutes=self.interval_minutes)
                    else:
                        self.change_trigger(event.job_id, trigger='cron', hour=self.cron_hour)

                    logger.info('任务: [%s]恢复原运行间隔' % event.job_id)
