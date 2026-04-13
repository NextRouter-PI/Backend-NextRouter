from django.db import models


class Register_Link(models.Model):
    company_request = models.ForeignKey('Company_Registration_Request', on_delete=models.PROTECT)
    contract_request = models.ForeignKey('Contract_Request', on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=128)
    expire_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Link de Registro'
        verbose_name_plural = 'Links de Registro'

    def __str__(self):
        return f"Link de Registro {self.id}"
