from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from production.models import Plan
from production.utils import calculate_planned_pph_for_date


class Command(BaseCommand):
    help = '計画PPHを再計算します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='過去何日分を再計算するか（デフォルト: 7日）'
        )

    def handle(self, *args, **options):
        days = options['days']
        today = timezone.now().date()
        start_date = today - timedelta(days=days)
        
        self.stdout.write(f"{start_date}から{today}までの計画PPHを再計算します...")
        
        # 日付とラインの組み合わせを取得
        plans = Plan.objects.filter(date__gte=start_date)
        processed = set()
        
        for plan in plans:
            key = (plan.line_id, plan.date)
            if key not in processed:
                try:
                    count = calculate_planned_pph_for_date(plan.line_id, plan.date)
                    self.stdout.write(f"  {plan.date} - {plan.line.name}: {count}件の計画PPHを計算")
                    processed.add(key)
                except Exception as e:
                    self.stderr.write(f"  エラー - {plan.date} - {plan.line.name}: {str(e)}")
        
        self.stdout.write(self.style.SUCCESS(f"完了: {len(processed)}件の日付/ライン組み合わせを処理しました")) 