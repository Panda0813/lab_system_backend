from django.conf.urls import url
from fba_estimate import views

urlpatterns = [
    url(r'^get-service-tree$', views.get_service_tree),
    url(r'^get-service-select$', views.get_service_select),
    url(r'^first-service$', views.FirstServiceList.as_view()),
    url(r'^first-service/(?P<pk>[0-9]+)$', views.FirstServiceDetail.as_view()),
    url(r'^second-service$', views.SecondServiceList.as_view()),
    url(r'^second-service/(?P<pk>[0-9]+)$', views.SecondServiceDetail.as_view()),
    url(r'^company$', views.CompanyList.as_view()),
    url(r'^company/(?P<pk>[0-9]+)$', views.CompanyDetail.as_view()),
    url(r'^get-company$', views.get_company),
    url(r'^option$', views.EstimateOptionList.as_view()),
    url(r'^option/(?P<pk>[0-9]+)$', views.EstimateOptionDetail.as_view()),
    url(r'^surplus$', views.CapitalSurplusList.as_view()),
    url(r'^surplus/(?P<pk>[0-9]+)$', views.CapitalSurplusDetail.as_view()),
    url(r'^get-last-month-surplus$', views.get_last_month_surplus),
    url(r'^get-write-option$', views.get_write_option),
    url(r'^month-detail$', views.MonthDetailList.as_view()),
    url(r'^month-detail/(?P<pk>[0-9]+)$', views.MonthDetailOperate.as_view()),
    url(r'^month-future$', views.MonthFutureList.as_view()),
    url(r'^month-future/(?P<pk>[0-9]+)$', views.MonthFutureOperate.as_view()),
    url(r'^export-detail$', views.export_month_detail),
    url(r'^export-monitor$', views.export_month_monitor),
]
