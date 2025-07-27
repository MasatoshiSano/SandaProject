#!/bin/bash

# Docker Compose Management Commands
# Usage: ./scripts/docker_commands.sh [command]

case "$1" in
    # Database Management
    "migrate")
        docker compose exec web python manage.py migrate
        ;;
    "makemigrations")
        docker compose exec web python manage.py makemigrations
        ;;
    "createsuperuser")
        docker compose exec web python manage.py createsuperuser
        ;;
    
    # Custom Management Commands
    "calculate_planned_pph")
        docker compose exec web python manage.py calculate_planned_pph
        ;;
    "create_sample_data")
        docker compose exec web python manage.py create_sample_data
        ;;
    "seed_result_data")
        docker compose exec web python manage.py seed_result_data
        ;;
    "seed_sample_data")
        docker compose exec web python manage.py seed_sample_data
        ;;
    
    # Development Tools
    "shell")
        docker compose exec web python manage.py shell
        ;;
    "collectstatic")
        docker compose exec web python manage.py collectstatic --noinput
        ;;
    "test")
        docker compose exec web python manage.py test production
        ;;
    
    # Database Utilities
    "check_db")
        docker compose exec web python check_db.py
        ;;
    "check_results")
        docker compose exec web python check_results.py
        ;;
    
    # Service Management
    "up")
        docker compose up -d
        ;;
    "down")
        docker compose down
        ;;
    "logs")
        docker compose logs -f web
        ;;
    "restart")
        docker compose restart web
        ;;
    "build")
        docker compose build --no-cache
        ;;
    
    # Help
    "help"|*)
        echo "Available commands:"
        echo "  migrate              - Run database migrations"
        echo "  makemigrations       - Create new migrations"
        echo "  createsuperuser      - Create Django superuser"
        echo "  calculate_planned_pph - Calculate planned production per hour"
        echo "  create_sample_data   - Create sample data"
        echo "  seed_result_data     - Seed result data"
        echo "  seed_sample_data     - Seed sample data"
        echo "  shell                - Open Django shell"
        echo "  collectstatic        - Collect static files"
        echo "  test                 - Run tests"
        echo "  check_db             - Check database connection"
        echo "  check_results        - Check results data"
        echo "  up                   - Start all services"
        echo "  down                 - Stop all services"
        echo "  logs                 - Show web service logs"
        echo "  restart              - Restart web service"
        echo "  build                - Rebuild containers"
        echo "  help                 - Show this help message"
        ;;
esac