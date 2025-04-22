# reddit_profile_analyzer/urls.py
from django.urls import path
from . import views
from .views import RedditProfileAnalyzerView, dashboard_view

urlpatterns = [
    path('dashboard/', dashboard_view, name='dashboard'),
    path('upload/', views.RedditProfileAnalyzerView.as_view(), name='reddit_profile_analyzer_upload'),
    path('analyze/', views.RedditProfileAnalyzerView.as_view(), name='reddit_profile_analyzer_analyze'), # You might combine upload and analyze in one view
    path('export/', views.export_to_excel_view, name='reddit_profile_analyzer_export'),
    
    
]