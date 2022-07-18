from django.conf.urls import url
from equipments import views

urlpatterns = [
    url(r'^equip-list$', views.get_equipment_list),
    url(r'^list$', views.EquipmentListGeneric.as_view()),
    url(r'^list/(?P<pk>\S+)$', views.EquipmentDetailGeneric.as_view()),
    url(r'^detail$', views.EquipmentDetail.as_view()),
    url(r'^upload-template$', views.get_upload_template),
    url(r'^import-base-data$', views.post_EquipmentData),
    url(r'^get-deposit-position$', views.get_deposit_position),
    url(r'^equipment-exist$', views.query_equip_exist),
    url(r'^get-map-options$', views.get_map_options),
    url(r'^get-category$', views.get_category),
    url(r'^depreciation$', views.DepreciationListGeneric.as_view()),
    url(r'^depreciation/(?P<pk>[0-9]+)$', views.DepreciationDetailGeneric.as_view()),

    # url(r'^borrow-apply$', views.BorrowListGeneric.as_view()),
    # url(r'^borrow-apply/(?P<pk>[0-9]+)$', views.OperateBorrowRecordGeneric.as_view()),
    # url(r'^allow-borrow-time$', views.get_AllowBorrowTime),
    # 无审批版本接口
    url(r'^borrow-apply$', views.BorrowListNoCheck.as_view()),
    url(r'^borrow-apply/(?P<pk>[0-9]+)$', views.OperateBorrowRecordNoCheck.as_view()),
    url(r'^allow-borrow-time$', views.allow_borrow_time_public),

    url(r'^return-apply$', views.ReturnListGeneric.as_view()),
    url(r'^return-apply/(?P<pk>[0-9]+)$', views.OperateReturnApplyGeneric.as_view()),
    url(r'^broken-info$', views.BrokenInfoGeneric.as_view()),
    url(r'^broken-info/(?P<pk>[0-9]+)$', views.OperateBrokenInfoGeneric.as_view()),
    url(r'^calibration$', views.CalibrationInfoGeneric.as_view()),
    url(r'^calibration/(?P<pk>[0-9]+)$', views.OperateCalibrationInfoGeneric.as_view()),
    url(r'^upload-calibration$', views.post_calibration),
    url(r'^certificate$', views.CertificateGeneric.as_view()),
    url(r'^certificate/(?P<pk>[0-9]+)$', views.OperateCertificateGeneric.as_view()),
    url(r'^upload-certificate$', views.post_batch_certificate),
    url(r'^add-certificate$', views.add_certificate),
    url(r'^maintenance$', views.MaintenanceGeneric.as_view()),
    url(r'^maintenance/(?P<pk>[0-9]+)$', views.OperateMaintenanceGeneric.as_view()),
    url(r'^maintain$', views.MaintainInfoGeneric.as_view()),
    url(r'^maintain/(?P<pk>[0-9]+)$', views.OperateMaintainInfoGeneric.as_view()),
    url(r'^upload-maintain$', views.post_maintain),
]
