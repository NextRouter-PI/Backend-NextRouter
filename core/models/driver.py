from django.db import models


class Driver(models.Model):
    home_address = models.TextField()
    register_phone = models.CharField(max_length=45)
    register_email = models.EmailField()
    driver_cpf = models.CharField(max_length=14)
    profile = models.ForeignKey('Profile', on_delete=models.PROTECT, related_name='drivers')
    password_hash = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'Motorista'
        verbose_name_plural = 'Motoristas'

    def __str__(self):
        return f'Motorista: {self.profile.first_name} {self.profile.last_name}'
