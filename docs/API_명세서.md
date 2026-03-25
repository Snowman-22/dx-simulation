# API 명세서 — 시뮬레이션 서버 (FastAPI)

> 작성일: 2026-03-22
> 통신 구조: **프론트엔드 ↔ Spring Boot ↔ 시뮬레이션 서버(FastAPI)**
> Base URL: `http://{simulation-host}:8000/api`
> 데이터 형식: JSON

---

## 통신 구조 개요

```
┌──────────┐      ┌─────────────┐      ┌──────────────────┐      ┌─────┐
│ 프론트엔드 │ ←→  │ Spring Boot  │ ←→  │ 시뮬레이션 서버    │ ←→  │ RDS │
│ (React)  │      │ (중계/인증)   │      │ (FastAPI/Python)  │      │     │
└──────────┘      └─────────────┘      └──────────────────┘      └─────┘
```

- Spring Boot: 사용자 인증, 권한 관리, 프론트 API 제공
- 시뮬레이션 서버: 배치 알고리즘, 제약조건 검증, AI 평가
- RDS(PostgreSQL): 공유 DB (두 서버 모두 접근)

---

## 목차

1. [제품 조회](#1-제품-조회)
2. [도면 조회](#2-도면-조회)
3. [배치 그룹 관리](#3-배치-그룹-관리)
4. [제품 배치 (수동)](#4-제품-배치-수동)
5. [자동 배치](#5-자동-배치)
6. [배치 검증](#6-배치-검증)
7. [AI 배치 설명](#7-ai-배치-설명)
8. [레이아웃 생성 및 평가](#8-레이아웃-생성-및-평가)

---

## 1. 제품 조회

### 1-1. 카테고리 목록 조회

```
GET /api/categories
```

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| placeable_only | bool | N | true | 배치 가능 제품만 |
| product_type | string | N | - | "appliance" 또는 "furniture" |

**Response 200**
```json
[
  { "category": "냉장고", "count": 120 },
  { "category": "소파", "count": 85 }
]
```

---

### 1-2. 제품 목록 조회 (검색/필터/페이징)

```
GET /api/products
```

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| category | string | N | - | 카테고리 필터 |
| search | string | N | - | 제품명/모델 검색 |
| product_type | string | N | - | "appliance" / "furniture" |
| placeable_only | bool | N | true | 배치 가능 제품만 |
| page | int | N | 1 | 페이지 번호 |
| per_page | int | N | 50 | 페이지당 항목 (최대 200) |

**Response 200**
```json
[
  {
    "model": "RQ585B5V1S",
    "name": "LG 디오스 냉장고 500L",
    "category": "냉장고",
    "product_type": "appliance",
    "brand": "LG",
    "list_price": 2500000,
    "discount_rate": 15,
    "price": 2125000,
    "review_score": 4.8,
    "review_count": 342,
    "url": "https://...",
    "image_url": "https://...",
    "width_mm": 912,
    "height_mm": 1793,
    "depth_mm": 890,
    "is_placeable": true,
    "mount_type": "floor"
  }
]
```

> **PostgreSQL 전환 시 변경점**
> - PK: `model`(TEXT) → `product_id`(int8)
> - 컬럼 매핑: name→product_name, price→discount_price, list_price→original_price, review_count→review_cnt
> - is_placeable, mount_type → product_placement_info 테이블에서 JOIN

---

### 1-3. 제품 상세 조회

```
GET /api/products/{model}
```

| 파라미터 | 위치 | 타입 | 설명 |
|---------|------|------|------|
| model | path | string | 제품 모델 ID |

**Response 200**: 1-2와 동일한 ProductOut 객체

**Response 404**
```json
{ "detail": "Product not found" }
```

> **PostgreSQL 전환 시**: `GET /api/products/{product_id}` (int8)로 변경

---

## 2. 도면 조회

### 2-1. 도면 목록 조회

```
GET /api/floor-plans
```

**Response 200**
```json
[
  {
    "id": 1,
    "name": "25평 아파트",
    "category": "아파트",
    "total_area_m2": 82.5,
    "total_width_mm": 11000,
    "total_height_mm": 7500,
    "thumbnail_url": null,
    "rooms": [
      {
        "id": 1,
        "name": "거실",
        "room_type": "living",
        "x_mm": 0,
        "y_mm": 0,
        "width_mm": 5000,
        "height_mm": 4000,
        "is_placeable": true,
        "features": [
          {
            "type": "door",
            "wall": "south",
            "offset": 1500,
            "width": 900,
            "swing_dir": "inward"
          },
          {
            "type": "window",
            "wall": "north",
            "offset": 800,
            "width": 1800
          }
        ]
      }
    ]
  }
]
```

> **PostgreSQL 전환 시**
> - floor_plans → floor_plan 테이블
> - floor_plan_rooms → floor_plan_room 테이블
> - id → floor_plan_id / room_id

---

### 2-2. 도면 상세 조회

```
GET /api/floor-plans/{plan_id}
```

**Response 200**: 2-1과 동일 구조 (단건)

**Response 404**
```json
{ "detail": "Floor plan not found" }
```

---

### 2-3. 테스트 제품 세트 조회

```
GET /api/floor-plans/{plan_id}/test-set
```

도면 크기에 따라 랜덤 제품 세트를 반환합니다.

**Response 200**
```json
{
  "size": "medium",
  "models": ["RQ585B5V1S", "WM-F100", ...],
  "count": 12
}
```

| 도면 면적 | size | 설명 |
|----------|------|------|
| < 40m² | small | 소형 |
| < 70m² | medium | 중형 |
| ≥ 70m² | large | 대형 |

---

## 3. 배치 그룹 관리

> **현재**: user_sessions 테이블 (session)
> **PostgreSQL 전환 후**: placement_group 테이블 (user_id + floor_plan_id)

### 3-1. 배치 그룹 생성

```
POST /api/sessions
```

**Request Body**
```json
{
  "floor_plan_id": 1,
  "session_name": "배치안 1"
}
```

> **PostgreSQL 전환 시 추가**: `user_id` 필드 (Spring Boot에서 인증된 사용자 ID 전달)

**Response 200**
```json
{
  "id": 1,
  "floor_plan_id": 1,
  "session_name": "배치안 1",
  "floor_plan": { ... }
}
```

---

### 3-2. 배치 그룹 조회

```
GET /api/sessions/{session_id}
```

**Response 200**: 3-1과 동일 구조

---

### 3-3. 배치 그룹 삭제

```
DELETE /api/sessions/{session_id}
```

**Response 200**
```json
{ "ok": true }
```

> 삭제 시 하위 placement 전체 CASCADE 삭제

---

## 4. 제품 배치 (수동)

### 4-1. 방 내 배치 목록 조회

```
GET /api/sessions/{session_id}/rooms/{room_id}/placements
```

**Response 200**
```json
[
  {
    "id": 1,
    "session_id": 1,
    "room_id": 1,
    "model": "RQ585B5V1S",
    "x_mm": 100,
    "y_mm": 200,
    "rotation": 0,
    "is_valid": true,
    "violations": [],
    "product": {
      "model": "RQ585B5V1S",
      "name": "LG 디오스 냉장고 500L",
      "category": "냉장고",
      "width_mm": 912,
      "height_mm": 1793,
      "depth_mm": 890,
      "mount_type": "floor"
    }
  }
]
```

---

### 4-2. 제품 배치 (수동)

```
POST /api/sessions/{session_id}/rooms/{room_id}/placements
```

**Request Body**
```json
{
  "model": "RQ585B5V1S",
  "x_mm": 100,
  "y_mm": 200,
  "rotation": 0
}
```

> **PostgreSQL 전환 시**: `model` → `product_id` (int8)

**Response 200**: PlacementOut (4-1 참조)

**Response 400** (제약조건 위반 시)
```json
{
  "detail": "배치 제약조건 위반",
  "violations": [
    "냉장고가 방 경계를 벗어납니다",
    "소파와 겹칩니다 (거리: 50mm)"
  ]
}
```

**Response 404**
```json
{ "detail": "Product not found" }
```

---

### 4-3. 배치 위치 수정

```
PUT /api/sessions/{session_id}/rooms/{room_id}/placements/{placement_id}
```

**Request Body**
```json
{
  "x_mm": 500,
  "y_mm": 300,
  "rotation": 90
}
```

**Response 200**: PlacementOut
**Response 400**: 제약조건 위반

---

### 4-4. 배치 삭제

```
DELETE /api/sessions/{session_id}/rooms/{room_id}/placements/{placement_id}
```

**Response 200**
```json
{ "ok": true }
```

---

## 5. 자동 배치

### 5-1. 방 단위 자동 배치

```
POST /api/sessions/{session_id}/rooms/{room_id}/placements/auto-place
```

**Request Body**
```json
{
  "models": ["RQ585B5V1S", "WM-F100", "SF-300"]
}
```

**Response 200**
```json
{
  "placements": [
    {
      "id": 10,
      "room_id": 1,
      "model": "RQ585B5V1S",
      "x_mm": 50,
      "y_mm": 50,
      "rotation": 0,
      "is_valid": true,
      "violations": [],
      "product": { ... }
    }
  ],
  "warnings": [
    "SF-300: 배치할 공간이 부족합니다"
  ]
}
```

> 기존 배치를 **전부 삭제** 후 새로 배치합니다.

---

### 5-2. 도면 전체 자동 배치

```
POST /api/sessions/{session_id}/auto-place
```

**Request Body**
```json
{
  "models": ["RQ585B5V1S", "WM-F100", "SF-300", "BED-200"]
}
```

**Response 200**: 5-1과 동일 구조

> 모든 방에 걸쳐 제품을 자동 분배합니다.
> - 냉장고 → 주방
> - 침대 → 침실
> - 소파 → 거실 (방 유형 기반 분배)

---

## 6. 배치 검증

### 6-1. 방 내 전체 배치 재검증

```
POST /api/sessions/{session_id}/rooms/{room_id}/placements/validate
```

**Request Body**: 없음

**Response 200**
```json
[
  {
    "placement_id": 1,
    "is_valid": true,
    "violations": []
  },
  {
    "placement_id": 2,
    "is_valid": false,
    "violations": [
      "문 열림 공간과 겹칩니다 (남쪽 벽 문)"
    ]
  }
]
```

### 검증 규칙 목록

| 규칙 | 설명 |
|------|------|
| 경계 검사 | 제품이 방 경계 안에 있는지 |
| 겹침 검사 | 같은 mount_type 제품끼리 겹치는지 (wall↔floor는 허용) |
| 문 열림 공간 | 문 스윙 영역에 제품이 있는지 |
| 문 통행 구역 | 문 앞 800mm 통행 공간 확보 |
| 창문 여유 공간 | 창문 주변 300mm 버퍼 |
| 빌트인 설비 | 싱크대, 붙박이장 등 고정 설비 영역 |

### 카테고리별 여유 공간 (clearance)

| 카테고리 | 전면 | 후면 | 측면 |
|----------|------|------|------|
| 냉장고 | 800mm | 50mm | 50mm |
| 세탁기/건조기 | 700mm | 50mm | 30mm |
| 에어컨 | 1,500mm | 50mm | 300mm |
| TV | 2,000mm | 50mm | 100mm |
| 전기레인지 | 600mm | 0mm | 100mm |
| 식기세척기 | 700mm | 50mm | 0mm |
| 정수기 | 400mm | 50mm | 50mm |
| 의류관리기 | 600mm | 50mm | 50mm |

---

## 7. AI 배치 설명

### 7-1. 배치 설명 스트리밍 (SSE)

```
POST /api/sessions/{session_id}/explain
```

**Request Body**: 없음

**Response**: `text/event-stream` (Server-Sent Events)

```
data: {"text": "현재 배치를 분석해"}

data: {"text": "보겠습니다. 거실에"}

data: {"text": " 배치된 소파는..."}

data: [DONE]
```

> - OpenAI GPT-4o-mini 기반
> - 인테리어 전문가 관점의 배치 평가/설명
> - Spring Boot에서 SSE를 그대로 프론트에 중계하거나, 별도 처리 필요

---

## 8. 레이아웃 생성 및 평가

### 8-1. 다중 레이아웃 생성 + AI 평가

```
POST /api/sessions/{session_id}/generate-layouts
```

**Request Body**
```json
{
  "models": ["RQ585B5V1S", "WM-F100", "SF-300"]
}
```

**Response 200**
```json
{
  "layouts": [
    {
      "layout_id": 0,
      "description": "벽면 중심 배치",
      "placements": [
        {
          "room_id": 1,
          "model": "RQ585B5V1S",
          "x_mm": 50,
          "y_mm": 50,
          "rotation": 0
        }
      ],
      "metrics": {
        "space_usage": 0.35,
        "circulation": 0.82,
        "pair_satisfaction": 0.9,
        "wall_balance": 0.75,
        "center_openness": 0.88,
        "front_zone": 0.95
      }
    }
  ],
  "ai_evaluation": {
    "rankings": [
      {
        "layout_id": 0,
        "score": 92,
        "pros": ["동선이 넓다", "벽면 활용도가 높다"],
        "cons": ["TV와 소파 거리가 멀다"]
      }
    ],
    "recommendation": 0,
    "summary": "레이아웃 1이 공간 활용도와 동선 면에서 가장 우수합니다."
  }
}
```

> 5개의 서로 다른 전략으로 배치안을 생성 후 AI가 순위를 매깁니다.

---

### 8-2. 레이아웃 적용

```
POST /api/sessions/{session_id}/apply-layout
```

**Request Body**
```json
{
  "layout_id": 0,
  "placements": [
    {
      "room_id": 1,
      "model": "RQ585B5V1S",
      "x_mm": 50,
      "y_mm": 50,
      "rotation": 0
    }
  ]
}
```

**Response 200**
```json
{
  "ok": true,
  "placements": [ ... ]
}
```

> 기존 배치를 전부 삭제하고 선택한 레이아웃으로 교체합니다.

---

## PostgreSQL 전환 시 주요 변경 사항

### ID 체계 변경

| 현재 (SQLite) | 전환 후 (PostgreSQL) |
|--------------|---------------------|
| model (TEXT) PK | product_id (int8) PK |
| session (id) | placement_group (group_id + user_id) |

### 컬럼명 매핑

| 현재 | PostgreSQL |
|------|-----------|
| name | product_name |
| price | discount_price |
| list_price | original_price |
| review_count | review_cnt |

### 테이블 매핑

| 현재 (SQLite) | PostgreSQL |
|--------------|-----------|
| products | product + product_spec + product_placement_info (JOIN) |
| floor_plans | floor_plan |
| floor_plan_rooms | floor_plan_room |
| user_sessions | placement_group |
| placements | placement |

### Request/Response 필드 변경

```
# 현재
{ "model": "RQ585B5V1S" }

# 전환 후
{ "product_id": 1234 }
```

---

## 에러 응답 형식

| HTTP 상태 | 의미 | 응답 |
|-----------|------|------|
| 200 | 성공 | 정상 응답 |
| 400 | 요청 오류 / 제약조건 위반 | `{ "detail": "메시지", "violations": [...] }` |
| 404 | 리소스 없음 | `{ "detail": "... not found" }` |
| 422 | 유효성 검사 실패 | FastAPI 자동 생성 |
| 500 | 서버 오류 | `{ "detail": "Internal server error" }` |

---

## Spring Boot 연동 시 고려사항

1. **인증/인가**: Spring Boot에서 JWT 등으로 user_id를 확인 후, 시뮬레이션 서버에 user_id를 전달
2. **SSE 중계**: `/explain` 엔드포인트는 SSE 스트리밍 → Spring Boot에서 WebFlux나 SseEmitter로 중계
3. **타임아웃**: 자동 배치/AI 평가는 처리 시간이 길 수 있음 → Spring Boot 타임아웃 설정 필요
4. **DB 공유**: 두 서버 모두 같은 RDS를 바라봄 → 트랜잭션 충돌 주의 (읽기는 자유, 쓰기는 시뮬레이션 서버만)
5. **내부 통신**: Spring Boot → 시뮬레이션 서버는 private network (EC2 간 통신) 권장
