from django.db import models
from equipments.models import Project
from lab_system_backend.settings import MEDIA_ROOT

import os


class Currency(models.Model):
    name = models.CharField(verbose_name='货币名称', max_length=50)
    short_name = models.CharField(verbose_name='缩写', max_length=20)
    exchange_rate = models.DecimalField(verbose_name='人民币兑换汇率', max_digits=12, decimal_places=5, null=True)
    opt_group = models.CharField(verbose_name='所属分组', max_length=20, null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)

    class Meta:
        unique_together = (
            ('name', 'short_name')
        )
        db_table = 'currency'
        verbose_name = '货币汇率表'
        verbose_name_plural = verbose_name


class Factory(models.Model):
    name = models.CharField(max_length=100, verbose_name='工厂名称')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'gc_foundry_factory'
        verbose_name = '设备存放工厂表'
        verbose_name_plural = verbose_name


class MachineModel(models.Model):
    name = models.CharField(max_length=100, verbose_name='机台型号')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'gc_foundry_machine_model'
        verbose_name = '设备存放工厂表'
        verbose_name_plural = verbose_name


class FoundryEquipment(models.Model):
    MACHINE_CATEGORY = (
        (1, 'Mask'),
        (2, '测试设备'),
        (3, 'RDL Mask'),
        (4, 'NRE')
    )
    FIXED_ASSET = (
        (1, '是'),
        (2, '否'),
        (3, '财务账上报废')
    )
    UNIT_TYPE = (
        (1, '套'),
        (2, '个'),
        (3, '台'),
        (4, '块')
    )
    name = models.CharField(verbose_name='设备型号名称', max_length=100, null=True)
    purchase_order_no = models.CharField(verbose_name='采购订单编号', max_length=100, null=True)
    supplier = models.CharField(verbose_name='供应商', max_length=100, null=True)
    category = models.IntegerField(verbose_name='类别', choices=MACHINE_CATEGORY, null=True)
    is_fixed_asset = models.IntegerField(verbose_name='是否为固定资产', choices=FIXED_ASSET, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, verbose_name='项目', null=True)
    number = models.IntegerField(verbose_name='数量', null=True)
    unit = models.IntegerField(verbose_name='单位', choices=UNIT_TYPE, null=True)
    price = models.DecimalField(verbose_name='原币单价', max_digits=20, decimal_places=2, null=True)
    currency = models.ForeignKey(Currency, on_delete=models.SET_NULL, verbose_name='币种', null=True)
    total_amount = models.DecimalField(verbose_name='原币总价', max_digits=20, decimal_places=2, null=True)
    base_total_amount = models.DecimalField(verbose_name='本位币总价', max_digits=20, decimal_places=2, null=True)
    factory = models.ForeignKey(Factory, on_delete=models.SET_NULL, verbose_name='存放地点', null=True)
    specification = models.TextField(verbose_name='技术信息', null=True)
    serial_number = models.CharField(max_length=60, verbose_name='序列号', null=True)
    fixed_asset_code = models.CharField(max_length=60, verbose_name='固定资产编号', null=True)
    assort_material = models.TextField(verbose_name='配套设备器材', null=True)
    custodian = models.CharField(max_length=60, verbose_name='保管人', null=True)
    image_path = models.CharField(verbose_name='对应照片存放地址', max_length=100, null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True)

    class Meta:
        db_table = 'gc_foundry_equipment'
        verbose_name = '测试机台表'
        verbose_name_plural = verbose_name

    @property
    def project_name(self):
        if self.project:
            return self.project.name
        else:
            return None

    @property
    def currency_name(self):
        if self.currency:
            return self.currency.name
        else:
            return None

    @property
    def currency_exchange_rate(self):
        if self.currency:
            return self.currency.exchange_rate
        else:
            return None

    @property
    def factory_name(self):
        if self.factory:
            return self.factory.name
        else:
            return None

    @property
    def image_ls(self):
        if self.image_path:
            return os.listdir(os.path.join(MEDIA_ROOT, self.image_path))
        else:
            return []


class FoundryTooling(models.Model):
    TOOLING_CATEGORY = (
        (1, '测试配件'),
        (2, '测试板'),
        (3, '探针卡'),
        (4, '探针卡+清针片')
    )
    FIXED_ASSET = (
        (1, '是'),
        (2, '否'),
        (3, '财务账上报废')
    )
    UNIT_TYPE = (
        (1, '套'),
        (2, '个'),
        (3, '台'),
        (4, '块')
    )
    name = models.CharField(verbose_name='设备型号名称', max_length=100, null=True)
    purchase_order_no = models.CharField(verbose_name='采购订单编号', max_length=100, null=True)
    supplier = models.CharField(verbose_name='供应商', max_length=100, null=True)
    category = models.IntegerField(verbose_name='类别', choices=TOOLING_CATEGORY, null=True)
    is_fixed_asset = models.IntegerField(verbose_name='是否为固定资产', choices=FIXED_ASSET, null=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, verbose_name='项目', null=True)
    number = models.IntegerField(verbose_name='数量', null=True)
    unit = models.IntegerField(verbose_name='单位', choices=UNIT_TYPE, null=True)
    price = models.DecimalField(verbose_name='原币单价', max_digits=20, decimal_places=2, null=True)
    currency = models.ForeignKey(Currency, on_delete=models.SET_NULL, verbose_name='币种', null=True)
    total_amount = models.DecimalField(verbose_name='原币总价', max_digits=20, decimal_places=2, null=True)
    base_total_amount = models.DecimalField(verbose_name='本位币总价', max_digits=20, decimal_places=2, null=True)
    factory = models.ForeignKey(Factory, on_delete=models.SET_NULL, verbose_name='存放地点', null=True)
    specification = models.TextField(verbose_name='技术信息', null=True)
    serial_number = models.CharField(max_length=60, verbose_name='序列号', null=True)
    fixed_asset_code = models.CharField(max_length=60, verbose_name='固定资产编号', null=True)
    used_machine = models.TextField(verbose_name='配套机台型号', null=True)
    custodian = models.CharField(max_length=60, verbose_name='保管人', null=True)
    image_path = models.CharField(verbose_name='对应照片存放地址', max_length=100, null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True)

    class Meta:
        db_table = 'gc_foundry_tooling_info'
        verbose_name = '设备器材表'
        verbose_name_plural = verbose_name

    @property
    def project_name(self):
        if self.project:
            return self.project.name
        else:
            return None

    @property
    def currency_name(self):
        if self.currency:
            return self.currency.name
        else:
            return None

    @property
    def currency_exchange_rate(self):
        if self.currency:
            return self.currency.exchange_rate
        else:
            return None

    @property
    def factory_name(self):
        if self.factory:
            return self.factory.name
        else:
            return None

    @property
    def image_ls(self):
        if self.image_path:
            return os.listdir(os.path.join(MEDIA_ROOT, self.image_path))
        else:
            return []


class FoundryTransfer(models.Model):
    foundry_equipment = models.ForeignKey(FoundryEquipment, verbose_name='测试机台', on_delete=models.SET_NULL, null=True)
    foundry_tooling = models.ForeignKey(FoundryTooling, verbose_name='设备器材', on_delete=models.SET_NULL, null=True)
    number = models.IntegerField(verbose_name='数量', default=1)
    before_factory = models.CharField(verbose_name='转移前工厂', max_length=100, null=True)
    after_factory = models.CharField(verbose_name='转移后工厂', max_length=100, null=True)
    before_project = models.CharField(verbose_name='转移前项目', max_length=100, null=True)
    after_project = models.CharField(verbose_name='转移后项目', max_length=100, null=True)
    transfer_time = models.DateTimeField(verbose_name='转移时间', null=True)
    operate_user = models.CharField(verbose_name='操作人', max_length=60, null=True)
    create_time = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    remarks = models.TextField(verbose_name='备注', null=True)

    class Meta:
        db_table = 'gc_foundry_transfer_record'
        verbose_name = '流转记录表'
        verbose_name_plural = verbose_name

    @property
    def equipment_name(self):
        if self.foundry_equipment:
            return self.foundry_equipment.name
        else:
            return None

    @property
    def equipment_order_no(self):
        if self.foundry_equipment:
            return self.foundry_equipment.purchase_order_no
        else:
            return None

    @property
    def tooling_name(self):
        if self.foundry_tooling:
            return self.foundry_tooling.name
        else:
            return None

    @property
    def tooling_order_no(self):
        if self.foundry_tooling:
            return self.foundry_tooling.purchase_order_no
        else:
            return None
