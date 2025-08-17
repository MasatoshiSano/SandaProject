"""
機種切り替えダウンタイムデータを投入するコマンド
"""
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from production.models import Line, Part, PartChangeDowntime


class Command(BaseCommand):
    help = '機種切り替えダウンタイムデータを作成・更新します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--line',
            type=str,
            help='特定のライン名を指定（指定しない場合は全ライン）'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='既存のダウンタイムデータを削除してから作成'
        )
        parser.add_argument(
            '--random',
            action='store_true',
            help='ランダムなダウンタイム時間を生成（デフォルトは固定パターン）'
        )

    def handle(self, *args, **options):
        # ライン・機種データ取得
        if options['line']:
            lines = Line.objects.filter(name=options['line'])
            if not lines.exists():
                self.stderr.write(
                    self.style.ERROR(f'ライン "{options["line"]}" が見つかりません')
                )
                return
        else:
            lines = Line.objects.all()

        if not lines.exists():
            self.stderr.write(self.style.ERROR('ラインデータが存在しません'))
            return

        # 既存データ削除
        if options['clear']:
            if options['line']:
                deleted_count = PartChangeDowntime.objects.filter(line__in=lines).count()
                PartChangeDowntime.objects.filter(line__in=lines).delete()
            else:
                deleted_count = PartChangeDowntime.objects.count()
                PartChangeDowntime.objects.all().delete()
            
            self.stdout.write(
                self.style.WARNING(f'既存ダウンタイムデータを削除: {deleted_count}件')
            )

        total_created = 0
        total_updated = 0

        # 全ての有効な機種を取得（ラインに依存しない）
        parts = Part.objects.filter(is_active=True)
        
        if parts.count() < 2:
            self.stderr.write(
                self.style.ERROR('有効な機種が2つ未満のため、ダウンタイム設定をスキップします')
            )
            return

        with transaction.atomic():
            for line in lines:
                line_created = 0
                line_updated = 0

                # 全ての機種ペアに対してダウンタイムを設定
                for from_part in parts:
                    for to_part in parts:
                        if from_part == to_part:
                            continue  # 同じ機種への切り替えはスキップ

                        # ダウンタイム時間を決定
                        if options['random']:
                            # ランダム: 5分〜30分
                            downtime_seconds = random.randint(300, 1800)
                        else:
                            # 固定パターン
                            downtime_seconds = self.get_standard_downtime(
                                from_part, to_part
                            )

                        # データ作成・更新
                        downtime, created = PartChangeDowntime.objects.get_or_create(
                            line=line,
                            from_part=from_part,
                            to_part=to_part,
                            defaults={'downtime_seconds': downtime_seconds}
                        )

                        if created:
                            line_created += 1
                        else:
                            # 既存データを更新
                            if downtime.downtime_seconds != downtime_seconds:
                                downtime.downtime_seconds = downtime_seconds
                                downtime.save()
                                line_updated += 1

                self.stdout.write(
                    f'ライン {line.name}: 作成 {line_created}件, 更新 {line_updated}件'
                )
                total_created += line_created
                total_updated += line_updated

        self.stdout.write(
            self.style.SUCCESS(
                f'完了: 合計 作成 {total_created}件, 更新 {total_updated}件'
            )
        )

        # 結果確認
        self.show_summary()

    def get_standard_downtime(self, from_part, to_part):
        """
        標準的なダウンタイム時間を返す
        実際の運用では機種の特性に応じて調整
        """
        # 機種名に基づく簡単なルール
        from_name = from_part.name.upper()
        to_name = to_part.name.upper()

        # 基本ダウンタイム: 10分
        base_time = 600

        # 機種特性による調整例
        if 'A' in from_name and 'B' in to_name:
            return 300  # A→B: 5分
        elif 'B' in from_name and 'A' in to_name:
            return 400  # B→A: 6.7分
        elif 'A' in from_name and 'C' in to_name:
            return 900  # A→C: 15分
        elif 'C' in from_name and 'A' in to_name:
            return 800  # C→A: 13.3分
        elif 'B' in from_name and 'C' in to_name:
            return 450  # B→C: 7.5分
        elif 'C' in from_name and 'B' in to_name:
            return 500  # C→B: 8.3分
        else:
            return base_time

    def show_summary(self):
        """現在のダウンタイム設定を表示"""
        self.stdout.write('\n=== 現在のダウンタイム設定 ===')
        
        lines = Line.objects.all()
        for line in lines:
            downtimes = PartChangeDowntime.objects.filter(line=line).order_by(
                'from_part__name', 'to_part__name'
            )
            
            if downtimes.exists():
                self.stdout.write(f'\n[{line.name}]')
                for dt in downtimes:
                    minutes = dt.downtime_seconds / 60
                    self.stdout.write(
                        f'  {dt.from_part.name} → {dt.to_part.name}: '
                        f'{dt.downtime_seconds}秒 ({minutes:.1f}分)'
                    )
            else:
                self.stdout.write(f'\n[{line.name}] ダウンタイム設定なし')