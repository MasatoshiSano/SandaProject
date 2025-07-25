from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from production.models import Line
from production.utils import calculate_planned_pph_for_date
from datetime import date, timedelta


class Command(BaseCommand):
    help = '計画PPHを計算します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--line',
            type=int,
            help='ライン ID（指定しない場合は全ライン）'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='計算対象日（YYYY-MM-DD形式、指定しない場合は今日）'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='計算する日数（デフォルト: 1日）'
        )

    def handle(self, *args, **options):
        # 対象日の決定
        target_date = date.today()
        if options['date']:
            target_date = parse_date(options['date'])
            if not target_date:
                self.stdout.write(
                    self.style.ERROR(f'無効な日付形式: {options["date"]}')
                )
                return

        # 対象ラインの決定
        lines = []
        if options['line']:
            try:
                line = Line.objects.get(id=options['line'], is_active=True)
                lines = [line]
            except Line.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'ライン ID {options["line"]} が見つかりません')
                )
                return
        else:
            lines = Line.objects.filter(is_active=True)

        if not lines:
            self.stdout.write(
                self.style.WARNING('対象ラインがありません')
            )
            return

        # 計算実行
        total_saved = 0
        days_count = options['days']
        
        for day_offset in range(days_count):
            calc_date = target_date + timedelta(days=day_offset)
            
            self.stdout.write(f'\n{calc_date} の計画PPH計算開始...')
            
            for line in lines:
                self.stdout.write(f'  ライン: {line.name}')
                
                try:
                    saved_count = calculate_planned_pph_for_date(line.id, calc_date)
                    total_saved += saved_count
                    
                    if saved_count > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f'    {saved_count}件保存しました')
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING('    計画データがありません')
                        )
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'    エラー: {str(e)}')
                    )

        self.stdout.write(
            self.style.SUCCESS(f'\n計算完了: 合計 {total_saved}件保存しました')
        )
 