from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager, AbstractUser
from django.db.models import QuerySet


class QuerySetManage(models.Manager):
    def get_queryset(self):
        return super(QuerySetManage, self).get_queryset().filter(is_delete=False)


class UserManager(BaseUserManager):
    """
    实现User的object功能
    """
    def get_queryset(self):
        return super(UserManager, self).get_queryset().filter(is_delete=False)

    def _create_user(self, telephone, username, password, **kwargs):
        user = self.model(telephone=telephone, username=username, **kwargs)
        user.set_password(password)
        user.save()
        return user

    # 创建普通用户
    def create_user(self, telephone, username, password, **kwargs):
        kwargs['login_name'] = kwargs.get('employee_no')
        kwargs['is_superuser'] = False
        kwargs['is_staff'] = False
        return self._create_user(telephone, username, password, **kwargs)

    # 创建超级用户
    def create_superuser(self, telephone, username, password, **kwargs):
        kwargs['login_name'] = kwargs.get('employee_no')
        kwargs['is_superuser'] = True
        kwargs['is_staff'] = True
        return self._create_user(telephone, username, password, **kwargs)


class Section(models.Model):
    """
    部门
    """
    name = models.CharField(max_length=20, verbose_name='部门名称', unique=True)
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    objects = QuerySetManage()

    class Meta:
        db_table = 'section'
        verbose_name = "部门表"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class User(AbstractBaseUser, PermissionsMixin):
    """
    重写User模型
    """
    username = models.CharField(max_length=50, verbose_name='用户名称')
    telephone = models.CharField(max_length=11, unique=True, verbose_name='联系方式')
    login_name = models.CharField(max_length=50, verbose_name='登录名', unique=True)
    employee_no = models.CharField(max_length=10, verbose_name='工号', unique=True)
    email = models.EmailField(unique=True, verbose_name='邮箱', max_length=100)
    section = models.ForeignKey(Section, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='所属部门')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    register_time = models.DateTimeField(auto_now_add=True, verbose_name='注册时间')
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')
    is_staff = models.BooleanField(default=False, verbose_name='是否是员工')

    USERNAME_FIELD = 'login_name'  # authenticate 进行验证的字段
    # createsuperuser命令输入的字段，django默认需要输入密码，所以不用指定要password
    REQUIRED_FIELDS = ['username', 'telephone', 'employee_no', 'email']
    EMAIL_FILED = 'email'  # 指定发送邮箱

    objects = UserManager()  # 存入model

    def get_full_name(self):
        return self.username

    def get_short_name(self):
        return self.username

    class Meta:
        db_table = 'user'
        verbose_name = "用户信息"
        verbose_name_plural = verbose_name

    @property
    def section_name(self):
        if self.section:
            return self.section.name
        else:
            return None

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class OperationLog(models.Model):
    table_name = models.CharField(max_length=60, verbose_name='操作表名')
    operate = models.CharField(max_length=20, verbose_name='操作类型')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='操作人')
    reason = models.CharField(max_length=100, verbose_name='操作原因', null=True)
    before = models.TextField(verbose_name='操作前', null=True)
    after = models.TextField(verbose_name='操作后', null=True)
    change = models.TextField(verbose_name='变化', null=True)
    create_time = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)

    class Meta:
        db_table = 'operation_log'
        verbose_name = '操作日志表'
        verbose_name_plural = verbose_name

