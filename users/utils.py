from django.db import connection
from equipments.ext_utils import dictfetchall

import re


def get_inner_email(login_id):
    name_number = re.findall(r'[0-9]+', login_id)
    whole_name = re.sub(r'[0-9]+', "", login_id)
    surname = whole_name.split('.')[1]
    name = whole_name.split('.')[0]
    if name_number:
        name_number = name_number[0]
        name += name_number
    sql = '''select email from inner_email_info where surname like '%{}%' and name like '%{}%' '''
    sql = sql.format(surname, name)
    with connection.cursor() as cursor:
        cursor.execute(sql)
        qs = dictfetchall(cursor)
    email = ''
    if qs:
        email = qs[0]['email']
        email = email + '@uniic.com'
    return email
