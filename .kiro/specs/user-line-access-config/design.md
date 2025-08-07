# Design Document

## Overview

This feature adds a comprehensive user line access configuration system to the existing Django production management application. The system allows users to configure their line access permissions through a dedicated interface, provides automatic redirection for new users, and includes administrative capabilities for managing other users' permissions. The feature integrates seamlessly with the existing UserLineAccess model and Docker Compose deployment architecture.

## Architecture

### System Components

The feature consists of the following main components:

1. **Line Access Configuration View** - User-facing interface for configuring line access
2. **Admin User Management View** - Administrative interface for managing other users' access
3. **Middleware/Login Hook** - Automatic redirection logic for new users
4. **Menu Integration** - Navigation links in the existing menu bar
5. **API Endpoints** - Backend services for saving and retrieving line access data

### Integration Points

- **Existing Models**: Leverages the current `UserLineAccess` and `Line` models
- **Authentication System**: Integrates with Django's built-in authentication
- **Menu System**: Extends the existing Bootstrap navbar in `templates/base.html`
- **URL Routing**: Adds new routes to `production/urls.py`
- **Docker Environment**: Ensures compatibility with the existing Docker Compose setup

## Components and Interfaces

### 1. Line Access Configuration View

**Template**: `templates/production/line_access_config.html`
**View Class**: `LineAccessConfigView(LoginRequiredMixin, TemplateView)`
**URL Pattern**: `/production/line-access-config/`

**Features**:
- Card-based display of available production lines
- Real-time search/filter functionality
- Bulk selection controls (Select All/Deselect All)
- Visual indication of current user's access permissions
- Save functionality with success/error feedback

**Interface Elements**:
```html
- Search input field for filtering lines
- "Select All" and "Deselect All" buttons
- Line cards showing name and description with color coding
- Toggle selection on card click
- Save button with loading state
- Success/error message display
```

**Card Design Specifications**:
- Cards are color-coded based on the first character of the line name
- Color mapping uses a consistent hash function for character-to-color assignment
- Selected cards show a distinct visual state (border/background change)
- No icons required - clean text-based design
- Responsive grid layout for different screen sizes

### 2. Admin User Management View

**Template**: `templates/production/admin_user_access.html`
**View Class**: `AdminUserAccessView(LoginRequiredMixin, TemplateView)`
**URL Pattern**: `/production/admin/user-access/`

**Features**:
- User list with search functionality
- Individual user line access configuration
- Bulk operations for multiple users
- Audit logging of administrative changes

**Access Control**: Restricted to `user.is_superuser`

### 3. Login Redirection Middleware

**File**: `production/middleware.py`
**Class**: `LineAccessRedirectMiddleware`

**Logic**:
```python
def process_request(request):
    if user.is_authenticated and not has_line_access(user):
        if request.path != '/production/line-access-config/':
            return redirect('/production/line-access-config/')
```

### 4. Menu Integration

**File**: `templates/base.html`
**Location**: Added to existing navbar structure

**Menu Items**:
- Regular users: "Line Access Settings" in user dropdown
- Administrators: "Manage User Access" in admin section

### 5. API Endpoints

**Save Line Access**: `POST /production/api/line-access/save/`
**Get User Access**: `GET /production/api/line-access/user/<user_id>/`
**Admin Update Access**: `POST /production/api/line-access/admin/update/`

### 6. Color Coding System

**Implementation**: JavaScript function to generate consistent colors based on line name's first character

```javascript
function getLineCardColor(lineName) {
    const firstChar = lineName.charAt(0).toUpperCase();
    const colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
        '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9'
    ];
    const index = firstChar.charCodeAt(0) % colors.length;
    return colors[index];
}
```

**Color Application**:
- Card border-left or background accent color
- Consistent across all instances of the same line
- Maintains accessibility standards for contrast

## Data Models

### Existing Models (No Changes Required)

**Line Model**:
```python
class Line(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    # ... existing fields
```

**UserLineAccess Model**:
```python
class UserLineAccess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    line = models.ForeignKey(Line, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'line']
```

### New Helper Functions

**File**: `production/utils.py`

```python
def has_line_access(user):
    """Check if user has any line access configured"""
    return UserLineAccess.objects.filter(user=user).exists()

def get_user_line_access(user):
    """Get all line access for a user"""
    return UserLineAccess.objects.filter(user=user).select_related('line')

def update_user_line_access(user, line_ids):
    """Update user's line access permissions"""
    # Implementation for bulk update
```

## Error Handling

### User-Facing Errors
- **No Lines Available**: Display message when no lines exist in system
- **Save Failures**: Show specific error messages for database issues
- **Permission Denied**: Redirect unauthorized users appropriately
- **Network Errors**: Handle AJAX failures gracefully

### System Errors
- **Database Connection**: Graceful degradation when database is unavailable
- **Missing Dependencies**: Proper error handling for missing models
- **Docker Environment**: Ensure proper URL resolution in containerized environment

### Error Response Format
```json
{
    "status": "error",
    "message": "User-friendly error message",
    "details": "Technical details for debugging",
    "code": "ERROR_CODE"
}
```

## Testing Strategy

### Unit Tests
- **Model Tests**: Verify UserLineAccess model behavior
- **View Tests**: Test all view classes and their permissions
- **Utility Function Tests**: Test helper functions in utils.py
- **Middleware Tests**: Verify redirection logic

### Integration Tests
- **End-to-End Flow**: Test complete user journey from login to configuration
- **Admin Workflow**: Test administrative user management features
- **API Integration**: Test all API endpoints with various scenarios
- **Docker Environment**: Test functionality in containerized environment

### Test Files Structure
```
production/tests/
├── test_line_access_config.py
├── test_admin_user_access.py
├── test_line_access_middleware.py
└── test_line_access_api.py
```

### Test Scenarios
1. **New User Flow**: User with no line access gets redirected
2. **Existing User Flow**: User with line access proceeds normally
3. **Configuration Save**: Line access selections are saved correctly
4. **Admin Management**: Administrators can modify other users' access
5. **Bulk Operations**: Select All/Deselect All functions work correctly
6. **Search Filtering**: Line filtering works with name and description
7. **Docker Compatibility**: All features work in Docker Compose environment

### Performance Considerations
- **Database Queries**: Optimize queries with select_related and prefetch_related
- **Caching**: Cache line data to reduce database load
- **AJAX Responses**: Minimize payload size for API responses
- **Frontend Performance**: Implement debouncing for search functionality

### Security Considerations
- **CSRF Protection**: All forms include CSRF tokens
- **Permission Checks**: Verify user permissions on all operations
- **Input Validation**: Sanitize all user inputs
- **Admin Access**: Restrict administrative functions to superusers only
- **Audit Logging**: Log all administrative changes for security tracking