# FE_IMPROVEMENT_SPEC.md — Frontend Specification Additions (Mission Planner)

**Version:** 1.0  
**Date:** 2025-07-31  
**Author:** Agnes-2.0-Flash (Sapiens AI)

---

## 1. Overview

This document specifies additional UI/UX requirements for the **Mission Planner** feature to be integrated into the existing Nuxt/Vue frontend. It builds on top of the existing `/scan` and `/scans` pages, adding new pages/views for mission management, location import, and real-time mission monitoring via WebSockets.

All endpoints follow the `/api/v1/missions/*` backend API defined in `IMPROVEMENT_FEATURE.md`.

---

## 2. New Pages / Views Structure

```
src/views/
├── Index.vue                  (existing dashboard)
├── ScanPage.vue               (existing /scan)
├── ScansListPage.vue          (existing /scans)
├── MissionListPage.vue        (NEW: /missions/list)       -- List all missions
├── MissionDetailPage.vue      (NEW: /missions/{id})      -- View & control single mission
├── LocationUploadPage.vue     (NEW: /missions/{id}/locations/upload) -- CSV upload per mission
├── LocationListPage.vue       (NEW: /missions/{id}/locations)   -- View imported locations
└── MissionsWebSocket.vue      (hidden component, real-time updates)
```

### 2.1 Route Configuration (`router/index.js`)

Add these routes:

```js
{
  path: '/missions',
  name: 'mission-list',
  component: () => import('@/views/MissionListPage.vue'),
  meta: { title: 'Missions' }
},
{
  path: '/missions/:id/locations/upload',
  name: 'location-upload',
  component: () => import('@/views/LocationUploadPage.vue'),
  meta: { title: 'Import Tower Locations' }
},
{
  path: '/missions/:id/locations',
  name: 'location-list',
  component: () => import('@/views/LocationListPage.vue'),
  meta: { title: 'Tower Locations' }
}
```

Existing navigation items: **Scan**, **History**. Add new nav entries: **Missions**, **Locations**.

---

## 3. Component Specifications

### 3.1 MissionListPage.vue

**Purpose:** List all missions with summary, filter by status, quick actions.

#### Props / Data

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `missions` | `Mission[]` | [] | Fetched from GET /api/v1/missions?status=all |

#### API Calls

- `GET /api/v1/missions` → paginated list (page, page_size, search optional)
- WebSocket event `mission_status` → update live status/counters in-place

#### UI Layout

```
Header: "Mission Dashboard" + [Create Button (+)]
─────────────────────────────────────────────
Status Filter: [ALL ▼] [IDLE] [RUNNING] [COMPLETED] ...

| ID | Name           | Status   | Progress | Created | Actions |
|----|----------------|----------|----------|---------|--------|
| 1  | Jakarta Sweep  | RUNNING  | 3/10     | 2025-...| Start/Pause/Stop/Delete/View |
| 2  | Downtown Scan  | COMPLETED| 10/10    | 2025-...| View / Delete |
```

**Actions on each row:**
- **Start** → disabled if not IDLE/READY; opens confirmation modal
- **Pause** → disabled if not RUNNING; POST /{id}/pause
- **Resume** → disabled if not PAUSED; POST /{id}/resume
- **Stop** → any state; POST /{id}/stop; confirmation required
- **View** → navigate to MissionDetailPage.vue (show full details)
- **Delete** → only if IDLE/READY/STOPPED; confirmation modal

#### Pagination

Standard pagination component: page size selector (10, 25, 50), current page, total count.

---

### 3.2 MissionDetailPage.vue

**Purpose:** Single mission overview with controls, route visualization, scan history.

#### Tabs Navigation

| Tab | Content |
|-----|---------|
| **Overview** | Mission metadata (name, description, radius, tty_port, status, counters), action buttons (Start/Stop/Plan/Reorder), live progress indicator |
| **Route** | Interactive map (Leaflet/Google Maps) showing all mission locations in sequence order; highlight current position as GPS updates; show distance between consecutive points |
| **Planner** | Table of mission_locations: sequence_order, tower_name, status, actual_visit_time, scan_session_id (link to detail). Supports manual reorder drag-and-drop or numeric input submit |
| **Scans** | Paginated list of scan_sessions linked to this mission (JOIN through mission_locations.scan_session_id); same filters as main Scans list |
| **Logs** | Event timeline of mission events (STARTING, VISITED, STOPPED, FAILED, etc.) with timestamps |

#### Action Buttons (conditional based on status)

- **Generate Plan** → POST /{id}/plan → shows auto-planner spinner, then refreshes Route tab
- **Manual Reorder** → open modal where user drags rows or enters sequence numbers → POST /{id}/route/reorder (payload: array of `{location_id, sequence_order}`)
- **Skip** → on a specific location row: POST /{id}/route/skip({location_id}) → mark as SKIPPED
- **Start** → POST /{id}/start (only when READY/IDLE); disables other actions until completed/stopped
- **Pause / Resume** → for RUNNING/PAUSED states
- **Stop** → any running state

#### Live Update (WebSocket)

Subscribe to channel `"mission"` and listen for:
- `mission_progress`: update `visited_locations`, `current_location_id`, `distance_to_target`
- `mission_visit`: add new entry to live log, update location status → VISITED, set `actual_visit_time`
- `mission_completed`: change status to COMPLETED, show completion toast
- `mission_failed`: change status to FAILED, show error toast with reason
- `mission_stopped`: change status to STOPPED, show stopped notification

---

### 3.3 LocationUploadPage.vue

**Purpose:** Upload CSV of tower locations, view results, manage batches.

#### Upload Form

```
[ Choose File   no-file-selected.txt ]
[ UPLOAD BUTTON ]
[ Status Indicator: Uploading... / Success / Failed ]
[ Error Log Display (collapsible) ]
[ Success Summary: X inserted, Y updated, Z skipped ]
```

**CSV Validation (server-side):**
- Must have header: `cellular_tower_id,cellular_tower_name,latitude,longitude`
- All columns required
- Latitude/longitude must be valid floats
- Duplicate cellular_tower_id triggers UPSERT (update, not insert)

On success, flash toast with batch ID and link to **Location List**.

#### Location List Table

| Tower ID | Tower Name | Latitude | Longitude | Source | Upload Batch | Actions |
|----------|------------|----------|-----------|--------|--------------|---------|
| TWR-001  | Jakarta P. | -6.2088  | 106.8456  | csv_import | batch-uuid | Delete / View in Mission |

**Features:** Search by ID/name, delete individual (blocked if referenced in active mission), bulk delete by batch ID.

---

### 3.4 LocationListPage.vue

Similar to above but standalone page listing all imported locations.

---

### 3.5 MissionsWebSocket.vue (Hidden Component)

Single Vue component mounted once that handles all WebSocket subscriptions for mission events.

**Structure:**

```vue
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouteStore } from '@/stores/mission' // Pinia store

const ws = ref(null)
const missionStore = useMissionStore()

onMounted(() => {
  const wsUrl = `${window.location.protocol === 'https' ? 'wss:' : 'ws:'}//${window.location.host}/ws/mission`
  ws.value = new WebSocket(wsUrl)
  
  ws.value.onopen = () => console.log('Mission WS connected')
  
  ws.value.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type.startsWith('mission_')) {
      missionStore.updateFromEvent(data.type, data.data)
    }
  }
  
  ws.value.onclose = () => {
    // Attempt reconnection logic
    setTimeout(() => onMounted(), 5000)
  }
})

onBeforeUnmount(() => {
  if (ws.value) ws.value.close()
})
</script>
```

**Pinia Store (`stores/mission.ts`)** maintains global mission state, receives WebSocket updates and mirrors them to components.

---

## 4. State Management (Pinia)

New store `mission.ts`:

```ts
export const useMissionStore = defineStore('mission', {
  state: () => ({
    missions: [] as MissionDTO[],
    currentMission: null as MissionDetailDTO | null,
    activeStatusFilter: string // 'all', 'IDLE', 'RUNNING', etc.
  }),
  actions: {
    async fetchMissions(filter = 'all') {
      const res = await api.get(`/missions?status=${filter}`)
      this.missions = res.data.items
    },
    
    async getMission(id: number) {
      const res = await api.get(`/missions/${id}`)
      this.currentMission = res.data
    },
    
    async startMission(id: number) {
      await api.post(`/missions/${id}/start`)
      // Refresh after action
      await this.fetchMissions(this.activeStatusFilter)
    },
    
    // similarly for pause, resume, stop, plan, reorder
  },
  
  getters: {
    getRunningMission(): MissionDTO | undefined {
      return this.missions.find(m => m.status === 'RUNNING')
    }
  }
})
```

**Getter note:** `getRunningMission` enforces singleton constraint visibility—if another user has one RUNNING, this can warn about potential concurrency conflict.

---

## 5. DTOs / Types (TypeScript Interfaces)

```ts
// Location
interface LocationDTO {
  id: number
  cellular_tower_id: string
  cellular_tower_name: string | null
  latitude: number
  longitude: number
  source: string
  upload_batch_id: string | null
  created_at: string
  updated_at: string
}

// Mission
interface MissionDTO {
  id: number
  name: string
  description: string | null
  status: 'IDLE' | 'PLANNING' | 'READY' | 'STARTING' | 'RUNNING' | 'PAUSED' | 
          'COMPLETED' | 'STOPPED' | 'FAILED'
  radius_meters: number
  tty_port: string | null
  start_location_id: number | null
  current_location_id: number | null
  total_locations: number
  visited_locations: number
  started_at: string | null
  completed_at: string | null
  stopped_at: string | null
  created_at: string
  updated_at: string
}

// Mission Planner
interface PlannerDTO {
  id: number
  mission_id: number
  mission_location_id: number
  location_name: string
  sequence_order: number
  status: 'PENDING' | 'IN_PROGRESS' | 'VISITED' | 'SKIPPED'
  distance_from_previous_meters: number | null
  bearing_from_previous_degrees: number | null
  estimated_arrival_time: string | null
  actual_visit_time: string | null
  scan_session_id: number | null
  visited_at: string | null
  created_at: string
}

// Mission Event Log (for logs tab) — event_type vocabulary matches backend (Phase 6 §4.6 / Phase 10 §6.2)
interface MissionLogEntry {
  timestamp: string
  event_type: 'STARTING' | 'RUNNING' | 'PAUSED' | 'RESUMED' | 'VISITED' | 'SKIPPED' |
              'STOPPED' | 'COMPLETED' | 'FAILED' | 'GPS_ERROR' | 'SCAN_ERROR' | 'INFO'
  message: string
}
```

API responses should match these structures.

---

## 6. Error Handling & Toast Notifications

All axios interceptors handle HTTP errors consistently. Specific toast messages:

| HTTP Code | Toast Message |
|-----------|---------------|
| 409 Conflict | "Another mission is already running. Please wait or stop it first." |
| 422 Validation | Show validation errors from server (e.g., invalid coordinates) |
| 404 Not Found | "Mission not found" or "Location not found" |
| 500 Internal | "An unexpected error occurred. Please try again." |
| WebSocket close | "WebSocket connection lost. Attempting to reconnect..." |

Use Toastify or similar toast library already in place.

---

## 7. Map Integration (Route Tab)

Use Leaflet.js (lightweight, no key required) for visual route:

- Load all mission_locations belonging to the mission
- Place markers colored by status (gray=PENDING, blue=IN_PROGRESS, green=VISITED, red=SKIPPED)
- Draw polyline connecting locations in sequence order
- If live GPS available (via existing `/ws/gps`), show a blue dot for current position
- Highlight current target marker when within radius (flash animation)
- Click marker → show tower details

Libraries needed: `leaflet`, `leaflet.markercluster` (optional for many points).

---

## 8. Reordering Modal (Manual Override)

Triggered from Planner tab → "Reorder Sequence" button.

Modal content:
- List of towers in current order with draggable rows OR numeric input fields for sequence number
- Submit button: "Save Order"
- Cancel button: Discard changes

Payload sent to backend: `[{"location_id": 5, "sequence_order": 1}, {"location_id": 2, "sequence_order": 2}]`

Validation: unique sequence numbers from 1 to N.

---

## 9. Integration with Existing Components

| Existing Component | Usage in New Feature |
|--------------------|---------------------|
| `ScanPage.vue` | Unchanged; background executor calls service layer directly without UI involvement |
| `ScansListPage.vue` | Unchanged; mission-scanned lists are separate endpoint `/missions/{id}/scans` |
| `WebSocketManager` (existing) | Extend to handle new `"mission"` channel alongside `"gps"` and `"scan"` |
| `ApolloClient` / `axios` | Added interceptor base URL `/api/v1/missions` |

No breaking changes to existing flow.

---

## 10. Loading States & Skeletons

All list/grid tables use skeleton loaders while fetching. Spinner on buttons during async actions. Mission progress bar (percentage = visited / total) shown on Detail page.

---

## 11. Responsive Design

Same grid/table layout as existing pages. Mobile-friendly: stack tabs vertically on small screens, use collapsible sections for detailed info.

---

## 12. Permissions / Access Control

All mission CRUD actions require authenticated session (if auth is implemented later). For now, assume all endpoints public on LAN. CSRF token protection if enabled.

---

## 13. Testing Checklist (Frontend)

- [ ] CSV upload page accepts valid CSV, shows correct summary
- [ ] CSV upload page rejects malformed CSV with error toast
- [ ] Mission list renders correctly, filters by status work
- [ ] Mission Detail page loads overview, route, locations, scans, logs tabs
- [ ] Generate Plan button shows spinner, then updates route visualization
- [ ] Manual reorder works: drag or numeric inputs, submits correctly
- [ ] Start button transitions state appropriately, WebSocket updates visible
- [ ] Pause/Resume/Stop buttons reflect correct disable states
- [ ] Map markers appear with correct colors
- [ ] Real-time updates (visit events) appear instantly without page refresh
- [ ] Only one mission can be STARTED at a time (concurrency check)

---

**End of Document.**
