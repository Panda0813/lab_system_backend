from django.db import models


class QuerySetManage(models.Manager):
    def get_queryset(self):
        return super(QuerySetManage, self).get_queryset().filter(is_delete=False)


class FirstService(models.Model):
    name = models.CharField(max_length=100, verbose_name='业务名称', unique=True)
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    class Meta:
        db_table = 'fba_first_service'
        verbose_name = '一类业务表'
        verbose_name_plural = verbose_name

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class SecondService(models.Model):
    first_service = models.ForeignKey(FirstService, verbose_name='所属一级业务', on_delete=models.CASCADE)
    name = models.CharField(max_length=100, verbose_name='业务名称')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')


    class Meta:
        unique_together = (
            ('first_service', 'name')
        )
        db_table = 'fba_second_service'
        verbose_name = '二类业务表'
        verbose_name_plural = verbose_name

    @property
    def first_service_name(self):
        if self.first_service:
            return self.first_service.name
        else:
            return None

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class Company(models.Model):
    name = models.CharField(max_length=100, verbose_name='收付款公司名称', unique=True)
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    class Meta:
        db_table = 'fba_transaction_company'
        verbose_name = '收付款公司表'
        verbose_name_plural = verbose_name

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class EstimateOption(models.Model):
    first_start_day = models.IntegerField(verbose_name='第一次开始填报日', null=True)
    first_end_day = models.IntegerField(verbose_name='第一次结束填报日', null=True)
    second_start_day = models.IntegerField(verbose_name='第二次开始填报日', null=True)
    second_end_day = models.IntegerField(verbose_name='第二次结束填报日', null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)

    class Meta:
        db_table = 'fba_estimate_option'
        verbose_name = '配置表'
        verbose_name_plural = verbose_name


class CapitalSurplus(models.Model):
    year = models.IntegerField(verbose_name='年')
    month = models.IntegerField(verbose_name='月')
    uniic_cny = models.CharField(verbose_name='紫光人民币结余', max_length=30, null=True)
    uniic_usd = models.CharField(verbose_name='紫光美金结余', max_length=30, null=True)
    hk_usd = models.CharField(verbose_name='香港集成美金结余', max_length=30, null=True)
    currency_exchange = models.DecimalField(verbose_name='美元汇率', max_digits=8, decimal_places=6, null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)

    class Meta:
        unique_together = (
            ('year', 'month')
        )
        db_table = 'fba_capital_surplus'
        verbose_name = '上月末资金余额表'
        verbose_name_plural = verbose_name


class EstimateMonthDetail(models.Model):
    DATA_TYPES = (
        (1, '预估数'),
        (2, '修正数')
    )
    region_types = (
        (1, '中国南区'),
        (2, '中国北区')
    )
    first_service = models.ForeignKey(FirstService, verbose_name='一级业务', on_delete=models.CASCADE)
    second_service = models.ForeignKey(SecondService, verbose_name='二级业务', on_delete=models.SET_NULL, null=True)
    region = models.IntegerField(verbose_name='区域', choices=region_types, null=True)
    in_company = models.CharField(verbose_name='收款公司', max_length=100, null=True)
    out_company = models.CharField(verbose_name='付款公司', max_length=100, null=True)
    data_type = models.IntegerField(verbose_name='数据类型', choices=DATA_TYPES)
    write_date = models.CharField(verbose_name='数据所属日期', max_length=20)
    year = models.IntegerField(verbose_name='年')
    month = models.IntegerField(verbose_name='月')
    day = models.IntegerField(verbose_name='日')
    in_usd = models.CharField(verbose_name='美金流入', max_length=30, null=True)
    in_cny = models.CharField(verbose_name='人民币流入', max_length=30, null=True)
    out_usd = models.CharField(verbose_name='美金流出', max_length=30, null=True)
    out_cny = models.CharField(verbose_name='人民币流出', max_length=30, null=True)
    writer_user = models.CharField(verbose_name='填报人', max_length=50)
    is_allow_update = models.BooleanField(verbose_name='是否允许修改', default=True)
    close_time = models.DateTimeField(verbose_name='数据存档时间', null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True)

    class Meta:
        db_table = 'fba_estimate_month_detail'
        verbose_name = '资金预估每月明细表'
        verbose_name_plural = verbose_name

    @property
    def first_service_name(self):
        if self.first_service:
            return self.first_service.name
        else:
            return None

    @property
    def second_service_name(self):
        if self.second_service:
            return self.second_service.name
        else:
            return None


class EstimateMonthFuture(models.Model):
    DATA_TYPES = (
        (1, '预估数'),
        (2, '修正数')
    )
    region_types = (
        (1, '中国南区'),
        (2, '中国北区')
    )
    first_service = models.ForeignKey(FirstService, verbose_name='一级业务', on_delete=models.CASCADE)
    second_service = models.ForeignKey(SecondService, verbose_name='二级业务', on_delete=models.SET_NULL, null=True)
    region = models.IntegerField(verbose_name='区域', choices=region_types, null=True)
    in_company = models.CharField(verbose_name='收款公司', max_length=100, null=True)
    out_company = models.CharField(verbose_name='付款公司', max_length=100, null=True)
    data_type = models.IntegerField(verbose_name='数据类型', choices=DATA_TYPES)
    write_date = models.CharField(verbose_name='数据所属日期', max_length=20)
    year = models.IntegerField(verbose_name='年')
    month = models.IntegerField(verbose_name='月')
    in_usd = models.CharField(verbose_name='美金流入', max_length=30, null=True)
    in_cny = models.CharField(verbose_name='人民币流入', max_length=30, null=True)
    out_usd = models.CharField(verbose_name='美金流出', max_length=30, null=True)
    out_cny = models.CharField(verbose_name='人民币流出', max_length=30, null=True)
    writer_user = models.CharField(verbose_name='填报人', max_length=50)
    is_allow_update = models.BooleanField(verbose_name='是否允许修改', default=True)
    close_time = models.DateTimeField(verbose_name='数据存档时间', null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True)

    class Meta:
        db_table = 'fba_estimate_future_month'
        verbose_name = '未来月份预估数据表'
        verbose_name_plural = verbose_name

    @property
    def first_service_name(self):
        if self.first_service:
            return self.first_service.name
        else:
            return None

    @property
    def second_service_name(self):
        if self.second_service:
            return self.second_service.name
        else:
            return None

