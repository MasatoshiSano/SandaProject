import random
from django.core.management.base import BaseCommand
from production.models import Category, Tag, Part


class Command(BaseCommand):
    help = '機種のサンプルデータを作成します（ラインに依存しない）'

    def handle(self, *args, **options):
        print('Category を作成中...')
        
        # 既存データ削除
        Part.objects.all().delete()
        Category.objects.all().delete()
        Tag.objects.all().delete()
        
        # Category 作成
        categories = []
        for g in range(1, 4):
            category = Category.objects.create(
                name=f'Category-{g}', description=f'グループ{g}'
            )
            categories.append(category)
            print(f'  Category-{g} を作成しました')

        # Tag 作成
        print('Tag を作成中...')
        tag_names = [
            '重点管理','量産','試作','高難度','検査要',
            '高速装置','新規導入','要調整','QC必要','保守'
        ]
        tags = []
        for tn in tag_names:
            tag = Tag.objects.create(name=tn)
            tags.append(tag)
            print(f'  {tn} を作成しました')

        # Part 作成（ラインに依存しない機種データ）
        print('Part を作成中...')
        part_data = [
            ('MotorA', 'MA001', 'モータタイプA'),
            ('MotorB', 'MB001', 'モータタイプB'),
            ('MotorC', 'MC001', 'モータタイプC'),
            ('HousingX', 'HX001', 'ハウジングタイプX'),
            ('HousingY', 'HY001', 'ハウジングタイプY'),
            ('HousingZ', 'HZ001', 'ハウジングタイプZ'),
            ('AssemblyA', 'AA001', 'アセンブリタイプA'),
            ('AssemblyB', 'AB001', 'アセンブリタイプB'),
            ('AssemblyC', 'AC001', 'アセンブリタイプC'),
            ('ComponentD', 'CD001', 'コンポーネントタイプD'),
        ]
        
        parts = []
        for name, part_number, description in part_data:
            part = Part.objects.create(
                name=name,
                part_number=part_number,
                category=categories[len(parts) % len(categories)],
                target_pph=random.choice(range(50, 101, 10)),
                description=description,
                is_active=True
            )
            part.tags.set(random.sample(tags, k=random.randint(3, 5)))
            parts.append(part)
            print(f'  {name} ({part_number}) を作成しました')

        print(f'合計 {len(parts)} 件の機種を作成しました。')