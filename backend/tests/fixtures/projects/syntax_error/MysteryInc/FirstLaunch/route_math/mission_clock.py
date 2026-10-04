def mission_clock(seconds: int) -> str:
    hours = seconds // 3600
    minutes = seconds % 3600 // 60
    secs = seconds % 60
    # :02 pads each field with a leading zero
    return f"{hours:02}:{minutes:02}:{secs:02}"
