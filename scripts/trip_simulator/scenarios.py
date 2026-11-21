"""Cenários modulares (Ida, Retorno e extensíveis) e interpolação de coordenadas."""

from dataclasses import dataclass
from math import hypot

DEV_PASSWORD = 'SenhaForte@123'
ADMIN_PASSWORD = 'Admin@12345'


@dataclass(frozen=True)
class PointSpec:
    name: str
    point_type: str
    street: str
    number: str
    neighborhood: str
    city: str
    state: str
    cep: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class PassengerSpec:
    email: str
    name: str
    cpf_seed: str
    phone: str
    point: PointSpec


@dataclass(frozen=True)
class TripScenario:
    key: str
    label: str
    direction: str  # 'outbound' | 'return'
    service_name: str
    target_hour: int
    target_minute: int
    garage: PointSpec
    destination: PointSpec
    passengers: tuple[PassengerSpec, ...]
    # Coordenadas [lng, lat] (GeoJSON) de fallback caso OSRM_URL não esteja configurado.
    fallback_geojson_coords: tuple[tuple[float, float], ...]


GARAGE_JOINVILLE = PointSpec(
    name='Garagem Central Joinville',
    point_type='garage',
    street='Rua XV de Novembro',
    number='500',
    neighborhood='Centro',
    city='Joinville',
    state='SC',
    cep='89201600',
    latitude=-26.3044,
    longitude=-48.8455,
)

DESTINATION_IFC = PointSpec(
    name='IFC Campus Araquari',
    point_type='destination',
    street='BR-280, km 27',
    number='S/N',
    neighborhood='Colégio Agrícola',
    city='Araquari',
    state='SC',
    cep='89245000',
    latitude=-26.3941,
    longitude=-48.7385,
)

PASSENGER_ANA = PassengerSpec(
    email='passageiro@nextrouter.local',
    name='Ana Souza',
    cpf_seed='900000004',
    phone='47999990004',
    point=PointSpec(
        name='Ponto de Ana Souza',
        point_type='passenger',
        street='Rua Monsenhor Gercino',
        number='1240',
        neighborhood='Itaum',
        city='Joinville',
        state='SC',
        cep='89210160',
        latitude=-26.3320,
        longitude=-48.8180,
    ),
)

PASSENGER_BRUNO = PassengerSpec(
    email='bruno@nextrouter.local',
    name='Bruno Costa',
    cpf_seed='900000006',
    phone='47999990006',
    point=PointSpec(
        name='Ponto de Bruno Costa',
        point_type='passenger',
        street='Rua Santa Catarina',
        number='2100',
        neighborhood='Floresta',
        city='Joinville',
        state='SC',
        cep='89212000',
        latitude=-26.3580,
        longitude=-48.7850,
    ),
)

# Trajeto realista aproximado Joinville (Centro -> Itaum -> Floresta -> BR-280 -> IFC Araquari) em [lng, lat].
_OUTBOUND_FALLBACK: tuple[tuple[float, float], ...] = (
    (-48.8455, -26.3044),
    (-48.8410, -26.3105),
    (-48.8345, -26.3170),
    (-48.8265, -26.3245),
    (-48.8180, -26.3320),  # Ana Souza
    (-48.8100, -26.3390),
    (-48.8015, -26.3455),
    (-48.7935, -26.3520),
    (-48.7850, -26.3580),  # Bruno Costa
    (-48.7760, -26.3655),
    (-48.7670, -26.3730),
    (-48.7575, -26.3805),
    (-48.7480, -26.3875),
    (-48.7385, -26.3941),  # IFC Campus Araquari
)

SCENARIOS: dict[str, TripScenario] = {
    'outbound': TripScenario(
        key='outbound',
        label='Ida — Joinville → IFC Campus Araquari',
        direction='outbound',
        service_name='Ida Manhã 07:30',
        target_hour=7,
        target_minute=30,
        garage=GARAGE_JOINVILLE,
        destination=DESTINATION_IFC,
        passengers=(PASSENGER_ANA, PASSENGER_BRUNO),
        fallback_geojson_coords=_OUTBOUND_FALLBACK,
    ),
    'return': TripScenario(
        key='return',
        label='Retorno — IFC Campus Araquari → Joinville',
        direction='return',
        service_name='Retorno Tarde 17:30',
        target_hour=17,
        target_minute=30,
        garage=GARAGE_JOINVILLE,
        destination=DESTINATION_IFC,
        passengers=(PASSENGER_ANA, PASSENGER_BRUNO),
        fallback_geojson_coords=tuple(reversed(_OUTBOUND_FALLBACK)),
    ),
}


def get_scenario(name: str) -> TripScenario:
    if name not in SCENARIOS:
        available = ', '.join(sorted(SCENARIOS))
        raise ValueError(f'Cenário desconhecido: {name!r}. Disponíveis: {available}.')
    return SCENARIOS[name]


def interpolate_route(
    geojson_coords: list[list[float]] | tuple[tuple[float, float], ...], steps: int
) -> list[tuple[float, float]]:
    """Interpola coordenadas GeoJSON [lng, lat] em `steps` pontos (lat, lng) igualmente espaçados."""
    if steps < 2:
        raise ValueError('steps deve ser >= 2.')
    if not geojson_coords or len(geojson_coords) < 2:
        raise ValueError('É necessário ao menos 2 coordenadas para interpolar o trajeto.')

    segments: list[tuple[tuple[float, float], tuple[float, float], float]] = []
    total_length = 0.0
    for index in range(len(geojson_coords) - 1):
        lng1, lat1 = float(geojson_coords[index][0]), float(geojson_coords[index][1])
        lng2, lat2 = float(geojson_coords[index + 1][0]), float(geojson_coords[index + 1][1])
        length = hypot(lat2 - lat1, lng2 - lng1)
        if length > 0:
            segments.append(((lat1, lng1), (lat2, lng2), length))
            total_length += length

    if total_length == 0:
        lng0, lat0 = float(geojson_coords[0][0]), float(geojson_coords[0][1])
        return [(lat0, lng0)] * steps

    points: list[tuple[float, float]] = []
    for step in range(steps):
        target_dist = (step / (steps - 1)) * total_length
        accumulated = 0.0
        placed = False
        for (lat1, lng1), (lat2, lng2), seg_len in segments:
            if accumulated + seg_len >= target_dist:
                ratio = (target_dist - accumulated) / seg_len
                lat = round(lat1 + (lat2 - lat1) * ratio, 6)
                lng = round(lng1 + (lng2 - lng1) * ratio, 6)
                points.append((lat, lng))
                placed = True
                break
            accumulated += seg_len
        if not placed:
            (lat2, lng2) = segments[-1][1]
            points.append((round(lat2, 6), round(lng2, 6)))
    return points
