# Requirements Document

## Introduction

This feature adds input count (投入数) functionality to the dashboard cards. The system will track and display the total count of production inputs from machines designated with an input count flag, aggregated by production line. The input count represents all production quantities regardless of quality judgment, calculated within daily work periods defined by the WorkCalendar.

## Requirements

### Requirement 1

**User Story:** As a production manager, I want to see input counts on dashboard cards, so that I can monitor the total volume of items being processed by each production line.

#### Acceptance Criteria

1. WHEN a user views the dashboard THEN the system SHALL display input count data on each line's dashboard card
2. WHEN calculating input counts THEN the system SHALL include all production quantities regardless of quality judgment or result status
3. WHEN displaying input counts THEN the system SHALL show the total count aggregated by production line

### Requirement 2

**User Story:** As a system administrator, I want to configure which machines contribute to input count calculations, so that I can control which equipment is included in input count metrics.

#### Acceptance Criteria

1. WHEN configuring machine settings THEN the system SHALL provide an input count flag (is_count_target) for each machine
2. WHEN the input count flag is enabled THEN the system SHALL include that machine's production data in input count calculations
3. WHEN the input count flag is disabled THEN the system SHALL exclude that machine's production data from input count calculations
4. WHEN saving machine configuration THEN the system SHALL persist the input count flag setting

### Requirement 3

**User Story:** As a production supervisor, I want input counts calculated based on work calendar periods, so that the metrics align with our operational schedule.

#### Acceptance Criteria

1. WHEN calculating daily input counts THEN the system SHALL use WorkCalendar.work_start_time as the period start time
2. WHEN determining the period end time THEN the system SHALL use the next day's WorkCalendar.work_start_time as the end time
3. WHEN no next day work calendar exists THEN the system SHALL handle the edge case gracefully
4. WHEN aggregating input counts THEN the system SHALL group production data within the defined work periods

### Requirement 4

**User Story:** As a production operator, I want input count data to be automatically updated, so that I can see current production volume without manual refresh.

#### Acceptance Criteria

1. WHEN new production results are recorded THEN the system SHALL automatically update input count calculations
2. WHEN machine input count flags are modified THEN the system SHALL recalculate affected input counts
3. WHEN work calendar changes occur THEN the system SHALL adjust input count period calculations accordingly
4. WHEN displaying dashboard data THEN the system SHALL show the most current input count information

### Requirement 5

**User Story:** As a quality control manager, I want input counts to be separate from quality metrics, so that I can distinguish between total input volume and quality outcomes.

#### Acceptance Criteria

1. WHEN calculating input counts THEN the system SHALL include all production quantities regardless of pass/fail status
2. WHEN displaying input counts THEN the system SHALL clearly distinguish input count from quality-based metrics
3. WHEN aggregating data THEN the system SHALL maintain separate calculations for input counts and quality metrics
4. WHEN presenting dashboard information THEN the system SHALL show input counts alongside but separate from existing quality indicators