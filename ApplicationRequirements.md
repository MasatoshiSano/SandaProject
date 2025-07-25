

# ✅ Application Requirements

---

## 1. 🎯 Application Overview

* **Name (Tentative)**: Production Planning and Performance Visualization & Analysis App
* **Purpose**:

  * Visualize production plans and actual results by line and product type
  * Monitor production progress in real-time with dashboards
  * Provide a foundation for future alerting and productivity improvement

---

## 2. ⚙️ Development Policy

* **Use Django Generic Views extensively** (`ListView`, `CreateView`, `UpdateView`, `DeleteView`, etc.)
* Reuse and extend Django's built-in class-based views wherever possible
* Use `base.html` for layout consistency
* For real-time features, use **Daphne + Django Channels + WebSocket**
* Graphs rendered with **Chart.js**
* Emphasis on **modular, extensible, and maintainable design**

---

## 3. 🔐 Authentication & User Access

* User login, logout, signup via **django-allauth** (email not required)
* Each user has access only to **permitted production lines**
* After login, users land on a **"Select Line and Date" page** (default: today)
* Last accessed line is stored and reused as default on next login

---

## 4. 🧠 Core Models

| Model                    | Description                                                                      |
| ------------------------ | -------------------------------------------------------------------------------- |
| **User**                 | Django’s built-in user model                                                     |
| **Line**                 | Production line                                                                  |
| **UserLineAccess**       | Restricts which lines a user can access                                          |
| **Machine**              | Equipment belonging to a line                                                    |
| **Category**             | Product category (editable via UI)                                               |
| **Tag**                  | Product tags (multi-tag support, editable via UI)                                |
| **Part**                 | Product type; has category, tags, target PPH, and cycle time                     |
| **Plan**                 | Production plan: date, line, part, quantity, order                               |
| **Result**               | Production result: timestamp, line, machine, part, serial number, result (OK/NG) |
| **PartChangeDowntime**   | Downtime in seconds when switching parts per line                                |
| **WorkCalendar**         | Working hours, morning meeting, and breaks                                       |
| **WorkingDay**           | Defines working and non-working days (weekends/holidays)                         |
| **DashboardCardSetting** | Admin can toggle dashboard cards' visibility                                     |

---

## 5. 🕒 Working Time & Calendar Settings

* Configurable **start time** (e.g. 08:30), **morning meeting**, and **break times**
* Default break times:

  * 10:45–11:00
  * 12:00–12:45
  * 15:00–15:15
  * 17:00–17:15
* **Production plans exclude** these times; actual production may occur during breaks
* **Part switch downtime** is also excluded from planned production time
* `WorkingDay` model defines whether a date is a working day

  * Weekends and Japanese public holidays are considered non-working

---

## 6. 📝 Production Plan Input Page (Generic View)

* Use `CreateView` for new plans
* Input fields:

  * Date (default: today), order, part (dropdown), quantity
* If a part is not registered, user can add it immediately:

  * Fields: name, category, tags (multi), target PPH
  * Cycle time auto-calculated as `3600 ÷ PPH`

---

## 7. 📈 Production Results Page (Generic View)

* Use `ListView` with advanced filtering:

  * AND-based filters for all fields
  * Timestamp: range filtering
  * Others: partial match
* If no filters are applied, no results are shown
* Serial numbers must be **unique**

---

## 8. 📊 Real-time Dashboard (WebSocket + Generic)

### Display Items

* Plan and actual counts per part
* Target, actual, and achievement rate cards
* Graphs:

  * Cumulative line graphs (plan/actual)
  * Hourly stacked bar chart per part

### Automatic Hourly Goal Calculation (NEW)

* When a plan is created:

  * Calculate **per-hour goals** for each part based on working hours
  * Exclude downtime (breaks, morning meeting, part switch)
  * Distribute planned quantity across usable time
* Reflected in the hourly bar chart (plan side)

### Progress Card Color Coding

* Green: ≥ 100%
* Yellow: 80–99%
* Red: < 80%
* Thresholds are configurable for future alerting support

---

## 9. 📅 Weekly / Monthly Graphs

* Toggle between **Weekly** and **Monthly** views
* Default: current week (week starts on Monday)

### Shared Display

* Cumulative actual (line graph)
* Daily part-wise actual (stacked bar chart)
* Non-working days are shown as gray or blank

### Weekly

* X-axis: Mon–Sun
* Graph per selected week

### Monthly

* X-axis: 1st–End of month
* Graph per selected month

---

## 10. 🖼 Frontend Design

* Use `base.html` for all templates
* Header contains:

  * App name, logged-in user, categorized links (dropdown/accordion), logout
* Uses **Bootstrap 5**, but with:

  * Modern, clean design
  * Minimal "Bootstrap feel"
* **Dark/Light mode toggle** with color contrast consideration
* CSS is centralized; avoid per-page styling

---

## 11. 🔄 Real-time Features (WebSocket)

* Real-time updates with **Daphne + Django Channels**
* When a result is submitted:

  * Dashboard graphs and cards update instantly
* Designed to support **future real-time alerts**

---

## 12. ⚙️ Admin Features

* Django Admin provides full CRUD access to:

  * Users, Lines, Machines, Parts, Categories, Tags
  * Plans, Results
  * Working Day & Time settings
  * Dashboard card visibility
* Tags and Categories can also be managed from the plan input page

---

## ✅ Feature Checklist

| Feature                                     | Status |
| ------------------------------------------- | ------ |
| Authentication with line access restriction | ✅      |
| Part/Machine/Line registration              | ✅      |
| Plan input (with modal part add)            | ✅      |
| Real-time dashboard with graphs/cards       | ✅      |
| Auto hour-based plan calculation            | ✅      |
| Weekly/Monthly stacked bar & line graphs    | ✅      |
| Result filtering with unique serial numbers | ✅      |
| Dark/Light mode                             | ✅      |
| WebSocket real-time updates                 | ✅      |
| Admin panel for full data control           | ✅      |
| Full use of Django Generic Views            | ✅      |

