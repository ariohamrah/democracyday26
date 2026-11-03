"""Competition scoring; model q and organizer p are never interchangeable."""
import math


def expected_points(q, p):
    if p is None:
        return None
    if not (0 <= q <= 1 and 0 <= p <= 1):
        raise ValueError('Probabilities must be in [0,1]')
    if p == 0:
        # No epsilon clipping: log(0) is undefined by the supplied rules.
        return None
    return q * -math.log2(p)


def choose(probabilities, prices):
    """Require prices for every mutually exclusive outcome before optimizing."""
    if abs(sum(probabilities.values()) - 1) > 1e-8:
        raise ValueError('Outcome probabilities must sum to one')
    likely = max(probabilities, key=probabilities.get)
    if any(prices.get(k) is None for k in probabilities):
        return likely, None, {}, 'missing_prices'
    points = {k: expected_points(q, prices[k]) for k, q in probabilities.items()}
    if any(v is None for v in points.values()):
        return likely, None, points, 'zero_price_requires_organizer_rule'
    selected = max(points, key=points.get)
    return likely, selected, points, 'ready'


def market_benchmark(prices):
    if len(prices) != 2 or any(p is None for p in prices.values()):
        return None
    if any(p <= 0 or p >= 1 for p in prices.values()) or abs(sum(prices.values()) - 1) > 1e-8:
        return None
    return choose(prices, prices)[1]
