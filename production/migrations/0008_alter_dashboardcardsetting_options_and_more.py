# Generated by Django 4.2.7 on 2025-06-12 04:57

import datetime
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0007_line_sta_no1_line_sta_no2'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='dashboardcardsetting',
            options={'ordering': ['order', 'name'], 'verbose_name': 'ダッシュボードカード設定', 'verbose_name_plural': 'ダッシュボードカード設定'},
        ),
        migrations.AlterModelOptions(
            name='part',
            options={'ordering': ['name'], 'verbose_name': '機種', 'verbose_name_plural': '機種'},
        ),
        migrations.AlterModelOptions(
            name='plan',
            options={'ordering': ['date', 'line', 'start_time'], 'verbose_name': '生産計画', 'verbose_name_plural': '生産計画'},
        ),
        migrations.AlterModelOptions(
            name='result',
            options={'ordering': ['-timestamp'], 'verbose_name': '実績', 'verbose_name_plural': '実績'},
        ),
        migrations.AlterUniqueTogether(
            name='plan',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='dashboardcardsetting',
            name='is_enabled',
        ),
        migrations.RemoveField(
            model_name='dashboardcardsetting',
            name='sequence',
        ),
        migrations.RemoveField(
            model_name='dashboardcardsetting',
            name='title',
        ),
        migrations.RemoveField(
            model_name='line',
            name='sta_no1',
        ),
        migrations.RemoveField(
            model_name='line',
            name='sta_no2',
        ),
        migrations.RemoveField(
            model_name='part',
            name='code',
        ),
        migrations.RemoveField(
            model_name='result',
            name='updated_at',
        ),
        migrations.AddField(
            model_name='category',
            name='color',
            field=models.CharField(default='#007bff', help_text='HEX形式 (#RRGGBB)', max_length=7, verbose_name='色'),
        ),
        migrations.AddField(
            model_name='category',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='有効'),
        ),
        migrations.AddField(
            model_name='dashboardcardsetting',
            name='alert_threshold_red',
            field=models.FloatField(default=80.0, verbose_name='赤色アラート閾値(%)'),
        ),
        migrations.AddField(
            model_name='dashboardcardsetting',
            name='alert_threshold_yellow',
            field=models.FloatField(default=80.0, verbose_name='黄色アラート閾値(%)'),
        ),
        migrations.AddField(
            model_name='dashboardcardsetting',
            name='is_visible',
            field=models.BooleanField(default=True, verbose_name='表示'),
        ),
        migrations.AddField(
            model_name='dashboardcardsetting',
            name='order',
            field=models.PositiveIntegerField(default=0, verbose_name='表示順'),
        ),
        migrations.AddField(
            model_name='machine',
            name='is_production_active',
            field=models.BooleanField(default=False, help_text='この設備が現在生産稼働中かを示すフラグ', verbose_name='生産稼働中'),
        ),
        migrations.AddField(
            model_name='part',
            name='cycle_time',
            field=models.FloatField(blank=True, editable=False, null=True, verbose_name='サイクルタイム(秒)'),
        ),
        migrations.AddField(
            model_name='part',
            name='part_number',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True, verbose_name='品番'),
        ),
        migrations.AddField(
            model_name='part',
            name='tags',
            field=models.ManyToManyField(blank=True, to='production.tag', verbose_name='タグ'),
        ),
        migrations.AddField(
            model_name='part',
            name='target_pph',
            field=models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)], verbose_name='目標PPH'),
        ),
        migrations.AddField(
            model_name='plan',
            name='end_time',
            field=models.TimeField(default=datetime.time(17, 0), verbose_name='終了時間'),
        ),
        migrations.AddField(
            model_name='plan',
            name='machine',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='production.machine', verbose_name='機械'),
        ),
        migrations.AddField(
            model_name='plan',
            name='notes',
            field=models.TextField(blank=True, verbose_name='備考'),
        ),
        migrations.AddField(
            model_name='plan',
            name='planned_quantity',
            field=models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)], verbose_name='計画数量'),
        ),
        migrations.AddField(
            model_name='plan',
            name='start_time',
            field=models.TimeField(default=datetime.time(8, 0), verbose_name='開始時間'),
        ),
        migrations.AddField(
            model_name='result',
            name='line',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='production.line', verbose_name='ライン'),
        ),
        migrations.AddField(
            model_name='result',
            name='machine',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='production.machine', verbose_name='設備'),
        ),
        migrations.AddField(
            model_name='result',
            name='part',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='production.part', verbose_name='機種'),
        ),
        migrations.AddField(
            model_name='tag',
            name='color',
            field=models.CharField(default='#6c757d', help_text='HEX形式 (#RRGGBB)', max_length=7, verbose_name='色'),
        ),
        migrations.AddField(
            model_name='tag',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='有効'),
        ),
        migrations.AlterField(
            model_name='category',
            name='name',
            field=models.CharField(max_length=100, unique=True, verbose_name='カテゴリ名'),
        ),
        migrations.AlterField(
            model_name='dashboardcardsetting',
            name='name',
            field=models.CharField(max_length=100, unique=True, verbose_name='カード名'),
        ),
        migrations.AlterField(
            model_name='part',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='production.category', verbose_name='カテゴリ'),
        ),
        migrations.AlterField(
            model_name='part',
            name='name',
            field=models.CharField(max_length=100, unique=True, verbose_name='機種名'),
        ),
        migrations.AlterField(
            model_name='plan',
            name='part',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='production.part', verbose_name='機種'),
        ),
        migrations.AlterField(
            model_name='plan',
            name='sequence',
            field=models.PositiveIntegerField(default=1, verbose_name='順番'),
        ),
        migrations.AlterField(
            model_name='result',
            name='judgment',
            field=models.CharField(choices=[('OK', 'OK'), ('NG', 'NG')], max_length=2, verbose_name='判定'),
        ),
        migrations.AlterField(
            model_name='result',
            name='plan',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='results', to='production.plan', verbose_name='計画'),
        ),
        migrations.AlterField(
            model_name='result',
            name='quantity',
            field=models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)], verbose_name='数量'),
        ),
        migrations.AlterField(
            model_name='result',
            name='serial_number',
            field=models.CharField(max_length=100, verbose_name='シリアル番号'),
        ),
        migrations.AlterField(
            model_name='tag',
            name='name',
            field=models.CharField(max_length=50, unique=True, verbose_name='タグ名'),
        ),
        migrations.AlterUniqueTogether(
            name='plan',
            unique_together={('date', 'line', 'sequence')},
        ),
        migrations.DeleteModel(
            name='UserProfile',
        ),
        migrations.RemoveField(
            model_name='plan',
            name='quantity',
        ),
    ]
