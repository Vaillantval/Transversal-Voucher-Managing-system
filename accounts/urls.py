from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',                          views.login_view,   name='login'),
    path('logout/',                         views.logout_view,  name='logout'),
    path('profil/',                         views.profile_view, name='profile'),
    path('utilisateurs/',                   views.user_list,    name='users'),
    path('utilisateurs/<int:pk>/modifier/', views.user_edit,    name='user_edit'),
    path('utilisateurs/<int:pk>/supprimer/',views.user_delete,      name='user_delete'),
    # Partenaires (public)
    path('partenaire/',                     views.partner_register, name='partner_register'),
    path('partenaire/merci/',               views.partner_success,  name='partner_success'),
    path('partenaire/produit/<int:pk>/',    views.product_public,   name='product_public'),
]
