"""
WebSocket input count integration tests
"""
from django.test import TestCase
from django.contrib.auth.models import User
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from datetime import datetime, date, time
import json
import logging
from unittest.mock import patch, MagicMock

from production.models import Line, Machine, WorkCalendar
from production.consumers import DashboardConsumer


class WebSocketInputCountTest(TestCase):
    """WebSocket投入数統合テスト"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        # ログレベルを設定
        logging.disable(logging.WARNING)
        
        # テストユーザー作成
        self.user = User.objects.create_user(
            username='websocketuser',
            password='testpass',
            is_superuser=True
        )
        
        # テストライン作成
        self.line = Line.objects.create(
            name='WebSocketテストライン',
            description='WebSocket用テストライン',
            is_active=True
        )
        
        # テスト設備作成
        self.machine = Machine.objects.create(
            name='WebSocket設備',
            line=self.line,
            is_active=True,
            is_count_target=True
        )
        
        # 稼働カレンダー作成
        self.work_calendar = WorkCalendar.objects.create(
            line=self.line,
            work_start_time=time(8, 30),
            morning_meeting_duration=15
        )
        
        self.test_date_str = '2025-01-15'
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        logging.disable(logging.NOTSET)
    
    @patch('production.utils.Result.objects.filter')
    async def test_dashboard_consumer_includes_input_count(self, mock_result_filter):
        """DashboardConsumerが投入数を含むことのテスト"""
        # モック設定
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = 150
        mock_result_filter.return_value = mock_queryset
        
        # WebSocketコミュニケーター作成
        communicator = WebsocketCommunicator(
            DashboardConsumer.as_asgi(),
            f"/ws/dashboard/{self.line.id}/{self.test_date_str}/"
        )
        
        # ユーザー認証設定
        communicator.scope["user"] = self.user
        
        # 接続テスト
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # データ更新要求
        await communicator.send_json_to({
            'type': 'request_update'
        })
        
        # レスポンス受信
        response = await communicator.receive_json_from()
        
        # レスポンス検証
        self.assertEqual(response['type'], 'dashboard_update')
        self.assertIn('data', response)
        
        dashboard_data = response['data']
        self.assertIn('input_count', dashboard_data)
        self.assertEqual(dashboard_data['input_count'], 150)
        
        # 接続終了
        await communicator.disconnect()
    
    @patch('production.utils.Result.objects.filter')
    async def test_dashboard_update_event_includes_input_count(self, mock_result_filter):
        """dashboard_updateイベントが投入数を含むことのテスト"""
        # モック設定
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = 200
        mock_result_filter.return_value = mock_queryset
        
        # WebSocketコミュニケーター作成
        communicator = WebsocketCommunicator(
            DashboardConsumer.as_asgi(),
            f"/ws/dashboard/{self.line.id}/{self.test_date_str}/"
        )
        
        # ユーザー認証設定
        communicator.scope["user"] = self.user
        
        # 接続テスト
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # DashboardConsumerインスタンスを取得
        consumer = communicator.application.application_mapping[communicator.scope["type"]]
        
        # dashboard_updateイベントをシミュレート
        await consumer.dashboard_update({
            'data': {
                'type': 'result_updated',
                'result_data': {
                    'line_name': self.line.name,
                    'timestamp': '2025-01-15T10:00:00'
                }
            }
        })
        
        # レスポンス受信
        response = await communicator.receive_json_from()
        
        # レスポンス検証
        self.assertEqual(response['type'], 'dashboard_update')
        self.assertIn('data', response)
        
        dashboard_data = response['data']
        self.assertIn('input_count', dashboard_data)
        self.assertEqual(dashboard_data['input_count'], 200)
        
        # 接続終了
        await communicator.disconnect()
    
    async def test_dashboard_consumer_authentication(self):
        """DashboardConsumerの認証テスト"""
        # 匿名ユーザーでの接続テスト
        communicator = WebsocketCommunicator(
            DashboardConsumer.as_asgi(),
            f"/ws/dashboard/{self.line.id}/{self.test_date_str}/"
        )
        
        # 匿名ユーザー設定
        from django.contrib.auth.models import AnonymousUser
        communicator.scope["user"] = AnonymousUser()
        
        # 接続テスト（失敗するはず）
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
    
    @patch('production.utils.Result.objects.filter')
    async def test_dashboard_consumer_error_handling(self, mock_result_filter):
        """DashboardConsumerのエラーハンドリングテスト"""
        # データベースエラーをシミュレート
        mock_result_filter.side_effect = Exception("Database error")
        
        # WebSocketコミュニケーター作成
        communicator = WebsocketCommunicator(
            DashboardConsumer.as_asgi(),
            f"/ws/dashboard/{self.line.id}/{self.test_date_str}/"
        )
        
        # ユーザー認証設定
        communicator.scope["user"] = self.user
        
        # 接続テスト
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # データ更新要求（エラーが発生するはず）
        await communicator.send_json_to({
            'type': 'request_update'
        })
        
        # レスポンス受信（エラー時でもレスポンスが返されるはず）
        response = await communicator.receive_json_from()
        
        # レスポンス検証（エラー時でも基本構造は保持される）
        self.assertEqual(response['type'], 'dashboard_update')
        self.assertIn('data', response)
        
        # 投入数がフォールバック値（0）になることを確認
        dashboard_data = response['data']
        self.assertIn('input_count', dashboard_data)
        self.assertEqual(dashboard_data['input_count'], 0)
        
        # 接続終了
        await communicator.disconnect()


class WebSocketNotificationTest(TestCase):
    """WebSocket通知機能テスト"""
    
    def setUp(self):
        """テストデータのセットアップ"""
        logging.disable(logging.WARNING)
        
        # テストライン作成
        self.line = Line.objects.create(
            name='通知テストライン',
            is_active=True
        )
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        logging.disable(logging.NOTSET)
    
    def test_websocket_notification_function(self):
        """WebSocket通知関数のテスト"""
        from production.models import send_aggregation_update_notification
        
        # モック結果インスタンス作成
        class MockResult:
            def __init__(self):
                self.line = self.line.name
                self.part = 'テスト機種'
                self.judgment = '1'
                self.quantity = 1
                self.timestamp = datetime.now()
        
        mock_result = MockResult()
        
        # 通知関数の実行（エラーが発生しないことを確認）
        try:
            send_aggregation_update_notification(mock_result)
            notification_sent = True
        except Exception as e:
            notification_sent = False
            print(f"Notification error: {e}")
        
        self.assertTrue(notification_sent, "WebSocket notification should be sent without errors")
    
    def test_websocket_notification_with_invalid_line(self):
        """無効なラインでのWebSocket通知テスト"""
        from production.models import send_aggregation_update_notification
        
        # 存在しないラインのモック結果インスタンス作成
        class MockResult:
            def __init__(self):
                self.line = '存在しないライン'
                self.part = 'テスト機種'
                self.judgment = '1'
                self.quantity = 1
                self.timestamp = datetime.now()
        
        mock_result = MockResult()
        
        # 通知関数の実行（エラーが発生しないことを確認）
        try:
            send_aggregation_update_notification(mock_result)
            notification_handled = True
        except Exception as e:
            notification_handled = False
            print(f"Unexpected error: {e}")
        
        self.assertTrue(notification_handled, "WebSocket notification should handle invalid line gracefully")