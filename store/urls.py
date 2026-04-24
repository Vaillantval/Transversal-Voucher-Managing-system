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
    path('commande/<str:order_ref>/',           views.order_confirm,     name='order_confirm'),
    path('commande/<str:order_ref>/status/',    views.order_status_api,  name='order_status'),
    path('partenaire/',                         views.partner_page,      name='partner'),
]
