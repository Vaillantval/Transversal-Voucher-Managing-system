from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_index, name='index'),
    path('csv/', views.export_csv, name='csv'),
    path('excel/', views.export_excel, name='excel'),
    path('pdf/', views.export_pdf, name='pdf'),
]
