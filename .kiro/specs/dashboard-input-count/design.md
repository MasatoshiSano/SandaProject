# Design Document

## Overview

This design implements input count (投入数) functionality for the dashboard cards by extending the existing dashboard system. The feature adds a new input count flag to the Machine model and modifies the dashboard data calculation to include input count metrics alongside existing production metrics. Input counts represent the total volume of items processed regardless of quality judgment, calculated within work calendar periods.

## Architecture

### Database Schema Changes

The design leverages the existing `is_count_target` field in the Machine model, which is already present in the codebase. This field will be repurposed to control which machines contribute to input count calculations.

### Data Flow

1. **Input Count Flag Configuration**: Administrators configure the `is_count_target` flag for each machine through the Django admin interface
2. **Dashboard Data Calculation**: The existing `get_dashboard_data()` function in `production/utils.py` will be extended to calculate input counts
3. **Time Period Calculation**: Input counts are calculated using WorkCalendar work periods (work_start_time to next day's work_start_time)
4. **Dashboard Display**: The dashboard template will be updated to display input count data alongside existing metrics

## Components and Interfaces

### 1. Machine Model Enhancement

The existing Machine model already contains the required `is_count_target` field:

```python
class Machine(models.Model):
    is_count_target = models.BooleanField('カウント対象', default=False, help_text='ダッシュボードで実績カウントの対象とする設備')
```

This field will be used to determine which machines contribute to input count calculations.

### 2. Dashboard Data Service Extension

The `get_dashboard_data()` function in `production/utils.py` will be extended with input count calculation logic:

```python
def calculate_input_count(line_id, date, work_start_time):
    """Calculate input count for machines with is_count_target=True"""
    # Get input count target machines
    input_count_machines = Machine.objects.filter(
        line_id=line_id, 
        is_count_target=True,
        is_active=True
    )
    
    # Calculate time period
    actual_work_start = datetime.combine(date, work_start_time)
    next_day_work_start = actual_work_start + timedelta(days=1)
    
    # Query results for input count (all judgments)
    input_results = Result.objects.filter(
        line=line_name,
        machine__in=[m.name for m in input_count_machines],
        timestamp__gte=actual_work_start.strftime('%Y%m%d%H%M%S'),
        timestamp__lt=next_day_work_start.strftime('%Y%m%d%H%M%S'),
        sta_no1='SAND'
    )
    
    return input_results.count()
```

### 3. Dashboard Template Updates

The dashboard template (`templates/production/dashboard.html`) will be updated to display input count data:

```html
<!-- Input Count Card -->
<div class="card">
    <div class="card-header">
        <h5>投入数</h5>
    </div>
    <div class="card-body">
        <h2>{{ dashboard_data.input_count }}</h2>
        <small class="text-muted">対象設備からの総投入数</small>
    </div>
</div>
```

### 4. API Response Extension

The dashboard API response will include input count data:

```python
{
    'parts': [...],
    'hourly': [...],
    'total_planned': 1000,
    'total_actual': 850,
    'input_count': 1200,  # New field
    'achievement_rate': 85.0,
    'remaining': 150,
    'last_updated': '2025-01-15T10:30:00Z'
}
```

## Data Models

### Machine Model (Existing)

The Machine model already contains the necessary field:

- `is_count_target`: Boolean flag to indicate if the machine should be included in input count calculations
- `line`: Foreign key to Line model for filtering by production line
- `is_active`: Boolean flag to exclude inactive machines

### Result Model (Existing)

The Result model provides the production data:

- `timestamp`: Production timestamp in YYYYMMDDHHMMSS format
- `line`: Production line name (string field)
- `machine`: Machine name (string field)  
- `judgment`: Quality judgment ('1' for OK, '2' for NG)
- `sta_no1`: Filter field (must be 'SAND')

### WorkCalendar Model (Existing)

The WorkCalendar model defines work periods:

- `work_start_time`: Daily work start time
- `line`: Associated production line

## Error Handling

### 1. Missing WorkCalendar Configuration

```python
try:
    work_calendar = WorkCalendar.objects.get(line_id=line_id)
    work_start_time = work_calendar.work_start_time
except WorkCalendar.DoesNotExist:
    work_start_time = time(8, 30)  # Default fallback
```

### 2. No Input Count Target Machines

```python
input_count_machines = Machine.objects.filter(
    line_id=line_id, 
    is_count_target=True,
    is_active=True
)

if not input_count_machines.exists():
    return 0  # Return zero if no machines are configured
```

### 3. Database Query Failures

```python
try:
    input_count = calculate_input_count(line_id, date, work_start_time)
except Exception as e:
    logger.error(f"Input count calculation error: {e}")
    input_count = 0  # Fallback to zero
```

## Testing Strategy

### 1. Unit Tests

- Test input count calculation with various machine configurations
- Test time period calculation with different WorkCalendar settings
- Test error handling for missing configurations

### 2. Integration Tests

- Test dashboard data API response includes input count
- Test dashboard template renders input count correctly
- Test WebSocket updates include input count changes

### 3. Performance Tests

- Test dashboard load time with input count calculations
- Test database query performance with large result datasets
- Test concurrent access to dashboard with input count data

### 4. User Acceptance Tests

- Verify input count displays correctly on dashboard
- Verify input count updates in real-time
- Verify input count configuration through admin interface

## Implementation Considerations

### 1. Backward Compatibility

The design maintains full backward compatibility by:
- Using existing database fields without schema changes
- Extending existing functions rather than replacing them
- Adding new template sections without modifying existing ones

### 2. Performance Optimization

- Input count calculation reuses existing database queries where possible
- Results are cached within the dashboard data response
- Database indexes on timestamp and line fields support efficient queries

### 3. Real-time Updates

The existing WebSocket infrastructure will automatically include input count updates when Result records are created or modified, as the dashboard data calculation includes input count.

### 4. Configuration Management

Machine input count configuration is managed through the existing Django admin interface, requiring no additional configuration screens.