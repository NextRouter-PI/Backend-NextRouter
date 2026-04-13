from django.db import models

from .company import Company


class Company_Registration_Request(models.Model):
    person_responsible_request = models.CharField(max_length=200)
    final_status = models.CharField(max_length=20)
    reason_rejection = models.TextField(blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    system_admin_finished_request = models.ForeignKey('System_Admin', on_delete=models.SET_NULL, null=True)
    company = models.OneToOneField(Company, on_delete=models.PROTECT, related_name='registration_request')

    class Meta:
        verbose_name = 'Solicitação de Cadastro de Empresa'
        verbose_name_plural = 'Solicitações de Cadastro de Empresas'

    def __str__(self):
        return f"Solicitação de Cadastro de Empresa: {self.company} - Status: {self.final_status}"
