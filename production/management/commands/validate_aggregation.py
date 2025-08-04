"""
集計データ整合性検証管理コマンド

使用例:
python manage.py validate_aggregation --line-id 1 --date 2025-01-15
python manage.py validate_aggregation --all-lines --start-date 2025-01-01 --end-date 2025-01-31
python manage.py validate_aggregation --line-id 1 --date 2025-01-15 --repair
python manage.py validate_aggregation --all-lines --date 2025-01-15 --detailed
"""

import logging
from datetime import datetime, date, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from production.models import Line, WeeklyResultAggregation
from production.services import AggregationService


class Command(BaseCommand):
    help = '集計データの整合性を検証し、必要に応じて修復します'
    
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
            help='検証対象のライン ID'
        )
        
        parser.add_argument(
            '--all-lines',
            action='store_true',
            help='全ラインを対象に検証'
        )
        
        # 日付指定
        parser.add_argument(
            '--date',
            type=str,
            help='検証対象日（YYYY-MM-DD形式）'
        )
        
        parser.add_argument(
            '--start-date',
            type=str,
            help='検証開始日（YYYY-MM-DD形式）'
        )
        
        parser.add_argument(
            '--end-date',
            type=str,
            help='検証終了日（YYYY-MM-DD形式）'
        )
        
        # オプション
        parser.add_argument(
            '--repair',
            action='store_true',
            help='不整合が検出された場合に自動修復を実行'
        )
        
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='詳細な検証結果を表示'
        )
        
        parser.add_argument(
            '--report-only',
            action='store_true',
            help='レポートのみ生成（修復は行わない）'
        )
        
        parser.add_argument(
            '--output-file',
            type=str,
            help='検証結果をファイルに出力'
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
            
            # 検証処理の実行
            validation_results = self._execute_validation(target_lines, target_dates, options)
            
            # 結果の表示
            self._display_results(validation_results, options)
            
            # ファイル出力
            if options['output_file']:
                self._write_report_to_file(validation_results, options['output_file'])
            
            # 終了メッセージ
            if validation_results['total_inconsistencies'] == 0:
                self.stdout.write(
                    self.style.SUCCESS('すべてのデータが整合性を保っています。')
                )
            else:
                if options['repair']:
                    self.stdout.write(
                        self.style.WARNING(
                            f'{validation_results["repaired_count"]}件の不整合を修復しました。'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f'{validation_results["total_inconsistencies"]}件の不整合が検出されました。'
                            ' --repair オプションで修復できます。'
                        )
                    )
            
        except CommandError:
            raise
        except Exception as e:
            self.logger.error(f"検証コマンドエラー: {e}")
            raise CommandError(f"検証処理中にエラーが発生しました: {e}")
    
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
        
        # 修復とレポートオンリーの競合チェック
        if options['repair'] and options['report_only']:
            raise CommandError('--repair と --report-only は同時に指定できません。')
    
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
        self.stdout.write(self.style.HTTP_INFO('=== 整合性検証サマリー ==='))
        
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
        if options['repair']:
            self.stdout.write(self.style.WARNING('自動修復モード: 不整合を検出した場合に修復'))
        
        if options['detailed']:
            self.stdout.write('詳細モード: 詳細な検証結果を表示')
        
        if options['report_only']:
            self.stdout.write('レポートモード: 修復は行わず結果のみ表示')
        
        if options['output_file']:
            self.stdout.write(f'出力ファイル: {options["output_file"]}')
        
        self.stdout.write('')
    
    def _execute_validation(self, target_lines, target_dates, options):
        """検証処理を実行"""
        total_operations = len(target_lines) * len(target_dates)
        completed_operations = 0
        
        validation_results = {
            'total_checks': 0,
            'consistent_checks': 0,
            'total_inconsistencies': 0,
            'repaired_count': 0,
            'failed_repairs': 0,
            'details': [],
            'summary_by_line': {}
        }
        
        self.stdout.write(self.style.HTTP_INFO('整合性検証を開始します...'))
        
        for line in target_lines:
            line_results = {
                'line_name': line.name,
                'line_id': line.id,
                'total_checks': 0,
                'consistent_checks': 0,
                'inconsistencies': 0,
                'repaired': 0,
                'failed_repairs': 0,
                'details': []
            }
            
            self.stdout.write(f'ライン: {line.name} の検証中...')
            
            for target_date in target_dates:
                try:
                    # 集計データの存在確認
                    aggregation_count = WeeklyResultAggregation.objects.filter(
                        line=line.name,
                        date=target_date
                    ).count()
                    
                    if aggregation_count == 0:
                        detail = {
                            'date': target_date,
                            'status': 'no_aggregation',
                            'message': '集計データが存在しません'
                        }
                        line_results['details'].append(detail)
                        
                        if options['detailed']:
                            self.stdout.write(
                                f'  {target_date}: 集計データなし'
                            )
                        
                        completed_operations += 1
                        continue
                    
                    # 整合性検証
                    is_consistent = self.service.validate_aggregation(line.id, target_date)
                    
                    validation_results['total_checks'] += 1
                    line_results['total_checks'] += 1
                    
                    if is_consistent:
                        validation_results['consistent_checks'] += 1
                        line_results['consistent_checks'] += 1
                        
                        detail = {
                            'date': target_date,
                            'status': 'consistent',
                            'message': '整合性OK'
                        }
                        
                        if options['detailed']:
                            self.stdout.write(
                                self.style.SUCCESS(f'  {target_date}: 整合性OK')
                            )
                    else:
                        validation_results['total_inconsistencies'] += 1
                        line_results['inconsistencies'] += 1
                        
                        detail = {
                            'date': target_date,
                            'status': 'inconsistent',
                            'message': '不整合検出'
                        }
                        
                        self.stdout.write(
                            self.style.ERROR(f'  {target_date}: 不整合検出')
                        )
                        
                        # 自動修復の実行
                        if options['repair'] and not options['report_only']:
                            try:
                                repair_success = self.service.repair_aggregation(line.id, target_date)
                                
                                if repair_success:
                                    validation_results['repaired_count'] += 1
                                    line_results['repaired'] += 1
                                    detail['status'] = 'repaired'
                                    detail['message'] = '不整合を修復しました'
                                    
                                    self.stdout.write(
                                        self.style.SUCCESS(f'    → 修復完了')
                                    )
                                else:
                                    validation_results['failed_repairs'] += 1
                                    line_results['failed_repairs'] += 1
                                    detail['status'] = 'repair_failed'
                                    detail['message'] = '修復に失敗しました'
                                    
                                    self.stdout.write(
                                        self.style.ERROR(f'    → 修復失敗')
                                    )
                                    
                            except Exception as e:
                                validation_results['failed_repairs'] += 1
                                line_results['failed_repairs'] += 1
                                detail['status'] = 'repair_error'
                                detail['message'] = f'修復エラー: {e}'
                                
                                self.stdout.write(
                                    self.style.ERROR(f'    → 修復エラー: {e}')
                                )
                    
                    line_results['details'].append(detail)
                    validation_results['details'].append(detail)
                    
                    # 進捗表示
                    completed_operations += 1
                    progress = (completed_operations / total_operations) * 100
                    
                    if not options['detailed']:
                        if completed_operations % 10 == 0 or completed_operations == total_operations:
                            self.stdout.write(f'  進捗: [{progress:.1f}%]')
                    
                except Exception as e:
                    self.logger.error(f"検証エラー: ライン={line.name}, 日付={target_date}, エラー={e}")
                    
                    detail = {
                        'date': target_date,
                        'status': 'error',
                        'message': f'検証エラー: {e}'
                    }
                    line_results['details'].append(detail)
                    validation_results['details'].append(detail)
                    
                    self.stdout.write(
                        self.style.ERROR(f'  {target_date}: 検証エラー - {e}')
                    )
                    
                    completed_operations += 1
                    continue
            
            validation_results['summary_by_line'][line.name] = line_results
        
        return validation_results
    
    def _display_results(self, results, options):
        """検証結果を表示"""
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('=== 検証結果 ==='))
        
        # 全体サマリー
        self.stdout.write(f'総検証数: {results["total_checks"]}')
        self.stdout.write(f'整合性OK: {results["consistent_checks"]}')
        self.stdout.write(f'不整合検出: {results["total_inconsistencies"]}')
        
        if results['repaired_count'] > 0:
            self.stdout.write(f'修復成功: {results["repaired_count"]}')
        
        if results['failed_repairs'] > 0:
            self.stdout.write(f'修復失敗: {results["failed_repairs"]}')
        
        # 整合性率の計算
        if results['total_checks'] > 0:
            consistency_rate = (results['consistent_checks'] / results['total_checks']) * 100
            self.stdout.write(f'整合性率: {consistency_rate:.1f}%')
        
        # ライン別サマリー
        if len(results['summary_by_line']) > 1:
            self.stdout.write('')
            self.stdout.write(self.style.HTTP_INFO('=== ライン別結果 ==='))
            
            for line_name, line_results in results['summary_by_line'].items():
                self.stdout.write(f'{line_name}:')
                self.stdout.write(f'  検証数: {line_results["total_checks"]}')
                self.stdout.write(f'  整合性OK: {line_results["consistent_checks"]}')
                self.stdout.write(f'  不整合: {line_results["inconsistencies"]}')
                
                if line_results['repaired'] > 0:
                    self.stdout.write(f'  修復成功: {line_results["repaired"]}')
                
                if line_results['failed_repairs'] > 0:
                    self.stdout.write(f'  修復失敗: {line_results["failed_repairs"]}')
    
    def _write_report_to_file(self, results, output_file):
        """検証結果をファイルに出力"""
        try:
            import json
            from datetime import datetime
            
            # JSON形式でレポートを作成
            report = {
                'generated_at': datetime.now().isoformat(),
                'summary': {
                    'total_checks': results['total_checks'],
                    'consistent_checks': results['consistent_checks'],
                    'total_inconsistencies': results['total_inconsistencies'],
                    'repaired_count': results['repaired_count'],
                    'failed_repairs': results['failed_repairs'],
                    'consistency_rate': (results['consistent_checks'] / results['total_checks'] * 100) if results['total_checks'] > 0 else 0
                },
                'line_summary': results['summary_by_line'],
                'details': [
                    {
                        'date': detail['date'].isoformat() if hasattr(detail['date'], 'isoformat') else str(detail['date']),
                        'status': detail['status'],
                        'message': detail['message']
                    }
                    for detail in results['details']
                ]
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            self.stdout.write(f'検証結果を {output_file} に出力しました。')
            
        except Exception as e:
            self.logger.error(f"レポート出力エラー: {e}")
            self.stdout.write(
                self.style.ERROR(f'レポート出力に失敗しました: {e}')
            )