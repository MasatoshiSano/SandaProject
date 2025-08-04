"""
実績データ集計管理コマンド

使用例:
python manage.py aggregate_results --line-id 1 --start-date 2025-01-01 --end-date 2025-01-31
python manage.py aggregate_results --line-id 1 --date 2025-01-15
python manage.py aggregate_results --all-lines --start-date 2025-01-01 --end-date 2025-01-07
python manage.py aggregate_results --line-id 1 --date 2025-01-15 --force
"""

import logging
from datetime import datetime, date, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from production.models import Line, WeeklyResultAggregation
from production.services import AggregationService


class Command(BaseCommand):
    help = '実績データの集計処理を実行します'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = AggregationService()
        self.logger = logging.getLogger(__name__)
    
    def add_arguments(self, parser):
        """コマンドライン引数を定義"""
        # ライン指定
        parser.add_argument(
            '--line-id',
            type=int,
            help='集計対象のライン ID'
        )
        
        parser.add_argument(
            '--all-lines',
            action='store_true',
            help='全ラインを対象に集計'
        )
        
        # 日付指定
        parser.add_argument(
            '--date',
            type=str,
            help='集計対象日（YYYY-MM-DD形式）'
        )
        
        parser.add_argument(
            '--start-date',
            type=str,
            help='集計開始日（YYYY-MM-DD形式）'
        )
        
        parser.add_argument(
            '--end-date',
            type=str,
            help='集計終了日（YYYY-MM-DD形式）'
        )
        
        # オプション
        parser.add_argument(
            '--force',
            action='store_true',
            help='既存の集計データを強制的に再作成'
        )
        
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='バッチ処理のサイズ（デフォルト: 100）'
        )
        
        parser.add_argument(
            '--validate',
            action='store_true',
            help='集計後にデータ整合性を検証'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の処理は行わず、処理内容のみ表示'
        )
    
    def handle(self, *args, **options):
        """メインの処理"""
        try:
            # 引数の検証
            self._validate_arguments(options)
            
            # 対象ラインの取得
            target_lines = self._get_target_lines(options)
            
            # 対象日付の取得
            target_dates = self._get_target_dates(options)
            
            # 処理内容の表示
            self._display_summary(target_lines, target_dates, options)
            
            if options['dry_run']:
                self.stdout.write(
                    self.style.WARNING('ドライランモードのため、実際の処理は行いません。')
                )
                return
            
            # 集計処理の実行
            self._execute_aggregation(target_lines, target_dates, options)
            
            self.stdout.write(
                self.style.SUCCESS('集計処理が正常に完了しました。')
            )
            
        except CommandError:
            raise
        except Exception as e:
            self.logger.error(f"集計コマンドエラー: {e}")
            raise CommandError(f"集計処理中にエラーが発生しました: {e}")
    
    def _validate_arguments(self, options):
        """引数の妥当性を検証"""
        # ライン指定の検証
        if not options['line_id'] and not options['all_lines']:
            raise CommandError('--line-id または --all-lines のいずれかを指定してください。')
        
        if options['line_id'] and options['all_lines']:
            raise CommandError('--line-id と --all-lines は同時に指定できません。')
        
        # 日付指定の検証
        date_options = [options['date'], options['start_date'], options['end_date']]
        specified_dates = [opt for opt in date_options if opt is not None]
        
        if not specified_dates:
            raise CommandError('日付を指定してください（--date または --start-date/--end-date）。')
        
        if options['date'] and (options['start_date'] or options['end_date']):
            raise CommandError('--date と --start-date/--end-date は同時に指定できません。')
        
        if (options['start_date'] and not options['end_date']) or \
           (not options['start_date'] and options['end_date']):
            raise CommandError('--start-date と --end-date は両方指定してください。')
    
    def _get_target_lines(self, options):
        """対象ラインを取得"""
        if options['all_lines']:
            lines = Line.objects.filter(is_active=True)
            if not lines.exists():
                raise CommandError('有効なラインが見つかりません。')
            return list(lines)
        else:
            try:
                line = Line.objects.get(id=options['line_id'], is_active=True)
                return [line]
            except Line.DoesNotExist:
                raise CommandError(f"ライン ID {options['line_id']} が見つかりません。")
    
    def _get_target_dates(self, options):
        """対象日付を取得"""
        try:
            if options['date']:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
                return [target_date]
            else:
                start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
                end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
                
                if start_date > end_date:
                    raise CommandError('開始日は終了日より前の日付を指定してください。')
                
                # 日付リストを生成
                dates = []
                current_date = start_date
                while current_date <= end_date:
                    dates.append(current_date)
                    current_date += timedelta(days=1)
                
                return dates
                
        except ValueError as e:
            raise CommandError(f"日付形式が正しくありません（YYYY-MM-DD形式で指定してください）: {e}")
    
    def _display_summary(self, target_lines, target_dates, options):
        """処理内容のサマリーを表示"""
        self.stdout.write(self.style.HTTP_INFO('=== 集計処理サマリー ==='))
        
        # 対象ライン
        self.stdout.write(f'対象ライン数: {len(target_lines)}')
        for line in target_lines:
            self.stdout.write(f'  - {line.name} (ID: {line.id})')
        
        # 対象日付
        self.stdout.write(f'対象日付数: {len(target_dates)}')
        if len(target_dates) <= 7:
            for target_date in target_dates:
                self.stdout.write(f'  - {target_date}')
        else:
            self.stdout.write(f'  - {target_dates[0]} ～ {target_dates[-1]}')
        
        # オプション
        if options['force']:
            self.stdout.write(self.style.WARNING('強制再作成モード: 既存データを削除して再作成'))
        
        if options['validate']:
            self.stdout.write('データ整合性検証: 有効')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('ドライランモード: 実際の処理は行いません'))
        
        # 推定処理時間
        total_operations = len(target_lines) * len(target_dates)
        estimated_time = total_operations * 0.1  # 1操作あたり0.1秒と仮定
        self.stdout.write(f'推定処理時間: 約{estimated_time:.1f}秒')
        
        self.stdout.write('')
    
    def _execute_aggregation(self, target_lines, target_dates, options):
        """集計処理を実行"""
        total_operations = len(target_lines) * len(target_dates)
        completed_operations = 0
        
        self.stdout.write(self.style.HTTP_INFO('集計処理を開始します...'))
        
        for line in target_lines:
            self.stdout.write(f'ライン: {line.name} の処理中...')
            
            for target_date in target_dates:
                try:
                    # 既存データの確認
                    existing_count = WeeklyResultAggregation.objects.filter(
                        line=line.name,
                        date=target_date
                    ).count()
                    
                    if existing_count > 0 and not options['force']:
                        self.stdout.write(
                            f'  {target_date}: スキップ（既存データあり、--force で強制実行可能）'
                        )
                        completed_operations += 1
                        continue
                    
                    # 集計処理の実行
                    with transaction.atomic():
                        created_count = self.service.aggregate_single_date(line.id, target_date)
                    
                    # 進捗表示
                    completed_operations += 1
                    progress = (completed_operations / total_operations) * 100
                    
                    self.stdout.write(
                        f'  {target_date}: 完了 ({created_count}件作成) '
                        f'[{progress:.1f}%]'
                    )
                    
                    # データ整合性検証
                    if options['validate']:
                        is_valid = self.service.validate_aggregation(line.id, target_date)
                        if not is_valid:
                            self.stdout.write(
                                self.style.WARNING(f'    警告: データ整合性に問題があります')
                            )
                    
                except Exception as e:
                    self.logger.error(f"集計エラー: ライン={line.name}, 日付={target_date}, エラー={e}")
                    self.stdout.write(
                        self.style.ERROR(f'  {target_date}: エラー - {e}')
                    )
                    completed_operations += 1
                    continue
        
        # 処理結果のサマリー
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('=== 処理結果 ==='))
        self.stdout.write(f'総処理数: {total_operations}')
        self.stdout.write(f'完了数: {completed_operations}')
        
        # 最終的なデータ統計
        total_aggregations = WeeklyResultAggregation.objects.count()
        self.stdout.write(f'総集計レコード数: {total_aggregations}')
    
    def _format_duration(self, seconds):
        """秒数を読みやすい形式に変換"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{int(minutes)}分{remaining_seconds:.1f}秒"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            return f"{int(hours)}時間{int(remaining_minutes)}分"