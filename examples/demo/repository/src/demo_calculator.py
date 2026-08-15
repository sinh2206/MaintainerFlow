def calculate_total(quantity: int, unit_price: int) -> int:
    if quantity < 0 or unit_price < 0:
        raise ValueError("quantity and unit_price must be non-negative")
    return quantity * unit_price
