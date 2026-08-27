from django.utils import timezone

from app.geocoding import geocode_address

ADDRESS_FIELDS = ('street', 'number', 'neighborhood', 'city', 'state', 'cep')


class GeocodableAddressMixin:
    """
    Geocodifica automaticamente o endereço (rua, número, bairro, cidade, UF, CEP)
    ao salvar, quando o endereço mudou e existe cidade suficiente para uma busca
    confiável. Nunca bloqueia o save por falha de geocodificação.
    """

    def _address_changed(self):
        if not self.pk:
            return True
        try:
            old = type(self).objects.get(pk=self.pk)
        except type(self).DoesNotExist:
            return True
        return any(getattr(old, field) != getattr(self, field) for field in ADDRESS_FIELDS)

    def save(self, *args, **kwargs):
        if self.city and self._address_changed():
            latitude, longitude = geocode_address(
                street=self.street,
                number=self.number,
                neighborhood=self.neighborhood,
                city=self.city,
                state=self.state,
                cep=self.cep,
            )
            if latitude is not None:
                self.latitude = latitude
                self.longitude = longitude
                self.geocoded_at = timezone.now()

        super().save(*args, **kwargs)
