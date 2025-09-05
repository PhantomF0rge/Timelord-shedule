### `docs/api.md`

````markdown
# Timelord Schedule — HTTP API (v1)

This document aggregates all current API endpoints that exist in the repository, grouped by module.  
Base path: `/api/v1`

> Auth is cookie-based (Flask-Login session cookie). For all unsafe methods (POST/PUT/DELETE) **you must send the CSRF token** in header `X-CSRF-Token`.  
> Get the token from `GET /api/v1/csrf` (response key is `csrf`) and also set by server as a cookie.

---

## Conventions

### Authentication & CSRF

- **Session**: after successful login, the server sets a session cookie.
- **CSRF**: for `POST/PUT/DELETE` include `X-CSRF-Token: <token>` where `<token>` is obtained from `/api/v1/csrf`.

```http
GET /api/v1/csrf
200 OK
{"csrf":"<random-token>"}
````

### Errors

There are two existing patterns depending on the area of the codebase:

1. **Common API** (constraints, planning, admin, import/export):

```json
{ "ok": false, "errors": [ { "code": "BAD_REQUEST", "details": {...} } ] }
```

2. **Auth routes**:

```json
{ "error": "invalid_credentials" }        // or "unauthorized", "too_many_attempts", ...
```

### Common error codes (non-exhaustive)

* `BAD_REQUEST` – invalid or missing parameters
* `UNAUTHORIZED` – not logged in (HTTP 401)
* `FORBIDDEN` – not enough privileges (HTTP 403)
* `NOT_FOUND` – resource doesn’t exist
* `CONSTRAINT_VIOLATION` – generic conflict
* `TEACHER_BUSY`, `GROUP_BUSY`, `ROOM_BUSY`
* `TEACHER_NOT_AVAILABLE`
* `TEACHER_LIMIT_EXCEEDED`
* `CURRICULUM_HOURS_EXCEEDED`
* `ROOM_CAPACITY_EXCEEDED`
* `ROOM_COMPUTERS_NOT_ENOUGH`
* `INVALID_BUILDING`
* `NOTHING_TO_COMMIT`
* `DUPLICATE` – duplicates on import (HTTP 422)
* `INVALID_INT`, `UNKNOWN_REFERENCE` – data validation errors on import

---

## Auth

### `GET /api/v1/csrf`

Return a CSRF token (also duplicated into a cookie).

**200**

```json
{ "csrf": "token-123" }
```

### `POST /api/v1/auth/login`

Body:

```json
{ "email": "admin@example.com", "password": "pass" }
```

Headers: `X-CSRF-Token` required.

**200**

```json
{ "ok": true, "user": { "id": 1, "email": "admin@example.com", "role": "ADMIN" } }
```

**401**

```json
{ "error": "invalid_credentials" }
```

**429**

```json
{ "error": "too_many_attempts" }
```

### `POST /api/v1/auth/logout`

Headers: `X-CSRF-Token`.

**200**

```json
{ "ok": true }
```

---

## Constraints

### `POST /api/v1/admin/constraints/check`

Check if a lesson can be placed (date/slot/teacher/group/room).

Body (JSON):

```json
{
  "date": "2025-01-01",
  "time_slot_id": 1,
  "group_id": 10,
  "subject_id": 5,
  "lesson_type_id": 2,
  "teacher_id": 7,
  "room_id": 3,
  "is_remote": false,
  "requires_computers": true,
  "enforce_building_type": true
}
```

**200**

```json
{ "ok": true, "errors": [] }
```

**409**

```json
{ "ok": false, "errors": [ {"code":"TEACHER_BUSY"}, {"code":"ROOM_BUSY"} ] }
```

---

## Planning

Greedy planner that proposes placements for a period. Supports empty teacher/group filters (then uses all).

### `POST /api/v1/admin/planning/generate`

Headers: `X-CSRF-Token`.

Body:

```json
{
  "date_from": "2025-03-10",
  "date_to":   "2025-03-14",
  "group_ids": [1,2],        // optional; if omitted -> all groups
  "teacher_ids":[10,11],     // optional; if omitted -> all teachers
  "honor_holidays": true
}
```

**200**

```json
{
  "ok": true,
  "preview_id": "0c8cb1f4-2a55-4d9a-bd71-4b2c2aaf6cfc",
  "proposed": [
    {
      "date":"2025-03-10",
      "time_slot_id": 1,
      "group_id": 1,
      "subject_id": 3,
      "lesson_type_id": 2,
      "teacher_id": 10,
      "room_id": 4
    }
  ],
  "unplaced": [
    {
      "group_id": 2,
      "subject_id": 5,
      "reason_codes": ["TEACHER_NOT_AVAILABLE", "ROOM_BUSY"],
      "context": {"date":"2025-03-11", "time_slot_id": 2}
    }
  ]
}
```

### `GET /api/v1/admin/planning/preview?id=<preview_id>`

**200**

```json
{
  "ok": true,
  "preview_id": "0c8cb1f4-2a55-4d9a-bd71-4b2c2aaf6cfc",
  "proposed": [ ... ],
  "unplaced": [ ... ]
}
```

**404**

```json
{ "ok": false, "errors": [ {"code":"NOT_FOUND"} ] }
```

### `POST /api/v1/admin/planning/commit`

Headers: `X-CSRF-Token`.

Body:

```json
{ "preview_id": "0c8cb1f4-2a55-4d9a-bd71-4b2c2aaf6cfc" }
```

**200**

```json
{ "ok": true, "committed": 12 }
```

**409**

```json
{ "ok": false, "errors": [ {"code":"TEACHER_BUSY"} ] }
```

---

## Admin: Schedule Editor (CRUD + lookup)

### `GET /api/v1/admin/schedule/lookup`

Lookup lists for UI editors.

**200**

```json
{
  "groups":      [{ "id":1, "code":"G1", "name":"Group 1" }],
  "teachers":    [{ "id":7, "full_name":"John Doe" }],
  "rooms":       [{ "id":3, "number":"101", "capacity":30 }],
  "subjects":    [{ "id":5, "name":"Math" }],
  "lesson_types":[{ "id":2, "name":"Practice" }],
  "timeslots":   [{ "id":1, "order_no":1, "start_time":"08:30", "end_time":"10:00" }]
}
```

### `POST /api/v1/admin/schedule`

Headers: `X-CSRF-Token`. Body is same as for constraints check.
Creates a schedule row after final validation.

**201**

```json
{ "id": 123, "ok": true }
```

**409**

```json
{ "ok": false, "errors": [ {"code":"ROOM_CAPACITY_EXCEEDED"} ] }
```

### `PUT /api/v1/admin/schedule/{id}`

Headers: `X-CSRF-Token`. Body may include any fields to move/adjust the lesson (e.g. `time_slot_id`, `room_id`).

**200**

```json
{ "ok": true }
```

**409**

```json
{ "ok": false, "errors": [ {"code":"GROUP_BUSY"} ] }
```

### `DELETE /api/v1/admin/schedule/{id}`

Headers: `X-CSRF-Token`.

**200**

```json
{ "ok": true }
```

---

## Reports (CSV)

All CSV files use **UTF-8** and **semicolon** (`;`) as delimiter.

### `GET /api/v1/reports/schedule/week`

Query:

```
scope=group|teacher|building
id=<entity_id>
week_start=YYYY-MM-DD
```

**200** (`text/csv`)

```
date;weekday;slot_order;group;teacher;room;subject;lesson_type
2025-03-10;1;1;G1;John Doe;101;Math;Practice
```

### `GET /api/v1/reports/teacher-hours`

Query: `week_start=YYYY-MM-DD`

**200** (`text/csv`)

```
teacher;hours;lessons
John Doe;18;12
```

### `GET /api/v1/reports/room-utilization`

Query: `week_start=YYYY-MM-DD`

**200** (`text/csv`)

```
room;slots_used;slots_total;utilization_pct
101;18;30;60
```

---

## Import / Export (CSV)

Endpoints support **multipart/form-data** with:

* `file`: CSV file
* `mapping`: JSON string that maps model fields to CSV column names (see examples below)

### `POST /api/v1/admin/import/preview?entity=groups|teachers|rooms|curriculum`

Detect CSV columns and propose mapping.

**200**

```json
{
  "ok": true,
  "detected_mapping": {
    "code":"code","name":"name","students_count":"students_count","education_level":"education_level"
  },
  "sample": [
    {"code":"A1","name":"Alpha","students_count":"10","education_level":"СПО"}
  ]
}
```

### `POST /api/v1/admin/import/validate?entity=groups|teachers|rooms|curriculum`

Validate a batch without saving.

**200 (groups with issues)**

```json
{
  "ok": false,
  "duplicates": [{"row":2, "code":"G1"}],
  "row_errors": [{"row":1, "code":"INVALID_INT", "field":"students_count", "value":"xx"}]
}
```

**200 (curriculum ok)**

```json
{ "ok": true }
```

### `POST /api/v1/admin/import/commit?entity=groups|teachers|rooms|curriculum`

Atomically import a batch. On any error the whole batch is rolled back.

**200 (success)**

```json
{ "ok": true, "committed": 2 }
```

**422 (duplicates/unknown references)**

```json
{
  "ok": false,
  "errors": [ {"code":"DUPLICATE", "row":1, "field":"code", "value":"X1"} ]
}
```

#### Mapping examples

**groups**

```json
{
  "code":"code",
  "name":"name",
  "students_count":"students_count",
  "education_level":"education_level"
}
```

**rooms**

```json
{
  "building_name":"building",
  "room_type_name":"room_type",
  "number":"number",
  "capacity":"capacity",
  "computers_count":"computers"
}
```

**curriculum**

```json
{
  "group_code":"group",
  "subject_name":"subject",
  "total_hours":"hours"
}
```

---

````

---

### `docs/openapi.yaml`
```yaml
openapi: 3.0.3
info:
  title: Timelord Schedule API
  version: "1.0.0"
  description: Cookie-based API with CSRF header for unsafe methods.
servers:
  - url: /
components:
  securitySchemes:
    cookieAuth:
      type: apiKey
      in: cookie
      name: session
    XCSRF:
      type: apiKey
      in: header
      name: X-CSRF-Token
  schemas:
    ApiOk:
      type: object
      properties:
        ok:
          type: boolean
          example: true
    ApiErrorList:
      type: object
      properties:
        ok:
          type: boolean
          example: false
        errors:
          type: array
          items:
            $ref: '#/components/schemas/ErrorItem'
    ErrorItem:
      type: object
      properties:
        code:
          type: string
        details:
          type: object
          nullable: true
    ConstraintCheckRequest:
      type: object
      required: [date, time_slot_id, group_id, subject_id, teacher_id]
      properties:
        date: { type: string, format: date }
        time_slot_id: { type: integer }
        group_id: { type: integer }
        subject_id: { type: integer }
        lesson_type_id: { type: integer, nullable: true }
        teacher_id: { type: integer }
        room_id: { type: integer, nullable: true }
        is_remote: { type: boolean }
        requires_computers: { type: boolean }
        enforce_building_type: { type: boolean, nullable: true }
    ConstraintCheckResponse:
      type: object
      properties:
        ok: { type: boolean }
        errors:
          type: array
          items: { $ref: '#/components/schemas/ErrorItem' }
    Proposed:
      type: object
      properties:
        date: { type: string, format: date }
        time_slot_id: { type: integer }
        group_id: { type: integer }
        subject_id: { type: integer }
        lesson_type_id: { type: integer }
        teacher_id: { type: integer }
        room_id: { type: integer }
    Unplaced:
      type: object
      properties:
        group_id: { type: integer }
        subject_id: { type: integer }
        reason_codes:
          type: array
          items: { type: string }
        context:
          type: object
    PlanningGenerateRequest:
      type: object
      required: [date_from, date_to]
      properties:
        date_from: { type: string, format: date }
        date_to: { type: string, format: date }
        group_ids:
          type: array
          items: { type: integer }
        teacher_ids:
          type: array
          items: { type: integer }
        honor_holidays: { type: boolean }
    PlanningPreviewPayload:
      type: object
      properties:
        proposed:
          type: array
          items: { $ref: '#/components/schemas/Proposed' }
        unplaced:
          type: array
          items: { $ref: '#/components/schemas/Unplaced' }
    ScheduleCreateRequest:
      allOf:
        - $ref: '#/components/schemas/ConstraintCheckRequest'
    ScheduleCreateResponse:
      type: object
      properties:
        ok: { type: boolean }
        id: { type: integer }
    LoginRequest:
      type: object
      required: [email, password]
      properties:
        email: { type: string, format: email }
        password: { type: string }
    LoginResponse:
      type: object
      properties:
        ok: { type: boolean }
        user:
          type: object
          properties:
            id: { type: integer }
            email: { type: string }
            role: { type: string }
    AuthError:
      type: object
      properties:
        error: { type: string, example: invalid_credentials }
paths:
  /api/v1/csrf:
    get:
      summary: Get CSRF token
      responses:
        '200':
          description: token
          content:
            application/json:
              schema:
                type: object
                properties:
                  csrf:
                    type: string
  /api/v1/auth/login:
    post:
      summary: Login
      security:
        - XCSRF: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/LoginRequest' }
      responses:
        '200':
          description: Logged in
          content:
            application/json:
              schema: { $ref: '#/components/schemas/LoginResponse' }
        '401':
          description: Invalid creds
          content:
            application/json:
              schema: { $ref: '#/components/schemas/AuthError' }
        '429':
          description: Rate limited
          content:
            application/json:
              schema: { $ref: '#/components/schemas/AuthError' }
  /api/v1/auth/logout:
    post:
      summary: Logout
      security:
        - cookieAuth: []
        - XCSRF: []
      responses:
        '200':
          description: ok
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ApiOk' }
  /api/v1/admin/constraints/check:
    post:
      summary: Check lesson constraints
      security:
        - cookieAuth: []
        - XCSRF: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ConstraintCheckRequest' }
      responses:
        '200':
          description: OK (no errors)
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ConstraintCheckResponse' }
        '409':
          description: Conflicts
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ConstraintCheckResponse' }
  /api/v1/admin/planning/generate:
    post:
      summary: Generate planning preview
      security:
        - cookieAuth: []
        - XCSRF: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/PlanningGenerateRequest' }
      responses:
        '200':
          description: Preview generated
          content:
            application/json:
              schema:
                type: object
                properties:
                  ok: { type: boolean }
                  preview_id: { type: string }
                  proposed:
                    type: array
                    items: { $ref: '#/components/schemas/Proposed' }
                  unplaced:
                    type: array
                    items: { $ref: '#/components/schemas/Unplaced' }
  /api/v1/admin/planning/preview:
    get:
      summary: Get planning preview by id
      security:
        - cookieAuth: []
      parameters:
        - in: query
          name: id
          required: true
          schema: { type: string }
      responses:
        '200':
          description: Preview payload
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/PlanningPreviewPayload'
                  - type: object
                    properties:
                      ok: { type: boolean }
                      preview_id: { type: string }
        '404':
          description: Not found
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ApiErrorList' }
  /api/v1/admin/planning/commit:
    post:
      summary: Commit planning preview
      security:
        - cookieAuth: []
        - XCSRF: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [preview_id]
              properties:
                preview_id: { type: string }
      responses:
        '200':
          description: Committed
          content:
            application/json:
              schema:
                type: object
                properties:
                  ok: { type: boolean }
                  committed: { type: integer }
        '409':
          description: Conflicts
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ApiErrorList' }
  /api/v1/admin/schedule/lookup:
    get:
      summary: Lookup lists for schedule editor
      security:
        - cookieAuth: []
      responses:
        '200':
          description: Data sets
          content:
            application/json:
              schema:
                type: object
                properties:
                  groups: { type: array, items: { type: object } }
                  teachers: { type: array, items: { type: object } }
                  rooms: { type: array, items: { type: object } }
                  subjects: { type: array, items: { type: object } }
                  lesson_types: { type: array, items: { type: object } }
                  timeslots: { type: array, items: { type: object } }
  /api/v1/admin/schedule:
    post:
      summary: Create schedule row
      security:
        - cookieAuth: []
        - XCSRF: []
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/ScheduleCreateRequest' }
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ScheduleCreateResponse' }
        '409':
          description: Conflicts
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ApiErrorList' }
  /api/v1/admin/schedule/{id}:
    put:
      summary: Update schedule row
      security:
        - cookieAuth: []
        - XCSRF: []
      parameters:
        - in: path
          name: id
          required: true
          schema: { type: integer }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
      responses:
        '200':
          description: Updated
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ApiOk' }
        '409':
          description: Conflicts
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ApiErrorList' }
    delete:
      summary: Delete schedule row
      security:
        - cookieAuth: []
        - XCSRF: []
      parameters:
        - in: path
          name: id
          required: true
          schema: { type: integer }
      responses:
        '200':
          description: Deleted
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ApiOk' }
  /api/v1/reports/schedule/week:
    get:
      summary: Weekly schedule CSV
      security:
        - cookieAuth: []
      parameters:
        - in: query
          name: scope
          schema: { type: string, enum: [group, teacher, building] }
          required: true
        - in: query
          name: id
          schema: { type: integer }
          required: true
        - in: query
          name: week_start
          schema: { type: string, format: date }
          required: true
      responses:
        '200':
          description: CSV
          content:
            text/csv:
              schema:
                type: string
                format: binary
  /api/v1/reports/teacher-hours:
    get:
      summary: Teacher hours CSV
      security:
        - cookieAuth: []
      parameters:
        - in: query
          name: week_start
          required: true
          schema: { type: string, format: date }
      responses:
        '200':
          description: CSV
          content:
            text/csv:
              schema:
                type: string
                format: binary
  /api/v1/reports/room-utilization:
    get:
      summary: Room utilization CSV
      security:
        - cookieAuth: []
      parameters:
        - in: query
          name: week_start
          required: true
          schema: { type: string, format: date }
      responses:
        '200':
          description: CSV
          content:
            text/csv:
              schema:
                type: string
                format: binary
  /api/v1/admin/import/preview:
    post:
      summary: CSV preview (detect mapping)
      security:
        - cookieAuth: []
        - XCSRF: []
      parameters:
        - in: query
          name: entity
          required: true
          schema: { type: string, enum: [groups, teachers, rooms, curriculum] }
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
      responses:
        '200':
          description: Detected mapping and sample
          content:
            application/json:
              schema:
                type: object
                properties:
                  ok: { type: boolean }
                  detected_mapping: { type: object, additionalProperties: { type: string } }
                  sample:
                    type: array
                    items: { type: object }
  /api/v1/admin/import/validate:
    post:
      summary: CSV dry-run validation
      security:
        - cookieAuth: []
        - XCSRF: []
      parameters:
        - in: query
          name: entity
          required: true
          schema: { type: string, enum: [groups, teachers, rooms, curriculum] }
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
                mapping:
                  type: string
                  description: JSON string for mapping
      responses:
        '200':
          description: Validation result
          content:
            application/json:
              schema:
                type: object
                properties:
                  ok: { type: boolean }
                  duplicates:
                    type: array
                    items: { type: object }
                  row_errors:
                    type: array
                    items: { $ref: '#/components/schemas/ErrorItem' }
  /api/v1/admin/import/commit:
    post:
      summary: CSV commit (atomic)
      security:
        - cookieAuth: []
        - XCSRF: []
      parameters:
        - in: query
          name: entity
          required: true
          schema: { type: string, enum: [groups, teachers, rooms, curriculum] }
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
                mapping:
                  type: string
                  description: JSON string for mapping
      responses:
        '200':
          description: Imported
          content:
            application/json:
              schema:
                type: object
                properties:
                  ok: { type: boolean }
                  committed: { type: integer }
        '422':
          description: Validation errors (rollback)
          content:
            application/json:
              schema: { $ref: '#/components/schemas/ApiErrorList' }
````

