import json
from django.db import transaction

from catalog.models import Product, Inventory
from common.exceptions import ValidationError
from common.money import format_money
from orders.services import create_draft_order as base_create_draft_order
from orders.money import calculate_line, calculate_order_totals
from assistant.retrieval import search_parts as do_search_parts

# Tool definitions exposed to the LLM
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_parts",
            "description": "Search the parts catalogue by natural language query (e.g. 'brake pads', 'oil filter') and optional vehicle fitment (e.g. 'Bajaj Pulsar 150', 'Duke 390'). Returns matching products with live catalogue price and stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords describing the part (e.g. 'brake pads', 'chain kit', 'LED indicator').",
                    },
                    "vehicle": {
                        "type": "string",
                        "description": "Optional targeted vehicle make and model (e.g. 'Bajaj Pulsar 150', 'KTM Duke 390', 'Yamaha R15 V4').",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of matching parts to return (default: 5, max: 10).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Check real-time stock quantity, catalogue price, and availability for a specific SKU directly from the warehouse database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {
                        "type": "string",
                        "description": "The exact SKU identifier (e.g. 'BRK-1044', 'FIL-1016').",
                    },
                },
                "required": ["sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft_order",
            "description": "Create a new DRAFT purchase order for the dealer with one or more line items. Note: This creates a DRAFT order only. It never confirms or dispatches orders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "List of line items to include in the draft order.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sku": {
                                    "type": "string",
                                    "description": "Product SKU (e.g. 'BRK-1044').",
                                },
                                "quantity": {
                                    "type": "integer",
                                    "description": "Number of units to order (must be an integer >= 1).",
                                },
                            },
                            "required": ["sku", "quantity"],
                        },
                    },
                },
                "required": ["items"],
            },
        },
    },
]


def execute_tool(name: str, arguments: dict, dealer_id: int) -> tuple[dict, dict | None]:
    """
    Execute a requested tool deterministically and safely.
    Returns: (tool_result_dict, action_or_none)
    Exceptions are caught and returned as structured errors for the model.
    """
    if name == "search_parts":
        query = arguments.get("query", "")
        vehicle = arguments.get("vehicle")
        limit = arguments.get("limit", 5)
        results = do_search_parts(query=query, vehicle=vehicle, limit=limit)
        return {"parts": results, "count": len(results)}, None

    elif name == "check_stock":
        sku = str(arguments.get("sku", "")).strip().upper()
        if not sku:
            return {"error": "invalid_argument", "message": "SKU must not be empty."}, None

        try:
            product = Product.objects.select_related("inventory").get(sku=sku)
            stock_qty = product.inventory.quantity if hasattr(product, "inventory") and product.inventory else 0
            return {
                "sku": product.sku,
                "name": product.name,
                "price": format_money(product.price),
                "stock": stock_qty,
                "in_stock": stock_qty > 0,
            }, None
        except Product.DoesNotExist:
            return {"error": "unknown_sku", "message": f"Product with SKU '{sku}' not found in catalogue."}, None

    elif name == "create_draft_order":
        items = arguments.get("items", [])
        if not isinstance(items, list) or len(items) == 0:
            return {"error": "validation_error", "message": "Order must contain at least one line item."}, None

        # Clean item parameters
        cleaned_items = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                return {"error": "validation_error", "message": f"Item at index {idx} is invalid."}, None
            sku = str(item.get("sku", "")).strip().upper()
            qty = item.get("quantity")
            if not isinstance(qty, int) or qty < 1 or qty > 1000:
                return {
                    "error": "validation_error",
                    "message": f"Quantity for SKU '{sku}' must be an integer between 1 and 1000.",
                }, None
            cleaned_items.append({"sku": sku, "quantity": qty})

        try:
            # Atomic draft order creation using identical business service as POST /api/orders/
            order = base_create_draft_order(dealer_or_id=dealer_id, items=cleaned_items)
            line_calcs = [
                calculate_line(it.product.price, it.quantity)
                for it in order.items.select_related("product").all()
            ]
            totals = calculate_order_totals(line_calcs)

            order_data = {
                "order_number": order.order_number,
                "status": "DRAFT",
                "items": [
                    {
                        "sku": it.product.sku,
                        "name": it.product.name,
                        "quantity": it.quantity,
                        "unit_price": format_money(it.product.price),
                    }
                    for it in order.items.select_related("product").all()
                ],
                "subtotal": format_money(totals.subtotal),
                "tax_total": format_money(totals.tax_total),
                "grand_total": format_money(totals.grand_total),
                "note": "This order has been created in DRAFT status. You or the dealership staff must confirm it separately in the portal.",
            }

            action = {
                "type": "draft_order_created",
                "order_number": order.order_number,
            }
            return order_data, action

        except ValidationError as e:
            return {
                "error": "validation_error",
                "message": e.message,
                "details": e.details,
            }, None
        except Exception as e:
            return {"error": "order_creation_failed", "message": str(e)}, None

    else:
        return {"error": "unknown_tool", "message": f"Tool '{name}' is not recognized."}, None
