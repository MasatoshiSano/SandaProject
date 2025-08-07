# Design Document

## Overview

This feature enhances the existing dashboard card management system by providing administrators with a comprehensive interface to control dashboard card visibility, ordering, and configuration through the Django admin panel. The system builds upon the existing `DashboardCardSetting` model and integrates with the current dashboard template structure.

## Architecture

### System Components

The dashboard card management system consists of the following components:

1. **Model Layer**: Enhanced `DashboardCardSetting` model with improved functionality
2. **Admin Interface**: Enhanced Django admin interface for card configuration
3. **View Layer**: Updated dashboard view to respect card settings
4. **Template Layer**: Modified dashboard template to dynamically render cards based on settings
5. **Management Commands**: Commands to initialize and manage card settings

### Data Flow

1. Administrator configures card settings through Django admin interface
2. Settings are stored in the `DashboardCardSetting` model
3. Dashboard view queries card settings and applies them to context data
4. Template renders only visible cards in the specified order
5. Changes take effect immediately without requiring application restart

## Components and Interfaces

### Enhanced DashboardCardSetting Model

The existing model will be enhanced with additional functionality:

```python
class DashboardCardSetting(models.Model):
    # Existing fields
    name = models.CharField('カード名', max_length=100, unique=True)
    is_visible = models.BooleanField('表示', default=True)
    order = models.PositiveIntegerField('表示順', default=0)
    alert_threshold_yellow = models.FloatField('黄色アラート閾値(%)', default=80.0)
    alert_threshold_red = models.FloatField('赤色アラート閾値(%)', default=80.0)
    
    # Enhanced fields
    description = models.TextField('説明', blank=True)
    card_type = models.CharField('カードタイプ', max_length=50)
    is_system_card = models.BooleanField('システムカード', default=False)
    
    class Meta:
        verbose_name = 'ダッシュボードカード設定'
        verbose_name_plural = 'ダッシュボードカード設定'
        ordering = ['order', 'name']
```

### Card Configuration Interface

Enhanced Django admin interface with the following features:

- **List View**: Display all cards with visibility status, order, and quick edit capabilities
- **Drag-and-Drop Ordering**: JavaScript-enhanced interface for easy reordering
- **Bulk Actions**: Enable/disable multiple cards at once
- **Card Preview**: Visual preview of how cards will appear on dashboard
- **Validation**: Ensure proper ordering and prevent conflicts

### Dashboard View Integration

The `DashboardView` will be enhanced to:

1. Query `DashboardCardSetting` for visible cards
2. Apply ordering to dashboard data
3. Filter out hidden cards from context
4. Provide fallback behavior when no settings exist

### Template Card System

Dashboard template will use a card registry system:

```python
DASHBOARD_CARDS = {
    'total_planned': {
        'name': '計画数',
        'template': 'dashboard/cards/total_planned.html',
        'context_key': 'total_planned',
        'default_order': 1,
        'system_card': True
    },
    'total_actual': {
        'name': '実績数', 
        'template': 'dashboard/cards/total_actual.html',
        'context_key': 'total_actual',
        'default_order': 2,
        'system_card': True
    },
    # ... other cards
}
```

## Data Models

### DashboardCardSetting Fields

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| name | CharField(100) | カード名（一意） | - |
| is_visible | BooleanField | 表示フラグ | True |
| order | PositiveIntegerField | 表示順序 | 0 |
| description | TextField | カード説明 | '' |
| card_type | CharField(50) | カードタイプ識別子 | - |
| is_system_card | BooleanField | システム標準カード | False |
| alert_threshold_yellow | FloatField | 黄色アラート閾値 | 80.0 |
| alert_threshold_red | FloatField | 赤色アラート閾値 | 80.0 |

### Card Registry Structure

```python
CardConfig = {
    'id': str,              # カード識別子
    'name': str,            # 表示名
    'template': str,        # テンプレートパス
    'context_key': str,     # コンテキストキー
    'default_order': int,   # デフォルト順序
    'system_card': bool,    # システムカードフラグ
    'description': str      # カード説明
}
```

## Error Handling

### Configuration Errors

- **Missing Card Settings**: Provide default configuration for all standard cards
- **Invalid Order Values**: Auto-correct ordering conflicts during save
- **Template Not Found**: Graceful fallback to default card template
- **Context Data Missing**: Skip card rendering with logging

### Runtime Errors

- **Database Connection Issues**: Use cached settings with periodic refresh
- **Template Rendering Errors**: Log errors and skip problematic cards
- **Permission Errors**: Ensure admin users have proper access rights

### Validation Rules

- Card names must be unique
- Order values must be positive integers
- At least one card must remain visible
- System cards cannot be permanently deleted

## Testing Strategy

### Unit Tests

1. **Model Tests**
   - Card setting creation and validation
   - Ordering logic and conflict resolution
   - Default value assignment

2. **Admin Interface Tests**
   - Card configuration form validation
   - Bulk action functionality
   - Permission-based access control

3. **View Tests**
   - Dashboard rendering with various card configurations
   - Card filtering and ordering logic
   - Context data preparation

### Integration Tests

1. **End-to-End Dashboard Tests**
   - Complete dashboard rendering with custom card settings
   - Card visibility changes reflected immediately
   - Order changes applied correctly

2. **Admin Workflow Tests**
   - Administrator can configure cards through admin interface
   - Changes persist across sessions
   - Multiple administrators can work simultaneously

### Performance Tests

1. **Dashboard Load Time**
   - Measure impact of card configuration queries
   - Optimize database queries for card settings
   - Cache frequently accessed settings

2. **Admin Interface Responsiveness**
   - Test drag-and-drop performance with many cards
   - Bulk operations on large card sets
   - Form submission and validation speed

### Browser Compatibility Tests

1. **Admin Interface**
   - Drag-and-drop functionality across browsers
   - Form validation and submission
   - JavaScript-enhanced features

2. **Dashboard Display**
   - Card rendering consistency
   - Responsive design with various card configurations
   - Mobile device compatibility

## Implementation Considerations

### Database Migration Strategy

- Enhance existing `DashboardCardSetting` model with new fields
- Create management command to populate default card settings
- Ensure backward compatibility with existing data

### Caching Strategy

- Cache card settings to reduce database queries
- Implement cache invalidation on settings changes
- Use Django's cache framework for optimal performance

### Security Considerations

- Restrict card configuration to admin users only
- Validate all input data to prevent injection attacks
- Implement proper permission checks for admin interface

### Internationalization

- Support Japanese language for all admin interface elements
- Provide translatable card names and descriptions
- Maintain consistency with existing application language settings