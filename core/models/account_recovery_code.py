from django.db import models


class Account_Recovery_Code(models.Model):
    code_hash = models.CharField(max_length=64)
    expire_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    register_email = models.EmailField()
    pending = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Código de Recuperação de Conta"
        verbose_name_plural = "Códigos de Recuperação de Conta"

    def __str__(self):
        return f"Account Recovery Code for {self.register_email} (expires at {self.expire_at})"
