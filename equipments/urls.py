from django.conf.urls import url
from equipments import views

urlpatterns = [
    url(r'^list$', views.EquipmentListGeneric.as_view()),
    url(r'^list/(?P<pk>\S+)$', views.EquipmentDetailGeneric.as_view()),
    url(r'^detail$', views.EquipmentDetail.as_view()),
    url(r'^install-template$', views.get_import_template),
    url(r'^import-base-data$', views.post_EquipmentData),
    url(r'^depreciation$', views.DepreciationListGeneric.as_view()),
    url(r'^depreciation/(?P<pk>[0-9]+)$', views.DepreciationDetailGeneric.as_view()),
    url(r'^borrow-apply$', views.BorrowListGeneric.as_view()),
    url(r'^borrow-apply/(?P<pk>[0-9]+)$', views.OperateBorrowRecordGeneric.as_view()),
    url(r'^allow-borrow-time$', views.get_AllowBorrowTime),
    url(r'^return-apply$', views.ReturnListGeneric.as_view()),
    url(r'^return-apply/(?P<pk>[0-9]+)$', views.OperateReturnApplyGeneric.as_view()),
    url(r'^broken-info$', views.BrokenInfoGeneric.as_view()),
    url(r'^broken-info/(?P<pk>[0-9]+)$', views.OperateBrokenInfoGeneric.as_view()),
    url(r'^calibration$', views.CalibrationInfoGeneric.as_view()),
    url(r'^calibration/(?P<pk>[0-9]+)$', views.OperateCalibrationInfoGeneric.as_view()),
    url(r'^maintenance$', views.MaintenanceGeneric.as_view()),
    url(r'^maintenance/(?P<pk>[0-9]+)$', views.OperateMaintenanceGeneric.as_view()),
]
