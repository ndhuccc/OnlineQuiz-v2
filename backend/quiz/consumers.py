from channels.generic.websocket import AsyncJsonWebsocketConsumer

from quiz.services.broadcast import session_group


class SessionConsumer(AsyncJsonWebsocketConsumer):
    """Subscribe to a quiz session room for live updates."""

    session_id: int | None = None

    async def connect(self):
        self.session_id = int(self.scope["url_route"]["kwargs"]["session_id"])
        self.group_name = session_group(self.session_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "type": "connected",
                "session_id": self.session_id,
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def relay_event(self, event):
        await self.send_json(
            {
                "type": event["event"],
                **event["payload"],
            }
        )


class QuizConsumer(AsyncJsonWebsocketConsumer):
    """Legacy echo endpoint for health checks."""

    async def connect(self):
        await self.accept()
        await self.send_json({"type": "connected", "message": "OnlineQuiz-v2 WebSocket ready"})

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})
        else:
            await self.send_json({"type": "echo", "data": content})
