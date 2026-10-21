from django.utils import timezone

from app.geocoding import geocode_address

ADDRESS_FIELDS = ('street', 'number', 'neighborhood', 'city', 'state', 'cep')
GEOCODE_FIELDS = ('latitude', 'longitude', 'geocoded_at')


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
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and not set(update_fields) & set(ADDRESS_FIELDS):
            # Salvamento parcial que não mexe no endereço (ex.: senha, last_login): nada a geocodificar.
            return super().save(*args, **kwargs)

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
                if update_fields is not None:
                    kwargs['update_fields'] = {*update_fields, *GEOCODE_FIELDS}

        return super().save(*args, **kwargs)
