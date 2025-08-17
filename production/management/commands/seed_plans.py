import random
from datetime import date, time, timedelta
from django.core.management.base import BaseCommand
from production.models import Line, Machine, Part, Plan


class Command(BaseCommand):
    help = '生産計画のサンプルデータを作成します'

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
        print('Plan を作成中...')
        
        # 既存データ削除
        Plan.objects.all().delete()
        
        lines = Line.objects.all()
        parts = Part.objects.all()
        
        if not lines.exists():
            print('エラー: ラインが存在しません。先に seed_lines を実行してください。')
            return
        
        if not parts.exists():
            print('エラー: 機種が存在しません。先に seed_parts を実行してください。')
            return
        
        # 各ラインの代表設備を取得
        machines_by_line = {}
        for line in lines:
            machine = Machine.objects.filter(line=line).first()
            if machine:
                machines_by_line[line.id] = machine
            else:
                print(f'警告: {line.name} に設備が存在しません。先に seed_machines を実行してください。')
                return
        
        # 日付範囲を解析
        try:
            start = date.fromisoformat(options['start_date'])
            end = date.fromisoformat(options['end_date'])
        except ValueError as e:
            print(f'エラー: 日付形式が正しくありません: {e}')
            return
        
        day = timedelta(days=1)
        dt = start
        plan_objs = []
        
        while dt <= end:
            for line in lines:
                # 各日、各ラインでランダムに3-5機種の計画を作成
                selected_parts = random.sample(list(parts), k=random.randint(3, 5))
                for seq, part in enumerate(selected_parts, 1):
                    plan_objs.append(Plan(
                        date=dt,
                        line=line,
                        part=part,
                        machine=machines_by_line[line.id],
                        start_time=time(8, 30),
                        end_time=time(8, 30),
                        planned_quantity=random.choice(range(300, 601, 10)),
                        sequence=seq
                    ))
            dt += day
        
        print(f'  合計 {len(plan_objs)} 件の Plan を bulk_create します...')
        Plan.objects.bulk_create(plan_objs)
        
        print(f'期間: {start} ～ {end}')
        print(f'合計 {len(plan_objs)} 件の生産計画を作成しました。')