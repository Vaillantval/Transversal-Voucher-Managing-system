from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_SUPERADMIN = 'superadmin'
    ROLE_SITE_ADMIN = 'site_admin'

    ROLE_CHOICES = [
        (ROLE_SUPERADMIN, 'Super Administrateur'),
        (ROLE_SITE_ADMIN, 'Administrateur de site'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_SITE_ADMIN,
        verbose_name='Rôle',
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name='Téléphone')

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    @property
    def is_superadmin(self):
        return self.role == self.ROLE_SUPERADMIN or self.is_superuser

    @property
    def is_site_admin(self):
        return self.role == self.ROLE_SITE_ADMIN

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
