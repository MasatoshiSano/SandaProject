
# production/management/commands/seed_sample_data.py

import random
from datetime import date, time, timedelta

from django.core.management.base import BaseCommand

from production.models import (
    Line, Machine, Category, Tag, Part,
    PartChangeDowntime, WorkCalendar, Plan, Result
)


class Command(BaseCommand):
    help = 'サンプルデータを削除＆投入します'

    def handle(self, *args, **options):
        # 1) 既存データ削除（外部キー制約を考慮した順序）
        print('既存データを削除中...')
        
        # 外部キー制約を無効化してから削除（PostgreSQL用）
        from django.db import connection
        cursor = connection.cursor()
        
        try:
            # PostgreSQLの場合：制約を一時的に無効化
            cursor.execute("SET session_replication_role = replica;")
            
            # 全テーブルのデータを削除
            Result.objects.all().delete()
            Plan.objects.all().delete()
            PartChangeDowntime.objects.all().delete()
            WorkCalendar.objects.all().delete()
            
            # Part削除前にtagsのクリア
            for part in Part.objects.all():
                part.tags.clear()
            Part.objects.all().delete()
            
            Tag.objects.all().delete()
            Category.objects.all().delete()
            Machine.objects.all().delete()
            Line.objects.all().delete()
            
            # 制約を再有効化
            cursor.execute("SET session_replication_role = DEFAULT;")
            
        except Exception as e:
            print(f'データ削除時エラー: {e}')
            # 制約を確実に再有効化
            try:
                cursor.execute("SET session_replication_role = DEFAULT;")
            except:
                pass

        # 2) Line 作成（コード＋日本語説明）
        print('Line を作成中...')
        line_defs = [
            ('KAHA01', 'ハウジング組立1号ライン'),
            ('KAHA02', 'ハウジング組立2号ライン'),
            ('KAHA03', 'ハウジング組立3号ライン'),
            ('KAHA04', 'ハウジング組立4号ライン'),
            ('KAHA05', 'ハウジング組立5号ライン'),
            ('KAHA06', 'ハウジング組立6号ライン'),
            ('KAHA07', 'ハウジング組立7号ライン'),
            ('KAHA08', 'ハウジング組立8号ライン'),
            ('KJCW42', '巻線42号ライン'),
            ('KJCW43', '巻線43号ライン'),
            ('KJMA41', 'モータ組立41号ライン'),
            ('KJMA42', 'モータ組立42号ライン'),
            ('KJMA43', 'モータ組立43号ライン'),
        ]
        lines = []
        for code, desc in line_defs:
            lines.append(Line.objects.create(name=code, description=desc, is_active=True))

        # 3) Machine 作成（各ライン5台）
        print('Machine を作成中...')
        machines_by_line = {}
        for line in lines:
            machines = []
            for i in range(1, 6):
                m = Machine.objects.create(
                    name=f'{line.name}-M{i:02d}',
                    line=line,
                    description=f'{line.description} 設備{i}',
                    is_active=True,
                    is_production_active=False
                )
                machines.append(m)
            machines_by_line[line.id] = machines

        # 4) Category 作成
        print('Category を作成中...')
        categories = []
        for g in range(1, 4):
            categories.append(Category.objects.create(
                name=f'Category-{g}', description=f'グループ{g}'
            ))

        # 5) Tag 作成
        print('Tag を作成中...')
        tag_names = [
            '重点管理','量産','試作','高難度','検査要',
            '高速装置','新規導入','要調整','QC必要','保守'
        ]
        tags = [Tag.objects.create(name=tn) for tn in tag_names]

        # 6) Part 作成
        print('Part を作成中...')
        parts = []
        for idx, ch in enumerate([chr(c) for c in range(65, 80)]):  # A-O
            part = Part.objects.create(
                name=f'Part-{ch}',
                part_number=f'P{ch}001',
                category=categories[idx//5],
                target_pph=random.choice(range(50, 101, 10)),
                description=f'機種{ch}',
                is_active=True
            )
            part.tags.set(random.sample(tags, k=random.randint(3,5)))
            parts.append(part)

        # 7) PartChangeDowntime 作成
        print('PartChangeDowntime を作成中...')
        for line in lines:
            objs = []
            for f in parts:
                for t in parts:
                    if f == t: continue
                    objs.append(PartChangeDowntime(
                        line=line,
                        from_part=f,
                        to_part=t,
                        downtime_seconds=random.randint(900, 1800)
                    ))
            PartChangeDowntime.objects.bulk_create(objs)

        # 8) WorkCalendar 作成
        print('WorkCalendar を作成中...')
        breaks = [
            {'start':'10:45','end':'11:00'},
            {'start':'12:00','end':'12:45'},
            {'start':'15:00','end':'15:45'},
            {'start':'17:00','end':'17:15'},
            {'start':'19:30','end':'20:00'},
            {'start':'23:00','end':'00:00'},
            {'start':'03:00','end':'03:30'},
        ]
        for line in lines:
            WorkCalendar.objects.create(
                line=line,
                work_start_time=time(8,30),
                morning_meeting_duration=15,
                break_times=breaks
            )

        # 9) Plan 作成
        print('Plan を作成中...')
        start = date(2025,7,1)
        end = date(2025,10,1)
        day = timedelta(days=1)
        dt = start
        plan_objs = []
        while dt <= end:
            for line in lines:
                for seq, part in enumerate(random.sample(parts, k=random.randint(3,5)), 1):
                    plan_objs.append(Plan(
                        date=dt, line=line, part=part,
                        machine=machines_by_line[line.id][-1],
                        start_time=time(8,30), end_time=time(8,30),
                        planned_quantity=random.choice(range(300,601,10)),
                        sequence=seq
                    ))
            dt += day
        print(f'  合計 {len(plan_objs)} 件の Plan を bulk_create します...')
        Plan.objects.bulk_create(plan_objs)

        print('サンプルデータ投入が完了しました。')

