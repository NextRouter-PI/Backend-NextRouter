ADDRESS_FIELDS = ('street', 'number', 'neighborhood', 'city', 'state', 'cep')
GEOCODE_FIELDS = ('latitude', 'longitude', 'geocoded_at')


class GeocodableAddressMixin:
    """
    Invalida coordenadas antigas quando o endereço é alterado.
    A nova geocodificação acontece no processamento do trajeto fora da requisição.
    """

    def _address_changed(self):
        if not self.pk:
            return False
        try:
            old = type(self).objects.get(pk=self.pk)
        except type(self).DoesNotExist:
            return False
        return any(getattr(old, field) != getattr(self, field) for field in ADDRESS_FIELDS)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and not set(update_fields) & set(ADDRESS_FIELDS):
            # Salvamento parcial que não mexe no endereço (ex.: senha, last_login): nada a geocodificar.
            return super().save(*args, **kwargs)

        if self._address_changed():
            self.latitude = None
            self.longitude = None
            self.geocoded_at = None
            if update_fields is not None:
                kwargs['update_fields'] = {*update_fields, *GEOCODE_FIELDS}

        return super().save(*args, **kwargs)
