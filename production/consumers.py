import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Line, UserLineAccess
# from .services import WeeklyAnalysisService  # 一時的にコメントアウト
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)


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
        # Get fresh dashboard data to include updated input count
        dashboard_data = await self.get_dashboard_data()
        
        # Send updated dashboard data to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'dashboard_update',
            'data': dashboard_data
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
        """ダッシュボードデータを取得（集計データ使用）"""
        from .utils import get_dashboard_data
        # from .services import WeeklyAnalysisService  # 一時的にコメントアウト
        from datetime import datetime, timedelta
        
        try:
            # 従来のダッシュボードデータを取得
            dashboard_data = get_dashboard_data(self.line_id, self.date)
            
            # 集計サービスを使用して追加の高速データを取得
            # weekly_service = WeeklyAnalysisService()  # 一時的にコメントアウト
            # target_date = datetime.strptime(self.date, '%Y-%m-%d').date()
            # 
            # # 週別データを取得
            # week_start = target_date - timedelta(days=target_date.weekday())
            # week_end = week_start + timedelta(days=6)
            # 
            # line = Line.objects.get(id=self.line_id)
            # weekly_data = weekly_service.get_weekly_data(line.name, week_start, week_end)
            # performance_metrics = weekly_service.get_performance_metrics(line.name, week_start, week_end)
            # 
            # # 集計データを追加
            # dashboard_data['aggregated_weekly_data'] = weekly_data
            # dashboard_data['performance_metrics'] = performance_metrics
            # dashboard_data['data_source'] = 'aggregated'  # データソースを明示
            
            return dashboard_data
            
        except Exception as e:
            # エラー時は従来のデータのみ返す
            return get_dashboard_data(self.line_id, self.date) 

class WeeklyAnalysisConsumer(AsyncWebsocketConsumer):
    """週別分析専用のWebSocketコンシューマー（集計データ使用）"""
    
    async def connect(self):
        self.line_id = self.scope['url_route']['kwargs']['line_id']
        self.room_group_name = f'weekly_analysis_{self.line_id}'
        
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
        
        # 接続時に初期データを送信
        initial_data = await self.get_weekly_analysis_data()
        await self.send(text_data=json.dumps({
            'type': 'weekly_analysis_data',
            'data': initial_data
        }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type', '')
        
        if message_type == 'request_weekly_data':
            # 週別データの更新要求
            start_date = text_data_json.get('start_date')
            end_date = text_data_json.get('end_date')
            
            weekly_data = await self.get_weekly_data_range(start_date, end_date)
            await self.send(text_data=json.dumps({
                'type': 'weekly_data_update',
                'data': weekly_data
            }))
            
        elif message_type == 'request_part_analysis':
            # 機種別分析の要求
            part_name = text_data_json.get('part_name')
            start_date = text_data_json.get('start_date')
            end_date = text_data_json.get('end_date')
            
            part_data = await self.get_part_analysis_data(part_name, start_date, end_date)
            await self.send(text_data=json.dumps({
                'type': 'part_analysis_update',
                'data': part_data
            }))
            
        elif message_type == 'request_performance_metrics':
            # パフォーマンス指標の要求
            start_date = text_data_json.get('start_date')
            end_date = text_data_json.get('end_date')
            
            metrics = await self.get_performance_metrics_data(start_date, end_date)
            await self.send(text_data=json.dumps({
                'type': 'performance_metrics_update',
                'data': metrics
            }))

    # Receive message from room group
    async def weekly_analysis_update(self, event):
        """週別分析データの更新を受信"""
        await self.send(text_data=json.dumps({
            'type': 'weekly_analysis_update',
            'data': event['data']
        }))
    
    async def aggregation_update(self, event):
        """集計データの更新を受信"""
        await self.send(text_data=json.dumps({
            'type': 'aggregation_update',
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
    def get_weekly_analysis_data(self):
        """週別分析データを取得（初期データ）"""
        try:
            line = Line.objects.get(id=self.line_id)
            # service = WeeklyAnalysisService()  # 一時的にコメントアウト
            
            # 今週のデータを取得
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            # weekly_data = service.get_weekly_data(line.name, week_start, week_end)  # 一時的にコメントアウト
            # performance_metrics = service.get_performance_metrics(line.name, week_start, week_end)  # 一時的にコメントアウト
            weekly_data = []
            performance_metrics = {}
            
            return {
                'line_name': line.name,
                'week_start': week_start.isoformat(),
                'week_end': week_end.isoformat(),
                'weekly_data': weekly_data,
                'performance_metrics': performance_metrics,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"週別分析データ取得エラー: {e}")
            return {'error': str(e)}

    @database_sync_to_async
    def get_weekly_data_range(self, start_date_str, end_date_str):
        """指定期間の週別データを取得"""
        try:
            line = Line.objects.get(id=self.line_id)
            # service = WeeklyAnalysisService()  # 一時的にコメントアウト
            
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            # weekly_data = service.get_weekly_data(line.name, start_date, end_date)  # 一時的にコメントアウト
            weekly_data = []
            
            return {
                'line_name': line.name,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'weekly_data': weekly_data,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"週別データ範囲取得エラー: {e}")
            return {'error': str(e)}

    @database_sync_to_async
    def get_part_analysis_data(self, part_name, start_date_str, end_date_str):
        """機種別分析データを取得"""
        try:
            line = Line.objects.get(id=self.line_id)
            # service = WeeklyAnalysisService()  # 一時的にコメントアウト
            
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            # part_data = service.get_part_analysis(line.name, part_name, start_date, end_date)  # 一時的にコメントアウト
            part_data = []
            
            return {
                'line_name': line.name,
                'part_name': part_name,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'part_data': part_data,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"機種別分析データ取得エラー: {e}")
            return {'error': str(e)}

    @database_sync_to_async
    def get_performance_metrics_data(self, start_date_str, end_date_str):
        """パフォーマンス指標データを取得"""
        try:
            line = Line.objects.get(id=self.line_id)
            # service = WeeklyAnalysisService()  # 一時的にコメントアウト
            
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            # metrics = service.get_performance_metrics(line.name, start_date, end_date)  # 一時的にコメントアウト
            metrics = {}
            
            return {
                'line_name': line.name,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'metrics': metrics,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"パフォーマンス指標取得エラー: {e}")
            return {'error': str(e)}


class AggregationStatusConsumer(AsyncWebsocketConsumer):
    """集計処理状況監視用のWebSocketコンシューマー"""
    
    async def connect(self):
        self.room_group_name = 'aggregation_status'
        
        # 管理者権限チェック
        user = self.scope["user"]
        if user.is_anonymous or not user.is_staff:
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        # 接続時に現在の状況を送信
        status_data = await self.get_aggregation_status()
        await self.send(text_data=json.dumps({
            'type': 'aggregation_status',
            'data': status_data
        }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type', '')
        
        if message_type == 'request_status':
            # 集計状況の更新要求
            status_data = await self.get_aggregation_status()
            await self.send(text_data=json.dumps({
                'type': 'aggregation_status',
                'data': status_data
            }))

    # Receive message from room group
    async def aggregation_status_update(self, event):
        """集計状況の更新を受信"""
        await self.send(text_data=json.dumps({
            'type': 'aggregation_status_update',
            'data': event['data']
        }))

    @database_sync_to_async
    def get_aggregation_status(self):
        """集計処理の状況を取得"""
        try:
            from .models import WeeklyResultAggregation, Result
            
            # 集計データの統計
            aggregation_count = WeeklyResultAggregation.objects.count()
            result_count = Result.objects.count()
            
            # 最新の集計データ
            latest_aggregation = WeeklyResultAggregation.objects.order_by('-date').first()
            latest_result = Result.objects.order_by('-timestamp').first()
            
            # ライン別の集計状況
            from django.db.models import Count
            line_stats = WeeklyResultAggregation.objects.values('line').annotate(
                count=Count('serial_number')
            ).order_by('-count')
            
            return {
                'aggregation_count': aggregation_count,
                'result_count': result_count,
                'latest_aggregation_date': latest_aggregation.date.isoformat() if latest_aggregation else None,
                'latest_result_timestamp': latest_result.timestamp.isoformat() if latest_result else None,
                'line_stats': list(line_stats),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"集計状況取得エラー: {e}")
            return {'error': str(e)}