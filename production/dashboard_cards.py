"""
Dashboard Card Registry System

This module defines all available dashboard cards and provides utilities
for managing card configurations and rendering.
"""

from typing import Dict, List, Optional, Any
from django.template.loader import get_template
from django.template import Context, Template
from django.utils.safestring import mark_safe
import logging

logger = logging.getLogger(__name__)

# Dashboard Cards Configuration
DASHBOARD_CARDS = {
    'total_planned': {
        'name': '計画数',
        'description': '当日の計画総数量を表示',
        'template': 'production/dashboard/cards/total_planned.html',
        'context_key': 'total_planned',
        'default_order': 1,
        'system_card': True,
        'icon': 'bi-target',
        'color_class': 'border-primary',
        'text_class': 'text-primary'
    },
    'total_actual': {
        'name': '実績数',
        'description': '当日の実績総数量を表示',
        'template': 'production/dashboard/cards/total_actual.html',
        'context_key': 'total_actual',
        'default_order': 2,
        'system_card': True,
        'icon': 'bi-check-circle',
        'color_class': 'border-success',
        'text_class': 'text-success'
    },
    'achievement_rate': {
        'name': '達成率',
        'description': '計画に対する実績の達成率を表示',
        'template': 'production/dashboard/cards/achievement_rate.html',
        'context_key': 'achievement_rate',
        'default_order': 3,
        'system_card': True,
        'icon': 'bi-graph-up',
        'color_class': 'border-info',
        'text_class': 'text-info'
    },
    'remaining': {
        'name': '残り',
        'description': '計画に対する残り数量を表示',
        'template': 'production/dashboard/cards/remaining.html',
        'context_key': 'remaining',
        'default_order': 4,
        'system_card': True,
        'icon': 'bi-hourglass-split',
        'color_class': 'border-warning',
        'text_class': 'text-warning'
    },
    'input_count': {
        'name': '投入数',
        'description': '対象設備からの総投入数を表示',
        'template': 'production/dashboard/cards/input_count.html',
        'context_key': 'input_count',
        'default_order': 5,
        'system_card': True,
        'icon': 'bi-box-arrow-in-right',
        'color_class': 'border-dark',
        'text_class': 'text-dark'
    },
    'forecast_time': {
        'name': '終了予測時刻',
        'description': '生産終了予測時刻を表示',
        'template': 'production/dashboard/cards/forecast_time.html',
        'context_key': 'forecast_time',
        'default_order': 6,
        'system_card': True,
        'icon': 'bi-clock',
        'color_class': 'border-secondary',
        'text_class': 'text-secondary'
    }
}


class DashboardCardRegistry:
    """Dashboard card registry for managing available cards"""
    
    def __init__(self):
        self._cards = DASHBOARD_CARDS.copy()
    
    def get_card_config(self, card_type: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific card type"""
        return self._cards.get(card_type)
    
    def get_all_cards(self) -> Dict[str, Dict[str, Any]]:
        """Get all available card configurations"""
        return self._cards.copy()
    
    def get_system_cards(self) -> Dict[str, Dict[str, Any]]:
        """Get only system cards"""
        return {
            card_type: config 
            for card_type, config in self._cards.items() 
            if config.get('system_card', False)
        }
    
    def get_custom_cards(self) -> Dict[str, Dict[str, Any]]:
        """Get only custom (non-system) cards"""
        return {
            card_type: config 
            for card_type, config in self._cards.items() 
            if not config.get('system_card', False)
        }
    
    def register_card(self, card_type: str, config: Dict[str, Any]) -> bool:
        """Register a new card type"""
        if card_type in self._cards:
            logger.warning(f"Card type '{card_type}' already exists. Overwriting.")
        
        # Validate required fields
        required_fields = ['name', 'template', 'context_key', 'default_order']
        for field in required_fields:
            if field not in config:
                logger.error(f"Missing required field '{field}' for card type '{card_type}'")
                return False
        
        self._cards[card_type] = config
        logger.info(f"Registered card type: {card_type}")
        return True
    
    def unregister_card(self, card_type: str) -> bool:
        """Unregister a card type"""
        if card_type not in self._cards:
            logger.warning(f"Card type '{card_type}' not found")
            return False
        
        config = self._cards[card_type]
        if config.get('system_card', False):
            logger.error(f"Cannot unregister system card: {card_type}")
            return False
        
        del self._cards[card_type]
        logger.info(f"Unregistered card type: {card_type}")
        return True
    
    def validate_card_type(self, card_type: str) -> bool:
        """Validate if a card type exists"""
        return card_type in self._cards
    
    def get_default_cards_data(self) -> List[Dict[str, Any]]:
        """Get default card data for initialization"""
        cards_data = []
        for card_type, config in self._cards.items():
            cards_data.append({
                'name': config['name'],
                'card_type': card_type,
                'description': config.get('description', ''),
                'is_visible': True,
                'order': config['default_order'],
                'is_system_card': config.get('system_card', False),
                'alert_threshold_yellow': 80.0,
                'alert_threshold_red': 60.0
            })
        return sorted(cards_data, key=lambda x: x['order'])


# Global registry instance
card_registry = DashboardCardRegistry()


def get_card_registry() -> DashboardCardRegistry:
    """Get the global card registry instance"""
    return card_registry


def get_visible_cards_config(card_settings=None) -> List[Dict[str, Any]]:
    """
    Get configuration for visible cards based on DashboardCardSetting
    
    Args:
        card_settings: QuerySet of DashboardCardSetting objects
    
    Returns:
        List of card configurations ordered by display order
    """
    from django.core.cache import cache
    from django.conf import settings
    
    # Try to get from cache first
    cache_key = 'dashboard_visible_cards_config'
    cached_config = cache.get(cache_key)
    
    if cached_config is not None and card_settings is None:
        logger.debug("Using cached visible cards configuration")
        return cached_config
    
    if card_settings is None:
        from .models import DashboardCardSetting
        card_settings = DashboardCardSetting.objects.filter(is_visible=True).order_by('order')
    
    visible_cards = []
    registry = get_card_registry()
    
    for setting in card_settings:
        card_config = registry.get_card_config(setting.card_type)
        if card_config:
            # Merge setting data with card config
            merged_config = card_config.copy()
            merged_config.update({
                'setting_id': setting.id,
                'name': setting.name,  # Use custom name if set
                'description': setting.description or card_config.get('description', ''),
                'order': setting.order,
                'alert_threshold_yellow': setting.alert_threshold_yellow,
                'alert_threshold_red': setting.alert_threshold_red,
            })
            visible_cards.append(merged_config)
        else:
            logger.warning(f"Card type '{setting.card_type}' not found in registry")
    
    # Cache the result for 5 minutes
    cache_timeout = getattr(settings, 'DASHBOARD_CARDS_CACHE_TIMEOUT', 300)
    cache.set(cache_key, visible_cards, cache_timeout)
    logger.debug(f"Cached visible cards configuration for {cache_timeout} seconds")
    
    return visible_cards


def render_card(card_config: Dict[str, Any], context_data: Dict[str, Any]) -> str:
    """
    Render a dashboard card using its template and context data
    
    Args:
        card_config: Card configuration dictionary
        context_data: Dashboard context data
    
    Returns:
        Rendered HTML string
    """
    try:
        template_path = card_config.get('template')
        if not template_path:
            logger.error(f"No template specified for card: {card_config.get('name', 'Unknown')}")
            return ""
        
        # Try to get the template
        try:
            template = get_template(template_path)
        except Exception as e:
            logger.warning(f"Template not found: {template_path}, using fallback. Error: {e}")
            # Use fallback template
            template = Template(get_fallback_card_template())
        
        # Prepare context
        card_context = {
            'card_config': card_config,
            'value': context_data.get(card_config.get('context_key', ''), 0),
            'dashboard_data': context_data
        }
        
        return template.render(card_context)
        
    except Exception as e:
        logger.error(f"Error rendering card {card_config.get('name', 'Unknown')}: {e}")
        return f'<div class="alert alert-danger">カード表示エラー: {card_config.get("name", "Unknown")}</div>'


def get_fallback_card_template() -> str:
    """Get fallback template for cards when specific template is not found"""
    return """
    <div class="col-12 col-md-6 col-xl-3 mb-3">
        <div class="card metric-card {{ card_config.color_class|default:'border-secondary' }}">
            <div class="card-body text-center">
                <div class="metric-value {{ card_config.text_class|default:'text-secondary' }}">
                    {{ value|default:0 }}
                </div>
                <div class="metric-label text-muted">{{ card_config.name }}</div>
                <small class="text-muted">
                    <i class="{{ card_config.icon|default:'bi-info-circle' }} me-1"></i>
                    {{ card_config.description|default:'データ' }}
                </small>
            </div>
        </div>
    </div>
    """