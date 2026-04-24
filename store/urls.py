from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    path('',                                    views.storefront,        name='storefront'),
    path('plan/<int:tier_id>/',                 views.plan_detail_api,   name='plan_detail'),
    path('panier/',                             views.cart_view,         name='cart_view'),
    path('panier/ajouter/',                     views.cart_add,          name='cart_add'),
    path('panier/retirer/',                     views.cart_remove,       name='cart_remove'),
    path('checkout/',                           views.initiate_checkout, name='checkout'),
    path('commande/',                            views.plopplop_return,   name='plopplop_return'),
    path('commande/<str:order_ref>/',           views.order_confirm,     name='order_confirm'),
    path('commande/<str:order_ref>/status/',    views.order_status_api,  name='order_status'),
    path('partenaire/',                         views.partner_page,      name='partner'),
    # Google OAuth
    path('auth/google/',                        views.google_login,      name='google_login'),
    path('auth/google/callback/',               views.google_callback,   name='google_callback'),
    path('auth/logout/',                        views.store_logout,      name='store_logout'),
    # Profil
    path('mon-compte/',                         views.my_orders,         name='my_orders'),
    path('mon-compte/profil/',                  views.update_profile,    name='update_profile'),
]
