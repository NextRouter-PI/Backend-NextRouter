from django.db import models

from .company import Company


class Company_Profile(models.Model):
    logo_url = models.CharField(max_length=255)
    biography = models.TextField()
    contact_email = models.EmailField(max_length=255)
    contact_phone = models.CharField(max_length=20)
    trade_name = models.CharField(max_length=50)
    company = models.OneToOneField(Company, on_delete=models.PROTECT)

    class Meta:
        verbose_name = 'Perfil de Empresa'
        verbose_name_plural = 'Perfis de Empresa'

    def __str__(self):
        return self.trade_name
