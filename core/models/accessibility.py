from django.db import models

from .profile import Profile


class Accessibility(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE)
    font_size = models.IntegerField()
    high_contrast = models.BooleanField(default=False)
    daltonism_filter = models.CharField(max_length=20)
