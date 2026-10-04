pilot = input("Pilot name:")
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
