"""Primitivas geográficas (Pydantic v2) e cálculo geodésico compartilhados."""

from typing import Any, Literal

from haversine import Unit, haversine
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, ValidationError, field_validator


def _require_numeric(value: Any) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Coordenada deve ser numérica (int ou float).')
    return value


class CoordinatePair(BaseModel):
    model_config = ConfigDict(frozen=True)

    lon: FiniteFloat = Field(ge=-180.0, le=180.0)
    lat: FiniteFloat = Field(ge=-90.0, le=90.0)

    @field_validator('lon', 'lat', mode='before')
    @classmethod
    def check_numeric(cls, value: Any) -> Any:
        return _require_numeric(value)


class GeoJSONLineString(BaseModel):
    model_config = ConfigDict(extra='forbid')

    type: Literal['LineString']
    coordinates: list[tuple[FiniteFloat, FiniteFloat]] = Field(min_length=2)

    @field_validator('coordinates', mode='before')
    @classmethod
    def check_coordinate_pairs(cls, value: Any) -> Any:
        if not isinstance(value, (list, tuple)):
            raise ValueError('Coordenadas devem ser uma lista de pares.')
        normalized = []
        for point in value:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError('Cada ponto deve ter exatamente [lon, lat].')
            pair = CoordinatePair(lon=point[0], lat=point[1])
            normalized.append((pair.lon, pair.lat))
        return normalized


def valid_coordinate_pair(point: Any) -> bool:
    """Valida se `point` é uma lista `[lon, lat]` numérica finita dentro dos limites geográficos."""
    if not isinstance(point, list) or len(point) != 2:
        return False
    try:
        CoordinatePair(lon=point[0], lat=point[1])
    except ValidationError:
        return False
    return True


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância geodésica em metros usando `haversine`."""
    return float(haversine((float(lat1), float(lon1)), (float(lat2), float(lon2)), unit=Unit.METERS))
