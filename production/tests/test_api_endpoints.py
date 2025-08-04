"""
APIエンドポイントのテスト
"""

import json
from datetime import date, timedelta
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from production.models import Line, UserLineAccess, WeeklyResultAggregation


@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    },
    DATABASE_ROUTERS=[],  # ルーターを無効化
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
)
class TestAPIEndpoints(TestCase):
    """APIエンドポイントのテスト"""
    
    def setUp(self):
        """テスト用データの準備"""
        # テスト用ユーザー作成
        self.user = User.objects.create_user(
            username='apiuser',
            password='apipass123'
        )
        
        # テスト用ライン作成
        self.line = Line.objects.create(
            name="APIテストライン",
            description="APIテスト用ライン"
        )
        
        # ユーザーラインアクセス設定
        UserLineAccess.objects.create(
            user=self.user,
            line=self.line
        )
        
        # テスト用日付
        self.test_date = date(2025, 1, 15)
        self.week_start = self.test_date - timedelta(days=self.test_date.weekday())
        self.week_dates = [self.week_start + timedelta(days=i) for i in range(7)]
        
        # テスト用集計データを作成
        self._create_test_aggregation_data()
        
        # クライアント設定
        self.client = Client()
        self.client.login(username='apiuser', password='apipass123')
    
    def _create_test_aggregation_data(self):
        """テスト用の集計データを作成"""
        aggregations = []
        
        # 各日に複数の機種のデータを作成
        for i, day in enumerate(self.week_dates):
            for part_num in range(3):  # 3機種
                # OK判定のデータ
                aggregations.append(
                    WeeklyResultAggregation(
                        date=day,
                        line=self.line.name,
                        machine=f"機械{part_num % 2}",
                        part=f"製品{part_num}",
                        judgment="OK",
                        total_quantity=50 + i * 5 + part_num * 10,
                        result_count=5 + i + part_num
                    )
                )
                
                # NG判定のデータ
                aggregations.append(
                    WeeklyResultAggregation(
                        date=day,
                        line=self.line.name,
                        machine=f"機械{part_num % 2}",
                        part=f"製品{part_num}",
                        judgment="NG",
                        total_quantity=2 + part_num,
                        result_count=1
                    )
                )
        
        # バルクインサートで効率的に作成
        WeeklyResultAggregation.objects.bulk_create(aggregations)
    
    def test_graph_data_api_weekly(self):
        """週別グラフデータAPIのテスト"""
        url = reverse('production:graph_api', kwargs={
            'line_id': self.line.id,
            'period': 'weekly',
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        response = self.client.get(url)
        
        # レスポンスの基本確認
        self.assertEqual(response.status_code, 200)
        
        # JSONデータの確認
        data = json.loads(response.content)
        self.assertIn('data', data)
        self.assertIn('source', data)
        
        # データ構造の確認
        api_data = data['data']
        self.assertEqual(len(api_data), 7)  # 7日分のデータ
        
        # 各日のデータ構造確認
        for day_data in api_data:
            self.assertIn('date', day_data)
            self.assertIn('total_planned', day_data)
            self.assertIn('total_actual', day_data)
            self.assertIn('parts', day_data)
            self.assertIn('achievement_rate', day_data)
    
    def test_weekly_analysis_api(self):
        """週別分析APIのテスト"""
        url = reverse('production:weekly_analysis_api', kwargs={
            'line_id': self.line.id,
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        response = self.client.get(url)
        
        # レスポンスの基本確認
        self.assertEqual(response.status_code, 200)
        
        # JSONデータの確認
        data = json.loads(response.content)
        
        # 必要なフィールドの確認
        expected_fields = [
            'line_id', 'date', 'week_start', 'week_end',
            'chart_data', 'weekly_stats', 'part_analysis',
            'performance_metrics', 'daily_data', 'metadata'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        # ライン ID の確認
        self.assertEqual(data['line_id'], self.line.id)
        
        # 週の範囲確認
        self.assertEqual(data['week_start'], self.week_dates[0].strftime('%Y-%m-%d'))
        self.assertEqual(data['week_end'], self.week_dates[-1].strftime('%Y-%m-%d'))
        
        # チャートデータの構造確認
        chart_data = data['chart_data']
        self.assertIn('labels', chart_data)
        self.assertIn('planned', chart_data)
        self.assertIn('actual', chart_data)
        self.assertEqual(len(chart_data['labels']), 7)
        
        # 機種別分析の確認
        part_analysis = data['part_analysis']
        self.assertIsInstance(part_analysis, list)
        if part_analysis:
            for part in part_analysis:
                self.assertIn('name', part)
                self.assertIn('ok_quantity', part)
                self.assertIn('achievement_rate', part)
        
        # メタデータの確認
        metadata = data['metadata']
        self.assertIn('source', metadata)
        self.assertIn('generated_at', metadata)
        self.assertEqual(metadata['source'], 'aggregation_service')
    
    def test_performance_metrics_api(self):
        """パフォーマンス指標APIのテスト"""
        url = reverse('production:performance_metrics_api', kwargs={
            'line_id': self.line.id,
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        response = self.client.get(url)
        
        # レスポンスの基本確認
        self.assertEqual(response.status_code, 200)
        
        # JSONデータの確認
        data = json.loads(response.content)
        
        # 必要なフィールドの確認
        expected_fields = [
            'line_id', 'date', 'week_dates',
            'performance_metrics', 'hourly_trend', 'metadata'
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)
        
        # パフォーマンス指標の確認
        metrics = data['performance_metrics']
        expected_metrics = [
            'total_production', 'total_defects', 'defect_rate',
            'working_days', 'daily_average', 'part_count',
            'machine_count', 'production_stability', 'efficiency_score'
        ]
        
        for metric in expected_metrics:
            self.assertIn(metric, metrics)
        
        # 数値の妥当性確認
        self.assertGreaterEqual(metrics['total_production'], 0)
        self.assertGreaterEqual(metrics['defect_rate'], 0)
        self.assertLessEqual(metrics['defect_rate'], 100)
        self.assertGreaterEqual(metrics['working_days'], 0)
        self.assertLessEqual(metrics['working_days'], 7)
    
    def test_api_error_handling(self):
        """APIエラーハンドリングのテスト"""
        # 無効な日付形式
        url = reverse('production:weekly_analysis_api', kwargs={
            'line_id': self.line.id,
            'date': 'invalid-date'
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
    
    def test_api_access_control(self):
        """APIアクセス制御のテスト"""
        # ログアウト
        self.client.logout()
        
        url = reverse('production:weekly_analysis_api', kwargs={
            'line_id': self.line.id,
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        response = self.client.get(url)
        
        # 認証が必要なため、リダイレクトまたは403エラー
        self.assertIn(response.status_code, [302, 403])
    
    def test_api_performance(self):
        """APIパフォーマンステスト"""
        import time
        
        url = reverse('production:weekly_analysis_api', kwargs={
            'line_id': self.line.id,
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        # 初回実行時間を測定
        start_time = time.time()
        response1 = self.client.get(url)
        first_execution_time = time.time() - start_time
        
        # 2回目実行時間を測定（キャッシュ効果）
        start_time = time.time()
        response2 = self.client.get(url)
        second_execution_time = time.time() - start_time
        
        # 両方とも成功することを確認
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        
        # キャッシュにより2回目が高速であることを確認
        self.assertLess(second_execution_time, first_execution_time)
        
        print(f"週別分析API - 初回: {first_execution_time:.4f}秒, キャッシュ: {second_execution_time:.4f}秒")
    
    def test_api_data_consistency(self):
        """APIデータ整合性のテスト"""
        # 週別分析APIとグラフデータAPIの結果を比較
        weekly_url = reverse('production:weekly_analysis_api', kwargs={
            'line_id': self.line.id,
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        graph_url = reverse('production:graph_api', kwargs={
            'line_id': self.line.id,
            'period': 'weekly',
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        weekly_response = self.client.get(weekly_url)
        graph_response = self.client.get(graph_url)
        
        self.assertEqual(weekly_response.status_code, 200)
        self.assertEqual(graph_response.status_code, 200)
        
        weekly_data = json.loads(weekly_response.content)
        graph_data = json.loads(graph_response.content)
        
        # 基本的なデータ整合性確認
        self.assertEqual(len(weekly_data['daily_data']), len(graph_data['data']))
    
    def test_api_response_format(self):
        """APIレスポンス形式のテスト"""
        url = reverse('production:weekly_analysis_api', kwargs={
            'line_id': self.line.id,
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Content-Typeの確認
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # JSONとしてパース可能であることを確認
        try:
            data = json.loads(response.content)
            self.assertIsInstance(data, dict)
        except json.JSONDecodeError:
            self.fail("レスポンスが有効なJSONではありません")
    
    def test_api_with_no_data(self):
        """データがない場合のAPIテスト"""
        # 集計データを削除
        WeeklyResultAggregation.objects.all().delete()
        
        url = reverse('production:weekly_analysis_api', kwargs={
            'line_id': self.line.id,
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        response = self.client.get(url)
        
        # データがない場合は404または空データを返す
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            data = json.loads(response.content)
            # 空データでも基本構造は維持される
            self.assertIn('chart_data', data)
            self.assertIn('weekly_stats', data)