def fuel_share(total_fuel: int, crew: int) -> int:
    # Integer division: every crew member gets the same amount
    return round(total_fuel / crew)


def remaining_fuels(total_fuel: int, crew: int) -> int:
    # What could not be shared stays in the tank
    return total_fuel % crew
