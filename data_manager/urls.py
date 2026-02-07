from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('import-hub/', views.import_hub, name='import_hub'),
    path('sync-data/', views.sync_data, name='sync_data'),
    path('bulletin/', views.bulletin, name='bulletin'),
    path('scrape-hub/', views.scrape_hub, name='scrape_hub'),
    path('run-web-scraper/', views.run_web_scraper, name='run_web_scraper'),
    path('scrape-review/', views.scrape_review, name='scrape_review'),
    path('scrape-publish/', views.publish_scraped_data, name='publish_scraped_data'),
    
    # Generic Listings with type arg
    path('list/<str:data_type>/', views.listings, name='listings'),
    
    # Auth
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),
]
