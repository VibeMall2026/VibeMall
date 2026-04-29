from django.urls import path
from . import views

app_name = 'trading'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('settings/', views.settings_page, name='settings'),
    path('bot-control/', views.bot_control, name='bot_control'),
    path('update-settings/', views.update_settings, name='update_settings'),
    path('update-channels/', views.update_channels, name='update_channels'),
    path('modify-position/<int:position_id>/', views.modify_position, name='modify_position'),
    path('parse-signal/', views.parse_signal, name='parse_signal'),
]
