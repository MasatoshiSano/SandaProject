import random
from django.core.management.base import BaseCommand
from production.models import Line, Part, PartChangeDowntime


class Command(BaseCommand):
    help = '機種切替ダウンタイムのサンプルデータを作成します'

    def handle(self, *args, **options):
        print('PartChangeDowntime を作成中...')
        
        # 既存データ削除
        PartChangeDowntime.objects.all().delete()
        
        lines = Line.objects.all()
        parts = Part.objects.all()
        
        if not lines.exists():
            print('エラー: ラインが存在しません。先に seed_lines を実行してください。')
            return
        
        if not parts.exists():
            print('エラー: 機種が存在しません。先に seed_parts を実行してください。')
            return
        
        total_downtimes = 0
        for line in lines:
            downtime_objs = []
            for from_part in parts:
                for to_part in parts:
                    if from_part == to_part:
                        continue
                    downtime_objs.append(PartChangeDowntime(
                        line=line,
                        from_part=from_part,
                        to_part=to_part,
                        downtime_seconds=random.randint(900, 1800)  # 15-30分
                    ))
            
            PartChangeDowntime.objects.bulk_create(downtime_objs)
            total_downtimes += len(downtime_objs)
            print(f'  {line.name}: {len(downtime_objs)} 件の段取り時間を作成しました')

        print(f'合計 {total_downtimes} 件の段取り時間を作成しました。')