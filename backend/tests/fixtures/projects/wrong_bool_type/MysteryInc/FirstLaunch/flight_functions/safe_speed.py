def is_safe(speed: int, limit: int) -> bool:
    # We are safe as long as we do not go over the limit
    if speed <= limit:
        return "True"
    else:
        return "False"
