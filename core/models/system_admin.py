from django.db import models


class System_Admin(models.Model):
    first_name = models.CharField(max_length=50)
    register_email = models.EmailField()
    password_hash = models.CharField(max_length=255)
    last_name = models.CharField(max_length=50)

    class Meta:
        verbose_name = "Administrador do Sistema"
        verbose_name_plural = "Administradores do Sistema"

    def __str__(self):
        return f'{self.first_name} {self.last_name}'
