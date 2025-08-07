"""
Management command to initialize default dashboard card settings.

This command creates default DashboardCardSetting entries for all
registered dashboard cards if they don't already exist.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from production.models import DashboardCardSetting
from production.dashboard_cards import get_card_registry
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    ダッシュボードカード設定の初期化を行います。
    
    このコマンドは、システムに登録されているすべてのダッシュボードカードについて
    デフォルトのDashboardCardSetting設定を作成します。
    
    例:
        python manage.py init_dashboard_cards
        python manage.py init_dashboard_cards --dry-run
        python manage.py init_dashboard_cards --force
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='既存のカード設定をデフォルト値で強制的に更新します。通常は新しいカードのみ作成されますが、このオプションを指定すると既存のカードも更新されます。',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際の変更を行わずに、何が作成・更新されるかをプレビュー表示します。本番実行前の確認に使用してください。',
        )

    def handle(self, *args, **options):
        force = options['force']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        registry = get_card_registry()
        default_cards_data = registry.get_default_cards_data()
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        try:
            with transaction.atomic():
                for card_data in default_cards_data:
                    card_type = card_data['card_type']
                    
                    try:
                        # Check if card setting already exists
                        existing_setting = DashboardCardSetting.objects.get(
                            card_type=card_type
                        )
                        
                        if force:
                            # Update existing setting with default values
                            if not dry_run:
                                for key, value in card_data.items():
                                    if key != 'card_type':  # Don't update the key field
                                        setattr(existing_setting, key, value)
                                existing_setting.save()
                            
                            updated_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'{"[DRY RUN] " if dry_run else ""}Updated: {card_data["name"]} ({card_type})'
                                )
                            )
                        else:
                            skipped_count += 1
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Skipped existing: {card_data["name"]} ({card_type})'
                                )
                            )
                    
                    except DashboardCardSetting.DoesNotExist:
                        # Create new card setting
                        if not dry_run:
                            DashboardCardSetting.objects.create(**card_data)
                        
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'{"[DRY RUN] " if dry_run else ""}Created: {card_data["name"]} ({card_type})'
                            )
                        )
                
                if dry_run:
                    # Rollback transaction in dry run mode
                    transaction.set_rollback(True)
        
        except Exception as e:
            raise CommandError(f'Error initializing dashboard cards: {e}')
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS(
                f'{"[DRY RUN] " if dry_run else ""}Dashboard Card Initialization Summary:'
            )
        )
        self.stdout.write(f'  Created: {created_count}')
        self.stdout.write(f'  Updated: {updated_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        self.stdout.write(f'  Total processed: {len(default_cards_data)}')
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    '\nDashboard card settings have been initialized successfully!'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    '\nThis was a dry run. Use --force to update existing cards or run without --dry-run to apply changes.'
                )
            )