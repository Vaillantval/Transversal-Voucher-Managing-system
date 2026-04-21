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


class PartnerApplication(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING,  'En attente'),
        (STATUS_APPROVED, 'Approuvé'),
        (STATUS_REJECTED, 'Rejeté'),
    ]

    first_name          = models.CharField(max_length=100, verbose_name='Prénom')
    last_name           = models.CharField(max_length=100, verbose_name='Nom')
    email               = models.EmailField(unique=True, verbose_name='Email')
    address             = models.TextField(verbose_name='Adresse')
    phone               = models.CharField(max_length=30, verbose_name='Téléphone')
    accepted_equipment  = models.BooleanField(default=False, verbose_name='Détient équipement réseau')
    accepted_conditions = models.BooleanField(default=False, verbose_name='Accepte les conditions')
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='Statut')
    user                = models.OneToOneField(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='partner_application', verbose_name='Compte créé',
    )
    admin_notes         = models.TextField(blank=True, verbose_name='Notes admin')
    created_at          = models.DateTimeField(auto_now_add=True)
    reviewed_at         = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name          = 'Demande partenaire'
        verbose_name_plural   = 'Demandes partenaires'
        ordering              = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_status_display()})"

    def full_name(self):
        return f"{self.first_name} {self.last_name}"
