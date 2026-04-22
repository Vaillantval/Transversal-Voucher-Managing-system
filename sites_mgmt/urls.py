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
    path('tarifs/<int:pk>/sites/<int:site_pk>/retirer/', views.tier_remove_site, name='tier_remove_site'),
    path('tarifs/admin/nouveau/', views.tier_admin_create, name='tier_admin_create'),
    path('tarifs/admin/<int:pk>/modifier/', views.tier_admin_edit, name='tier_admin_edit'),
    path('tarifs/remplacements/', views.tier_replacement_list, name='tier_replacement_list'),
    path('tarifs/remplacements/nouveau/', views.tier_replacement_create, name='tier_replacement_create'),
    path('api/<str:site_id>/stats/', views.site_stats_json, name='stats_json'),
    path('api/<str:site_id>/guests/', views.site_guests_json, name='guests_json'),
    path('configuration/', views.config_edit, name='config'),
    path('configuration/conditions/preview/', views.conditions_pdf_preview, name='conditions_pdf_preview'),
    path('configuration/conditions/confirmer/', views.conditions_pdf_confirm, name='conditions_pdf_confirm'),
    path('configuration/conditions/supprimer/', views.conditions_delete, name='conditions_delete'),
    # Partenaires (admin)
    path('configuration/partenaires/',                       views.partners_view,   name='partners'),
    path('configuration/partenaires/<int:pk>/approuver/',    views.partner_approve, name='partner_approve'),
    path('configuration/partenaires/<int:pk>/rejeter/',      views.partner_reject,  name='partner_reject'),
    # Produits partenaires
    path('configuration/partenaires/produits/',                           views.product_list,         name='product_list'),
    path('configuration/partenaires/produits/nouveau/',                   views.product_create,       name='product_create'),
    path('configuration/partenaires/produits/<int:pk>/',                  views.product_detail,       name='product_detail'),
    path('configuration/partenaires/produits/<int:pk>/modifier/',         views.product_edit,         name='product_edit'),
    path('configuration/partenaires/produits/<int:pk>/supprimer/',        views.product_delete,       name='product_delete'),
    path('configuration/partenaires/produits/images/<int:pk>/supprimer/', views.product_image_delete, name='product_image_delete'),
]
