from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth
from portal import views, maintenance
urlpatterns = [
    path('maintenance/', maintenance.workspace, name='maintenance_workspace'),
    path('api/maintenance/context/', maintenance.context, name='maintenance_context'),
    path('api/maintenance/requests/', maintenance.collection, name='maintenance_collection'),
    path('api/maintenance/requests/<uuid:job_id>/', maintenance.detail, name='maintenance_detail'),
    path('verify/resend/',views.resend_verification,name='resend_verification'),
    path('',views.dashboard,name='dashboard'),path('register/',views.register,name='register'),
    path('login/',views.PortalLogin.as_view(),name='login'),path('logout/',auth.LogoutView.as_view(),name='logout'),
    path('team/invite/',views.invite_pm,name='invite_pm'),path('properties/new/',views.property_edit,name='property_new'),
    path('properties/<uuid:pid>/edit/',views.property_edit,name='property_edit'),path('properties/<uuid:pid>/tenant/',views.invite_tenant,name='invite_tenant'),
    path('invitation/<str:token>/',views.accept_invitation,name='accept_invitation'),
    path('password/reset/',views.PortalPasswordReset.as_view(),name='password_reset'),path('password/reset/sent/',auth.PasswordResetDoneView.as_view(),name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/',auth.PasswordResetConfirmView.as_view(success_url=reverse_lazy('password_reset_complete')),name='password_reset_confirm'),
    path('password/reset/complete/',auth.PasswordResetCompleteView.as_view(),name='password_reset_complete'),
]
