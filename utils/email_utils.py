from django.core import mail
from django.core.mail import EmailMultiAlternatives

import os
import logging

logger = logging.getLogger('django')


def send_mail(to, cc, info, borrow):
    # with mail.get_connection(fail_silently=False) as conn:
    msg = EmailMultiAlternatives(
        subject='设备使用到期提醒',
        body='testBody',
        from_email='uniic_lab_bot@unisemicon.com',
        to=to,
        cc=cc
    )
    h = '''<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>设备使用到期提醒邮件</title>
            </head>
            <body>
            <p>Hi, %s：</p>
            <p></p>
            <p>您正在使用的设备：【%s】，使用时间%s，请及时在《实验室设备资源管理系统》提交归还申请，避免给后面使用设备的同事带来不便，谢谢！</p>
            <p>使用信息：</p>
            <table border="1" style="border-collapse: collapse;" cellpadding="5">
                <tbody>
                    <tr>
                        <th>设备ID</th>
                        <th>设备名称</th>
                        <th>项目</th>
                        <th>开始时间</th>
                        <th>结束时间</th>
                    </tr>
                    <tr>
                        <td>%s</td>
                        <td>%s</td>
                        <td>%s</td>
                        <td>%s</td>
                        <td>%s</td>
                    </tr>
                </tbody>
            </table>
            <p>   </p>
            <br>
            
            <p style="color:red">注意: 该邮件由系统发送，无需回复！</p>
            <p>————————————————————————————————————</p>
            <p>IT平台部  CAD&amp;IT </p>
            </body>
            </html>''' % (borrow.user_name, borrow.equipment_id, info, borrow.equipment_id,
                          borrow.equipment_name, borrow.project_name, borrow.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                          borrow.end_time.strftime('%Y-%m-%d %H:%M:%S'))
    msg.attach_alternative(content=h, mimetype="text/html")
    msg.send()
