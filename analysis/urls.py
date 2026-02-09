from django.urls import path
from . import views

urlpatterns = [
    path('', views.analysis_dashboard, name='analysis_dashboard'),
    path('analyze/<str:unique_key>/', views.analyze_match, name='analyze_match'),
    path('analyze/advanced/<str:unique_key>/', views.analyze_match_advanced, name='analyze_match_advanced'),
    path('ask-ai/<str:unique_key>/', views.ask_gemini_analysis, name='ask_gemini_analysis'),
    path('api/push-bulletin/', views.receive_external_bulletin, name='push_bulletin'),
    path('scrape-local-push/', views.scrape_local_and_push_view, name='scrape_local_push'),
]
