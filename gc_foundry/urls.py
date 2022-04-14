from django.conf.urls import url
from gc_foundry import views

urlpatterns = [
    url(r'^get-map-options$', views.get_map_options),
    url(r'^factory$', views.FactoryListGeneric.as_view()),
    url(r'^factory/(?P<pk>[0-9]+)$', views.FactoryDetailGeneric.as_view()),
    url(r'^machine-model$', views.ModelListGeneric.as_view()),
    url(r'^machine-model/(?P<pk>[0-9]+)$', views.ModelDetailGeneric.as_view()),
    url(r'^upload-image$', views.upload_image),
    url(r'^equipment$', views.FoundryEquipmentList.as_view()),
    url(r'^equipment/(?P<pk>[0-9]+)$', views.FoundryEquipmentDetail.as_view()),
    url(r'^tooling$', views.FoundryToolingList.as_view()),
    url(r'^tooling/(?P<pk>[0-9]+)$', views.FoundryToolingDetail.as_view()),
    url(r'^transfer$', views.FoundryTransferList.as_view()),
    url(r'^export-equipment-list$', views.export_equipment_list),
    url(r'^export-tooling-list$', views.export_tooling_list),
]
