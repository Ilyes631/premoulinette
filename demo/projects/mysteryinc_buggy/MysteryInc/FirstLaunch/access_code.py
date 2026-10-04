code = input("Enter access code: ")

# Only the exact code opens the Mystery Machine
if code.upper() == "SCOOBY":
    print("Access granted. Welcome aboard!")
else:
    print("Access denied.")
