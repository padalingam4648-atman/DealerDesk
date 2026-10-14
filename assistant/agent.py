import json
import logging
from django.db import transaction

from common.exceptions import ValidationError
from dealers.models import Dealer
from assistant.models import ChatSession, ChatMessage
from assistant.prompts import SYSTEM_PROMPT
from assistant.tools import TOOL_SCHEMAS, execute_tool
from assistant.llm import call_llm, LLMUnavailableError
from assistant.grounding import verify_and_ground_reply

logger = logging.getLogger(__name__)


def run_chat_turn(session_id: str, dealer_id: int, message: str) -> dict:
    """
    Execute a single turn of the dealer assistant.
    1. Loads/creates the session with dealer isolation.
    2. Loads recent history and sanitizes stale figures.
    3. Executes the multi-step tool-calling loop (capped at 6 iterations).
    4. Runs programmatic grounding verification.
    5. Returns exact API contract response dictionary.
    """
    # 1. Resolve dealer
    try:
        dealer = Dealer.objects.get(id=dealer_id)
    except (Dealer.DoesNotExist, TypeError, ValueError):
        raise ValidationError(
            message=f"Dealer with ID '{dealer_id}' does not exist.",
            details=[f"dealer_id: Dealer '{dealer_id}' not found."],
        )

    # 2. Resolve or create ChatSession with tenant isolation check
    session, created = ChatSession.objects.get_or_create(
        session_id=session_id,
        defaults={"dealer": dealer},
    )
    if not created and session.dealer_id != dealer.id:
        raise ValidationError(
            message="Session already belongs to a different dealer.",
            details=["session_id: Cross-tenant session reuse is prohibited."],
        )

    # 3. Persist incoming user message
    ChatMessage.objects.create(
        session=session,
        role="user",
        content=message,
    )

    # 4. Assemble history for the LLM (cap to last 20 messages)
    history_qs = session.messages.order_by("-created_at")[:20]
    history_messages = list(reversed(history_qs))

    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for msg in history_messages:
        if msg.role == "user":
            llm_messages.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant":
            # Note: Historical assistant replies are treated as conversational context,
            # but model is instructed to re-fetch live prices/stocks.
            llm_messages.append({"role": "assistant", "content": msg.content})
        elif msg.role == "tool":
            # Mark prior turn tool calls as stale
            stale_payload = {
                "status": "STALE_HISTORY",
                "note": "Historical record only. You must re-run check_stock or search_parts to get current stock and price.",
            }
            llm_messages.append({
                "role": "tool",
                "tool_call_id": f"hist_{msg.id}",
                "name": msg.tool_name or "tool",
                "content": json.dumps(stale_payload),
            })

    # 5. Tool-calling loop
    recorded_tool_calls = []
    recorded_tool_results = []
    recorded_actions = []
    final_reply = ""
    max_iterations = 4
    seen_tool_calls = set()

    for iteration in range(max_iterations):
        try:
            response = call_llm(messages=llm_messages, tool_schemas=TOOL_SCHEMAS, temperature=0.0)
        except LLMUnavailableError as e:
            logger.error(f"LLM Unavailable in chat turn: {e}")
            return {
                "reply": "I apologize, but the assistant is temporarily unavailable. Please try again shortly.",
                "cited_skus": [],
                "tool_calls": recorded_tool_calls,
                "actions": recorded_actions,
            }

        # If LLM requested tool calls:
        if response.tool_calls:
            # Build assistant message with tool calls for context
            assistant_msg_dict = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ],
            }
            llm_messages.append(assistant_msg_dict)

            for tc in response.tool_calls:
                call_sig = (tc.name, json.dumps(tc.arguments, sort_keys=True))
                if call_sig in seen_tool_calls:
                    logger.info(f"Duplicate tool call {tc.name} suppressed in iteration {iteration}")
                    result = {
                        "note": f"You already executed {tc.name} with these arguments in this turn. Use the data already returned above to formulate your final answer to the dealer."
                    }
                    action = None
                else:
                    seen_tool_calls.add(call_sig)
                    result, action = execute_tool(tc.name, tc.arguments, dealer_id=dealer.id)
                    recorded_tool_calls.append({
                        "name": tc.name,
                        "arguments": tc.arguments,
                    })

                recorded_tool_results.append(result)

                if action:
                    recorded_actions.append(action)

                # Append tool result to conversation
                llm_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": json.dumps(result),
                })

                # Persist tool message
                ChatMessage.objects.create(
                    session=session,
                    role="tool",
                    tool_name=tc.name,
                    tool_payload=result,
                )

        else:
            # Model generated final text reply
            final_reply = response.content or ""
            break

    if not final_reply and recorded_tool_results:
        # Fallback if model halted without terminal text
        final_reply = "Here are the requested parts and availability from the catalogue."

    # 6. Programmatic Grounding Verification
    verified_reply, cited_skus, extra_calls = verify_and_ground_reply(
        reply=final_reply,
        tool_calls_this_turn=recorded_tool_calls,
        tool_results_this_turn=recorded_tool_results,
        dealer_id=dealer.id,
    )
    recorded_tool_calls.extend(extra_calls)

    # 7. Persist final assistant reply
    ChatMessage.objects.create(
        session=session,
        role="assistant",
        content=verified_reply,
    )

    return {
        "reply": verified_reply,
        "cited_skus": cited_skus,
        "tool_calls": recorded_tool_calls,
        "actions": recorded_actions,
    }
