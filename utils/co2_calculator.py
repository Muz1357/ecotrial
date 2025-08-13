# Emission factors in kg CO2 per km
EMISSION_FACTORS = {
    'walking': 0,
    'cycling': 0,
    'train': 0.041,
    'bus': 0.105,
    'car': 0.192,
    'taxi': 0.21,
    'flight': 0.255
}

def calculate_co2(distance_km, transport_mode):
    factor = EMISSION_FACTORS.get(transport_mode.lower(), 0.2)
    return distance_km * factor
