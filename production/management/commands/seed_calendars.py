from datetime import time
from django.core.management.base import BaseCommand
from production.models import Line, WorkCalendar


class Command(BaseCommand):
    help = 'ライン毎の稼働カレンダーサンプルデータを作成します'

    def handle(self, *args, **options):
        print('WorkCalendar を作成中...')
        
        # 既存データ削除
        WorkCalendar.objects.all().delete()
        
        lines = Line.objects.all()
        if not lines.exists():
            print('エラー: ラインが存在しません。先に seed_lines を実行してください。')
            return
        
        # 8:30開始、朝礼15分、標準的な休憩時間
        breaks = [
            {'start':'10:45','end':'11:00'},     # 朝休憩
            {'start':'12:00','end':'12:45'},     # 昼休憩
            {'start':'15:00','end':'15:45'},     # 午後休憩
            {'start':'17:00','end':'17:15'},     # 夕方休憩
            {'start':'19:30','end':'20:00'},     # 夜休憩
            {'start':'23:00','end':'00:00'},     # 深夜休憩
            {'start':'03:00','end':'03:30'},     # 早朝休憩
        ]
        
        total_calendars = 0
        for line in lines:
            calendar = WorkCalendar.objects.create(
                line=line,
                work_start_time=time(8, 30),
                morning_meeting_duration=15,
                break_times=breaks
            )
            total_calendars += 1
            print(f'  {line.name}: 稼働カレンダーを作成しました')

        print(f'合計 {total_calendars} 件の稼働カレンダーを作成しました。')