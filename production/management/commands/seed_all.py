from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = '全てのサンプルデータを順序通りに作成します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            default='2025-07-01',
            help='計画開始日 (YYYY-MM-DD形式、デフォルト: 2025-07-01)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            default='2025-10-01',
            help='計画終了日 (YYYY-MM-DD形式、デフォルト: 2025-10-01)'
        )

    def handle(self, *args, **options):
        print('=== 全サンプルデータ作成開始 ===')
        
        commands = [
            ('seed_lines', '1. ライン作成'),
            ('seed_machines', '2. 設備作成'),
            ('seed_parts', '3. 機種作成'),
            ('seed_downtime', '4. 段取り時間作成'),
            ('seed_calendars', '5. 稼働カレンダー作成'),
        ]
        
        # 順次実行
        for cmd, description in commands:
            print(f'\n{description}...')
            try:
                call_command(cmd)
                print(f'✓ {description} 完了')
            except Exception as e:
                print(f'✗ {description} 失敗: {e}')
                return
        
        # 生産計画作成（日付オプション付き）
        print(f'\n6. 生産計画作成...')
        try:
            call_command('seed_plans', 
                        start_date=options['start_date'],
                        end_date=options['end_date'])
            print('✓ 生産計画作成 完了')
        except Exception as e:
            print(f'✗ 生産計画作成 失敗: {e}')
            return
        
        print('\n=== 全サンプルデータ作成完了 ===')
        print('※ 計画PPH計算を実行する場合:')
        print(f'   python manage.py calculate_planned_pph --date {options["start_date"]} --days 92')