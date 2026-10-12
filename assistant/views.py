from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from common.exceptions import ValidationError
from assistant.agent import run_chat_turn


class AssistantChatView(APIView):
    """
    POST /api/assistant/chat/
    Orchestrates dealer chat interactions with tool calling, live database grounding,
    and draft order creation.
    """

    def post(self, request):
        data = request.data
        if not isinstance(data, dict):
            raise ValidationError(
                message="Request body must be a valid JSON object.",
                details=["body: Expected JSON object."],
            )

        session_id = data.get("session_id")
        if not session_id or not isinstance(session_id, str) or not session_id.strip():
            raise ValidationError(
                message="Field 'session_id' is required and must be a non-empty string.",
                details=["session_id: Must be a non-empty string."],
            )
        session_id = session_id.strip()
        if len(session_id) > 100:
            raise ValidationError(
                message="Field 'session_id' cannot exceed 100 characters.",
                details=["session_id: Length exceeds 100 characters."],
            )

        message = data.get("message")
        if not message or not isinstance(message, str) or not message.strip():
            raise ValidationError(
                message="Field 'message' is required and must be a non-empty string.",
                details=["message: Must be a non-empty string."],
            )
        message = message.strip()
        if len(message) > 2000:
            raise ValidationError(
                message="Field 'message' cannot exceed 2000 characters.",
                details=["message: Length exceeds 2000 characters."],
            )

        dealer_id = data.get("dealer_id")
        if dealer_id is None:
            raise ValidationError(
                message="Field 'dealer_id' is required.",
                details=["dealer_id: Field is required."],
            )
        try:
            dealer_id = int(dealer_id)
        except (ValueError, TypeError):
            raise ValidationError(
                message="Field 'dealer_id' must be an integer.",
                details=["dealer_id: Expected integer."],
            )

        # Execute conversation turn
        result = run_chat_turn(
            session_id=session_id,
            dealer_id=dealer_id,
            message=message,
        )

        return Response(result, status=status.HTTP_200_OK)
