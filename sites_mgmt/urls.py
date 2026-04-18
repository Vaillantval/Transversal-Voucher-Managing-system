from django.urls import path
from . import views

app_name = 'sites'

urlpatterns = [
    path('', views.site_list, name='list'),
    path('nouveau/', views.site_create, name='create'),
    path('<int:pk>/modifier/', views.site_edit, name='edit'),
    path('tarifs/', views.tier_list, name='tiers'),
    path('tarifs/nouveau/', views.tier_create, name='tier_create'),
    path('tarifs/<int:pk>/modifier/', views.tier_edit, name='tier_edit'),
    path('tarifs/<int:pk>/supprimer/', views.tier_delete, name='tier_delete'),
    path('api/<str:site_id>/stats/', views.site_stats_json, name='stats_json'),
    path('api/<str:site_id>/guests/', views.site_guests_json, name='guests_json'),
]
