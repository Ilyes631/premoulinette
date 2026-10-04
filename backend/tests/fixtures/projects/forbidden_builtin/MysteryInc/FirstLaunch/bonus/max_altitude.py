def max_altitude(a: int, b: int, c: int) -> int:
    # max() is forbidden, so compare by hand
    highest = a
    if b > highest:
        highest = b
    if c > highest:
        highest = c
    return highest
