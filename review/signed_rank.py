from collections.abc import Iterable
from fractions import Fraction
from itertools import groupby, product


def average_absolute_ranks(values: Iterable[Fraction]) -> tuple[tuple[Fraction, Fraction], ...]:
    ordered = sorted((value for value in values if value != 0), key=abs)
    ranked = []
    previous = 0
    for _, equal_values in groupby(ordered, key=abs):
        group = list(equal_values)
        rank = Fraction(2 * previous + len(group) + 1, 2)
        ranked.extend((value, rank) for value in group)
        previous += len(group)
    return tuple(ranked)


def exact_signed_rank_p(values: Iterable[Fraction]) -> Fraction:
    ranked = average_absolute_ranks(values)
    if not ranked:
        return Fraction(1)
    # Twice each average rank is integral, including ties spanning two ranks.
    weights = tuple(int(2 * rank) for _, rank in ranked)
    observed = abs(sum(weight if value > 0 else -weight for (value, _), weight in zip(ranked, weights)))
    tail = 0
    for signs in product((-1, 1), repeat=len(weights)):
        flipped = sum(sign * weight for sign, weight in zip(signs, weights))
        tail += abs(flipped) >= observed
    return Fraction(tail, 1 << len(weights))
