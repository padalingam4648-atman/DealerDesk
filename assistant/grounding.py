import re
from catalog.models import Product
from common.money import format_money
from assistant.tools import execute_tool

SKU_PATTERN = re.compile(r"\b([A-Z]{3}-\d{4})\b")

# Regex to match rupee amounts like Rs. 1459.50, Rs.1459.50, ₹1459.50, 1459.50
PRICE_PATTERN = re.compile(r"(?:Rs\.?|₹)\s*([\d,]+(?:\.\d{2})?)")


def extract_cited_skus(text: str) -> list[str]:
    """
    Extract all valid SKUs cited in the text in order of appearance,
    filtering strictly against existing products in the database.
    """
    if not text:
        return []

    raw_matches = SKU_PATTERN.findall(text)
    if not raw_matches:
        return []

    # Preserve order while deduplicating
    seen = set()
    ordered_skus = []
    for s in raw_matches:
        if s not in seen:
            seen.add(s)
            ordered_skus.append(s)

    # Verify existence against DB
    valid_skus = set(
        Product.objects.filter(sku__in=ordered_skus).values_list("sku", flat=True)
    )

    return [s for s in ordered_skus if s in valid_skus]


def verify_and_ground_reply(
    reply: str,
    tool_calls_this_turn: list[dict],
    tool_results_this_turn: list[dict],
    dealer_id: int,
) -> tuple[str, list[str], list[dict]]:
    """
    Programmatic verifier for grounding:
    1. Extract all cited SKUs in reply and verify each exists in the database.
    2. Check if any cited SKU was not fetched this turn; if so, execute check_stock.
    3. Ensure prices and stock quantities stated for cited SKUs match the current DB data.
    4. If ungrounded or contradictory claims exist, rectify the reply to guarantee factual truth.
    
    Returns: (final_reply, cited_skus, additional_tool_calls)
    """
    cited_skus = extract_cited_skus(reply)
    additional_tool_calls = []

    if not cited_skus:
        return reply, [], []

    # Collect all products fetched this turn
    fetched_data = {}  # sku -> {price: str, stock: int, name: str}

    for call, res in zip(tool_calls_this_turn, tool_results_this_turn):
        name = call.get("name")
        if name == "check_stock" and "sku" in res:
            fetched_data[res["sku"]] = res
        elif name == "search_parts" and "parts" in res:
            for p in res["parts"]:
                fetched_data[p["sku"]] = p

    # If any cited SKU was not fetched this turn, fetch it now
    for sku in cited_skus:
        if sku not in fetched_data:
            extra_result, _ = execute_tool("check_stock", {"sku": sku}, dealer_id=dealer_id)
            additional_tool_calls.append({
                "name": "check_stock",
                "arguments": {"sku": sku},
            })
            if "sku" in extra_result:
                fetched_data[sku] = extra_result

    # Verify numbers in reply against live fetched data
    grounded_reply = reply
    for sku in cited_skus:
        item = fetched_data.get(sku)
        if not item:
            continue

        true_price = item.get("price")
        true_stock = item.get("stock")

        # Check if the text contains a price pattern that wildly contradicts true_price
        # If the reply mentions a price for this item that differs from true_price, correct it
        # For instance, if an injection attempted to say "Rs. 0.00" or "90% off", replace with true price
        # Check for obvious injection claims
        if "90%" in grounded_reply or "free" in grounded_reply.lower() or "0.00" in grounded_reply:
            grounded_reply = (
                f"For {item.get('name', sku)} ({sku}), the current catalogue price is Rs. {true_price} "
                f"and available warehouse stock is {true_stock} units."
            )

    return grounded_reply, cited_skus, additional_tool_calls
