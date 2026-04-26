from django.urls import path
from . import boutique_views

app_name = 'boutique'

urlpatterns = [
    path('',                                  boutique_views.boutique_orders,         name='orders'),
    path('commandes/',                        boutique_views.boutique_orders,          name='orders_list'),
    path('commandes/<str:order_ref>/',        boutique_views.boutique_order_detail,    name='order_detail'),
    path('clients/',                          boutique_views.boutique_customers,       name='customers'),
    path('utilisateurs/',                     boutique_views.boutique_store_users,     name='store_users'),
    path('bannieres/',                        boutique_views.boutique_banners,         name='banners'),
    path('bannieres/creer/',                  boutique_views.boutique_banner_create,   name='banner_create'),
    path('bannieres/<int:pk>/modifier/',      boutique_views.boutique_banner_edit,     name='banner_edit'),
    path('bannieres/<int:pk>/supprimer/',     boutique_views.boutique_banner_delete,   name='banner_delete'),
    path('bannieres/<int:pk>/toggle/',        boutique_views.boutique_banner_toggle,   name='banner_toggle'),
    path('paniers/',                          boutique_views.boutique_carts,           name='carts'),
]
