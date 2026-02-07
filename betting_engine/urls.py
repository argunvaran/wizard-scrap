from django.urls import path
from . import views

urlpatterns = [
    path('olustur/', views.coupon_create, name='coupon_create'),
    path('portfoy/', views.coupon_portfolio, name='coupon_portfolio'),
    path('liste/', views.coupon_list, name='coupon_list'),
    path('logs/', views.coupon_logs, name='coupon_logs'), # New Logging View
    path('sil/<int:pk>/', views.coupon_delete, name='coupon_delete'), # New Delete Action
    path('detay/<int:pk>/', views.coupon_detail, name='coupon_detail'),
    
    # Bilyoner Automation
    path('bilyoner/ayarlar/', views.bilyoner_settings, name='bilyoner_settings'),
    path('bilyoner/oyna/<int:pk>/', views.play_coupon_on_bilyoner, name='play_coupon_on_bilyoner'),
]
