from django.core.management.base import BaseCommand
from django.db import transaction
import csv
from pathlib import Path
from production.models import Machine, Line


class Command(BaseCommand):
    help = 'STA_NO3.csvの内容でMachineテーブルを更新'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-path',
            type=str,
            default='/home/sano/SandaDev/STA_NO3.csv',
            help='CSVファイルのパス'
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        
        if not Path(csv_path).exists():
            self.stdout.write(
                self.style.ERROR(f'CSVファイルが見つかりません: {csv_path}')
            )
            return
        
        self.stdout.write('=== Machineテーブル更新開始 ===')
        
        try:
            with transaction.atomic():
                # 既存のMachineレコードを削除
                deleted_count = Machine.objects.count()
                Machine.objects.all().delete()
                self.stdout.write(f'{deleted_count}件のMachineレコードを削除しました。')
                
                # CSVファイルからデータを読み込み
                created_count = 0
                with open(csv_path, 'r', encoding='utf-8-sig') as file:
                    reader = csv.DictReader(file)
                    
                    for row in reader:
                        line_name = row['line'].strip()
                        machine_name = row['name'].strip()
                        description = row['description'].strip()
                        
                        # Lineオブジェクトを取得または作成
                        line, line_created = Line.objects.get_or_create(
                            name=line_name,
                            defaults={
                                'description': f'{line_name}ライン',
                                'is_active': True
                            }
                        )
                        
                        if line_created:
                            self.stdout.write(f'新しいライン \'{line_name}\' を作成しました。')
                        
                        # Machineオブジェクトを作成
                        Machine.objects.create(
                            name=machine_name,
                            line=line,
                            description=description,
                            is_active=True,
                            is_production_active=True
                        )
                        
                        created_count += 1
                        if created_count % 100 == 0:
                            self.stdout.write(f'{created_count}件のMachineレコードを作成しました...')
                
                self.stdout.write(
                    self.style.SUCCESS(f'合計 {created_count}件のMachineレコードを作成しました。')
                )
                
                # 結果確認
                total_machines = Machine.objects.count()
                total_lines = Line.objects.count()
                self.stdout.write(f'現在のMachine数: {total_machines}')
                self.stdout.write(f'現在のLine数: {total_lines}')
                
                self.stdout.write(self.style.SUCCESS('=== Machineテーブル更新完了 ==='))
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'エラーが発生しました: {e}')
            )
            raise