"""Deterministic decomposition operators. The model never does this arithmetic itself."""

from . import additive, divisive, growth_accounting, multiplicative, pvm, second_order, shrink

OUTPUT_FIELDS = {
    "additive": additive.OUTPUT_FIELDS,
    "multiplicative": multiplicative.OUTPUT_FIELDS,
    "divisive": divisive.OUTPUT_FIELDS,
    "second_order_time": second_order.OUTPUT_FIELDS_TIME,
    "second_order_sides": second_order.OUTPUT_FIELDS_SIDES,
    "growth_accounting": growth_accounting.OUTPUT_FIELDS,
    "pvm": pvm.OUTPUT_FIELDS,
}

__all__ = ["additive", "divisive", "growth_accounting", "multiplicative", "pvm", "second_order", "shrink", "OUTPUT_FIELDS"]
