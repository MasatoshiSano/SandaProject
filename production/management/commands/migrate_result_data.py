from django.core.management.base import BaseCommand
from django.db.models import Q
from production.models import Result, Plan
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = '既存の実績データを新しいplan構造に移行'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の更新は行わず、結果のみ表示する',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # planフィールドがNullの実績を取得
        results_without_plan = Result.objects.filter(plan__isnull=True)
        total_count = results_without_plan.count()
        
        self.stdout.write(f'移行対象の実績数: {total_count}')
        
        updated_count = 0
        not_found_count = 0
        
        for result in results_without_plan:
            # 実績の日付を取得
            result_date = result.timestamp.date()
            
            # 同じライン、機種、機械で当日の計画を検索
            matching_plans = Plan.objects.filter(
                line=result.line,
                part=result.part,
                machine=result.machine,
                date=result_date
            ).order_by('sequence')
            
            if matching_plans.exists():
                # 最初にマッチした計画を選択
                selected_plan = matching_plans.first()
                
                if not dry_run:
                    result.plan = selected_plan
                    result.save()
                
                updated_count += 1
                self.stdout.write(
                    f'✓ 実績 {result.serial_number} → 計画 {selected_plan.id} '
                    f'({selected_plan.date} {selected_plan.part.name})'
                )
            else:
                # マッチする計画が見つからない場合
                not_found_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠ 実績 {result.serial_number} にマッチする計画が見つかりません '
                        f'(日付: {result_date}, ライン: {result.line.name}, '
                        f'機種: {result.part.name}, 機械: {result.machine.name})'
                    )
                )
        
        self.stdout.write('')
        self.stdout.write(f'=== 移行結果 ===')
        self.stdout.write(f'更新された実績: {updated_count}')
        self.stdout.write(f'計画が見つからない実績: {not_found_count}')
        self.stdout.write(f'合計: {updated_count + not_found_count}')
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('DRY RUN完了。実際の更新は行われませんでした。'))
        else:
            self.stdout.write(self.style.SUCCESS('データ移行完了。')) 