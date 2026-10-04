# Practical 3: Weather Station

**Course:** Algo 101 · **Deadline:** Friday 18:00

## Architecture

```
weather/
├── convert.py
├── checks.py
├── ask_city.py
└── extras/
    └── stats.py
```

Files in `extras/` are optional. You must include a `.gitignore` file.

Do not push `__pycache__` directories or `.pyc` files: they are penalized.

## Constraints

Allowed builtins: `print`, `input`, `int`, `len`.

Forbidden functions: `max()`, `min()`.

No import is allowed.

## Exercise 1: Fahrenheit

File: `convert.py`

```python
def to_fahrenheit(celsius: float) -> float:
```

Returns `celsius * 9 / 5 + 32`.

```python
to_fahrenheit(0) -> 32.0
to_fahrenheit(100) == 212.0
to_fahrenheit(-40)  # -40.0
```

## Exercise 2: Freezing check

File: `weather/checks.py`

```python
def is_freezing(temp: int) -> bool:
def describe(temp: int) -> str:
```

`is_freezing` returns `True` if `temp <= 0`, otherwise returns `False`.

`describe` grades the temperature:

- `temp < 10` -> `'cold'`
- `10 <= temp < 25` -> `'mild'`
- otherwise -> `'hot'`

```python
>>> is_freezing(-3)
True
>>> describe(30)
'hot'
```

## Exercise 3: City prompt

File: `ask_city.py`

Ask the user for a city with the prompt `"City? "`, then print `Weather for <city>: sunny`.

```console
$ python3 ask_city.py
City? Paris
Weather for Paris: sunny
```

## Bonus

### Bonus 1: Stats

File: `extras/stats.py`

```python
def average(a: int, b: int) -> float:
```

```python
>>> average(2, 4)
3.0
```
