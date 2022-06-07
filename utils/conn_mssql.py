from equipments.ext_utils import dictfetchall
from django.db import connection, transaction, close_old_connections
import pymssql
import logging

logger = logging.getLogger('django')


def get_mssql_conn():
    try:
        conn = pymssql.connect(host='172.21.12.104', user='DBConUser', password='Uniic8253Yw#',
                               database='UNIIC_OA')

        return conn
    except Exception as e:
        logger.error('连接oa数据库失败, error:{}'.format(str(e)))
        return None


def get_oa_users(request):
    from users.models import User
    exist_users = User.objects.all().filter(is_delete=False).values('employee_no')
    exist_users = [item['employee_no'] for item in exist_users if item['employee_no']]
    count_sql = '''select count(*) as count
                from UniicUsers where CurrentStatus=1 and not (User_name like '%紫存%') {}
                '''
    sql = '''select User_id, loginid, convert(nvarchar(50), User_name) as User_name,
                convert(nvarchar(50), Department) as Department, Worker_id
                from UniicUsers where CurrentStatus=1 and not (User_name like '%紫存%') {} order by User_name
                offset {} rows
                fetch next {} rows only'''
    filter_sql = ''
    page = 1
    size = 10
    for k, v in request.GET.items():
        if k == 'page':
            page = int(v)
        elif k == 'size':
            size = int(v)
        elif k == 'DepartmentId':
            filter_sql += ' and DepartmentId={}'.format(int(v))
        else:
            if v != None and v != '':
                cell = k + ' like ' + "'%{}%'".format(v)
                filter_sql += ' and ' + cell
    if exist_users:
        if len(exist_users) == 1:
            filter_sql += ' and Worker_id <> {}'.format(exist_users[0])
        else:
            filter_sql += ' and Worker_id not in {}'.format(tuple(exist_users))
    total_sql = count_sql.format(filter_sql)
    with connection.cursor() as cursor:
        cursor.execute(total_sql)
        total_qs = dictfetchall(cursor)
        total = total_qs[0]['count']
        if total:
            offset = (page - 1) * size
            sql = sql.format(filter_sql, offset, size)
            cursor.execute(sql)
            users = dictfetchall(cursor)
        else:
            users = []
    return total, users


def get_oa_sections():
    sql = '''select distinct DepartmentId,convert(nvarchar(50), Department) as Department 
                from UniicUsers where CurrentStatus=1'''
    with connection.cursor() as cursor:
        cursor.execute(sql)
        sections = dictfetchall(cursor)
    if sections:
        sections = [{'value': item['DepartmentId'], 'label': item['Department']} for item in sections]
    return sections
