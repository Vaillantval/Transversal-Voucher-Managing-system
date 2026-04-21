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
    path('configuration/', views.config_edit, name='config'),
    # Partenaires (admin)
    path('configuration/partenaires/',                       views.partners_view,   name='partners'),
    path('configuration/partenaires/<int:pk>/approuver/',    views.partner_approve, name='partner_approve'),
    path('configuration/partenaires/<int:pk>/rejeter/',      views.partner_reject,  name='partner_reject'),
    # Produits partenaires
    path('configuration/partenaires/produits/',              views.product_list,    name='product_list'),
    path('configuration/partenaires/produits/nouveau/',      views.product_create,  name='product_create'),
    path('configuration/partenaires/produits/<int:pk>/modifier/',  views.product_edit,   name='product_edit'),
    path('configuration/partenaires/produits/<int:pk>/supprimer/', views.product_delete, name='product_delete'),
]
