from django.db import models
from users.models import User, Section


class QuerySetManage(models.Manager):
    def get_queryset(self):
        return super(QuerySetManage, self).get_queryset().filter(is_delete=False)


class Project(models.Model):
    name = models.CharField(max_length=100, verbose_name='项目名称')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    objects = QuerySetManage()

    class Meta:
        db_table = 'project'
        verbose_name = '项目表'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


# class Equipment(models.Model):
#     FIXED_ASSET_CATEGORYS = (
#         (1, 'APT MB & SLT System'),
#         (2, 'ATE Tester'),
#         (3, 'Device Test Tooling'),
#         (4, 'Facility Equipment & Tool'),
#         (5, 'Inspection & Rework'),
#         (6, 'Measurement & Intrumentation'),
#         (7, 'Other Tool, Jig & Kit'),
#         (8, 'Probe, Tip & Assembly'),
#         (9, 'Reliability & Environment'),
#         (10, 'Tester Cell Machine')
#     )
#     EQUIPMENT_STATES = (
#         (1, '待用'),
#         (2, '使用中'),
#         # (3, '已送检'),
#         (4, '代管'),
#         (5, '维护中'),
#         (6, '闲置'),
#         (7, '报废')
#     )
#
#     id = models.CharField(max_length=60, verbose_name='设备仪器ID', primary_key=True)
#     name = models.CharField(max_length=100, verbose_name='设备名称')
#     number = models.IntegerField(verbose_name='资产数量', default=1)
#     serial_number = models.CharField(max_length=50, verbose_name='序列号', null=True, blank=True)
#     fixed_asset_code = models.CharField(max_length=50, verbose_name='固定资产编码', null=True, blank=True)
#     fixed_asset_name = models.CharField(max_length=100, verbose_name='固定资产名称', null=True, blank=True)
#     fixed_asset_category = models.IntegerField(choices=FIXED_ASSET_CATEGORYS, default=3, verbose_name='固定资产类别')
#     specification = models.CharField(max_length=100, verbose_name='规格型号描述', null=True, blank=True)
#     performance = models.TextField(verbose_name='主要性能', null=True, blank=True)
#     purpose = models.CharField(max_length=200, verbose_name='用途', null=True, blank=True)
#     default_borrow_hours = models.IntegerField(verbose_name='默认可借用时长(H)', null=True, blank=True)
#     allow_borrow_days = models.IntegerField(verbose_name='最长可借用天数(Day)', null=True, blank=True)
#     per_hour_price = models.DecimalField(verbose_name='每小时使用单价', max_digits=10, decimal_places=2, null=True, blank=True)  # 预留
#     is_allow_renew = models.BooleanField(verbose_name='能否续借', default=False)
#     deposit_position = models.CharField(max_length=100, verbose_name='存放地点')
#     manufacturer = models.CharField(max_length=50, verbose_name='制造商', null=True, blank=True)
#     manufacture_date = models.CharField(max_length=20, verbose_name='制造日期', null=True, blank=True)
#     custodian = models.CharField(max_length=20, verbose_name='保管人', null=True, blank=True)
#     equipment_state = models.IntegerField(choices=EQUIPMENT_STATES, default=1, verbose_name='设备状态')
#     usage_description = models.CharField(max_length=200, verbose_name='使用/故障情况说明', null=True, blank=True)
#     dispose_suggestion = models.CharField(max_length=200, verbose_name='处理建议', null=True, blank=True)
#     application_specialist = models.CharField(max_length=60, verbose_name='应用技术支持专家', null=True, blank=True)
#     user_manual = models.CharField(max_length=100, verbose_name='使用手册地址', null=True, blank=True)
#     license = models.CharField(max_length=100, verbose_name='配套软件与许可证', null=True, blank=True)
#     purchase_date = models.CharField(max_length=20, verbose_name='采购日期', null=True, blank=True)
#     purchase_cost = models.DecimalField(verbose_name='采购成本', max_digits=16, decimal_places=2, null=True, blank=True)
#     entry_date = models.CharField(max_length=20, verbose_name='财务入账日期', null=True, blank=True)
#     original_cost = models.DecimalField(verbose_name='资产原值', max_digits=16, decimal_places=2, null=True, blank=True)
#     estimate_life = models.IntegerField(verbose_name='预计使用期间数', null=True, blank=True)
#     net_salvage = models.DecimalField(verbose_name='预计净残值', max_digits=16, decimal_places=2, null=True, blank=True)
#     create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
#     update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
#     remarks = models.TextField(verbose_name='备注', null=True)
#     is_delete = models.BooleanField(default=False, verbose_name='是否删除')
#
#     # objects = QuerySetManage()
#
#     class Meta:
#         db_table = 'equipment'
#         verbose_name = '设备基础数据表'
#         verbose_name_plural = verbose_name
#
#     def __str__(self):
#         return self.id
#
#     def delete(self, using=None, keep_parents=False):
#         self.is_delete = True
#         self.save()
#         return 'delete success'


class Equipment(models.Model):
    FIXED_ASSET_CATEGORYS = (
        (1, 'ATE Tester'),
        (2, 'Tester Cell Machine'),
        (3, 'Reliability & Environment'),
        (4, 'Measurement & Intrumentation'),
        (5, 'Probe, Tip & Assembly'),
        (6, 'Device Test Tooling'),
        (7, 'Inspection & Rework'),
        (8, 'Other Tool, Jig & Kit'),
        (9, 'Facility Equipment & Tool'),
        (10, 'APT MB & SLT System')
    )
    EQUIPMENT_STATES = (
        (1, '可用'),
        (2, '使用中'),
        (3, '维护中'),
        (4, '停用'),
        (5, '代管'),
        (6, '报废')
    )
    SERVICE_TYPES = (
        (1, '不可用'),
        (2, '领用'),
        (3, '随用'),
        (4, '预约'),
        (5, '专用')
    )
    MANAGE_TYPES = (
        (1, 'PM'),
        (2, 'Check'),
        (3, 'Inspection')
    )

    id = models.CharField(max_length=60, verbose_name='设备仪器ID', primary_key=True)
    name = models.CharField(max_length=100, verbose_name='设备名称', null=True)
    number = models.IntegerField(verbose_name='数量', default=1)
    serial_number = models.CharField(max_length=50, verbose_name='序列号', null=True, blank=True)
    fixed_asset_code = models.CharField(max_length=50, verbose_name='固定资产编号', null=True, blank=True)
    fixed_asset_category = models.IntegerField(choices=FIXED_ASSET_CATEGORYS, null=True, verbose_name='类别')
    custodian = models.CharField(max_length=20, verbose_name='固定资产保管人', null=True, blank=True)
    equipment_state = models.IntegerField(choices=EQUIPMENT_STATES, null=True, verbose_name='设备状态')
    service_type = models.IntegerField(choices=SERVICE_TYPES, null=True, verbose_name='管理方式')
    specification = models.TextField(verbose_name='技术指标', null=True, blank=True)
    performance = models.TextField(verbose_name='主要功能和应用领域', null=True, blank=True)
    assort_material = models.TextField(verbose_name='配套设备器材', null=True, blank=True)
    allow_borrow_days = models.IntegerField(verbose_name='最长可借用天数(Day)', null=True, blank=True)
    per_hour_price = models.DecimalField(verbose_name='每小时使用单价', max_digits=10, decimal_places=2, null=True, blank=True)  # 预留
    deposit_position = models.CharField(max_length=100, verbose_name='存放地点', null=True)
    install_date = models.CharField(max_length=20, verbose_name='安装日期', null=True, blank=True)
    manage_type = models.IntegerField(verbose_name='管理方式', choices=MANAGE_TYPES, null=True)
    manager = models.CharField(max_length=20, verbose_name='管理人', null=True, blank=True)
    application_specialist = models.CharField(max_length=100, verbose_name='应用技术专家', null=True, blank=True)
    manufacturer = models.CharField(max_length=50, verbose_name='制造商', null=True, blank=True)
    manufacture_date = models.CharField(max_length=20, verbose_name='生产日期', null=True, blank=True)
    origin_place = models.CharField(max_length=50, verbose_name='原产地', null=True, blank=True)
    user_manual = models.CharField(max_length=100, verbose_name='使用手册地址', null=True, blank=True)
    license = models.CharField(max_length=100, verbose_name='配套软件与许可证', null=True, blank=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    remarks = models.TextField(verbose_name='备注', null=True)
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    # objects = QuerySetManage()

    class Meta:
        db_table = 'equipment'
        verbose_name = '设备基础数据表'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.id

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class ExtendAttribute(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, verbose_name='设备')
    attribute_name = models.CharField(max_length=100, verbose_name='属性名称')
    attribute_value = models.CharField(max_length=200, verbose_name='属性值')

    class Meta:
        unique_together = (
            ('equipment', 'attribute_name')
        )
        db_table = 'equipment_extend_attribute'
        verbose_name = '设备扩展属性表'
        verbose_name_plural = verbose_name


class EquipmentDepreciationRecord(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, verbose_name='设备')
    method = models.CharField(max_length=50, verbose_name='折旧方法', default='平均年限法(基于净值)')
    periods = models.IntegerField(verbose_name='已折旧期间数')
    depreciated_total = models.DecimalField(verbose_name='累计折旧值', max_digits=16, decimal_places=2)
    net_value = models.DecimalField(verbose_name='净值', max_digits=16, decimal_places=2)
    net_amount = models.DecimalField(verbose_name='净额', max_digits=16, decimal_places=2)
    depreciate_date = models.CharField(max_length=20, verbose_name='折旧日期')
    create_time = models.DateTimeField(verbose_name='生成时间', auto_now_add=True)

    class Meta:
        db_table = 'equipment_depreciation_record'
        verbose_name = '资产折旧记录表'
        verbose_name_plural = verbose_name

    @property
    def equipment_name(self):
        if self.equipment:
            return self.equipment.name
        else:
            return None


class EquipmentBorrowRecord(models.Model):
    BORROW_TYPE = (
        ('正常申请', '正常申请'),
        ('紧急申请', '紧急申请'),
        ('恢复中断', '恢复中断'),
        ('续借', '续借')
    )
    CONFIRM_STATE = (
        ('正常', '正常'),
        ('损坏', '损坏')
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='借用人')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, verbose_name='项目')
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, verbose_name='设备')
    start_time = models.DateTimeField(verbose_name='借用开始时间')
    end_time = models.DateTimeField(verbose_name='借用结束时间')
    borrow_type = models.CharField(verbose_name='借用类型', choices=BORROW_TYPE, default=BORROW_TYPE[0][0], max_length=20)
    is_approval = models.IntegerField(default=0, verbose_name='是否批准')  # 0 待审核, 1 已批准， 2 已拒绝
    refuse_reason = models.CharField(max_length=100, verbose_name='拒绝原因', null=True)
    is_borrow = models.BooleanField(default=False, verbose_name='是否借用成功')
    remarks = models.TextField(verbose_name='备注', null=True)
    is_interrupted = models.BooleanField(default=False, verbose_name='借用是否被中断')
    is_recovery_interrupt = models.BooleanField(default=False, verbose_name='是否已恢复中断')
    actual_end_time = models.DateTimeField(verbose_name='实际借用结束时间', null=True)
    expect_usage_time = models.DecimalField(max_digits=6, decimal_places=2, verbose_name='预计使用时长', null=True)
    actual_usage_time = models.DecimalField(max_digits=6, decimal_places=2, verbose_name='实际使用时长', null=True)
    per_hour_price = models.DecimalField(verbose_name='每小时使用单价', max_digits=10, decimal_places=2, null=True,
                                         blank=True)  # 预留, 每次借用记录中存当前最新的费用
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='使用总计费', null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)
    is_final_remind = models.BooleanField(default=False, verbose_name='是否已提醒临期')
    is_overtime_remind = models.BooleanField(default=False, verbose_name='是否已提醒超时')
    is_return = models.IntegerField(default=0, verbose_name='是否已归还')  # 0 未归还，1 待确认，2 已归还
    return_position = models.CharField(max_length=100, verbose_name='归还位置', null=True)
    return_confirm_state = models.CharField(verbose_name='归还确认结果', max_length=20, choices=CONFIRM_STATE, null=True)
    is_delete = models.BooleanField(default=False, verbose_name='是否删除')

    objects = QuerySetManage()

    class Meta:
        db_table = 'equipment_borrow_record'
        verbose_name = '设备借用记录表'
        verbose_name_plural = verbose_name

    @property
    def user_name(self):
        if self.user:
            return self.user.username
        else:
            return None

    @property
    def section_name(self):
        if self.user:
            return self.user.section_name
        else:
            return None

    @property
    def project_name(self):
        if self.project:
            return self.project.name
        else:
            return None

    @property
    def equipment_name(self):
        if self.equipment:
            return self.equipment.name
        else:
            return None

    def delete(self, using=None, keep_parents=False):
        self.is_delete = True
        self.save()
        return 'delete success'


class EquipmentReturnRecord(models.Model):
    CONFIRM_STATE = (
        ('正常', '正常'),
        ('损坏', '损坏')
    )
    # positions = list(Equipment.objects.values('deposit_position').distinct())
    # RETURN_POSITION = tuple([(p['deposit_position'], p['deposit_position']) for p in positions])

    borrow_record = models.OneToOneField(EquipmentBorrowRecord, on_delete=models.CASCADE, verbose_name='借用记录')
    # TODO 后面正式环境申请归还时，已提交时间作为归还时间auto_now_add=True
    return_time = models.DateTimeField(verbose_name='归还时间')
    return_position = models.CharField(max_length=100, verbose_name='归还位置')
    is_confirm = models.BooleanField(verbose_name='管理员是否确认', default=False)
    confirm_state = models.CharField(verbose_name='确认结果', max_length=20, choices=CONFIRM_STATE, null=True)
    remarks = models.TextField(verbose_name='备注', null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)

    class Meta:
        db_table = 'equipment_return_record'
        verbose_name = '设备归还记录表'
        verbose_name_plural = verbose_name

    @property
    def user_name(self):
        if self.borrow_record:
            return self.borrow_record.user.username
        else:
            return None

    @property
    def section_name(self):
        if self.borrow_record:
            return self.borrow_record.section_name
        else:
            return None

    @property
    def project_name(self):
        if self.borrow_record:
            return self.borrow_record.project.name
        else:
            return None

    @property
    def equipment(self):
        if self.borrow_record:
            return self.borrow_record.equipment.id
        else:
            return None

    @property
    def equipment_name(self):
        if self.borrow_record:
            return self.borrow_record.equipment.name
        else:
            return None


class EquipmentBrokenInfo(models.Model):
    EVALUATION_RESULT = (
        ('故障', '故障'),
        ('闲置', '闲置'),
        ('报废', '报废')
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='损坏人')
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, verbose_name='设备')
    broken_time = models.DateTimeField(verbose_name='损坏时间')
    broken_reason = models.CharField(verbose_name='损坏原因', max_length=200, null=True)
    image_path = models.CharField(verbose_name='损坏图片/视频地址', max_length=100, null=True)
    evaluation_result = models.CharField(verbose_name='评估结果', max_length=20, choices=EVALUATION_RESULT, null=True)
    maintenance_plan = models.TextField(verbose_name='维修计划', null=True)
    is_maintenance = models.BooleanField(verbose_name='是否已维修', default=False)
    remarks = models.TextField(verbose_name='备注', null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)

    class Meta:
        db_table = 'equipment_broken_info'
        verbose_name = '设备损坏信息表'
        verbose_name_plural = verbose_name

    @property
    def user_name(self):
        if self.user:
            return self.user.username
        else:
            return None

    @property
    def section_name(self):
        if self.user:
            return self.user.section_name
        else:
            return None

    @property
    def equipment_name(self):
        if self.equipment:
            return self.equipment.name
        else:
            return None


class EquipmentCalibrationInfo(models.Model):
    STATE = (
        ('校验完成', '校验完成'),
        ('待送检', '待送检'),
        ('已送检', '已送检')
    )

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, verbose_name='设备')
    specification = models.CharField(verbose_name='校准规范', max_length=200, null=True)
    environment = models.CharField(verbose_name='环境要求', max_length=100, null=True)
    calibration_cycle = models.IntegerField(verbose_name='校准周期(月)', default=12)
    calibration_time = models.DateField(verbose_name='校准日期', null=True)
    recalibration_time = models.DateField(verbose_name='再校准日期', null=True)
    due_date = models.CharField(verbose_name='到期日', max_length=50, null=True)
    state = models.CharField(verbose_name='校验状态', max_length=20, choices=STATE, null=True)
    remarks = models.TextField(verbose_name='备注', null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)

    class Meta:
        db_table = 'equipment_calibration_info'
        verbose_name = '设备校验信息表'
        verbose_name_plural = verbose_name

    @property
    def equipment_name(self):
        if self.equipment:
            return self.equipment.name
        else:
            return None

    @property
    def equipment_state(self):
        if self.equipment:
            return self.equipment.equipment_state
        else:
            return None

    @property
    def certificate_set(self):
        if self.equipment:
            return self.equipment.equipmentcalibrationcertificate_set.order_by('certificate_year').\
                                values('id', 'certificate_year', 'certificate')
        else:
            return None


class EquipmentCalibrationCertificate(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, verbose_name='设备')
    certificate_year = models.CharField(verbose_name='校准年份', max_length=10)
    certificate = models.CharField(verbose_name='校准报告', max_length=100, null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)

    class Meta:
        db_table = 'equipment_calibration_certificate'
        verbose_name = '设备校验报告表'
        verbose_name_plural = verbose_name


class EquipmentMaintenanceRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, verbose_name='使用人', null=True)
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, verbose_name='设备')
    fault_description = models.TextField(verbose_name='故障现象描述', null=True)
    reason_measure = models.TextField(verbose_name='原因和采取措施', null=True)
    down_time = models.DateTimeField(verbose_name='停机开始时间')
    up_time = models.DateTimeField(verbose_name='停机结束时间')
    maintenance_hours = models.DecimalField(verbose_name='维修耗时(H)', max_digits=6, decimal_places=2)
    maintenance_user = models.CharField(verbose_name='响应者', max_length=50)
    broken_part_code = models.CharField(verbose_name='坏板序列号', max_length=100, null=True)
    broken_part_cost = models.CharField(verbose_name='坏板委外维修费', max_length=50, null=True)
    remarks = models.TextField(verbose_name='备注', null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)

    class Meta:
        db_table = 'equipment_maintenance_record'
        verbose_name = '设备维修记录表'
        verbose_name_plural = verbose_name

    @property
    def user_name(self):
        if self.user:
            return self.user.username
        else:
            return None

    @property
    def equipment_name(self):
        if self.equipment:
            return self.equipment.name
        else:
            return None


class EquipmentMaintainInfo(models.Model):
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, verbose_name='设备')
    calibration_time = models.DateField(verbose_name='校准日期', null=True)
    recalibration_time = models.DateField(verbose_name='再校准日期', null=True)
    due_date = models.CharField(verbose_name='离PM-Y时间', max_length=50, null=True)
    pm_q1 = models.CharField(verbose_name='PM-Q1', max_length=20, null=True)
    pm_q2 = models.CharField(verbose_name='PM-Q2', max_length=20, null=True)
    pm_q3 = models.CharField(verbose_name='PM-Q3', max_length=20, null=True)
    pm_q4 = models.CharField(verbose_name='PM-Q4', max_length=20, null=True)
    remarks = models.TextField(verbose_name='备注', null=True)
    create_time = models.DateTimeField(verbose_name='添加时间', auto_now_add=True)
    update_time = models.DateTimeField(verbose_name='更新时间', auto_now=True, auto_now_add=False)

    class Meta:
        db_table = 'equipment_maintain_info'
        verbose_name = '设备定期维护表'
        verbose_name_plural = verbose_name

    @property
    def equipment_name(self):
        if self.equipment:
            return self.equipment.name
        else:
            return None

    @property
    def equipment_state(self):
        if self.equipment:
            return self.equipment.equipment_state
        else:
            return None
