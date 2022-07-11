from django.db import models
from users.models import User
from equipments.models import Project


class QuerySetManage(models.Manager):
    def get_queryset(self):
        return super(QuerySetManage, self).get_queryset().filter(is_delete=False)


class WaferInfo(models.Model):
    general_type = (
        ('晶圆', '晶圆'),
    )
    subdivision_type = (
        ('Dram', 'Dram'),
        ('Logic', 'Logic')
    )
    technology_type = (
        ('25nm', '25nm'),
        ('38nm', '38nm'),
        ('45nm', '45nm'),
        ('55nm', '55nm'),
        ('63nm', '63nm')
    )
    id = models.CharField(verbose_name='型号', max_length=100, primary_key=True)
    project = models.ForeignKey(Project, verbose_name='项目', on_delete=models.SET_NULL, null=True)
    general = models.CharField(verbose_name='产品大类', max_length=20, null=True)
    subdivision = models.CharField(verbose_name='产品细分', max_length=20, null=True)
    technology = models.CharField(verbose_name='工艺', max_length=20, null=True)
    gross_die = models.IntegerField(verbose_name='粗略数量(Gross die)', default=0)
    has_bom = models.BooleanField(verbose_name='是否有BOM', default=False)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True)
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    objects = QuerySetManage()

    class Meta:
        db_table = 'pwm_cost_wafer_info'
        verbose_name = 'wafer基础信息表'
        verbose_name_plural = verbose_name

    @property
    def project_name(self):
        if self.project:
            return self.project.name
        else:
            return None

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class WaferBom(models.Model):
    belong_wafer = models.ForeignKey(WaferInfo, verbose_name='所属wafer', on_delete=models.CASCADE, related_name='belong_wafer')
    wafer_source = models.ForeignKey(WaferInfo, verbose_name='wafer来源', on_delete=models.CASCADE, related_name='wafer_source')
    count = models.IntegerField(verbose_name='数量', default=1)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True, blank=True)

    class Meta:
        db_table = 'pwm_cost_wafer_bom'
        verbose_name = '合成wafer明细表'
        verbose_name_plural = verbose_name


class UploadRecord(models.Model):
    data_types = (
        (1, 'Wafer成本'),
        (2, '良率'),
        (3, '测试费')
    )
    user = models.ForeignKey(User, verbose_name='上传用户', on_delete=models.CASCADE)
    data_type = models.IntegerField(verbose_name='数据类型', choices=data_types)
    file_path = models.CharField(verbose_name='文件存放地址', max_length=100, null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True)
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    objects = QuerySetManage()

    class Meta:
        db_table = 'pwm_cost_upload_record'
        verbose_name = '维护信息上传记录'
        verbose_name_plural = verbose_name

    @property
    def user_name(self):
        if self.user:
            return self.user.username
        else:
            return None

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class WaferPrice(models.Model):
    wafer = models.ForeignKey(WaferInfo, verbose_name='关联wafer', on_delete=models.CASCADE)
    upload = models.ForeignKey(UploadRecord, verbose_name='上传记录', on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, verbose_name='创建人', on_delete=models.SET_NULL, null=True)
    price_source = models.CharField(verbose_name='价格来源', max_length=60, null=True)
    supplier = models.CharField(verbose_name='供应商', max_length=100, null=True)
    purchase_price = models.DecimalField(verbose_name='采购单价', max_digits=12, decimal_places=2, null=True)
    order_date = models.CharField(verbose_name='下单日期', max_length=20, null=True)
    wafer_price = models.DecimalField(verbose_name='Wafer U/P', max_digits=12, decimal_places=2, null=True)
    maintain_period = models.CharField(verbose_name='数据所属周期', max_length=20)
    create_time = models.DateTimeField(verbose_name='提交时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True)
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    objects = QuerySetManage()

    class Meta:
        db_table = 'pwm_cost_wafer_price'
        verbose_name = 'wafer单价维护记录'
        verbose_name_plural = verbose_name

    @property
    def project_name(self):
        if self.wafer:
            return self.wafer.project_name
        else:
            return None

    @property
    def user_name(self):
        if self.user:
            return self.user.username
        else:
            return None

    @property
    def general(self):
        if self.wafer:
            return self.wafer.general
        else:
            return None

    @property
    def subdivision(self):
        if self.wafer:
            return self.wafer.subdivision
        else:
            return None

    @property
    def technology(self):
        if self.wafer:
            return self.wafer.technology
        else:
            return None

    @property
    def gross_die(self):
        if self.wafer:
            return self.wafer.gross_die
        else:
            return None

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class GrainInfo(models.Model):
    general_type = (
        ('颗粒', '颗粒'),
    )
    subdivision_type = (
        ('KGD', 'KGD'),
        ('IC', 'IC'),
        ('ASIC', 'ASIC')
    )
    technology_type = (
        ('25nm', '25nm'),
        ('38nm', '38nm'),
        ('45nm', '45nm'),
        ('55nm', '55nm'),
        ('63nm', '63nm')
    )
    id = models.CharField(verbose_name='料号(PN)', max_length=100, primary_key=True)
    wafer = models.ForeignKey(WaferInfo, verbose_name='关联wafer', on_delete=models.SET_NULL, null=True)
    project = models.ForeignKey(Project, verbose_name='项目', on_delete=models.SET_NULL, null=True)
    general = models.CharField(verbose_name='产品大类', max_length=20, null=True)
    subdivision = models.CharField(verbose_name='产品细分', max_length=20, null=True)
    technology = models.CharField(verbose_name='工艺', max_length=20, null=True)
    package_mode = models.CharField(verbose_name='封装方式(Package)', max_length=100, null=True)
    package_size = models.CharField(verbose_name='封装尺寸(Package size)', max_length=50, null=True)
    grade = models.CharField(verbose_name='等级(Grade)', max_length=50, null=True)
    type = models.CharField(verbose_name='类型', max_length=50, null=True)
    sub_con = models.CharField(verbose_name='分包商(Sub-con)', max_length=50, null=True)
    has_bom = models.BooleanField(verbose_name='是否有BOM', default=False)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True)
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    objects = QuerySetManage()

    class Meta:
        db_table = 'pwm_cost_grain_info'
        verbose_name = '颗粒基础信息'
        verbose_name_plural = verbose_name

    @property
    def project_name(self):
        if self.project:
            return self.project.name
        else:
            return None

    @property
    def gross_die(self):
        if self.wafer:
            return self.wafer.gross_die
        else:
            return None

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class GrainBom(models.Model):
    belong_grain = models.ForeignKey(GrainInfo, verbose_name='所属grain', on_delete=models.CASCADE, related_name='belong_grain')
    grain_source = models.ForeignKey(GrainInfo, verbose_name='grain来源', on_delete=models.CASCADE, related_name='grain_source')
    count = models.IntegerField(verbose_name='数量', default=1)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True, blank=True)

    class Meta:
        db_table = 'pwm_cost_grain_bom'
        verbose_name = '合成颗粒明细表'
        verbose_name_plural = verbose_name


class GrainYield(models.Model):
    wafer = models.ForeignKey(WaferInfo, verbose_name='关联wafer', on_delete=models.SET_NULL, null=True)
    grain = models.ForeignKey(GrainInfo, verbose_name='关联grain(料号)', on_delete=models.CASCADE)
    upload = models.ForeignKey(UploadRecord, verbose_name='上传记录', on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, verbose_name='创建人', on_delete=models.SET_NULL, null=True)
    hb_yld = models.DecimalField(verbose_name='HB YLD', max_digits=8, decimal_places=6, default=1)
    cp_yld = models.DecimalField(verbose_name='CP YLD', max_digits=8, decimal_places=6, default=1)
    rdl_yld = models.DecimalField(verbose_name='RDL YLD', max_digits=8, decimal_places=6, default=1)
    bp_yld = models.DecimalField(verbose_name='BP YLD', max_digits=8, decimal_places=6, default=1)
    wafer_yld = models.DecimalField(verbose_name='TTL Wafer YLD', max_digits=8, decimal_places=6, default=1)  # 前段良率
    ap_yld = models.DecimalField(verbose_name='AP YLD', max_digits=8, decimal_places=6, default=1)
    bi_yld = models.DecimalField(verbose_name='BI YLD', max_digits=8, decimal_places=6, default=1)
    ft1_yld = models.DecimalField(verbose_name='FT1 YLD', max_digits=8, decimal_places=6, default=1)
    ft2_yld = models.DecimalField(verbose_name='FT2 YLD', max_digits=8, decimal_places=6, default=1)
    ft3_yld = models.DecimalField(verbose_name='FT3 YLD', max_digits=8, decimal_places=6, default=1)
    ft4_yld = models.DecimalField(verbose_name='FT4 YLD', max_digits=8, decimal_places=6, default=1)
    ft5_yld = models.DecimalField(verbose_name='FT5 YLD', max_digits=8, decimal_places=6, default=1)
    ft6_yld = models.DecimalField(verbose_name='FT6 YLD', max_digits=8, decimal_places=6, default=1)
    ft_yld = models.DecimalField(verbose_name='TTL FT YLD', max_digits=8, decimal_places=6, default=1)  # 后段良率
    period = models.CharField(verbose_name='数据所属周期', max_length=20)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True)
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    objects = QuerySetManage()

    class Meta:
        db_table = 'pwm_cost_grain_yld'
        verbose_name = '良率维护记录'
        verbose_name_plural = verbose_name

    @property
    def user_name(self):
        if self.user:
            return self.user.username
        else:
            return None

    @property
    def subdivision(self):
        if self.grain:
            return self.grain.subdivision
        else:
            return None

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class GrainUnitPrice(models.Model):
    wafer = models.ForeignKey(WaferInfo, verbose_name='关联wafer', on_delete=models.SET_NULL, null=True)
    grain = models.ForeignKey(GrainInfo, verbose_name='关联grain(料号)', on_delete=models.CASCADE)
    upload = models.ForeignKey(UploadRecord, verbose_name='上传记录', on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, verbose_name='创建人', on_delete=models.SET_NULL, null=True)
    wafer_price = models.DecimalField(verbose_name='Wafer U/P', max_digits=12, decimal_places=2, null=True)
    purchase_price = models.DecimalField(verbose_name='采购单价', max_digits=10, decimal_places=2, default=0)
    hb_up = models.DecimalField(verbose_name='HB U/P', max_digits=10, decimal_places=2, default=0)
    cp_up = models.DecimalField(verbose_name='CP U/P', max_digits=10, decimal_places=2, default=0)
    rdl_up = models.DecimalField(verbose_name='RDL U/P', max_digits=10, decimal_places=2, default=0)
    bp_up = models.DecimalField(verbose_name='BP U/P', max_digits=10, decimal_places=2, default=0)
    wafer_amt = models.DecimalField(verbose_name='TTL Wafer 加工费', max_digits=10, decimal_places=2, default=0)  # 前段成本之和
    ap_up = models.DecimalField(verbose_name='AP U/P', max_digits=10, decimal_places=2, default=0)
    ap_amt = models.DecimalField(verbose_name='AP AMT', max_digits=10, decimal_places=2, default=0)
    bi_up = models.DecimalField(verbose_name='BI U/P', max_digits=10, decimal_places=2, default=0)
    bi_amt = models.DecimalField(verbose_name='BI AMT', max_digits=10, decimal_places=2, default=0)
    ft1_up = models.DecimalField(verbose_name='FT1 U/P', max_digits=10, decimal_places=2, default=0)
    ft1_amt = models.DecimalField(verbose_name='FT1 AMT', max_digits=10, decimal_places=2, default=0)
    ft2_up = models.DecimalField(verbose_name='FT2 U/P', max_digits=10, decimal_places=2, default=0)
    ft2_amt = models.DecimalField(verbose_name='FT2 AMT', max_digits=10, decimal_places=2, default=0)
    ft3_up = models.DecimalField(verbose_name='FT3 U/P', max_digits=10, decimal_places=2, default=0)
    ft3_amt = models.DecimalField(verbose_name='FT3 AMT', max_digits=10, decimal_places=2, default=0)
    ft4_up = models.DecimalField(verbose_name='FT4 U/P', max_digits=10, decimal_places=2, default=0)
    ft4_amt = models.DecimalField(verbose_name='FT4 AMT', max_digits=10, decimal_places=2, default=0)
    ft5_up = models.DecimalField(verbose_name='FT5 U/P', max_digits=10, decimal_places=2, default=0)
    ft5_amt = models.DecimalField(verbose_name='FT5 AMT', max_digits=10, decimal_places=2, default=0)
    ft6_up = models.DecimalField(verbose_name='FT6 U/P', max_digits=10, decimal_places=2, default=0)
    ft6_amt = models.DecimalField(verbose_name='FT6 AMT', max_digits=10, decimal_places=2, default=0)
    msp_up = models.DecimalField(verbose_name='MSP U/P', max_digits=10, decimal_places=2, default=0)
    msp_amt = models.DecimalField(verbose_name='MSP AMT', max_digits=10, decimal_places=2, default=0)
    ft_amt = models.DecimalField(verbose_name='TTL FT 加工费', max_digits=10, decimal_places=2, default=0)  # 后段成本之和
    ic_up = models.DecimalField(verbose_name='IC U/P', max_digits=10, decimal_places=2, default=0)
    die_up = models.DecimalField(verbose_name='Die U/P', max_digits=10, decimal_places=2, default=0)
    ft_up = models.DecimalField(verbose_name='FT U/P', max_digits=10, decimal_places=2, default=0)
    period = models.CharField(verbose_name='数据所属周期', max_length=20)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True)
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    objects = QuerySetManage()

    class Meta:
        db_table = 'pwm_cost_grain_price'
        verbose_name = '加工费维护记录'
        verbose_name_plural = verbose_name

    @property
    def user_name(self):
        if self.user:
            return self.user.username
        else:
            return None

    @property
    def subdivision(self):
        if self.grain:
            return self.grain.subdivision
        else:
            return None

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'
