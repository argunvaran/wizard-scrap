from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='automation_dashboard'),
    path('workflows/', views.workflow_list, name='workflow_list'),
    path('workflow/create/', views.workflow_create, name='workflow_create'),
    path('workflow/<int:pk>/', views.workflow_detail, name='workflow_detail'),
    path('workflow/<int:pk>/run/', views.workflow_run, name='workflow_run'),
    path('workflow/<int:pk>/delete/', views.workflow_delete, name='workflow_delete'),
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/<int:pk>/run/', views.task_run_direct, name='task_run_direct'),
    path('fetch/<str:country>/<str:data_type>/', views.fetch_data_view, name='fetch_data_view'),
    path('preview/', views.data_preview_view, name='data_preview_view'),
    path('commit/', views.data_commit_view, name='data_commit_view'),
    path('sync/', views.sync_tasks, name='sync_tasks'),
    path('logs/', views.task_log_list, name='task_log_list'),
]
