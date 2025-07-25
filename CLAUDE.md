# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Django Management
```bash
# Run development server
daphne -p 8000 config.asgi:application

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Run custom management commands
python manage.py calculate_planned_pph
python manage.py create_sample_data
python manage.py seed_result_data
```

### Dependency Management
```bash
# Install dependencies
pip install -r requirements.txt

# Database operations
python check_db.py
python check_results.py
```

### Testing
```bash
# Run Django tests
python manage.py test production
```

## Project Architecture

### Core Application Structure
- **Django Framework**: Version 4.2.7 with Japanese localization (Asia/Tokyo timezone)
- **Main App**: `production` - Handles all production planning and tracking functionality
- **Authentication**: Django Allauth with username-based authentication
- **Real-time Features**: Django Channels with Redis for WebSocket communication
- **Database**: SQLite for development (configured for MySQL and Oracle in production)

### Key Models (`production/models.py`)
- **Line**: Production lines with user access control
- **Machine**: Equipment within production lines
- **Part**: Product types/parts being manufactured  
- **Plan**: Production plans with scheduling and quantities
- **Result**: Actual production results and performance data
- **UserLineAccess**: Role-based access control for production lines
- **Feedback**: User feedback system

### URL Structure (`production/urls.py`)
- Dashboard: `/production/dashboard/<line_id>/<date>/`
- Plans: `/production/plan/<line_id>/<date>/`
- Results: `/production/result/<line_id>/`
- API endpoints for real-time data updates
- Graph views for weekly/monthly analytics

### External Integrations
- **Snowflake**: Data warehouse connection via `connect_snowflake.py` and `snowflake_utils.py`
- **Oracle Database**: Production data integration via oracledb package
- **Japanese Holidays**: jpholiday package for business day calculations

### Authentication Flow
- Login redirects to `/production/line-select/`
- Users must select a production line before accessing features
- Line-based access control via UserLineAccess model

### Management Commands
Located in `production/management/commands/`:
- `calculate_planned_pph.py`: Calculate planned hourly production rates
- `seed_*.py`: Various data seeding utilities
- `migrate_result_data.py`: Data migration utilities

### Static Assets
- Custom CSS: `static/css/custom.css`
- JavaScript: `static/js/common.js`, `static/js/theme.js`
- Vendor libraries in `static/vendor/`

## Development Guidelines

### Database Considerations
- Primary development uses SQLite (`db.sqlite3`)
- Production ready for MySQL (`mysqlclient`) and Oracle (`oracledb`)
- Contains sensitive Oracle connection packages in `cx_oracle_packages/`

### Real-time Features
- Uses Django Channels with Redis backend
- WebSocket consumers in `production/consumers.py`
- Dashboard auto-updates via WebSocket connections

### Japanese Localization
- Language code: 'ja'
- Time zone: 'Asia/Tokyo'
- Uses jpholiday for Japanese business day calculations
- Interface elements use Japanese labels and terminology

### Security Notes
- Debug mode enabled in development
- Secret key exposed in settings (development only)
- ALLOWED_HOSTS set to ['*'] for development