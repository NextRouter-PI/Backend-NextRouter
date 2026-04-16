from django.db import models


class Driver(models.Model):
    home_address = models.TextField()
    register_phone = models.CharField(max_length=45)
    register_email = models.EmailField()
    driver_cpf = models.CharField(max_length=14)
    password_hash = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'Motorista'
        verbose_name_plural = 'Motoristas'

    def __str__(self):
        return self.driver_cpf
