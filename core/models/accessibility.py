from django.db import models

from .profile import Profile


class Accessibility(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.PROTECT, related_name='accessibility')
    font_size = models.IntegerField()
    high_contrast = models.BooleanField(default=False)
    daltonism_filter = models.CharField(max_length=20)

    class Meta:
        verbose_name = 'Acessibilidade'
        verbose_name_plural = 'Acessibilidades'

    def __str__(self):
        return f"Acessibilidade de {self.profile.first_name} {self.profile.last_name}"
