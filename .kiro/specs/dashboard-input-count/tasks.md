# Implementation Plan

- [x] 1. Implement input count calculation function
  - Create `calculate_input_count()` function in `production/utils.py`
  - Handle time period calculation using WorkCalendar work_start_time
  - Query Result model for machines with is_count_target=True
  - Include all judgments (both OK and NG) in input count
  - _Requirements: 1.2, 1.3, 2.2, 3.1, 3.2, 5.1_

- [x] 2. Extend dashboard data service with input count
  - Modify `get_dashboard_data()` function in `production/utils.py`
  - Integrate input count calculation into existing dashboard data flow
  - Add input_count field to dashboard data response
  - Ensure backward compatibility with existing dashboard functionality
  - _Requirements: 1.1, 1.3, 4.1_

- [x] 3. Update dashboard template to display input count
  - Modify `templates/production/dashboard.html` to include input count card
  - Add input count display alongside existing metrics
  - Ensure responsive design and consistent styling
  - Add appropriate labels and descriptions for input count
  - _Requirements: 1.1, 5.2_

- [x] 4. Update dashboard API response format
  - Modify `DashboardDataAPIView` in `production/views.py` to include input count
  - Ensure API response includes input_count field
  - Maintain backward compatibility for existing API consumers
  - Update API documentation if needed
  - _Requirements: 1.1, 4.1_

- [x] 5. Add error handling for input count calculations
  - Implement fallback behavior when WorkCalendar is missing
  - Handle cases where no machines have is_count_target=True
  - Add logging for input count calculation errors
  - Ensure dashboard remains functional even if input count calculation fails
  - _Requirements: 3.3, 4.1_

- [x] 6. Create unit tests for input count functionality
  - Test `calculate_input_count()` function with various scenarios
  - Test input count calculation with different machine configurations
  - Test time period calculation with various WorkCalendar settings
  - Test error handling for missing configurations
  - _Requirements: 2.2, 2.3, 3.1, 3.2_

- [x] 7. Create integration tests for dashboard input count
  - Test dashboard data API includes input count in response
  - Test dashboard template renders input count correctly
  - Test input count updates when Result records are created
  - Test input count behavior with machine configuration changes
  - _Requirements: 1.1, 4.1, 4.2_

- [x] 8. Update WebSocket consumers for real-time input count updates
  - Ensure existing WebSocket infrastructure includes input count in updates
  - Test real-time updates when new Result records are added
  - Verify input count changes are reflected immediately in dashboard
  - Test WebSocket performance with input count calculations
  - _Requirements: 4.1, 4.2_