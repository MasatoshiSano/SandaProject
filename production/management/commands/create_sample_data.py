from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, time, datetime, timedelta
import random

from production.models import (
    Line, UserLineAccess, Machine, Category, Tag, Part, Plan, Result,
    PartChangeDowntime, WorkCalendar, WorkingDay, DashboardCardSetting, UserPreference
)
from production.utils import calculate_planned_pph_for_date


class Command(BaseCommand):
    help = 'サンプルデータを作成します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='既存データを削除してから作成'
        )
        parser.add_argument(
            '--with-results',
            action='store_true',
            help='実績データも作成'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('既存データを削除中...')
            self.clear_existing_data()

        self.stdout.write('サンプルデータ作成開始...')
        
        # 1. ライン作成
        lines = self.create_lines()
        
        # 2. カテゴリとタグ作成
        categories = self.create_categories()
        tags = self.create_tags()
        
        # 3. 機種作成
        parts = self.create_parts(categories, tags)
        
        # 4. 機械作成
        machines = self.create_machines(lines)
        
        # 5. 稼働カレンダー作成
        self.create_work_calendars(lines)
        
        # 6. 機種切替ダウンタイム作成
        self.create_part_change_downtimes(lines, parts)
        
        # 7. 稼働日設定作成
        self.create_working_days()
        
        # 8. ダッシュボード設定作成
        self.create_dashboard_settings()
        
        # 9. 計画作成（過去1週間分）
        plans = self.create_plans(lines, parts, machines)
        
        # 10. 実績作成（オプション）
        if options['with_results']:
            self.create_results(plans)
        
        # 11. ユーザーアクセス設定
        self.create_user_access(lines)
        
        # 12. 計画PPH計算
        self.calculate_planned_pph(lines)
        
        self.stdout.write(
            self.style.SUCCESS('サンプルデータ作成完了！')
        )

    def clear_existing_data(self):
        """既存データを削除"""
        models_to_clear = [
            Result, Plan, PartChangeDowntime, Part, Machine, Tag, Category,
            WorkCalendar, UserLineAccess, Line, WorkingDay, DashboardCardSetting
        ]
        
        for model in models_to_clear:
            count = model.objects.count()
            if count > 0:
                model.objects.all().delete()
                self.stdout.write(f'  {model.__name__}: {count}件削除')

    def create_lines(self):
        """ライン作成"""
        lines_data = [
            {'name': 'ライン1', 'description': 'メイン生産ライン'},
            {'name': 'ライン2', 'description': 'サブ生産ライン'},
            {'name': 'ライン3', 'description': 'テスト用ライン'},
        ]
        
        lines = []
        for line_data in lines_data:
            line, created = Line.objects.get_or_create(
                name=line_data['name'],
                defaults=line_data
            )
            lines.append(line)
            if created:
                self.stdout.write(f'  ライン作成: {line.name}')
        
        return lines

    def create_categories(self):
        """カテゴリ作成"""
        categories_data = [
            {'name': '電子部品', 'color': '#007bff', 'description': '電子部品カテゴリ'},
            {'name': '機械部品', 'color': '#28a745', 'description': '機械部品カテゴリ'},
            {'name': '樹脂部品', 'color': '#ffc107', 'description': '樹脂部品カテゴリ'},
            {'name': 'アッセンブリ', 'color': '#dc3545', 'description': 'アッセンブリカテゴリ'},
        ]
        
        categories = []
        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults=cat_data
            )
            categories.append(category)
            if created:
                self.stdout.write(f'  カテゴリ作成: {category.name}')
        
        return categories

    def create_tags(self):
        """タグ作成"""
        tags_data = [
            {'name': '高精度', 'color': '#6f42c1'},
            {'name': '量産品', 'color': '#20c997'},
            {'name': '試作品', 'color': '#fd7e14'},
            {'name': '重要品', 'color': '#e83e8c'},
        ]
        
        tags = []
        for tag_data in tags_data:
            tag, created = Tag.objects.get_or_create(
                name=tag_data['name'],
                defaults=tag_data
            )
            tags.append(tag)
            if created:
                self.stdout.write(f'  タグ作成: {tag.name}')
        
        return tags

    def create_parts(self, categories, tags):
        """機種作成"""
        parts_data = [
            {'name': '機種A', 'part_number': 'PT-001', 'target_pph': 60, 'category': categories[0]},
            {'name': '機種B', 'part_number': 'PT-002', 'target_pph': 80, 'category': categories[0]},
            {'name': '機種C', 'part_number': 'PT-003', 'target_pph': 120, 'category': categories[1]},
            {'name': '機種D', 'part_number': 'PT-004', 'target_pph': 90, 'category': categories[1]},
            {'name': '機種E', 'part_number': 'PT-005', 'target_pph': 150, 'category': categories[2]},
            {'name': '機種F', 'part_number': 'PT-006', 'target_pph': 100, 'category': categories[2]},
            {'name': '機種G', 'part_number': 'PT-007', 'target_pph': 45, 'category': categories[3]},
            {'name': '機種H', 'part_number': 'PT-008', 'target_pph': 75, 'category': categories[3]},
        ]
        
        parts = []
        for part_data in parts_data:
            part, created = Part.objects.get_or_create(
                name=part_data['name'],
                defaults=part_data
            )
            
            if created:
                # ランダムにタグを割り当て
                part.tags.set(random.sample(tags, random.randint(1, 3)))
                self.stdout.write(f'  機種作成: {part.name} (PPH: {part.target_pph})')
            
            parts.append(part)
        
        return parts

    def create_machines(self, lines):
        """機械作成"""
        machines = []
        
        for i, line in enumerate(lines, 1):
            # 各ラインに2-3台の機械を配置
            machine_count = 2 if i <= 2 else 3
            
            for j in range(1, machine_count + 1):
                machine, created = Machine.objects.get_or_create(
                    name=f'{line.name}-機械{j}',
                    line=line,
                    defaults={'description': f'{line.name}の機械{j}'}
                )
                machines.append(machine)
                if created:
                    self.stdout.write(f'  機械作成: {machine.name}')
        
        return machines

    def create_work_calendars(self, lines):
        """稼働カレンダー作成"""
        default_breaks = [
            {"start": "10:45", "end": "11:00"},  # 休憩1
            {"start": "12:00", "end": "12:45"},  # 昼休み
            {"start": "15:00", "end": "15:15"},  # 休憩2
            {"start": "17:00", "end": "17:15"},  # 休憩3
        ]
        
        work_times = [
            {'start': time(8, 30), 'meeting': 15},  # ライン1
            {'start': time(9, 0), 'meeting': 10},   # ライン2
            {'start': time(8, 0), 'meeting': 20},   # ライン3
        ]
        
        for i, line in enumerate(lines):
            work_time = work_times[i] if i < len(work_times) else work_times[0]
            
            calendar, created = WorkCalendar.objects.get_or_create(
                line=line,
                defaults={
                    'work_start_time': work_time['start'],
                    'morning_meeting_duration': work_time['meeting'],
                    'break_times': default_breaks,
                }
            )
            if created:
                self.stdout.write(f'  稼働カレンダー作成: {line.name}')

    def create_part_change_downtimes(self, lines, parts):
        """機種切替ダウンタイム作成"""
        # 各ラインで主要な機種切替パターンを設定
        downtime_patterns = [
            (parts[0], parts[1], 300),  # 機種A → 機種B: 5分
            (parts[1], parts[0], 400),  # 機種B → 機種A: 6.7分
            (parts[0], parts[2], 600),  # 機種A → 機種C: 10分
            (parts[2], parts[0], 500),  # 機種C → 機種A: 8.3分
            (parts[1], parts[2], 450),  # 機種B → 機種C: 7.5分
            (parts[2], parts[1], 350),  # 機種C → 機種B: 5.8分
        ]
        
        count = 0
        for line in lines:
            for from_part, to_part, seconds in downtime_patterns:
                downtime, created = PartChangeDowntime.objects.get_or_create(
                    line=line,
                    from_part=from_part,
                    to_part=to_part,
                    defaults={'downtime_seconds': seconds}
                )
                if created:
                    count += 1
        
        self.stdout.write(f'  機種切替ダウンタイム: {count}件作成')

    def create_working_days(self):
        """稼働日設定作成"""
        # 過去2週間の稼働日設定
        start_date = date.today() - timedelta(days=14)
        
        working_days = []
        for i in range(15):  # 2週間 + 1日
            target_date = start_date + timedelta(days=i)
            
            # 土日は非稼働、平日は稼働
            is_working = target_date.weekday() < 5
            
            working_day, created = WorkingDay.objects.get_or_create(
                date=target_date,
                defaults={
                    'is_working': is_working,
                    'description': '自動生成' if is_working else '週末'
                }
            )
            working_days.append(working_day)
        
        self.stdout.write(f'  稼働日設定: {len(working_days)}件確認')

    def create_dashboard_settings(self):
        """ダッシュボード設定作成"""
        card_settings = [
            {'name': '計画数', 'alert_threshold_yellow': 95.0, 'alert_threshold_red': 90.0},
            {'name': '実績数', 'alert_threshold_yellow': 95.0, 'alert_threshold_red': 90.0},
            {'name': '達成率', 'alert_threshold_yellow': 95.0, 'alert_threshold_red': 90.0},
            {'name': 'PPH', 'alert_threshold_yellow': 95.0, 'alert_threshold_red': 90.0},
        ]
        
        for i, setting in enumerate(card_settings):
            card, created = DashboardCardSetting.objects.get_or_create(
                name=setting['name'],
                defaults={
                    'order': i * 10,
                    'alert_threshold_yellow': setting['alert_threshold_yellow'],
                    'alert_threshold_red': setting['alert_threshold_red'],
                }
            )
            if created:
                self.stdout.write(f'  ダッシュボード設定: {card.name}')

    def create_plans(self, lines, parts, machines):
        """計画作成（過去1週間分）"""
        plans = []
        
        # 過去1週間の稼働日に計画を作成
        for days_ago in range(7):
            plan_date = date.today() - timedelta(days=days_ago)
            
            # 土日はスキップ
            if plan_date.weekday() >= 5:
                continue
            
            for line in lines:
                line_machines = [m for m in machines if m.line == line]
                if not line_machines:
                    continue
                
                machine = line_machines[0]  # 各ラインの最初の機械を使用
                
                # 各ラインで2-3個の計画を作成
                daily_parts = random.sample(parts, random.randint(2, 4))
                
                for seq, part in enumerate(daily_parts, 1):
                    # 計画数量をランダム生成（PPHに基づいて妥当な数量）
                    base_quantity = part.target_pph * random.randint(1, 3)
                    planned_quantity = base_quantity + random.randint(-20, 20)
                    planned_quantity = max(50, planned_quantity)  # 最小50個
                    
                    plan, created = Plan.objects.get_or_create(
                        date=plan_date,
                        line=line,
                        part=part,
                        machine=machine,
                        sequence=seq,
                        defaults={
                            'planned_quantity': planned_quantity,
                            'start_time': time(8, 30),
                            'end_time': time(17, 0),
                            'notes': f'サンプル計画 - {part.name}'
                        }
                    )
                    
                    if created:
                        plans.append(plan)
        
        self.stdout.write(f'  計画: {len(plans)}件作成')
        return plans

    def create_results(self, plans):
        """実績作成"""
        results = []
        serial_counter = 1
        
        for plan in plans:
            # 計画の70-110%の実績を作成
            achievement_rate = random.uniform(0.7, 1.1)
            actual_quantity = int(plan.planned_quantity * achievement_rate)
            
            # 稼働時間内にランダムに実績を分散
            work_start = datetime.combine(plan.date, time(8, 45))  # 朝礼後
            work_end = datetime.combine(plan.date, time(17, 0))
            
            # タイムゾーンを適用
            work_start = timezone.make_aware(work_start)
            work_end = timezone.make_aware(work_end)
            lunch_start = timezone.make_aware(datetime.combine(plan.date, time(12, 0)))
            lunch_end = timezone.make_aware(datetime.combine(plan.date, time(12, 45)))
            
            # 実績を時間内に分散して作成
            for i in range(actual_quantity):
                # ランダムな時間を生成
                total_seconds = (work_end - work_start).total_seconds()
                random_seconds = random.randint(0, int(total_seconds))
                result_time = work_start + timedelta(seconds=random_seconds)
                
                # 昼休み時間は避ける
                if lunch_start <= result_time <= lunch_end:
                    result_time = lunch_end + timedelta(minutes=random.randint(0, 60))
                
                # 判定をランダムに決定（95%はOK）
                judgment = 'OK' if random.random() < 0.95 else 'NG'
                
                # ユニークなシリアル番号を生成
                serial_number = f'SN{plan.date.strftime("%Y%m%d")}{plan.line.id:02d}{plan.part.id:02d}{serial_counter:06d}'
                serial_counter += 1
                
                result = Result.objects.create(
                    plan=plan,
                    quantity=1,
                    timestamp=result_time,
                    serial_number=serial_number,
                    judgment=judgment,
                    notes='サンプル実績' if judgment == 'OK' else 'サンプル不良'
                )
                results.append(result)
        
        self.stdout.write(f'  実績: {len(results)}件作成')

    def create_user_access(self, lines):
        """ユーザーアクセス設定"""
        # adminユーザーが存在する場合、全ラインにアクセス権を付与
        try:
            admin_user = User.objects.get(username='admin')
            
            access_count = 0
            for line in lines:
                access, created = UserLineAccess.objects.get_or_create(
                    user=admin_user,
                    line=line
                )
                if created:
                    access_count += 1
            
            if access_count > 0:
                self.stdout.write(f'  ユーザーアクセス: {access_count}件作成')
                
        except User.DoesNotExist:
            self.stdout.write('  adminユーザーが見つかりません（アクセス設定スキップ）')

    def calculate_planned_pph(self, lines):
        """計画PPH計算"""
        total_calculated = 0
        
        # 過去1週間分の計画PPHを計算
        for days_ago in range(7):
            calc_date = date.today() - timedelta(days=days_ago)
            
            # 土日はスキップ
            if calc_date.weekday() >= 5:
                continue
            
            for line in lines:
                try:
                    count = calculate_planned_pph_for_date(line.id, calc_date)
                    total_calculated += count
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  計画PPH計算エラー ({line.name}, {calc_date}): {str(e)}')
                    )
        
        if total_calculated > 0:
            self.stdout.write(
                self.style.SUCCESS(f'  計画PPH: {total_calculated}件計算完了')
            ) 