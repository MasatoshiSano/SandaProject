import jpholiday
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from production.models import WorkingDay

class Command(BaseCommand):
    help = '稼働日を2025-01-01～2027-01-01まで登録します'

    def handle(self, *args, **options):
        start_date = date(2025, 1, 1)
        end_date = date(2027, 1, 1)
        delta = timedelta(days=1)
        current = start_date
        count = 0

        while current <= end_date:
            # 祝日判定
            holiday_name = jpholiday.is_holiday_name(current)
            is_holiday = bool(holiday_name)
            # 土日または祝日は非稼働日
            is_working = not (current.weekday() >= 5 or is_holiday)

            # WorkingDay を update_or_create
            WorkingDay.objects.update_or_create(
                date=current,
                defaults={
                    'is_working': is_working,
                    'is_holiday': is_holiday,
                    'holiday_name': holiday_name or None,
                }
            )
            count += 1
            current += delta

        self.stdout.write(self.style.SUCCESS(
            f'{count} 件の稼働日情報を登録しました。'
        ))