/**
 * Student sources of demo/projects/mysteryinc_buggy (verbatim), used to build code excerpts
 * and to fake GET /api/projects/{id}/file in tests and component development.
 */
import type { CodeExcerpt } from '@/lib/types'

export const DEMO_ROOT = 'MysteryInc/FirstLaunch'

export const buggySources: Record<string, string> = {
  [`${DEMO_ROOT}/flight_functions/safe_speed.py`]: `def is_safe(speed: int, limit: int) -> bool:
    # We are safe as long as we do not go over the limit
    if speed <= limit:
        return "True"
    else:
        return "False"
`,
  [`${DEMO_ROOT}/flight_functions/kelvin.py`]: `def to_kelvin(celsius: float) -> float:
    # 0 degrees Celsius is 273.15 Kelvin
    return celsius + 273.15


print(to_kelvin(25))
`,
  [`${DEMO_ROOT}/flight_functions/grade_landing.py`]: `def landing_grade(vertical_speed: int) -> str:
    # The slower we touch the ground, the better the landing
    if vertical_speed < 2:
        return "Perfect touchdown"
    elif vertical_speed <= 5:
        return "Hard landing"
    else:
        return "Crash!"
`,
  [`${DEMO_ROOT}/route_math/fuel_share.py`]: `def fuel_share(total_fuel: int, crew: int) -> int:
    # Integer division: every crew member gets the same amount
    return round(total_fuel / crew)


def remaining_fuels(total_fuel: int, crew: int) -> int:
    # What could not be shared stays in the tank
    return total_fuel % crew
`,
  [`${DEMO_ROOT}/mission_clock.py`]: `def mission_clock(seconds: int) -> str:
    hours = seconds // 3600
    minutes = seconds % 3600 // 60
    secs = seconds % 60
    # :02 pads each field with a leading zero
    print(f"{hours:02}:{minutes:02}:{secs:02}")
`,
  [`${DEMO_ROOT}/FIXME2.py`]: `def average_speed(distance: float, hours: float) -> float:
    # Shaggy forgot that we cannot divide by zero hours
    if hours == 0
        return 0.0
    return distance / hours
`,
  [`${DEMO_ROOT}/access_code.py`]: `code = input("Enter access code: ")

# Only the exact code opens the Mystery Machine
if code.upper() == "SCOOBY":
    print("Access granted. Welcome aboard!")
else:
    print("Access denied.")
`,
  [`${DEMO_ROOT}/launch_sequence.py`]: `pilot = input("Pilot name:")
fuel = int(input("Starting fuel: "))

print("Where's the Mystery Machine headed today?")
print("1 - Crystal Cove")
print("2 - The Older Mill")
print("3 - Spooky Swamp")
choice = input("Your choice: ")

# Each destination has its own fuel cost
if choice == "1":
    destination = "Crystal Cove"
    cost = 50
elif choice == "2":
    destination = "The Old Mill"
    cost = 120
else:
    destination = "Spooky Swamp"
    cost = 200

if fuel < cost:
    print("Not enough fuel! The gang stays home.")
else:
    fuel = fuel - cost
    print("Destination: " + destination)
    print("Fuel after the trip: " + str(fuel))
    action = input("Set a trap or callect evidence? (trap/evidence) ")
    if action == "trap":
        print(pilot + " sets a trap at " + destination + ". Zoinks!")
    else:
        print(pilot + " collects evidence at " + destination + ". Jinkies!")
`,
  [`${DEMO_ROOT}/bonus/max_altitude.py`]: `def max_altitude(a: int, b: int, c: int) -> int:
    return max(a, b, c)
`,
}

/** Lines `start..end` (1-based, inclusive) of a demo file as a CodeExcerpt. */
export function excerpt(file: string, start: number, end: number, highlight: number[] = []): CodeExcerpt {
  const source = buggySources[file]
  if (source === undefined) throw new Error(`Unknown demo file: ${file}`)
  const lines = source.replace(/\n$/, '').split('\n')
  return { file, start_line: start, lines: lines.slice(start - 1, end), highlight }
}
