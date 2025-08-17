from django.core.management.base import BaseCommand
from production.models import Line, Machine


class Command(BaseCommand):
    help = 'ライン毎の設備サンプルデータを作成します'

    def handle(self, *args, **options):
        print('Machine を作成中...')
        
        # 既存データ削除
        Machine.objects.all().delete()
        
        lines = Line.objects.all()
        if not lines.exists():
            print('エラー: ラインが存在しません。先に seed_lines を実行してください。')
            return
        
        total_machines = 0
        for line in lines:
            for i in range(1, 6):  # 各ライン5台の設備
                machine = Machine.objects.create(
                    name=f'{line.name}-M{i:02d}',
                    line=line,
                    description=f'{line.description} 設備{i}',
                    is_active=True,
                    is_production_active=False
                )
                total_machines += 1
                print(f'  {machine.name} ({line.description}) を作成しました')

        print(f'合計 {total_machines} 件の設備を作成しました。')