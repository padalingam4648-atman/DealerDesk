from django.db import models
from dealers.models import Dealer


class ChatSession(models.Model):
    """
    Carries conversational state and history across turns for a specific session_id.
    Strictly scoped to a specific dealer. If an existing session is reused with a
    different dealer_id, it is safely rejected to prevent cross-tenant session hijacking.
    """
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    dealer = models.ForeignKey(Dealer, on_delete=models.PROTECT, related_name="chat_sessions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ChatSession({self.session_id}, dealer={self.dealer_id})"


class ChatMessage(models.Model):
    """
    Individual turn message within a ChatSession.
    Preserves user prompts, tool executions, and assistant responses in temporal order.
    """
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("tool", "Tool"),
        ("system", "System"),
    ]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField(blank=True, default="")
    tool_name = models.CharField(max_length=100, null=True, blank=True)
    tool_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"ChatMessage({self.session.session_id}, role={self.role})"
