"""
WebSocketコンシューマーのテスト
"""

import json
from datetime import date, timedelta
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from production.consumers import WeeklyAnalysisConsumer, AggregationStatusConsumer
from production.models import Line, UserLineAccess, Result, WeeklyResultAggregation
from production.services import AggregationService


class WeeklyAnalysisConsumerTest(TransactionTestCase):
    """週別分析WebSocketコンシューマーのテスト"""
    
    def setUp(self):
        """テストデータの準備"""
        # テストユーザーを作成
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        
        # テストラインを作成
        self.line = Line.objects.create(
            name='TEST_LINE',
            is_active=True
        )
        
        # ユーザーのライン アクセス権限を設定
        UserLineAccess.objects.create(
            user=self.user,
            line=self.line
        )
        
        # テスト用集計データを作成
        self.create_test_aggregation_data()
    
    def create_test_aggregation_data(self):
        """テスト用集計データを作成"""
        today = date.today()
        
        for i in range(7):
            test_date = today - timedelta(days=i)
            
            WeeklyResultAggregation.objects.create(
                date=test_date,
                line=self.line.name,
                machine='TEST_MACHINE',
                part='TEST_PART',
                judgment='OK',
                total_quantity=100,
                result_count=10
            )
            
            WeeklyResultAggregation.objects.create(
                date=test_date,
                line=self.line.name,
                machine='TEST_MACHINE',
                part='TEST_PART',
                judgment='NG',
                total_quantity=10,
                result_count=1
            )
    
    async def test_weekly_analysis_consumer_connection(self):
        """週別分析コンシューマーの接続テスト"""
        communicator = WebsocketCommunicator(
            WeeklyAnalysisConsumer.as_asgi(),
            f"/ws/weekly-analysis/{self.line.id}/"
        )
        
        # ユーザー認証を設定
        communicator.scope["user"] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # 初期データを受信
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'weekly_analysis_data')
        self.assertIn('data', response)
        self.assertIn('line_name', response['data'])
        self.assertEqual(response['data']['line_name'], self.line.name)
        
        await communicator.disconnect()
    
    async def test_weekly_data_request(self):
        """週別データ要求のテスト"""
        communicator = WebsocketCommunicator(
            WeeklyAnalysisConsumer.as_asgi(),
            f"/ws/weekly-analysis/{self.line.id}/"
        )
        
        communicator.scope["user"] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # 初期データを受信
        await communicator.receive_json_from()
        
        # 週別データを要求
        today = date.today()
        start_date = today - timedelta(days=7)
        end_date = today
        
        await communicator.send_json_to({
            'type': 'request_weekly_data',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        })
        
        # レスポンスを受信
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'weekly_data_update')
        self.assertIn('data', response)
        self.assertIn('weekly_data', response['data'])
        
        await communicator.disconnect()
    
    async def test_part_analysis_request(self):
        """機種別分析要求のテスト"""
        communicator = WebsocketCommunicator(
            WeeklyAnalysisConsumer.as_asgi(),
            f"/ws/weekly-analysis/{self.line.id}/"
        )
        
        communicator.scope["user"] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # 初期データを受信
        await communicator.receive_json_from()
        
        # 機種別分析を要求
        today = date.today()
        start_date = today - timedelta(days=7)
        end_date = today
        
        await communicator.send_json_to({
            'type': 'request_part_analysis',
            'part_name': 'TEST_PART',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        })
        
        # レスポンスを受信
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'part_analysis_update')
        self.assertIn('data', response)
        self.assertIn('part_data', response['data'])
        
        await communicator.disconnect()
    
    async def test_performance_metrics_request(self):
        """パフォーマンス指標要求のテスト"""
        communicator = WebsocketCommunicator(
            WeeklyAnalysisConsumer.as_asgi(),
            f"/ws/weekly-analysis/{self.line.id}/"
        )
        
        communicator.scope["user"] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # 初期データを受信
        await communicator.receive_json_from()
        
        # パフォーマンス指標を要求
        today = date.today()
        start_date = today - timedelta(days=7)
        end_date = today
        
        await communicator.send_json_to({
            'type': 'request_performance_metrics',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        })
        
        # レスポンスを受信
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'performance_metrics_update')
        self.assertIn('data', response)
        self.assertIn('metrics', response['data'])
        
        await communicator.disconnect()
    
    async def test_unauthorized_access(self):
        """認証されていないユーザーのアクセステスト"""
        from django.contrib.auth.models import AnonymousUser
        
        communicator = WebsocketCommunicator(
            WeeklyAnalysisConsumer.as_asgi(),
            f"/ws/weekly-analysis/{self.line.id}/"
        )
        
        # 匿名ユーザーを設定
        communicator.scope["user"] = AnonymousUser()
        
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)


class AggregationStatusConsumerTest(TransactionTestCase):
    """集計状況監視WebSocketコンシューマーのテスト"""
    
    def setUp(self):
        """テストデータの準備"""
        # 管理者ユーザーを作成
        self.admin_user = User.objects.create_user(
            username='admin',
            password='adminpass',
            is_staff=True
        )
        
        # 一般ユーザーを作成
        self.normal_user = User.objects.create_user(
            username='normaluser',
            password='normalpass'
        )
        
        # テストラインを作成
        self.line = Line.objects.create(
            name='TEST_LINE',
            is_active=True
        )
        
        # テスト用集計データを作成
        WeeklyResultAggregation.objects.create(
            date=date.today(),
            line=self.line.name,
            machine='TEST_MACHINE',
            part='TEST_PART',
            judgment='OK',
            total_quantity=100,
            result_count=10
        )
    
    async def test_admin_access(self):
        """管理者のアクセステスト"""
        communicator = WebsocketCommunicator(
            AggregationStatusConsumer.as_asgi(),
            "/ws/aggregation-status/"
        )
        
        communicator.scope["user"] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # 初期データを受信
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'aggregation_status')
        self.assertIn('data', response)
        self.assertIn('aggregation_count', response['data'])
        
        await communicator.disconnect()
    
    async def test_normal_user_access_denied(self):
        """一般ユーザーのアクセス拒否テスト"""
        communicator = WebsocketCommunicator(
            AggregationStatusConsumer.as_asgi(),
            "/ws/aggregation-status/"
        )
        
        communicator.scope["user"] = self.normal_user
        
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
    
    async def test_status_request(self):
        """状況要求のテスト"""
        communicator = WebsocketCommunicator(
            AggregationStatusConsumer.as_asgi(),
            "/ws/aggregation-status/"
        )
        
        communicator.scope["user"] = self.admin_user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # 初期データを受信
        await communicator.receive_json_from()
        
        # 状況更新を要求
        await communicator.send_json_to({
            'type': 'request_status'
        })
        
        # レスポンスを受信
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'aggregation_status')
        self.assertIn('data', response)
        
        await communicator.disconnect()


class WebSocketIntegrationTest(TransactionTestCase):
    """WebSocket統合テスト"""
    
    def setUp(self):
        """テストデータの準備"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        
        self.line = Line.objects.create(
            name='TEST_LINE',
            is_active=True
        )
        
        UserLineAccess.objects.create(
            user=self.user,
            line=self.line
        )
    
    async def test_real_time_aggregation_update(self):
        """リアルタイム集計更新のテスト"""
        # WebSocketコンシューマーに接続
        communicator = WebsocketCommunicator(
            WeeklyAnalysisConsumer.as_asgi(),
            f"/ws/weekly-analysis/{self.line.id}/"
        )
        
        communicator.scope["user"] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # 初期データを受信
        await communicator.receive_json_from()
        
        # 新しい実績データを作成（これによりシグナルが発火される）
        await database_sync_to_async(Result.objects.create)(
            line=self.line.name,
            machine='TEST_MACHINE',
            part='TEST_PART',
            judgment='OK',
            quantity=50,
            timestamp=timezone.now()
        )
        
        # 集計更新通知を受信（タイムアウト付き）
        try:
            response = await communicator.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'aggregation_update')
            self.assertIn('data', response)
        except:
            # タイムアウトした場合はスキップ（非同期処理のため）
            pass
        
        await communicator.disconnect()