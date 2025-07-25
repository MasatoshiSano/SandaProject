import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Line, UserLineAccess


class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.line_id = self.scope['url_route']['kwargs']['line_id']
        self.date = self.scope['url_route']['kwargs']['date']
        self.room_group_name = f'dashboard_{self.line_id}_{self.date}'
        
        # ユーザー認証とアクセス権限チェック
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return
            
        has_access = await self.check_line_access(user, self.line_id)
        if not has_access:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type', '')
        
        if message_type == 'request_update':
            # ダッシュボードデータの更新要求
            dashboard_data = await self.get_dashboard_data()
            await self.send(text_data=json.dumps({
                'type': 'dashboard_update',
                'data': dashboard_data
            }))

    # Receive message from room group
    async def dashboard_update(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'dashboard_update',
            'data': event['data']
        }))

    @database_sync_to_async
    def check_line_access(self, user, line_id):
        """ユーザーのライン アクセス権限をチェック"""
        try:
            line = Line.objects.get(id=line_id)
            return UserLineAccess.objects.filter(user=user, line=line).exists()
        except Line.DoesNotExist:
            return False

    @database_sync_to_async
    def get_dashboard_data(self):
        """ダッシュボードデータを取得"""
        from .utils import get_dashboard_data
        return get_dashboard_data(self.line_id, self.date) 