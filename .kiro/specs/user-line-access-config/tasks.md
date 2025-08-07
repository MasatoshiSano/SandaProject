# Implementation Plan

- [x] 1. Create utility functions for line access management
  - Implement helper functions in production/utils.py for checking and managing user line access
  - Add functions: has_line_access(), get_user_line_access(), update_user_line_access()
  - Write unit tests for all utility functions
  - _Requirements: 1.1, 5.2_

- [x] 2. Create line access configuration view and template
  - [x] 2.1 Implement LineAccessConfigView class
    - Create view class in production/views.py with proper authentication
    - Handle GET requests to display current user's line access configuration
    - Handle POST requests to save line access selections
    - _Requirements: 3.1, 3.3, 5.1_

  - [x] 2.2 Create line access configuration template
    - Design responsive card-based layout for line selection
    - Implement search/filter functionality for line names and descriptions
    - Add bulk selection controls (Select All/Deselect All)
    - Implement color coding based on line name's first character
    - _Requirements: 3.1, 3.2, 4.1, 4.2, 4.3, 6.1, 6.2_

  - [x] 2.3 Add JavaScript functionality for interactive features
    - Implement real-time search filtering
    - Add click handlers for card selection and bulk operations
    - Create color generation function for line cards
    - Add form submission with AJAX and loading states
    - _Requirements: 4.1, 4.2, 4.3, 6.1, 6.2_

- [x] 3. Create admin user access management functionality
  - [x] 3.1 Implement AdminUserAccessView class
    - Create admin-only view for managing other users' line access
    - Add user search and selection functionality
    - Implement bulk operations for multiple users
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 3.2 Create admin user access template
    - Design user list interface with search functionality
    - Create individual user line access configuration interface
    - Add bulk operation controls for multiple users
    - _Requirements: 7.3, 7.4, 7.5_

- [x] 4. Implement automatic redirection middleware
  - Create LineAccessRedirectMiddleware class in production/middleware.py
  - Add logic to redirect users without line access to configuration page
  - Ensure middleware doesn't create redirect loops
  - Add middleware to Django settings
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 5. Add menu navigation links
  - [x] 5.1 Update base template navigation
    - Add "Line Access Settings" link to user dropdown menu
    - Add "Manage User Access" link to admin section for superusers
    - Ensure proper URL routing and active state indication
    - _Requirements: 2.1, 2.2, 2.3, 7.1, 7.2_

  - [x] 5.2 Update URL patterns
    - Add URL patterns for line access configuration view
    - Add URL patterns for admin user access management
    - Add API endpoints for AJAX operations
    - _Requirements: 2.1, 7.2_

- [x] 6. Create API endpoints for AJAX operations
  - [x] 6.1 Implement line access save API
    - Create POST endpoint for saving user line access selections
    - Add proper validation and error handling
    - Return JSON responses with success/error status
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 6.2 Implement admin user access API
    - Create endpoints for admin to update other users' line access
    - Add proper permission checks for admin-only operations
    - Implement audit logging for administrative changes
    - _Requirements: 7.5, 7.6_

- [x] 7. Add comprehensive error handling
  - Implement user-friendly error messages for all failure scenarios
  - Add proper handling for database connection issues
  - Ensure graceful degradation when services are unavailable
  - Add client-side error handling for AJAX operations
  - _Requirements: 5.4, 8.1, 8.2, 8.3_

- [x] 8. Write comprehensive tests
  - [x] 8.1 Create unit tests for utility functions
    - Test has_line_access() function with various user scenarios
    - Test get_user_line_access() function for data retrieval
    - Test update_user_line_access() function for bulk updates
    - _Requirements: 1.1, 5.2_

  - [x] 8.2 Create view tests for line access configuration
    - Test LineAccessConfigView GET and POST methods
    - Test permission requirements and access control
    - Test form validation and error handling
    - _Requirements: 3.1, 3.3, 5.1_

  - [x] 8.3 Create middleware tests
    - Test redirection logic for users without line access
    - Test that users with line access are not redirected
    - Test middleware doesn't interfere with configuration page
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 8.4 Create admin functionality tests
    - Test AdminUserAccessView permissions and functionality
    - Test admin API endpoints with proper authorization
    - Test audit logging for administrative changes
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 9. Ensure Docker Compose compatibility and deployment
  - [x] 9.1 Configure for Docker Compose environment
    - Ensure all new files are properly included in Docker container
    - Verify static files are collected and served correctly via nginx
    - Test database migrations work in PostgreSQL container
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 9.2 Test functionality in Docker Compose
    - Start application using `docker-compose up` command
    - Test all functionality at http://127.0.0.1:8001/ (Docker port mapping)
    - Verify URL routing works correctly in containerized setup
    - Test database operations and persistence in Docker volumes
    - _Requirements: 8.1, 8.2, 8.3_

- [x] 10. Integration testing and final validation in Docker Compose
  - [x] 10.1 Test complete user journey in Docker environment
    - Start application with `docker-compose up` and access at http://127.0.0.1:8001/
    - Test new user login and automatic redirection to line access configuration
    - Test line access configuration and saving functionality
    - Test subsequent logins proceed to http://127.0.0.1:8001/production/line-select/
    - _Requirements: 1.1, 1.2, 1.3, 5.1, 5.2_

  - [x] 10.2 Test admin workflow in Docker environment
    - Test admin access to user management interface via Docker deployment
    - Test admin ability to modify other users' line access
    - Test bulk operations and audit logging functionality
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 10.3 Test UI/UX features in Docker environment
    - Test search/filter functionality with various inputs
    - Test bulk selection controls (Select All/Deselect All)
    - Test color coding consistency across different line names
    - Test responsive design on different screen sizes
    - Verify all static assets load correctly through nginx proxy
    - _Requirements: 4.1, 4.2, 4.3, 6.1, 6.2_