from enum import StrEnum
from fractions import Fraction


class RetestVerdict(StrEnum):
    ALL = 'all'
    SOME = 'some'
    NONE = 'none'


def classify_retest(minimum: Fraction, maximum: Fraction, threshold: Fraction) -> RetestVerdict:
    if maximum <= threshold:
        return RetestVerdict.ALL
    if minimum > threshold:
        return RetestVerdict.NONE
    return RetestVerdict.SOME
