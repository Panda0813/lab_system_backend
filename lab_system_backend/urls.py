from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from equipments.views import ProjectListGeneric, ProjectDetailGeneric
from rest_framework.schemas import get_schema_view
from rest_framework_swagger.renderers import SwaggerUIRenderer, OpenAPIRenderer
from gc_foundry.views import CurrencyListGeneric, CurrencyDetailGeneric
from django.views.static import serve

from lab_system_backend.settings import MEDIA_ROOT

schema_view = get_schema_view(title='Lab System API', renderer_classes=[OpenAPIRenderer, SwaggerUIRenderer])

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^', include('users.urls')),
    url(r'^equipments/', include('equipments.urls')),
    url(r'^reports/', include('reports.urls')),
    url(r'^projects$', ProjectListGeneric.as_view()),
    url(r'^projects/(?P<pk>[0-9]+)$', ProjectDetailGeneric.as_view()),
    url(r'^gc-foundry/', include('gc_foundry.urls')),
    url(r'^currency$', CurrencyListGeneric.as_view()),
    url(r'^currency/(?P<pk>[0-9]+)$', CurrencyDetailGeneric.as_view()),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^docs/$', schema_view, name='docs'),
    url(r'^media/(?P<path>.*)$', serve, {'document_root': MEDIA_ROOT}),
]