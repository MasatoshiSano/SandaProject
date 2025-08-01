# Generated by Django 4.2.7 on 2025-06-07 09:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0002_result_notes_result_plan_result_quantity_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlannedHourlyProduction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='日付')),
                ('hour', models.PositiveIntegerField(help_text='0-47（0-23=当日、24-47=翌日）', verbose_name='時間帯')),
                ('planned_quantity', models.PositiveIntegerField(default=0, verbose_name='計画数量')),
                ('working_seconds', models.PositiveIntegerField(default=0, help_text='休憩時間を除いた実稼働秒数', verbose_name='稼働秒数')),
                ('production_events', models.JSONField(default=list, help_text='この時間帯の生産イベント詳細', verbose_name='生産イベント')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='作成日時')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新日時')),
                ('line', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='production.line', verbose_name='ライン')),
                ('machine', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='production.machine', verbose_name='機械')),
                ('part', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='production.part', verbose_name='機種')),
            ],
            options={
                'verbose_name': '計画時間別生産数',
                'verbose_name_plural': '計画時間別生産数',
                'ordering': ['date', 'line', 'hour'],
                'indexes': [models.Index(fields=['date', 'line'], name='production__date_76f14f_idx'), models.Index(fields=['date', 'line', 'hour'], name='production__date_8ad91f_idx')],
                'unique_together': {('date', 'line', 'part', 'machine', 'hour')},
            },
        ),
    ]
