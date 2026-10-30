"""Deterministic decomposition operators. The model never does this arithmetic itself."""

from . import additive, divisive, multiplicative, second_order

OUTPUT_FIELDS = {
    "additive": additive.OUTPUT_FIELDS,
    "multiplicative": multiplicative.OUTPUT_FIELDS,
    "divisive": divisive.OUTPUT_FIELDS,
    "second_order_time": second_order.OUTPUT_FIELDS_TIME,
    "second_order_sides": second_order.OUTPUT_FIELDS_SIDES,
}

__all__ = ["additive", "divisive", "multiplicative", "second_order", "OUTPUT_FIELDS"]
