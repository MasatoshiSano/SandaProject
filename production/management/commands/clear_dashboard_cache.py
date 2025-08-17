from django.core.management.base import BaseCommand
from django.core.cache import cache
from production.models import Line
from production.utils import clear_dashboard_cache
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'ダッシュボードキャッシュをクリアします'

    def add_arguments(self, parser):
        parser.add_argument(
            '--line-id',
            type=int,
            help='特定のラインIDのキャッシュのみクリア'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='特定の日付のキャッシュのみクリア (YYYY-MM-DD形式)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='すべてのキャッシュをクリア'
        )

    def handle(self, *args, **options):
        if options['all']:
            # すべてのキャッシュをクリア
            cache.clear()
            self.stdout.write(
                self.style.SUCCESS('すべてのキャッシュをクリアしました')
            )
            return

        line_id = options.get('line_id')
        date_str = options.get('date')

        if line_id and date_str:
            # 特定のライン・日付のキャッシュをクリア
            clear_dashboard_cache(line_id, date_str)
            self.stdout.write(
                self.style.SUCCESS(
                    f'ライン{line_id}、日付{date_str}のダッシュボードキャッシュをクリアしました'
                )
            )
        elif line_id:
            # 特定のラインのキャッシュをクリア（今日の日付）
            from django.utils import timezone
            today = timezone.now().date().strftime('%Y-%m-%d')
            clear_dashboard_cache(line_id, today)
            self.stdout.write(
                self.style.SUCCESS(
                    f'ライン{line_id}の本日({today})のダッシュボードキャッシュをクリアしました'
                )
            )
        else:
            # すべてのラインの今日のキャッシュをクリア
            from django.utils import timezone
            today = timezone.now().date().strftime('%Y-%m-%d')
            
            lines = Line.objects.all()
            for line in lines:
                clear_dashboard_cache(line.id, today)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'すべてのライン({lines.count()}ライン)の本日({today})のダッシュボードキャッシュをクリアしました'
                )
            )