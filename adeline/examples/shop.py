def fetch_price(item):
    raise RuntimeError("External service is unavailable in this example")


def calculate_total(items):
    return sum(fetch_price(item) for item in items)
