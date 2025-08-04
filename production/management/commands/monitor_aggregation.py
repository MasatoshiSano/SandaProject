"""
集計システム監視コマンド
"""

import json
import time
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from production.monitoring import health_checker, performance_monitor, alert_manager
from production.models import WeeklyResultAggregation, Result


class Command(BaseCommand):
    help = '集計システムの監視とヘルスチェックを実行'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            choices=['health', 'performance', 'continuous', 'report'],
            default='health',
            help='監視モード'
        )
        
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='連続監視の間隔（秒）'
        )
        
        parser.add_argument(
            '--duration',
            type=int,
            default=3600,
            help='連続監視の継続時間（秒）'
        )
        
        parser.add_argument(
            '--output',
            type=str,
            choices=['console', 'json', 'file'],
            default='console',
            help='出力形式'
        )
        
        parser.add_argument(
            '--output-file',
            type=str,
            help='出力ファイルパス（--output=file時）'
        )

    def handle(self, *args, **options):
        mode = options['mode']
        
        if mode == 'health':
            self.run_health_check(options)
        elif mode == 'performance':
            self.run_performance_check(options)
        elif mode == 'continuous':
            self.run_continuous_monitoring(options)
        elif mode == 'report':
            self.generate_report(options)

    def run_health_check(self, options):
        """ヘルスチェックを実行"""
        self.stdout.write("システムヘルスチェックを実行中...")
        
        health_status = health_checker.check_system_health()
        
        if options['output'] == 'json':
            self.stdout.write(json.dumps(health_status, indent=2, ensure_ascii=False))
        elif options['output'] == 'file':
            self.write_to_file(health_status, options['output_file'])
        else:
            self.display_health_status(health_status)
        
        # アラートチェック
        if health_status['overall_status'] != 'healthy':
            alert_manager.send_health_alert(health_status)

    def run_performance_check(self, options):
        """パフォーマンスチェックを実行"""
        self.stdout.write("パフォーマンスチェックを実行中...")
        
        stats = performance_monitor.get_performance_stats()
        
        if options['output'] == 'json':
            self.stdout.write(json.dumps(stats, indent=2, ensure_ascii=False))
        elif options['output'] == 'file':
            self.write_to_file(stats, options['output_file'])
        else:
            self.display_performance_stats(stats)

    def run_continuous_monitoring(self, options):
        """連続監視を実行"""
        interval = options['interval']
        duration = options['duration']
        end_time = time.time() + duration
        
        self.stdout.write(f"連続監視を開始（間隔: {interval}秒, 継続時間: {duration}秒）")
        
        try:
            while time.time() < end_time:
                timestamp = datetime.now().isoformat()
                
                # ヘルスチェック
                health_status = health_checker.check_system_health()
                
                # パフォーマンスチェック
                perf_stats = performance_monitor.get_performance_stats()
                
                # 結果を表示
                self.stdout.write(f"\n[{timestamp}] 監視結果:")
                self.stdout.write(f"  全体ステータス: {health_status['overall_status']}")
                
                # 問題があればアラート
                if health_status['overall_status'] != 'healthy':
                    alert_manager.send_health_alert(health_status)
                
                # 次の監視まで待機
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.stdout.write("\n監視を停止しました")

    def generate_report(self, options):
        """監視レポートを生成"""
        self.stdout.write("監視レポートを生成中...")
        
        # 基本統計
        result_count = Result.objects.count()
        aggregation_count = WeeklyResultAggregation.objects.count()
        
        # 最近24時間の統計
        yesterday = datetime.now() - timedelta(days=1)
        recent_results = Result.objects.filter(timestamp__gte=yesterday).count()
        
        # ライン別統計
        from django.db.models import Count, Max, Min
        line_stats = WeeklyResultAggregation.objects.values('line').annotate(
            count=Count('id'),
            latest_date=Max('date'),
            earliest_date=Min('date')
        ).order_by('-count')
        
        # エラー統計
        error_stats = {}
        try:
            # 既知のエラータイプをチェック
            error_types = [
                'AggregationError', 'DataInconsistencyError', 'AggregationTimeoutError',
                'DatabaseConnectionError', 'ValidationError', 'ConcurrencyError'
            ]
            for error_type in error_types:
                key = f'aggregation_error_stats_{error_type}'
                stat = cache.get(key)
                if stat:
                    error_stats[error_type] = stat
        except Exception:
            error_stats = {}
        
        # パフォーマンス統計
        perf_stats = performance_monitor.get_performance_stats()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'basic_stats': {
                'total_results': result_count,
                'total_aggregations': aggregation_count,
                'recent_results_24h': recent_results
            },
            'line_stats': list(line_stats),
            'error_stats': error_stats,
            'performance_stats': perf_stats,
            'health_status': health_checker.check_system_health()
        }
        
        if options['output'] == 'json':
            self.stdout.write(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        elif options['output'] == 'file':
            self.write_to_file(report, options['output_file'])
        else:
            self.display_report(report)

    def display_health_status(self, health_status):
        """ヘルスステータスを表示"""
        overall = health_status['overall_status']
        
        if overall == 'healthy':
            self.stdout.write(self.style.SUCCESS(f"✅ システム全体: {overall}"))
        elif overall == 'degraded':
            self.stdout.write(self.style.WARNING(f"⚠️  システム全体: {overall}"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ システム全体: {overall}"))
        
        self.stdout.write("\n詳細チェック結果:")
        for check_name, result in health_status['checks'].items():
            status = result.get('status', 'unknown')
            
            if status == 'healthy':
                self.stdout.write(f"  ✅ {check_name}: {status}")
            elif status == 'degraded':
                self.stdout.write(f"  ⚠️  {check_name}: {status}")
            else:
                self.stdout.write(f"  ❌ {check_name}: {status}")
                if 'error' in result:
                    self.stdout.write(f"     エラー: {result['error']}")

    def display_performance_stats(self, stats):
        """パフォーマンス統計を表示"""
        if not stats:
            self.stdout.write("パフォーマンス統計がありません")
            return
        
        self.stdout.write("パフォーマンス統計:")
        for operation, stat in stats.items():
            success_rate = stat.get('success_rate', 0)
            avg_duration = stat.get('avg_duration', 0)
            count = stat.get('count', 0)
            
            status_icon = "✅" if success_rate >= 95 and avg_duration < 5 else "⚠️"
            
            self.stdout.write(
                f"  {status_icon} {operation}: "
                f"成功率 {success_rate:.1f}%, "
                f"平均時間 {avg_duration:.3f}秒, "
                f"実行回数 {count}"
            )

    def display_report(self, report):
        """レポートを表示"""
        self.stdout.write("=== 集計システム監視レポート ===")
        self.stdout.write(f"生成時刻: {report['timestamp']}")
        
        # 基本統計
        basic = report['basic_stats']
        self.stdout.write(f"\n📊 基本統計:")
        self.stdout.write(f"  総実績データ数: {basic['total_results']:,}")
        self.stdout.write(f"  総集計データ数: {basic['total_aggregations']:,}")
        self.stdout.write(f"  24時間以内の実績: {basic['recent_results_24h']:,}")
        
        # ライン別統計
        self.stdout.write(f"\n🏭 ライン別統計（上位5位）:")
        for i, line_stat in enumerate(report['line_stats'][:5], 1):
            self.stdout.write(
                f"  {i}. {line_stat['line']}: {line_stat['count']:,}件 "
                f"({line_stat['earliest_date']} - {line_stat['latest_date']})"
            )
        
        # エラー統計
        if report['error_stats']:
            self.stdout.write(f"\n❌ エラー統計:")
            for error_type, stat in report['error_stats'].items():
                self.stdout.write(f"  {error_type}: {stat['count']}回")
        
        # ヘルスステータス
        health = report['health_status']
        self.stdout.write(f"\n🏥 ヘルスステータス: {health['overall_status']}")

    def write_to_file(self, data, file_path):
        """データをファイルに書き込み"""
        if not file_path:
            raise CommandError("--output-file が指定されていません")
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            self.stdout.write(f"結果を {file_path} に保存しました")
            
        except Exception as e:
            raise CommandError(f"ファイル書き込みエラー: {e}")