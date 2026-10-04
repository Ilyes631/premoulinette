def landing_grade(vertical_speed: int) -> str:
    # The slower we touch the ground, the better the landing
    if vertical_speed <= 2:
        return "Perfect touchdown"
    elif vertical_speed <= 5:
        return "Hard landing"
    else:
        return "Crash!"


# Bonus
def emoji_grade(vertical_speed: int) -> str:
    if vertical_speed <= 2:
        return "🟢"
    elif vertical_speed <= 5:
        return "🟡"
    else:
        return "🔴"
