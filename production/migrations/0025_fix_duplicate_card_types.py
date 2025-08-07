# Generated manually to fix duplicate card_types

from django.db import migrations


def fix_duplicate_card_types(apps, schema_editor):
    """既存のダッシュボードカード設定の重複するcard_typeを修正"""
    DashboardCardSetting = apps.get_model('production', 'DashboardCardSetting')
    
    # 既存のすべてのカード設定を取得
    cards = DashboardCardSetting.objects.all().order_by('id')
    
    # カード名に基づいてcard_typeを推測・設定
    card_type_mapping = {
        '計画数': 'total_planned',
        '実績数': 'total_actual',
        '達成率': 'achievement_rate',
        '残り': 'remaining',
        '投入数': 'input_count',
        '終了予測時刻': 'forecast_time',
        '完了予測時刻': 'forecast_time',
    }
    
    for i, card in enumerate(cards):
        # カード名からcard_typeを推測
        matched_type = None
        for name_pattern, card_type in card_type_mapping.items():
            if name_pattern in card.name:
                matched_type = card_type
                break
        
        # マッチしない場合は、インデックスベースで一意のcard_typeを生成
        if matched_type:
            new_card_type = matched_type
        else:
            new_card_type = f"card_{i+1:03d}"
        
        # 重複チェックと修正
        existing_count = DashboardCardSetting.objects.filter(card_type=new_card_type).exclude(id=card.id).count()
        if existing_count > 0:
            # 重複する場合は番号を追加
            counter = 1
            while DashboardCardSetting.objects.filter(card_type=f"{new_card_type}_{counter}").exclude(id=card.id).exists():
                counter += 1
            new_card_type = f"{new_card_type}_{counter}"
        
        # card_typeを更新
        card.card_type = new_card_type
        card.save(update_fields=['card_type'])


def reverse_fix_duplicate_card_types(apps, schema_editor):
    """逆向きマイグレーション（元に戻す必要はないが、空の実装を提供）"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('production', '0024_dashboardcardsetting_card_type_and_more'),
    ]

    operations = [
        migrations.RunPython(
            fix_duplicate_card_types,
            reverse_fix_duplicate_card_types,
        ),
    ]