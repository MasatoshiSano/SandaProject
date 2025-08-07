# Generated manually to add unique constraint on card_type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0025_fix_duplicate_card_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dashboardcardsetting',
            name='card_type',
            field=models.CharField(
                max_length=50, 
                unique=True,  # 一意制約を追加
                default='unknown',
                verbose_name='カードタイプ', 
                help_text='カードの識別子です（例: total_planned, total_actual, achievement_rate）。システムが内部的に使用します。'
            ),
        ),
    ]