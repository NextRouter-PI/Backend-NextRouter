from django.db import models


class Contract_Request(models.Model):
    contact_phone = models.CharField(max_length=20)
    contact_email = models.EmailField()
    type = models.CharField(max_length=20)
    home_address = models.TextField()
    reason_rejection = models.TextField(blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    final_status = models.CharField(max_length=20)
    company_admin_finished_request = models.ForeignKey('Company_Admin', on_delete=models.PROTECT, null=True)
    person_cpf = models.CharField(max_length=14)

    class Meta:
        verbose_name = 'Solicitação de Contrato'
        verbose_name_plural = 'Solicitações de Contratos'

    def __str__(self):
        return self.contact_email
