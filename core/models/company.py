from django.db import models


class Company(models.Model):
    company_cnpj = models.CharField(max_length=14)
    business_address = models.TextField()
    identification_document_url = models.CharField(max_length=255)
    company_email = models.EmailField()
    company_phone = models.CharField(max_length=45)

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'

    def __str__(self):
        return self.company_cnpj
