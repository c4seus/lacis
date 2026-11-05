def passes_luhn_check(identifier: str) -> bool:
    total = 0
    for position, character in enumerate(reversed(identifier)):
        digit = int(character)
        if position % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0
