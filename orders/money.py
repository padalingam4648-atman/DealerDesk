from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple

GST_RATE = Decimal("0.18")
TWOPLACES = Decimal("0.01")


class LineTotals(NamedTuple):
    unit_price: Decimal
    quantity: int
    line_subtotal: Decimal
    line_tax: Decimal
    line_total: Decimal


class OrderTotals(NamedTuple):
    subtotal: Decimal
    tax_total: Decimal
    grand_total: Decimal


def quantize_money(amount: Decimal | str | int) -> Decimal:
    """Quantize amount to 2 decimal places using standard ROUND_HALF_UP."""
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount).strip())
    return amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def calculate_line_subtotal(unit_price: Decimal, quantity: int) -> Decimal:
    """Calculate line subtotal = unit_price * quantity quantized to 2 decimal places."""
    return quantize_money(unit_price * quantity)


def calculate_line_tax(line_subtotal: Decimal) -> Decimal:
    """
    Calculate GST at 18% per line rounded with ROUND_HALF_UP (0.005 -> 0.01).
    Tax is rounded per line, not on the order total.
    """
    return quantize_money(line_subtotal * GST_RATE)


def calculate_line_total(line_subtotal: Decimal, line_tax: Decimal) -> Decimal:
    """Calculate line total = line_subtotal + line_tax."""
    return quantize_money(line_subtotal + line_tax)


def calculate_line(unit_price: Decimal | str, quantity: int) -> LineTotals:
    """Calculate all money figures for a single line item."""
    price = quantize_money(unit_price)
    subtotal = calculate_line_subtotal(price, quantity)
    tax = calculate_line_tax(subtotal)
    total = calculate_line_total(subtotal, tax)
    return LineTotals(
        unit_price=price,
        quantity=quantity,
        line_subtotal=subtotal,
        line_tax=tax,
        line_total=total,
    )


def calculate_order_totals(line_totals: list[LineTotals]) -> OrderTotals:
    """
    Calculate order totals as sum of line values:
    subtotal = sum(line_subtotal)
    tax_total = sum(line_tax)
    grand_total = subtotal + tax_total (which equals sum(line_total))
    """
    subtotal = sum((line.line_subtotal for line in line_totals), Decimal("0.00"))
    tax_total = sum((line.line_tax for line in line_totals), Decimal("0.00"))
    grand_total = quantize_money(subtotal + tax_total)
    return OrderTotals(
        subtotal=quantize_money(subtotal),
        tax_total=quantize_money(tax_total),
        grand_total=grand_total,
    )
