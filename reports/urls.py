from django.conf.urls import url
from reports import views

urlpatterns = [
    url(r'^usage-rate$', views.get_usage_rate),
    url(r'^use-detail$', views.get_use_detail),
    url(r'^maintenance-time$', views.get_maintenance_time),
    url(r'^broken-record$', views.get_broken_record),
    url(r'^use-fee$', views.get_equipment_fee),
]
