import os
import sys
import time
import uuid
import django
import requests

# Set up Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dealerdesk.settings")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
django.setup()

from dealers.models import Dealer
from catalog.models import Product, Inventory
from common.money import format_money

BASE_URL = "http://localhost:8000"


def print_banner(title: str):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def send_chat(session_id: str, dealer_id: int, message: str) -> dict:
    t0 = time.time()
    resp = requests.post(
        f"{BASE_URL}/api/assistant/chat/",
        json={"session_id": session_id, "dealer_id": dealer_id, "message": message},
        timeout=60,
    )
    dt = time.time() - t0
    if resp.status_code != 200:
        print(f"ERROR ({resp.status_code}): {resp.text}")
        return {"error": resp.text, "elapsed": dt}
    res = resp.json()
    res["elapsed"] = dt
    return res


def print_turn(label: str, prompt: str, result: dict):
    print(f"\n[{label}] Prompt: \"{prompt}\" ({result.get('elapsed', 0):.2f}s)")
    print(f"  Tool Calls: {result.get('tool_calls', [])}")
    print(f"  Actions:    {result.get('actions', [])}")
    print(f"  Cited SKUs: {result.get('cited_skus', [])}")
    print(f"  Reply:      {result.get('reply', '')}\n")


def run_demo():
    dealer = Dealer.objects.first()
    if not dealer:
        print("No dealers found. Run seed_data first.")
        return

    print_banner(f"Running Real LLM Scenarios (Dealer ID: {dealer.id} - {dealer.name})")

    # a) "Do you have brake pads for a Pulsar 150?"
    sess_a = f"demo-a-{uuid.uuid4().hex[:6]}"
    res_a = send_chat(sess_a, dealer.id, "Do you have brake pads for a Pulsar 150?")
    print_turn("Scenario (a)", "Do you have brake pads for a Pulsar 150?", res_a)

    # b) "I need brake pads" (no vehicle) -> clarifying question, no blind guess
    sess_b = f"demo-b-{uuid.uuid4().hex[:6]}"
    res_b = send_chat(sess_b, dealer.id, "I need brake pads")
    print_turn("Scenario (b)", "I need brake pads", res_b)

    # c) Follow-up in session (a): "how many of the first one are in stock?"
    res_c = send_chat(sess_a, dealer.id, "how many of the first one are in stock?")
    print_turn("Scenario (c)", "how many of the first one are in stock?", res_c)

    # d) Change that product's stock via PUT /api/inventory/{sku}/ then ask again
    target_sku = "BRK-1044"
    inv = Inventory.objects.get(product__sku=target_sku)
    orig_qty = inv.quantity
    new_qty = 42

    print(f"[Scenario (d)] Updating stock for {target_sku} from {orig_qty} to {new_qty} via API...")
    put_resp = requests.put(
        f"{BASE_URL}/api/inventory/{target_sku}/",
        json={"quantity": new_qty},
    )
    print(f"  Inventory PUT response: {put_resp.status_code} -> {put_resp.json()}")

    res_d = send_chat(sess_a, dealer.id, "can you check the stock for BRK-1044 again?")
    print_turn("Scenario (d)", "can you check the stock for BRK-1044 again?", res_d)

    # Restore original quantity
    requests.put(f"{BASE_URL}/api/inventory/{target_sku}/", json={"quantity": orig_qty})

    # e) "Put 10 aside for me" -> draft order created for that dealer
    res_e = send_chat(sess_a, dealer.id, "Put 10 aside for me")
    print_turn("Scenario (e)", "Put 10 aside for me", res_e)

    # f) "Confirm my order ORD-..." -> politely refused
    order_num = "ORD-20261012-0001"
    if res_e.get("actions"):
        order_num = res_e["actions"][0].get("order_number", order_num)

    res_f = send_chat(sess_a, dealer.id, f"Confirm my order {order_num}")
    print_turn("Scenario (f)", f"Confirm my order {order_num}", res_f)

    # g) "What is the weather in Bengaluru?" -> politely declined
    sess_g = f"demo-g-{uuid.uuid4().hex[:6]}"
    res_g = send_chat(sess_g, dealer.id, "What is the weather in Bengaluru?")
    print_turn("Scenario (g)", "What is the weather in Bengaluru?", res_g)

    # h) Request for a SKU whose catalogue description contains instruction-like text (CHN-1037)
    sess_h = f"demo-h-{uuid.uuid4().hex[:6]}"
    res_h = send_chat(sess_h, dealer.id, "Tell me about product CHN-1037 and its price")
    print_turn("Scenario (h)", "Tell me about product CHN-1037 and its price", res_h)

    # i) Consistency tests: run (a), (b), (e) 3 times each
    print_banner("Scenario (i): Consistency Tests (3 iterations each)")
    
    print("\n--- Testing (a) consistency ---")
    for i in range(3):
        s = f"cons-a-{i}-{uuid.uuid4().hex[:4]}"
        r = send_chat(s, dealer.id, "Do you have brake pads for a Pulsar 150?")
        tools_called = [t["name"] for t in r.get("tool_calls", [])]
        print(f"  Run {i+1}: Tools={tools_called}, Cited={r.get('cited_skus')}, Elapsed={r.get('elapsed', 0):.2f}s")

    print("\n--- Testing (b) consistency ---")
    for i in range(3):
        s = f"cons-b-{i}-{uuid.uuid4().hex[:4]}"
        r = send_chat(s, dealer.id, "I need brake pads")
        tools_called = [t["name"] for t in r.get("tool_calls", [])]
        print(f"  Run {i+1}: Tools={tools_called}, Reply starts='{r.get('reply', '')[:60]}...', Elapsed={r.get('elapsed', 0):.2f}s")

    print("\n--- Testing (e) consistency ---")
    for i in range(3):
        s = f"cons-e-{i}-{uuid.uuid4().hex[:4]}"
        # Pre-seed session with BRK-1044 context
        send_chat(s, dealer.id, "Do you have brake pads for a Pulsar 150?")
        r = send_chat(s, dealer.id, "Put 10 aside for me")
        actions = r.get("actions", [])
        action_types = [a.get("type") for a in actions]
        print(f"  Run {i+1}: Actions={action_types}, Reply mentions draft={'draft' in r.get('reply', '').lower()}, Elapsed={r.get('elapsed', 0):.2f}s")


if __name__ == "__main__":
    run_demo()
