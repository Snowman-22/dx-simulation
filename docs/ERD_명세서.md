# ERD 명세서 (현재 RDS 기준)

> 작성일: 2026-03-22
> DB: PostgreSQL (RDS) — snowman-rds
> Schema: public
> 총 테이블: 19개 / 총 레코드: ~10,583건

---

## 테이블 관계도 (텍스트 ERD)

```
                         ┌─────────────────┐
                         │      user       │
                         │  (PK: user_id)  │
                         └────────┬────────┘
                  ┌───────┬──────┼───────┬──────────┐
                  │       │      │       │          │
                  ▼       ▼      ▼       ▼          ▼
            ┌──────┐ ┌──────┐ ┌────┐ ┌─────────┐ ┌──────────┐
            │ chat │ │ cart │ │ d2 │ │blueprint│ │  (향후)  │
            └──┬───┘ └──────┘ │sim │ └────┬────┘ │placement │
               │              └────┘      │      │ _group   │
               ▼                          ▼      └──────────┘
        ┌──────────────┐            ┌──────────┐
        │recommendation│            │   zone   │
        └──────────────┘            └──────────┘

              ┌───────────────────┐
              │     product       │
              │ (PK: product_id)  │
              └────────┬──────────┘
     ┌────────┬────────┼────────┬─────────────┬──────────────┐
     │        │        │        │             │              │
     ▼        ▼        ▼        ▼             ▼              ▼
┌────────┐┌───────┐┌──────┐┌──────────┐┌───────────┐┌────────────┐
│product ││subscr.││cart  ││electron. ││furniture  ││product_    │
│_spec   ││_price ││     ││_derived  ││_derived   ││review_emb. │
└────────┘└───────┘└──────┘└──────────┘└───────────┘└────────────┘
```

---

## 1. user

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **user_id** (PK) | bigint | NO | IDENTITY | 사용자 ID |
| user_name | varchar(255) | NO | | 사용자명 |
| email | varchar(255) | YES | | 이메일 (UNIQUE) |
| password | varchar(255) | NO | | 비밀번호 |
| gender | varchar(255) | YES | | 성별 (CHECK: 'M', 'F') |
| birth_date | varchar(255) | YES | | 생년월일 |
| phone | varchar(255) | YES | | 전화번호 |
| terms_accepted | boolean | NO | | 이용약관 동의 |
| privacy_accepted | boolean | NO | | 개인정보 동의 |
| create_date | timestamp(6) | NO | | 가입일시 |

- **행 수**: 2건
- **참조하는 테이블**: blueprint, cart, chat, d2_simulation

---

## 2. product

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **product_id** (PK) | bigint | NO | IDENTITY | 제품 ID |
| model_id | varchar(255) | NO | | 모델 식별자 |
| product_name | varchar(255) | NO | | 제품명 |
| category | varchar(255) | YES | | 대분류 (TV, 냉장고, 소파 등) |
| product_category | varchar(255) | YES | | 제품 유형 (가전/가구 구분) |
| brand | varchar(255) | YES | | 브랜드 |
| original_price | bigint | YES | | 정가 |
| discount_price | bigint | YES | | 할인가 |
| discount_rate | integer | YES | | 할인율 (%) |
| is_subscribe | boolean | YES | | 구독 가능 여부 |
| review_score | real | YES | | 리뷰 점수 |
| review_cnt | integer | YES | | 리뷰 수 |
| product_url | varchar(255) | YES | | 제품 URL |
| product_image_url | varchar(255) | YES | | 이미지 URL |

- **행 수**: 3,294건
- **참조하는 테이블**: product_spec, cart, d2_details, electronics_derived, furniture_derived, subscribe_price

---

## 3. product_spec

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **product_id** (PK, FK) | bigint | NO | | → product.product_id |
| width | double precision | YES | | 가로 (mm) |
| height | double precision | YES | | 높이 (mm) |
| depth | double precision | YES | | 깊이 (mm) |

- **행 수**: 3,294건 (product와 1:1)
- **FK**: product_id → product(product_id) ON UPDATE CASCADE ON DELETE CASCADE
- **비고**: 1단계에서 `is_placeable`, `mount_type` 컬럼 추가 예정

---

## 4. electronics_derived

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **product_id** (PK, FK) | bigint | NO | | → product.product_id |
| discount_rate | integer | YES | | 할인율 |
| energy_grade | varchar(20) | YES | | 에너지효율등급 |
| value_score | double precision | YES | | 가성비 점수 |
| popularity_score | double precision | YES | | 인기도 점수 |
| review_reliability | double precision | YES | | 리뷰 신뢰도 |
| has_ai | boolean | YES | | AI 기능 여부 |
| premium_line | varchar(50) | YES | | 프리미엄 라인 |
| color_series | varchar(50) | YES | | 색상 계열 |
| design_style | varchar(50) | YES | | 디자인 스타일 |
| size_grade | varchar(20) | YES | | 크기 등급 |
| recommended_area | double precision | YES | | 권장 평수 |
| single_score | integer | YES | | 1인가구 적합도 |
| large_family_score | integer | YES | | 대가족 적합도 |
| busy_worker_score | integer | YES | | 바쁜직장인 적합도 |
| pet_score | integer | YES | | 반려동물 적합도 |

- **행 수**: 811건
- **FK**: product_id → product(product_id) ON UPDATE CASCADE ON DELETE CASCADE

---

## 5. furniture_derived

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **product_id** (PK, FK) | bigint | NO | | → product.product_id |
| discount_rate | integer | YES | | 할인율 |
| material_grade | varchar(30) | YES | | 소재 등급 |
| is_eco_friendly | boolean | YES | | 친환경 여부 |
| maintenance_score | integer | YES | | 관리 용이성 |
| color_series | varchar(50) | YES | | 색상 계열 |
| design_style | varchar(50) | YES | | 디자인 스타일 |
| size_grade | varchar(20) | YES | | 크기 등급 |
| bed_size | varchar(20) | YES | | 침대 사이즈 |
| sofa_capacity | integer | YES | | 소파 인원수 |
| dining_capacity | integer | YES | | 식탁 인원수 |
| is_installation_included | boolean | YES | | 설치 포함 여부 |
| delivery_score | integer | YES | | 배송 편의 점수 |
| single_score | integer | YES | | 1인가구 적합도 |
| newlywed_score | integer | YES | | 신혼부부 적합도 |
| large_family_score | integer | YES | | 대가족 적합도 |
| space_saving_score | integer | YES | | 공간절약 적합도 |
| pet_score | integer | YES | | 반려동물 적합도 |
| image_vector | vector | YES | | 이미지 임베딩 벡터 |

- **행 수**: 2,483건
- **FK**: product_id → product(product_id) ON UPDATE CASCADE ON DELETE CASCADE

---

## 6. subscribe_price

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **subscribe_id** (PK) | bigint | NO | | 구독가 ID |
| product_id (FK) | bigint | NO | | → product.product_id |
| price | integer | YES | | 구독 월 가격 |
| contract_period_year | integer | YES | | 계약 기간 (년) |
| mandatory_period_year | integer | YES | | 의무 사용 기간 (년) |
| visit_service_type | varchar(100) | YES | | 방문 서비스 유형 |
| visit_cycle_month | integer | YES | | 방문 주기 (월) |

- **행 수**: 2,475건
- **FK**: product_id → product(product_id) ON UPDATE CASCADE ON DELETE CASCADE

---

## 7. product_tags

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **product_id** (PK) | integer | NO | | 제품 ID |
| tags | text[] | NO | | 태그 배열 |

- **행 수**: 732건

---

## 8. product_review_embeddings

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **product_id** (PK) | integer | NO | | 제품 ID |
| review_vector | vector | NO | | 리뷰 임베딩 벡터 |

- **행 수**: 732건

---

## 9. category_price_stats

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **id** (PK) | integer | NO | SERIAL | ID |
| category | varchar(100) | NO | | 카테고리명 (UNIQUE) |
| median_price | double precision | NO | | 중간 가격 |

- **행 수**: 33건

---

## 10. category_stats

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **id** (PK) | integer | NO | SERIAL | ID |
| category | varchar(100) | NO | | 카테고리명 |
| column_name | varchar(100) | NO | | 통계 컬럼명 |
| median_value | double precision | NO | | 중간값 |

- **행 수**: 6건
- **UNIQUE**: (category, column_name)

---

## 11. chat

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **chat_id** (PK) | bigint | NO | | 채팅 ID |
| user_id (FK) | bigint | YES | | → user.user_id |
| blueprint_id (FK) | bigint | YES | | → blueprint.blueprint_id |
| starter_package_id (FK) | bigint | NO | | → starter_package.starter_package_id |
| chat_title | varchar(255) | YES | | 채팅 제목 |
| chat_conv_id | varchar(255) | YES | | 대화 ID (UNIQUE) |
| is_select_blueprint | boolean | NO | | 도면 선택 여부 |
| start_date | timestamp | NO | | 시작 시간 |
| end_date | timestamp | YES | | 종료 시간 |

- **행 수**: 11건
- **FK**: user_id → user, blueprint_id → blueprint, starter_package_id → starter_package

---

## 12. recommendation

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **recommendation_id** (PK) | bigint | NO | | 추천 ID |
| chat_id (FK) | bigint | NO | | → chat.chat_id |
| products | varchar(255) | YES | | 추천 제품 목록 |
| reason | varchar(255) | YES | | 추천 사유 |
| is_selected | boolean | NO | false | 선택 여부 |

- **행 수**: 0건

---

## 13. starter_package

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **starter_package_id** (PK) | bigint | NO | | 패키지 ID |
| starter_package_name | varchar(255) | YES | | 패키지명 |
| is_use | boolean | YES | | 사용 여부 |

- **행 수**: 6건

---

## 14. cart

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **cart_id** (PK) | bigint | NO | | 장바구니 ID |
| user_id (FK) | bigint | NO | | → user.user_id |
| product_id (FK) | bigint | NO | | → product.product_id |
| quantity | integer | NO | | 수량 |
| is_delete | boolean | NO | | 삭제 여부 |
| create_date | timestamp | NO | | 생성 일시 |

- **행 수**: 0건

---

## 15. blueprint

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **blueprint_id** (PK) | bigint | NO | | 도면 ID |
| user_id (FK) | bigint | NO | | → user.user_id |
| zone_id (FK) | bigint | NO | | → zone.zone_id |
| blueprint_title | varchar(255) | NO | | 도면 제목 |
| description | varchar(255) | YES | | 설명 |
| blueprint_image_url | varchar(255) | YES | | 이미지 URL |
| width | real | YES | | 가로 (mm) |
| depth | real | YES | | 세로 (mm) |
| ceiling_height | real | YES | | 천장 높이 |
| area_n2 | real | YES | | 면적 (m2) |
| square_footage | real | NO | | 평수 |
| room_count | integer | YES | | 방 개수 |

- **행 수**: 0건
- **FK**: user_id → user, zone_id → zone

---

## 16. zone

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **zone_id** (PK) | bigint | NO | | 영역 ID |
| blueprint_id (FK) | bigint | NO | | → blueprint.blueprint_id |
| zone_type | varchar(255) | NO | | 영역 유형 |
| width | real | NO | | 가로 |
| height | real | NO | | 높이 |

- **행 수**: 0건
- **FK**: blueprint_id → blueprint

---

## 17. d2_simulation

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **layout_2d_id** (PK) | bigint | NO | | 2D 레이아웃 ID |
| user_id (FK) | bigint | NO | | → user.user_id |
| layout_2d_img_url | varchar(255) | NO | | 2D 이미지 URL |

- **행 수**: 0건

---

## 18. d2_details

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **d2_details_id** (PK) | bigint | NO | | 상세 ID |
| **layout_2d_id** (PK, FK) | bigint | NO | | → d2_simulation.layout_2d_id |
| **product_id** (PK, FK) | bigint | NO | | → product.product_id |
| corr_x | real | NO | | X 좌표 |
| corr_y | real | NO | | Y 좌표 |
| rotation | real | YES | | 회전 각도 |

- **행 수**: 0건
- **복합 PK**: (d2_details_id, layout_2d_id, product_id)

---

## 19. d3_simulation

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|------|------|------|--------|------|
| **layout_3d_id** (PK) | bigint | NO | | 3D 레이아웃 ID |
| layout_2d_id (FK) | bigint | NO | | → d2_simulation.layout_2d_id |
| layout_3d_img_url | varchar(255) | NO | | 3D 이미지 URL |

- **행 수**: 0건

---

## FK 관계 요약

| FK | 원본 테이블 | 컬럼 | 참조 테이블 | 참조 컬럼 |
|----|-------------|------|-------------|-----------|
| 1 | product_spec | product_id | product | product_id |
| 2 | electronics_derived | product_id | product | product_id |
| 3 | furniture_derived | product_id | product | product_id |
| 4 | subscribe_price | product_id | product | product_id |
| 5 | cart | product_id | product | product_id |
| 6 | cart | user_id | user | user_id |
| 7 | d2_details | product_id | product | product_id |
| 8 | d2_details | layout_2d_id | d2_simulation | layout_2d_id |
| 9 | d2_simulation | user_id | user | user_id |
| 10 | d3_simulation | layout_2d_id | d2_simulation | layout_2d_id |
| 11 | blueprint | user_id | user | user_id |
| 12 | blueprint | zone_id | zone | zone_id |
| 13 | zone | blueprint_id | blueprint | blueprint_id |
| 14 | chat | user_id | user | user_id |
| 15 | chat | blueprint_id | blueprint | blueprint_id |
| 16 | chat | starter_package_id | starter_package | starter_package_id |
| 17 | recommendation | chat_id | chat | chat_id |

---

## 데이터 현황

| 테이블 | 행 수 | 크기 | 비고 |
|--------|-------|------|------|
| product | 3,294 | 1,040 kB | 가전 811 + 가구 2,483 |
| product_spec | 3,294 | 320 kB | product와 1:1 |
| electronics_derived | 811 | 184 kB | 가전 파생 속성 |
| furniture_derived | 2,483 | 7,320 kB | 가구 파생 속성 (image_vector 포함) |
| subscribe_price | 2,475 | 296 kB | 구독가 정보 |
| product_review_embeddings | 732 | 3,104 kB | 리뷰 벡터 |
| product_tags | 732 | 208 kB | 제품 태그 |
| category_price_stats | 33 | 40 kB | 카테고리별 가격 통계 |
| category_stats | 6 | 40 kB | 카테고리 통계 |
| chat | 11 | 48 kB | 채팅 세션 |
| starter_package | 6 | 24 kB | 스타터 패키지 |
| user | 2 | 48 kB | 사용자 |
| recommendation | 0 | 16 kB | 추천 |
| cart | 0 | 8 kB | 장바구니 |
| blueprint | 0 | 16 kB | 도면 |
| zone | 0 | 8 kB | 영역 |
| d2_simulation | 0 | 8 kB | 2D 시뮬레이션 |
| d2_details | 0 | 8 kB | 2D 배치 상세 |
| d3_simulation | 0 | 8 kB | 3D 시뮬레이션 |

---

## 도메인 그룹 분류

### A. 제품 (Product)
`product` → `product_spec` / `electronics_derived` / `furniture_derived` / `subscribe_price` / `product_tags` / `product_review_embeddings`

### B. 사용자 (User)
`user` → `cart` / `chat` / `blueprint` / `d2_simulation`

### C. 추천/채팅 (Recommendation)
`starter_package` → `chat` → `recommendation`

### D. 도면/시뮬레이션 (Simulation)
`blueprint` ↔ `zone`, `chat` → `blueprint`
`d2_simulation` → `d2_details` → `d3_simulation`

### E. 통계 (Stats)
`category_price_stats`, `category_stats` (독립)

---

## 1단계 추가 예정 (미실행)

### product_spec 컬럼 추가
- `is_placeable` (bool, NOT NULL, DEFAULT true)
- `mount_type` (varchar(20), NOT NULL, DEFAULT 'floor', CHECK: 'floor'/'wall')

### 신규 테이블 4개
- `floor_plan` — 도면 정보
- `floor_plan_room` — 도면 내 방 정보
- `placement_group` — 배치 그룹 (user + floor_plan)
- `placement` — 제품 배치 좌표
