from django.db import models


class Profile(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    profile_picture_url = models.CharField(max_length=255, blank=True, null=True)
    contact_phone = models.CharField(max_length=20)
    user_type = models.CharField(max_length=20)
