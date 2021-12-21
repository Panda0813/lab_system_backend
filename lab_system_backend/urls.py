from django.conf.urls import url
from django.contrib import admin
from django.urls import path, include
from equipments import views
from rest_framework.schemas import get_schema_view
from rest_framework_swagger.renderers import SwaggerUIRenderer, OpenAPIRenderer

schema_view = get_schema_view(title='Lab System API', renderer_classes=[OpenAPIRenderer, SwaggerUIRenderer])

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^', include('users.urls')),
    url(r'^equipments/', include('equipments.urls')),
    url(r'^reports/', include('reports.urls')),
    url(r'^projects$', views.ProjectListGeneric.as_view()),
    url(r'^projects/(?P<pk>[0-9]+)$', views.ProjectDetailGeneric.as_view()),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^docs/$', schema_view, name='docs'),
]
