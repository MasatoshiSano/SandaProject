import random
import string
from datetime import datetime, date, timedelta, time
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from production.models import Plan, Result, WorkCalendar


def generate_unique_serial(existing_serials, length=15):
    """生成されたシリアルが既存セットにないように15桁の数字文字列を返す。"""
    while True:
        serial = ''.join(random.choices(string.digits, k=length))
        if serial not in existing_serials:
            existing_serials.add(serial)
            return serial


class Command(BaseCommand):
    help = (
        '計画データに基づいてサンプル実績データを作成します。'
        'OK=90-110%、NG率5-10%。休憩中はスキップし、日を越えません。'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--line',
            type=int,
            help='ラインID（指定しない場合は全ライン）'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='開始日（YYYY-MM-DD形式、指定しない場合は今日）'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='指定日以降何日分実行するか（デフォルト:1日）'
        )

    def handle(self, *args, **options):
        # 実績テーブルをクリア（Oracleデータベース）
        Result.objects.using('oracle').all().delete()
        self.stdout.write(self.style.WARNING('既存の実績を全て削除しました'))

        # 引数から日付範囲を決定
        if options['date']:
            try:
                start_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR(
                    '日付の形式が不正です。YYYY-MM-DD で指定してください。'
                ))
                return
        else:
            start_date = timezone.localdate()

        days = options['days']
        line_filter = {}
        if options['line']:
            line_filter['line_id'] = options['line']

        existing_serials = set()
        total_created = 0

        for delta in range(days):
            plan_date = start_date + timedelta(days=delta)
            plans_qs = Plan.objects.filter(date=plan_date, **line_filter).order_by('sequence')
            if not plans_qs.exists():
                self.stdout.write(f'[{plan_date}] 計画データなし → スキップ')
                continue

            self.stdout.write(f'[{plan_date}] サンプル実績作成開始')

            # カレンダー取得
            if options['line']:
                wc = WorkCalendar.objects.filter(line_id=options['line']).first()
            else:
                wc = WorkCalendar.objects.filter(
                    line_id__in=plans_qs.values_list('line_id', flat=True)
                ).first()

            if wc:
                work_start = wc.work_start_time
                breaks = wc.break_times or wc.get_default_break_times()
            else:
                work_start = time(8, 30)
                breaks = [
                    {"start": "10:45", "end": "11:00"},
                    {"start": "12:00", "end": "12:45"},
                    {"start": "15:00", "end": "15:15"},
                    {"start": "17:00", "end": "17:15"},
                ]

            # 休憩時間展開
            all_breaks = []
            next_day = plan_date + timedelta(days=1)
            for bp in breaks:
                b_start = datetime.combine(plan_date, datetime.strptime(bp['start'], '%H:%M').time())
                b_end = datetime.combine(plan_date, datetime.strptime(bp['end'], '%H:%M').time())
                all_breaks.append({'start': b_start, 'end': b_end})
                if datetime.strptime(bp['start'], '%H:%M').time() < work_start:
                    all_breaks.append({
                        'start': datetime.combine(next_day, b_start.time()),
                        'end':   datetime.combine(next_day, b_end.time()),
                    })
            next_day_start = datetime.combine(next_day, work_start)

            created = 0
            current_time = datetime.combine(plan_date, work_start)

            with transaction.atomic():
                for plan in plans_qs:
                    qty_planned = plan.planned_quantity
                    ok_qty = random.randint(int(qty_planned * 0.9), int(qty_planned * 1.1))
                    ng_rate = random.uniform(0.05, 0.10)
                    total_qty = int(ok_qty / (1 - ng_rate))

                    for idx in range(total_qty):
                        if current_time >= next_day_start:
                            break
                        # 休憩中なら終了時刻にスキップ
                        br = next((b for b in all_breaks
                                   if b['start'] <= current_time < b['end']), None)
                        if br:
                            current_time = br['end']
                            if current_time >= next_day_start:
                                break

                        # サイクルタイムをランダム化
                        base_ct   = plan.part.cycle_time
                        cycle_sec = random.uniform(base_ct * 0.9, base_ct * 1.2)
                        serial    = generate_unique_serial(existing_serials)
                        judgment  = 'OK' if idx < ok_qty else 'NG'
                        timestamp = timezone.make_aware(current_time)

                        # ← ここを修正：数値IDではなく name プロパティを文字列で保存
                        Result.objects.using('oracle').create(
                            line=plan.line.name,
                            machine=plan.machine.name,
                            part=plan.part.name,
                            quantity=1,
                            serial_number=serial,
                            judgment=judgment,
                            timestamp=timestamp
                        )
                        created += 1
                        current_time += timedelta(seconds=cycle_sec)

                    if current_time >= next_day_start:
                        break

            self.stdout.write(self.style.SUCCESS(
                f'  → {plan_date} 完了: {created} 件作成'
            ))
            total_created += created

        self.stdout.write(self.style.SUCCESS(
            f'全日程終了: 合計 {total_created} 件のサンプル実績を作成しました。'
        ))
