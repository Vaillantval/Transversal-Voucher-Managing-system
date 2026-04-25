from django.urls import path
from . import views

app_name = 'vouchers'

urlpatterns = [
    path('', views.voucher_list, name='list'),
    path('creer/', views.voucher_create, name='create'),
    path('recherche/', views.voucher_search, name='search'),
    path('<str:unifi_id>/supprimer/', views.voucher_delete, name='delete'),
    path('sync/<int:site_pk>/', views.sync_vouchers, name='sync'),
]
