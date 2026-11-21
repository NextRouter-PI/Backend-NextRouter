ADDRESS_FIELDS = ('street', 'number', 'neighborhood', 'city', 'state', 'cep')
GEOCODE_FIELDS = ('latitude', 'longitude', 'geocoded_at')


class GeocodableAddressMixin:
    """
    Invalida coordenadas antigas quando o endereço é alterado sem coordenadas novas explícitas.
    Rastreia os valores carregados via `from_db` para evitar uma consulta `SELECT` extra por `save()`.
    """

    @classmethod
    def from_db(cls, db, field_names, values, **kwargs):
        instance = super().from_db(db, field_names, values, **kwargs)
        loaded = dict(zip(field_names, values, strict=False))
        instance._loaded_address = {field: loaded[field] for field in ADDRESS_FIELDS if field in loaded}
        instance._loaded_geocode = {field: loaded[field] for field in GEOCODE_FIELDS if field in loaded}
        return instance

    def refresh_from_db(self, using=None, fields=None, from_queryset=None):
        super().refresh_from_db(using=using, fields=fields, from_queryset=from_queryset)
        self._sync_loaded_address_state(fields=fields)

    def _sync_loaded_address_state(self, *, fields=None):
        deferred = self.get_deferred_fields()
        if fields is None:
            self._loaded_address = {field: getattr(self, field) for field in ADDRESS_FIELDS if field not in deferred}
            self._loaded_geocode = {field: getattr(self, field) for field in GEOCODE_FIELDS if field not in deferred}
            return
        field_set = set(fields)
        loaded_address = getattr(self, '_loaded_address', None)
        loaded_geocode = getattr(self, '_loaded_geocode', None)
        if loaded_address is not None:
            for field in ADDRESS_FIELDS:
                if field in field_set and field not in deferred:
                    loaded_address[field] = getattr(self, field)
        if loaded_geocode is not None:
            for field in GEOCODE_FIELDS:
                if field in field_set and field not in deferred:
                    loaded_geocode[field] = getattr(self, field)

    def _previous_address_and_geocode(self):
        loaded_address = getattr(self, '_loaded_address', None)
        loaded_geocode = getattr(self, '_loaded_geocode', None)
        if (
            loaded_address is not None
            and loaded_geocode is not None
            and len(loaded_address) == len(ADDRESS_FIELDS)
            and len(loaded_geocode) == len(GEOCODE_FIELDS)
        ):
            return loaded_address, loaded_geocode
        row = type(self).objects.filter(pk=self.pk).values(*ADDRESS_FIELDS, *GEOCODE_FIELDS).first()
        if row is None:
            return None, None
        return (
            {field: row[field] for field in ADDRESS_FIELDS},
            {field: row[field] for field in GEOCODE_FIELDS},
        )

    def _address_changed_and_needs_invalidation(self):
        if self._state.adding or not self.pk:
            return False
        previous_address, previous_geocode = self._previous_address_and_geocode()
        if previous_address is None:
            return False
        if not any(previous_address[field] != getattr(self, field) for field in ADDRESS_FIELDS):
            return False
        # Preserva coordenadas quando o chamador já gravou novo par válido neste mesmo save.
        geocode_updated = (
            self.latitude is not None
            and self.longitude is not None
            and (
                self.latitude != previous_geocode['latitude']
                or self.longitude != previous_geocode['longitude']
                or self.geocoded_at != previous_geocode['geocoded_at']
            )
        )
        return not geocode_updated

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and not set(update_fields) & set(ADDRESS_FIELDS):
            # Salvamento parcial que não mexe no endereço (ex.: senha, last_login): nada a geocodificar.
            result = super().save(*args, **kwargs)
            self._sync_loaded_address_state(fields=update_fields)
            return result

        if self._address_changed_and_needs_invalidation():
            self.latitude = None
            self.longitude = None
            self.geocoded_at = None
            if update_fields is not None:
                update_fields = {*update_fields, *GEOCODE_FIELDS}
                kwargs['update_fields'] = update_fields

        result = super().save(*args, **kwargs)
        self._sync_loaded_address_state(fields=update_fields)
        return result
