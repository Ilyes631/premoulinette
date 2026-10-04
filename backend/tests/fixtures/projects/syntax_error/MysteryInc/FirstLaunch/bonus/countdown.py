def main() -> None:
    number = int(input("Countdown start: "))
    # range() is not authorized: count down with a while loop
    while number >= 1:
        print(number)
        number = number - 1
    print("Liftoff!")


if __name__ == "__main__":
    main()
