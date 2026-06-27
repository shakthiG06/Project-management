from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Auth urls
    path('register/', views.signup, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard url
    path('', views.dashboard, name='dashboard'),
    
    # Project urls
    path('projects/new/', views.project_create, name='project_create'),
    path('projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('projects/<int:pk>/edit/', views.project_edit, name='project_edit'),
    path('projects/<int:pk>/delete/', views.project_delete, name='project_delete'),
    
    # Milestone urls
    path('projects/<int:pk>/milestone/new/', views.milestone_create, name='milestone_create'),
    path('projects/<int:project_id>/milestone/<int:milestone_id>/toggle/', views.milestone_toggle, name='milestone_toggle'),
    path('projects/<int:project_id>/milestone/<int:milestone_id>/edit/', views.milestone_edit, name='milestone_edit'),
    path('projects/<int:project_id>/milestone/<int:milestone_id>/delete/', views.milestone_delete, name='milestone_delete'),
    
    # Document urls
    path('projects/<int:pk>/document/upload/', views.document_upload, name='document_upload'),
    path('projects/<int:project_id>/document/<int:document_id>/delete/', views.document_delete, name='document_delete'),
    
    # Task urls
    path('projects/<int:pk>/tasks/new/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:pk>/status/', views.task_status_update, name='task_status_update'),
    path('tasks/<int:pk>/comment/', views.comment_add, name='comment_add'),
    
    # Notification urls
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/read-all/', views.notifications_read_all, name='notifications_read_all'),
    
    # Reports url
    path('reports/', views.reports_view, name='reports_view'),
]
