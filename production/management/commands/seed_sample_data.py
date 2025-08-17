
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
        
        try:
            # 外部キー制約を考慮した順序で削除
            print('  Result削除中...')
            Result.objects.using('default').all().delete()
            
            print('  Plan削除中...')
            Plan.objects.using('default').all().delete()
            
            print('  PartChangeDowntime削除中...')
            PartChangeDowntime.objects.using('default').all().delete()
            
            print('  WorkCalendar削除中...')
            WorkCalendar.objects.using('default').all().delete()
            
            print('  Part削除中...')
            # Part削除前にtagsのクリア
            for part in Part.objects.using('default').all():
                part.tags.clear()
            Part.objects.using('default').all().delete()
            
            print('  Tag削除中...')
            Tag.objects.using('default').all().delete()
            
            print('  Category削除中...')
            Category.objects.using('default').all().delete()
            
            print('  Machine削除中...')
            Machine.objects.using('default').all().delete()
            
            print('  Line削除中...')
            Line.objects.using('default').all().delete()
            
            print('既存データ削除完了')
            
        except Exception as e:
            print(f'データ削除時エラー: {e}')
            print('エラーを無視して処理を続行します...')

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
            category, created = Category.objects.get_or_create(
                name=f'Category-{g}',
                defaults={'description': f'グループ{g}'}
            )
            categories.append(category)
            if created:
                print(f'  Category-{g} を作成しました')
            else:
                print(f'  Category-{g} は既存です')

        # 5) Tag 作成
        print('Tag を作成中...')
        tag_names = [
            '重点管理','量産','試作','高難度','検査要',
            '高速装置','新規導入','要調整','QC必要','保守'
        ]
        tags = []
        for tn in tag_names:
            tag, created = Tag.objects.get_or_create(name=tn)
            tags.append(tag)
            if created:
                print(f'  {tn} を作成しました')
            else:
                print(f'  {tn} は既存です')

        # 6) Part 作成（同じ機種を複数ラインで生産）
        print('Part を作成中...')
        parts = []
        part_names = ['MotorA', 'MotorB', 'HousingX', 'HousingY', 'AssemblyZ']
        
        # 各機種を複数のラインで生産できるように設定
        part_line_combinations = [
            # MotorA は複数のモータ組立ラインで生産
            ('MotorA', ['KJMA41', 'KJMA42', 'KJMA43']),
            # MotorB も複数のモータ組立ラインで生産  
            ('MotorB', ['KJMA41', 'KJMA42']),
            # HousingX は複数のハウジング組立ラインで生産
            ('HousingX', ['KAHA01', 'KAHA02', 'KAHA03', 'KAHA04']),
            # HousingY は一部のハウジング組立ラインで生産
            ('HousingY', ['KAHA05', 'KAHA06', 'KAHA07']),
            # AssemblyZ は巻線ラインで生産
            ('AssemblyZ', ['KJCW42', 'KJCW43']),
        ]
        
        for part_name, line_codes in part_line_combinations:
            for line_code in line_codes:
                # ライン名からLineオブジェクトを取得
                line = next((l for l in lines if l.name == line_code), None)
                if not line:
                    continue
                    
                part, created = Part.objects.get_or_create(
                    part_number=f'{part_name}-{line_code}',
                    defaults={
                        'name': part_name,
                        'line': line,
                        'category': categories[len(parts) % len(categories)],
                        'target_pph': random.choice(range(50, 101, 10)),
                        'description': f'{part_name}（{line.description}用）',
                        'is_active': True
                    }
                )
                if created:
                    part.tags.set(random.sample(tags, k=random.randint(3,5)))
                    print(f'  {part_name} を {line.name} ラインに作成しました')
                else:
                    print(f'  {part_name} @ {line.name} は既存です')
                parts.append(part)
        
        print(f'合計 {len(parts)} 件の機種×ライン組み合わせを作成しました')

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
        start = date(2025,8,1)
        end = date(2025,9,1)
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
        print('※ 計画PPH計算は手動で実行してください: python manage.py calculate_planned_pph --date 2025-07-01 --days 92')

