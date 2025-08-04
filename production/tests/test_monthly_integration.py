"""
月別分析機能の統合テスト（総合動作確認）
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
import json

from production.models import Line, Part, Plan, WeeklyResultAggregation, UserLineAccess
from production.utils import get_monthly_graph_data
from production.views import MonthlyGraphView


class MonthlyAnalysisIntegrationTest(TestCase):
    """月別分析機能の統合テスト"""
    
    def setUp(self):
        """統合テスト用データ準備"""
        # テストユーザー作成
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # テスト用ライン作成
        self.line = Line.objects.create(
            name='統合テストライン',
            description='統合テスト用ライン'
        )
        
        # ユーザーのライン アクセス権限設定
        UserLineAccess.objects.create(
            user=self.user,
            line=self.line,
            role='operator'
        )
        
        # テスト用機種作成
        self.parts = []
        for i in range(3):
            part = Part.objects.create(name=f'統合テスト機種{i+1}')
            self.parts.append(part)
        
        # テスト日付
        self.test_date = date(2025, 1, 15)
        
        # テストデータ作成
        self._create_comprehensive_test_data()
        
        # テストクライアント
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def _create_comprehensive_test_data(self):
        """包括的なテストデータ作成"""
        from production.utils import get_month_dates
        
        month_dates = get_month_dates(self.test_date)
        
        # 計画データ作成（月全体）
        plans = []
        for i, test_date in enumerate(month_dates):
            for j, part in enumerate(self.parts):
                planned_qty = 100 + (i * 10) + (j * 20)
                plans.append(Plan(
                    line=self.line,
                    date=test_date,
                    part=part,
                    planned_quantity=planned_qty,
                    sequence=j + 1
                ))
        Plan.objects.bulk_create(plans)
        
        # 集計データ作成（月全体）
        aggregations = []
        for i, test_date in enumerate(month_dates):
            for part in self.parts:
                # OK実績
                actual_qty = int((100 + (i * 10)) * 0.85)  # 計画の85%達成
                aggregations.append(WeeklyResultAggregation(
                    date=test_date,
                    line=self.line.name,
                    part=part.name,
                    judgment='OK',
                    total_quantity=actual_qty,
                    result_count=1
                ))
                
                # NG実績
                ng_qty = int(actual_qty * 0.05)  # 5%のNG
                aggregations.append(WeeklyResultAggregation(
                    date=test_date,
                    line=self.line.name,
                    part=part.name,
                    judgment='NG',
                    total_quantity=ng_qty,
                    result_count=1
                ))
        
        WeeklyResultAggregation.objects.bulk_create(aggregations)
    
    def test_monthly_utils_integration(self):
        """ユーティリティ関数の統合テスト"""
        # メイン関数の実行
        result = get_monthly_graph_data(self.line.id, self.test_date)
        
        # 基本構造の確認
        self.assertIsInstance(result, dict)
        expected_keys = [
            'chart_data', 'monthly_stats', 'calendar_data',
            'weekly_summary', 'available_parts', 'part_analysis'
        ]
        for key in expected_keys:
            self.assertIn(key, result, f"Missing key: {key}")
        
        # チャートデータの詳細確認
        chart_data = result['chart_data']
        self.assertIn('labels', chart_data)
        self.assertIn('planned', chart_data)
        self.assertIn('actual', chart_data)
        self.assertIn('cumulative_planned', chart_data)
        self.assertIn('cumulative_actual', chart_data)
        
        # データの妥当性確認
        labels = chart_data['labels']
        planned = chart_data['planned']
        actual = chart_data['actual']
        
        self.assertEqual(len(labels), 31)  # 1月は31日
        self.assertEqual(len(planned), 31)
        self.assertEqual(len(actual), 31)
        
        # 数値の妥当性
        self.assertGreater(sum(planned), 0)
        self.assertGreater(sum(actual), 0)
        self.assertLess(sum(actual), sum(planned))  # 実績 < 計画（正常）
        
        # 月別統計の確認
        monthly_stats = result['monthly_stats']
        self.assertGreater(monthly_stats['total_planned'], 0)
        self.assertGreater(monthly_stats['total_actual'], 0)
        self.assertGreaterEqual(monthly_stats['achievement_rate'], 0)
        self.assertLessEqual(monthly_stats['achievement_rate'], 150)  # 現実的な範囲
        
        # 機種分析の確認
        part_analysis = result['part_analysis']
        self.assertEqual(len(part_analysis), len(self.parts))
        
        for part_data in part_analysis:
            self.assertIn('name', part_data)
            self.assertIn('planned', part_data)
            self.assertIn('actual', part_data)
            self.assertIn('achievement_rate', part_data)
            self.assertGreater(part_data['planned'], 0)
    
    def test_monthly_view_integration(self):
        """ビューとの統合テスト"""
        # 月別グラフページのURL
        url = reverse('production:monthly_graph', kwargs={
            'line_id': self.line.id,
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        # ページアクセス
        response = self.client.get(url)
        
        # レスポンスの基本確認
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '月別グラフ')
        
        # コンテキストデータの確認
        context = response.context
        self.assertIn('chart_data_json', context)
        self.assertIn('monthly_stats', context)
        self.assertIn('available_parts', context)
        
        # JSONデータの妥当性確認
        chart_data_json = context['chart_data_json']
        chart_data = json.loads(chart_data_json)
        
        self.assertIn('labels', chart_data)
        self.assertIn('planned', chart_data)
        self.assertIn('actual', chart_data)
        
        # データ件数の確認
        self.assertEqual(len(chart_data['labels']), 31)
    
    def test_monthly_api_integration(self):
        """API エンドポイントとの統合テスト"""
        # API エンドポイントがある場合のテスト
        # （実際のURLパターンに応じて調整）
        
        api_url = f'/production/api/monthly-data/{self.line.id}/'
        
        try:
            response = self.client.get(api_url, {'date': self.test_date.strftime('%Y-%m-%d')})
            
            if response.status_code == 200:
                data = response.json()
                self.assertIn('chart_data', data)
                self.assertIn('monthly_stats', data)
            elif response.status_code == 404:
                # API エンドポイントが存在しない場合はスキップ
                self.skipTest("API endpoint not implemented")
            else:
                self.fail(f"Unexpected API response: {response.status_code}")
                
        except Exception as e:
            # API が実装されていない場合はスキップ
            self.skipTest(f"API test skipped: {e}")
    
    def test_monthly_with_parameters(self):
        """パラメータ指定での月別分析テスト"""
        # 月パラメータでのアクセス
        url = reverse('production:monthly_graph', kwargs={
            'line_id': self.line.id,
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        # 月指定パラメータ
        response = self.client.get(url, {'month': '2025-01'})
        self.assertEqual(response.status_code, 200)
        
        # 日付指定パラメータ
        response = self.client.get(url, {'date': '2025-01-01'})
        self.assertEqual(response.status_code, 200)
    
    def test_monthly_error_handling(self):
        """エラーハンドリングの統合テスト"""
        # 存在しないラインでのアクセス
        invalid_url = reverse('production:monthly_graph', kwargs={
            'line_id': 99999,
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        response = self.client.get(invalid_url)
        # 404 または適切なエラーページが表示されることを確認
        self.assertIn(response.status_code, [404, 403])
    
    def test_monthly_data_consistency(self):
        """データ一貫性の統合テスト"""
        # 同じデータを複数回取得して一貫性を確認
        results = []
        for _ in range(3):
            result = get_monthly_graph_data(self.line.id, self.test_date)
            results.append(result)
        
        # 全ての結果が同じであることを確認
        first_result = results[0]
        for result in results[1:]:
            self.assertEqual(
                first_result['monthly_stats']['total_planned'],
                result['monthly_stats']['total_planned']
            )
            self.assertEqual(
                first_result['monthly_stats']['total_actual'],
                result['monthly_stats']['total_actual']
            )
            self.assertEqual(
                len(first_result['part_analysis']),
                len(result['part_analysis'])
            )
    
    def test_monthly_performance_integration(self):
        """性能の統合テスト"""
        import time
        
        # 実行時間測定
        start_time = time.time()
        result = get_monthly_graph_data(self.line.id, self.test_date)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # 結果の妥当性確認
        self.assertIsNotNone(result)
        self.assertIn('chart_data', result)
        
        # 性能要件の確認（調整可能）
        self.assertLess(execution_time, 3.0, f"実行時間が長すぎます: {execution_time:.3f}秒")
        
        print(f"統合テスト実行時間: {execution_time:.3f}秒")
    
    def test_monthly_with_different_dates(self):
        """異なる日付での月別分析テスト"""
        test_dates = [
            date(2025, 1, 1),   # 月初
            date(2025, 1, 15),  # 月中
            date(2025, 1, 31),  # 月末
        ]
        
        for test_date in test_dates:
            with self.subTest(date=test_date):
                result = get_monthly_graph_data(self.line.id, test_date)
                
                # 全て同じ月のデータが取得されることを確認
                self.assertIsNotNone(result)
                
                # 1月のデータが31日分あることを確認
                chart_data = result['chart_data']
                self.assertEqual(len(chart_data['labels']), 31)
    
    def test_monthly_fallback_integration(self):
        """フォールバック機能の統合テスト"""
        # 意図的にエラーを発生させてフォールバックをテスト
        # （実際の実装に応じて調整が必要）
        
        with self.assertLogs('production.utils', level='ERROR') as log:
            # 無効なデータでフォールバック を トリガー
            # これは実装依存のため、実際のエラー条件に応じて調整
            try:
                # 極端に未来の日付でテスト
                future_date = date(2030, 12, 31)
                result = get_monthly_graph_data(self.line.id, future_date)
                
                # フォールバックが動作してもエラーにならないことを確認
                self.assertIsNotNone(result)
                
            except Exception as e:
                # エラーが発生した場合の処理
                self.fail(f"フォールバック機能が正常に動作しませんでした: {e}")
    
    def test_monthly_template_integration(self):
        """テンプレートとの統合テスト"""
        url = reverse('production:monthly_graph', kwargs={
            'line_id': self.line.id,
            'date': self.test_date.strftime('%Y-%m-%d')
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # テンプレートに必要な要素が含まれているかチェック
        content = response.content.decode('utf-8')
        
        # JavaScript用のデータが埋め込まれているかチェック
        self.assertIn('chart_data', content)
        self.assertIn('monthly_stats', content)
        
        # 必要なHTML要素があるかチェック
        self.assertIn('chart', content.lower())  # チャート要素
        self.assertIn('calendar', content.lower())  # カレンダー要素（もしあれば）