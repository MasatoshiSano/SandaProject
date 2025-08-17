from django.core.management.base import BaseCommand
from production.models import Line


class Command(BaseCommand):
    help = 'ラインのサンプルデータを作成します'

    def handle(self, *args, **options):
        print('Line を作成中...')
        
        # 既存データ削除
        Line.objects.all().delete()
        
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
            line = Line.objects.create(name=code, description=desc, is_active=True)
            lines.append(line)
            print(f'  {code} - {desc} を作成しました')

        print(f'合計 {len(lines)} 件のラインを作成しました。')