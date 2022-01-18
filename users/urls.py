from django.conf.urls import url, include
from users import views
from rest_framework.routers import DefaultRouter
from rest_framework_jwt.views import obtain_jwt_token
from rest_framework_jwt.authentication import JSONWebTokenAuthentication

router = DefaultRouter()

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^login$', views.JwtLoginView.as_view()),
    # url(r'^login$', views.LoginView.as_view()),
    url(r'^logout$', views.LogoutView.as_view()),
    url(r'^register$', views.UserRegisterView.as_view()),
    url(r'^groups$', views.GroupListGeneric.as_view()),
    url(r'^roles$', views.RoleListGeneric.as_view()),
    url(r'^roles/(?P<pk>[0-9]+)', views.RoleDetailGeneric.as_view()),
    url(r'^sections$', views.SectionListGeneric.as_view()),
    url(r'^sections/(?P<pk>[0-9]+)', views.SectionDetailGeneric.as_view()),
    url(r'^users$', views.UserListGeneric.as_view()),
    url(r'^users/(?P<pk>[0-9]+)', views.UserDetailGeneric.as_view()),
    url(r'^change-password$', views.ChangePassword.as_view()),
    url(r'^operation-log$', views.OperationLogGeneric.as_view()),
]
