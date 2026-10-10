"""ISO 6346 container number validation (4 letters, 6 digits, 1 check digit)."""
import re


def normalize(number: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (number or "").upper())


def check_digit(first10: str) -> int:
    values, v = {}, 10
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if v % 11 == 0:
            v += 1  # letter values skip multiples of 11
        values[ch] = v
        v += 1
    total = sum((values[c] if c.isalpha() else int(c)) * (2 ** i) for i, c in enumerate(first10))
    return total % 11 % 10


def validate(number: str) -> dict:
    n = normalize(number)
    if not re.fullmatch(r"[A-Z]{3}[UJZ][0-9]{7}", n):
        return {"valid": False, "normalized": n, "reason": "Expected 4 letters ending in U, J or Z, then 7 digits."}
    expected = check_digit(n[:10])
    if int(n[10]) != expected:
        return {"valid": False, "normalized": n, "reason": f"The check digit should be {expected}. This may be a typo."}
    return {"valid": True, "normalized": n, "reason": ""}
