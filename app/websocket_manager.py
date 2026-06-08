from fastapi import WebSocket
from collections import defaultdict

class ConnectionManager:
    def __init__(self):
        self.active_connections = defaultdict(list)

    async def connect(self, pin: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[pin].append(websocket)

    def disconnect(self, pin: str, websocket: WebSocket):
        self.active_connections[pin].remove(websocket)

    async def broadcast(self, pin: str, message: dict):
        for connection in self.active_connections[pin]:
            await connection.send_json(message)

manager = ConnectionManager()