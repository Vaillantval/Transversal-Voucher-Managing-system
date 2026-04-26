from django.urls import path
from . import boutique_views

app_name = 'boutique'

urlpatterns = [
    path('',                            boutique_views.boutique_orders,       name='orders'),
    path('commandes/',                  boutique_views.boutique_orders,        name='orders_list'),
    path('commandes/<str:order_ref>/',  boutique_views.boutique_order_detail,  name='order_detail'),
    path('clients/',                    boutique_views.boutique_customers,     name='customers'),
    path('utilisateurs/',               boutique_views.boutique_store_users,   name='store_users'),
    path('bannieres/',                  boutique_views.boutique_banners,       name='banners'),
    path('paniers/',                    boutique_views.boutique_carts,         name='carts'),
]
