from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',                          views.login_view,   name='login'),
    path('logout/',                         views.logout_view,  name='logout'),
    path('profil/',                         views.profile_view, name='profile'),
    path('utilisateurs/',                   views.user_list,    name='users'),
    path('utilisateurs/<int:pk>/modifier/', views.user_edit,    name='user_edit'),
    path('utilisateurs/<int:pk>/supprimer/',views.user_delete,  name='user_delete'),
]
