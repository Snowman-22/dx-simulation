"""
AI auto-placement engine with advanced rule-based scoring.
- Category-specific profiles (clearance, wall affinity, feature preferences)
- Product relationship rules (pairing, facing, separation)
- Functional zone scoring (kitchen work triangle, living viewing zone)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from services.constraint_validator import (
    get_footprint, get_rect, rects_overlap,
    get_door_swing_rect, get_door_passage_zone, get_door_entry_zone, get_window_zone,
    get_fixture_zone, validate_single_placement,
)

# 렌더러와 동일한 최소 표시 치수 (canvas_renderer.js MIN_DIM과 일치)
# 너무 얇은 제품(TV 30mm 등)이 벽을 넘어 표시되는 것을 방지
MIN_DISPLAY_DIM = 250


def get_display_footprint(width_mm: float, depth_mm: float, rotation: int, mount_type: str = "floor") -> tuple[float, float]:
    """렌더링에서 실제 보이는 크기와 동일한 footprint를 반환."""
    fw, fd = get_footprint(width_mm, depth_mm, rotation)
    if mount_type == "wall":
        # 벽면 제품: 가로는 실제 크기, 세로(깊이)는 얇게 표시
        return (max(fw, 200), min(fd, 120))
    return (max(fw, MIN_DISPLAY_DIM), max(fd, MIN_DISPLAY_DIM))


@dataclass
class PlacementProfile:
    wall_affinity: str = "required"       # "required" | "preferred" | "none"
    preferred_walls: list[str] | None = None
    clearance_front_mm: float = 300
    clearance_back_mm: float = 50
    clearance_sides_mm: float = 50
    near_features: list[str] = field(default_factory=list)
    near_feature_max_mm: float = 1500
    avoid_features: list[str] = field(default_factory=list)
    avoid_near_categories: list[str] = field(default_factory=list)  # keep away from these
    priority: int = 10


# ═══════════════════════════════════════════════════
# 1. CATEGORY PROFILES
# ═══════════════════════════════════════════════════

PROFILES: dict[str, PlacementProfile] = {
    # ── Appliances ──
    "냉장고": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=900,       # 냉장고 문 열림 + 통행 공간
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=50,
        near_features=["water_hookup"],
        avoid_features=["window"],
        avoid_near_categories=["전기레인지", "오븐", "전자레인지"],  # 열원과 분리
        priority=1,
    ),
    "세탁기": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=800,       # 드럼 문 열림 + 빨래 꺼내는 공간
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=30,
        near_features=["water_hookup"],
        near_feature_max_mm=1500,
        priority=2,
    ),
    "워시타워": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=800,
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=30,
        near_features=["water_hookup"],
        near_feature_max_mm=1500,
        priority=2,
    ),
    "워시콤보": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=800,
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=30,
        near_features=["water_hookup"],
        near_feature_max_mm=1500,
        priority=2,
    ),
    "의류건조기": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=800,
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=30,
        near_features=["water_hookup"],
        priority=3,
    ),
    "전기레인지": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=700,       # 조리 공간
        clearance_back_mm=0,
        clearance_sides_mm=150,       # 양옆 안전 거리
        near_features=["gas_line"],
        avoid_features=["window"],    # 커튼 화재 위험
        avoid_near_categories=["냉장고"],  # 열원 분리
        priority=2,
    ),
    "TV": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=2500,      # 최소 시청 거리
        clearance_back_mm=0,          # 벽걸이/벽 밀착
        clearance_sides_mm=150,
        avoid_features=["window"],    # 빛반사
        priority=2,                   # 소파보다 먼저 배치 (소파가 TV 기준으로 마주봄)
    ),
    "스탠바이미": PlacementProfile(
        wall_affinity="preferred",
        clearance_front_mm=1500,
        clearance_back_mm=0,
        clearance_sides_mm=100,
        priority=8,
    ),
    "에어컨": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=1500,      # 냉기 흐름 공간
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=300,       # 양옆 공기 순환
        near_features=["window"],     # 실외기 연결
        priority=5,
    ),
    "에어컨_wall": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=0,         # 벽걸이: 바닥 앞 공간 불필요
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=200,       # 양옆 최소 여유
        near_features=["window"],     # 실외기 연결
        priority=5,
    ),
    "식기세척기": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=800,       # 문 열림 + 그릇 꺼내기
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=0,
        near_features=["water_hookup"],
        priority=6,
    ),
    "의류관리기": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=700,       # 문 열림
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=50,
        priority=7,
    ),
    "오븐": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=500,
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=100,       # 방열
        avoid_features=["window"],
        priority=9,
    ),
    "전자레인지": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=500,
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=100,       # 방열
        avoid_features=["window"],
        priority=9,
    ),
    "정수기": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=500,       # 물받기 공간
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=50,
        near_features=["water_hookup"],
        priority=6,
    ),

    # ── Furniture ──
    "침대": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=700,       # 침대 앞 통행
        clearance_back_mm=0,          # 헤드보드 벽 밀착
        clearance_sides_mm=500,       # 한쪽 통행 + 협탁 공간
        avoid_features=["door", "window"],  # 머리맡에 문/창문 피함
        priority=1,
    ),
    "소파": PlacementProfile(
        wall_affinity="preferred",
        clearance_front_mm=600,       # 커피테이블 + 통행
        clearance_back_mm=0,          # 벽 밀착
        clearance_sides_mm=50,
        priority=3,                   # TV 바로 다음에 배치 (TV 기준 마주보기)
    ),
    "식탁·테이블": PlacementProfile(
        wall_affinity="none",
        clearance_front_mm=900,       # 의자 + 뒤로 빠지는 공간
        clearance_back_mm=900,
        clearance_sides_mm=900,
        priority=1,
    ),
    "옷장·행거": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=800,       # 문 열림 + 옷 꺼내기
        clearance_back_mm=0,
        clearance_sides_mm=0,
        avoid_features=["window"],    # 창문 앞에 옷장 놓지 않음
        priority=2,
    ),
    "책상": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=800,       # 의자 + 통행
        clearance_back_mm=0,
        clearance_sides_mm=100,
        near_features=["window"],     # 자연광 선호
        priority=3,
    ),
    "책장·수납장": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=600,       # 책 꺼내기
        clearance_back_mm=0,
        clearance_sides_mm=0,
        priority=4,
    ),
    "화장대·콘솔": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=700,       # 의자 + 사용 공간
        clearance_back_mm=0,
        clearance_sides_mm=50,
        near_features=["window"],     # 자연광 (화장 시 필요)
        priority=5,
    ),
    "TV거실장": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=2500,      # TV 시청 거리와 동일
        clearance_back_mm=0,
        clearance_sides_mm=100,
        avoid_features=["window"],
        priority=2,
    ),
    "선반": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=500,
        clearance_back_mm=0,
        clearance_sides_mm=0,
        priority=7,
    ),
    "의자": PlacementProfile(
        wall_affinity="none",
        clearance_front_mm=400,
        clearance_back_mm=600,        # 의자 뒤로 빠지는 공간
        clearance_sides_mm=100,
        priority=8,
    ),
    "유아동가구": PlacementProfile(
        wall_affinity="required",
        clearance_front_mm=600,
        clearance_back_mm=0,
        clearance_sides_mm=100,
        avoid_features=["window"],    # 아이 안전
        priority=6,
    ),
}

DEFAULT_PROFILE = PlacementProfile(
    wall_affinity="preferred",
    clearance_front_mm=300, clearance_back_mm=50, clearance_sides_mm=50,
    priority=10,
)


# ═══════════════════════════════════════════════════
# 2. PRODUCT RELATIONSHIP RULES
# ═══════════════════════════════════════════════════

# (category_a, category_b) → rule
# "adjacent": must be side by side (< 200mm gap)
# "nearby":   should be close (< 1000mm)
# "facing":   should be on opposite walls
# "apart":    should be at least Nmm apart

PAIR_RULES: list[dict] = [
    # ── 반드시 붙어있어야 함 ──
    {"a": "세탁기", "b": "의류건조기", "rule": "adjacent", "bonus": 400,
     "reason": "세탁기와 건조기는 나란히 배치"},
    {"a": "워시타워", "b": "의류건조기", "rule": "adjacent", "bonus": 400,
     "reason": "워시타워와 건조기는 나란히 배치"},

    # ── 마주보기 (반대편 벽) ──
    {"a": "TV", "b": "소파", "rule": "facing", "bonus": 1000,
     "reason": "TV와 소파는 마주보기 배치"},
    {"a": "TV거실장", "b": "소파", "rule": "facing", "bonus": 1000,
     "reason": "TV거실장과 소파는 마주보기 배치"},

    # ── 가까이 있어야 함 ──
    {"a": "TV", "b": "TV거실장", "rule": "nearby", "dist": 500, "bonus": 350,
     "reason": "TV와 TV거실장은 같은 위치"},
    {"a": "책상", "b": "의자", "rule": "adjacent", "bonus": 500,
     "reason": "책상 앞에 의자 밀착"},
    {"a": "식탁·테이블", "b": "의자", "rule": "adjacent", "bonus": 500,
     "reason": "식탁에 의자 밀착"},
    {"a": "화장대·콘솔", "b": "의자", "rule": "adjacent", "bonus": 500,
     "reason": "화장대 앞에 의자 밀착"},
    {"a": "냉장고", "b": "전기레인지", "rule": "nearby", "dist": 2500, "bonus": 100,
     "reason": "주방 작업 동선 (냉장고↔레인지)"},
    {"a": "냉장고", "b": "식기세척기", "rule": "nearby", "dist": 2000, "bonus": 100,
     "reason": "주방 작업 동선 (냉장고↔식기세척기)"},

    # ── 떨어져 있어야 함 ──
    {"a": "냉장고", "b": "오븐", "rule": "adjacent", "bonus": 400,
     "reason": "전자레인지는 냉장고 옆에 밀착 배치"},
    {"a": "냉장고", "b": "전기레인지", "rule": "apart", "dist": 500, "penalty": -300,
     "reason": "냉장고와 레인지 최소 50cm 이격 (열 영향)"},
    {"a": "침대", "b": "TV", "rule": "apart", "dist": 2000, "penalty": -100,
     "reason": "침대에서 TV 최소 시청 거리"},
    {"a": "에어컨", "b": "침대", "rule": "apart", "dist": 1500, "penalty": -200,
     "reason": "에어컨 직접 바람이 침대에 닿지 않도록"},
]


# ═══════════════════════════════════════════════════
# 3. FRONT ZONE EXCLUSION (제품 앞 금지 구역)
# ═══════════════════════════════════════════════════
# 특정 제품의 전면 영역에 다른 제품이 오면 안 됨

FRONT_ZONE_RULES: dict[str, dict] = {
    "TV":        {"depth": 2500, "blocked": True, "reason": "TV 시청 영역"},
    "TV거실장":   {"depth": 2500, "blocked": True, "reason": "TV거실장 시청 영역"},
    "냉장고":     {"depth": 900,  "blocked": True, "reason": "냉장고 문 열림 공간"},
    "세탁기":     {"depth": 800,  "blocked": True, "reason": "세탁기 도어 개폐 공간"},
    "워시타워":   {"depth": 800,  "blocked": True, "reason": "워시타워 도어 개폐 공간"},
    "워시콤보":   {"depth": 800,  "blocked": True, "reason": "워시콤보 도어 개폐 공간"},
    "의류건조기": {"depth": 800,  "blocked": True, "reason": "건조기 도어 개폐 공간"},
    "식기세척기": {"depth": 800,  "blocked": True, "reason": "식기세척기 도어 개폐 공간"},
    "옷장·행거":  {"depth": 800,  "blocked": True, "reason": "옷장 문 열림 공간"},
    "에어컨":     {"depth": 1500, "blocked": True, "reason": "에어컨 냉기 흐름 공간"},
    "전기레인지": {"depth": 700,  "blocked": True, "reason": "조리 공간"},
    "침대":       {"depth": 700,  "blocked": True, "reason": "침대 앞 통행로"},
}


# ═══════════════════════════════════════════════════
# 3b. WEIGHT PRESETS & STRATEGIES
# ═══════════════════════════════════════════════════

WEIGHT_PRESETS = {
    "default": {
        "corner_bonus": 1.0, "door_penalty": 1.0, "near_feature": 1.0,
        "pair_rule": 1.0, "front_zone": 1.0, "center_bonus": 1.0, "spacing": 1.0,
    },
    "circulation": {
        "corner_bonus": 1.5, "door_penalty": 2.0, "near_feature": 0.8,
        "pair_rule": 0.7, "front_zone": 1.5, "center_bonus": 1.3, "spacing": 1.5,
    },
    "compact": {
        "corner_bonus": 2.0, "door_penalty": 0.8, "near_feature": 1.2,
        "pair_rule": 1.5, "front_zone": 0.7, "center_bonus": 0.5, "spacing": 0.5,
    },
    "aesthetic": {
        "corner_bonus": 0.8, "door_penalty": 1.0, "near_feature": 0.7,
        "pair_rule": 2.0, "front_zone": 1.0, "center_bonus": 1.5, "spacing": 1.2,
    },
    "open": {
        "corner_bonus": 2.0, "door_penalty": 1.0, "near_feature": 1.0,
        "pair_rule": 0.8, "front_zone": 0.5, "center_bonus": 0.3, "spacing": 0.8,
    },
}

STRATEGIES = [
    {"name": "기본 배치", "desc": "표준 우선순위 기반 배치", "order": "default", "weights": "default", "wall_start": "north", "diversity_k": 1},
    {"name": "대형가구 우선", "desc": "큰 가구를 먼저 배치하여 안정적 구조", "order": "size_desc", "weights": "default", "wall_start": "east", "diversity_k": 3},
    {"name": "동선 최적화", "desc": "문/통행로 중심으로 여유 공간 확보", "order": "appliance_first", "weights": "circulation", "wall_start": "south", "diversity_k": 3},
    {"name": "공간 활용 극대화", "desc": "코너와 벽면을 최대한 활용", "order": "size_asc", "weights": "compact", "wall_start": "west", "diversity_k": 3},
    {"name": "개방감 중심", "desc": "방 중앙 공간을 최대한 확보", "order": "furniture_first", "weights": "open", "wall_start": "south", "diversity_k": 3},
]


# ═══════════════════════════════════════════════════
# 4. GEOMETRY HELPERS
# ═══════════════════════════════════════════════════

def _range_float(start: float, end: float, step: float) -> list[float]:
    result = []
    val = start
    while val <= end + 0.1:
        result.append(val)
        val += step
    return result


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


def _feature_position(feat, room_w: float, room_h: float) -> tuple[float, float]:
    wall = feat["wall"]
    offset = feat.get("offset", feat.get("offset_mm", 0))
    fw = feat.get("width", feat.get("width_mm", 0))
    center_along = offset + fw / 2

    if wall == "north":
        return (center_along, 0)
    elif wall == "south":
        return (center_along, room_h)
    elif wall == "west":
        return (0, center_along)
    else:
        return (room_w, center_along)


def _get_wall_of_position(cx, cy, room_w, room_h) -> str:
    """Determine which wall a position is closest to."""
    dists = {
        "north": cy,
        "south": room_h - cy,
        "west": cx,
        "east": room_w - cx,
    }
    return min(dists, key=dists.get)


def _opposite_wall(wall: str) -> str:
    return {"north": "south", "south": "north", "east": "west", "west": "east"}.get(wall, "")


# ═══════════════════════════════════════════════════
# 5. CANDIDATE GENERATION
# ═══════════════════════════════════════════════════

def _get_wall_candidates(
    product_w: float, product_d: float, rotation: int,
    wall: str, room_w: float, room_h: float,
    profile: PlacementProfile,
) -> list[dict]:
    # 표시 크기 기준으로 후보 생성 (벽 넘어가는 것 방지)
    fw, fd = get_display_footprint(product_w, product_d, rotation)
    candidates = []
    step = 100

    if wall == "north":
        y = profile.clearance_back_mm + fd / 2
        for x_s in _range_float(fw / 2, room_w - fw / 2, step):
            candidates.append({"x": x_s, "y": y, "wall": wall})
    elif wall == "south":
        y = room_h - profile.clearance_back_mm - fd / 2
        for x_s in _range_float(fw / 2, room_w - fw / 2, step):
            candidates.append({"x": x_s, "y": y, "wall": wall})
    elif wall == "west":
        x = profile.clearance_back_mm + fw / 2
        for y_s in _range_float(fd / 2, room_h - fd / 2, step):
            candidates.append({"x": x, "y": y_s, "wall": wall})
    elif wall == "east":
        x = room_w - profile.clearance_back_mm - fw / 2
        for y_s in _range_float(fd / 2, room_h - fd / 2, step):
            candidates.append({"x": x, "y": y_s, "wall": wall})

    return candidates


# ═══════════════════════════════════════════════════
# 6. SCORING
# ═══════════════════════════════════════════════════

def _score_candidate(
    cx: float, cy: float, rotation: int,
    product_w: float, product_d: float,
    category: str,
    profile: PlacementProfile,
    room_w: float, room_h: float,
    features: list, occupied: list[tuple],
    placed_items: list[dict],
    wall: str,
    mount_type: str = "floor",
    weights: dict | None = None,
    open_walls: set | None = None,
) -> float:
    w = weights or WEIGHT_PRESETS["default"]
    is_wall_mount = mount_type == "wall"
    # 표시 크기 기준으로 경계+겹침 체크 (렌더링 시 벽 넘어가는 것 방지)
    fw, fd = get_display_footprint(product_w, product_d, rotation, mount_type)
    rect = get_rect(cx, cy, fw, fd)

    # ── DISQUALIFY ──
    if rect[0] < -1 or rect[1] < -1 or rect[2] > room_w + 1 or rect[3] > room_h + 1:
        return float("-inf")

    for orect in occupied:
        if rects_overlap(rect, orect):
            return float("-inf")

    # 투명벽(open_walls) 통행 구역 → 실격
    open_walls = open_walls or set()
    open_margin = 300
    for wall in open_walls:
        if wall == "north":
            oz = (0, 0, room_w, open_margin)
        elif wall == "south":
            oz = (0, room_h - open_margin, room_w, room_h)
        elif wall == "west":
            oz = (0, 0, open_margin, room_h)
        elif wall == "east":
            oz = (room_w - open_margin, 0, room_w, room_h)
        else:
            continue
        if rects_overlap(rect, oz):
            return float("-inf")

    # 빌트인 설비 영역 충돌 → 실격
    for feat in features:
        if feat.get("type") == "fixture":
            fix_zone = get_fixture_zone(feat, room_w, room_h)
            if rects_overlap(rect, fix_zone):
                return float("-inf")

    score = 0.0

    # ── NATURAL ORIENTATION BONUS ──
    # 넓은 면(width)이 벽을 따라가는 것이 자연스러움
    # north/south 벽: fw(가로) > fd(세로)이면 자연스러움
    # east/west 벽: fd(세로) > fw(가로)이면 자연스러움
    actual_fw, actual_fd = get_footprint(product_w, product_d, rotation)
    if wall in ("north", "south"):
        if actual_fw >= actual_fd:
            score += 250  # 가로가 넓음 → 자연스러운 배치
        else:
            score -= 200  # 세로로 세워짐 → 부자연스러움
    elif wall in ("east", "west"):
        if actual_fd >= actual_fw:
            score += 250
        else:
            score -= 200

    # ── DOOR PENALTY (벽면 제품은 벽 상단 설치이므로 문 검사 면제) ──
    if not is_wall_mount:
        for feat in features:
            if feat.get("type") == "door":
                # 문 열림 아크 체크
                door_rect = get_door_swing_rect(feat, room_w, room_h)
                if rects_overlap(rect, door_rect):
                    return float("-inf")  # 문 열림 공간은 즉시 탈락

                # 문 통행 구역 체크 (문 앞 800mm, 양옆 200mm 여유)
                passage_rect = get_door_passage_zone(feat, room_w, room_h)
                if rects_overlap(rect, passage_rect):
                    return float("-inf")  # 문 통행 구역도 즉시 탈락

                # 문 진입 구역 체크 (반대쪽 접근 방향)
                entry_rect = get_door_entry_zone(feat, room_w, room_h)
                if rects_overlap(rect, entry_rect):
                    return float("-inf")  # 문 진입 구역도 즉시 탈락

                # 문 근처 추가 감점 (더 넓은 범위)
                fx, fy = _feature_position(feat, room_w, room_h)
                dist = _distance(cx, cy, fx, fy)
                if dist < 1200:
                    score -= 600 * w["door_penalty"]

    # ── WINDOW PENALTY (벽면 제품은 창문 위에 설치 가능 → 면제, 오히려 창문 근처 선호) ──
    if is_wall_mount:
        for feat in features:
            if feat.get("type") == "window":
                fx, fy = _feature_position(feat, room_w, room_h)
                dist = _distance(cx, cy, fx, fy)
                if dist < 2000:
                    score += 200 * (1 - dist / 2000)  # 창문 근처 보너스 (실외기 연결)
    else:
        for feat in features:
            if feat.get("type") == "window":
                win_zone = get_window_zone(feat, room_w, room_h)
                if rects_overlap(rect, win_zone):
                    if "window" in profile.avoid_features:
                        score -= 1500
                    else:
                        score -= 800

    # ── NEAR FEATURE BONUS ──
    for feat_type in profile.near_features:
        if feat_type in ("window", "door"):
            # Handle window/door proximity specially
            matching = [f for f in features if f.get("type") == feat_type]
            for f in matching:
                fx, fy = _feature_position(f, room_w, room_h)
                dist = _distance(cx, cy, fx, fy)
                if dist < 2000:
                    score += 200 * (1 - dist / 2000) * w["near_feature"]
            continue
        matching = [f for f in features if f.get("type") == feat_type]
        if matching:
            min_dist = min(
                _distance(cx, cy, *_feature_position(f, room_w, room_h))
                for f in matching
            )
            if min_dist < profile.near_feature_max_mm:
                score += 250 * (1 - min_dist / profile.near_feature_max_mm) * w["near_feature"]
            else:
                score -= 200 * w["near_feature"]

    # ── AVOID FEATURE PENALTY ──
    for avoid_type in profile.avoid_features:
        if avoid_type in ("window",):
            continue  # handled above
        matching = [f for f in features if f.get("type") == avoid_type]
        for f in matching:
            fx, fy = _feature_position(f, room_w, room_h)
            dist = _distance(cx, cy, fx, fy)
            if dist < 600:
                score -= 400

    # ── CORNER BONUS (카테고리별 차등) ──
    corner_threshold = 500
    near_left = cx - fw / 2 < corner_threshold
    near_right = room_w - (cx + fw / 2) < corner_threshold
    near_top = cy - fd / 2 < corner_threshold
    near_bottom = room_h - (cy + fd / 2) < corner_threshold
    if (near_left or near_right) and (near_top or near_bottom):
        # 대형가전/대형가구: 높은 코너 보너스
        CORNER_HIGH = {"냉장고", "옷장·행거", "침대", "소파"}
        # 중형: 기본 코너 보너스
        CORNER_MID = {"세탁기", "워시타워", "워시콤보", "의류건조기", "책장·수납장", "오븐", "전자레인지"}
        # 코너 회피 (벽 중앙이 자연스러운 제품)
        CORNER_AVOID = {"에어컨", "TV", "TV거실장", "의류관리기"}

        if category in CORNER_HIGH:
            score += 500 * w["corner_bonus"]
        elif category in CORNER_MID:
            score += 200 * w["corner_bonus"]
        elif category in CORNER_AVOID:
            score -= 100 * w["corner_bonus"]  # 코너 배치 감점
        else:
            score += 100 * w["corner_bonus"]  # 기본

    # ── SPACING FROM OTHER PRODUCTS (벽면 제품은 같은 레이어끼리만) ──
    if not is_wall_mount:
        for orect in occupied:
            ocx = (orect[0] + orect[2]) / 2
            ocy = (orect[1] + orect[3]) / 2
            dist = _distance(cx, cy, ocx, ocy)
            if dist < 200:
                score -= 200 * w["spacing"]       # too close
            elif dist < 500:
                score -= 50 * w["spacing"]
            elif 800 < dist < 1500:
                score += 30 * w["spacing"]        # comfortable spacing

    # ── FRONT ZONE BLOCKING (벽면 제품은 바닥 전면 구역에 영향 없음) ──
    if not is_wall_mount:
        # Check if this position blocks the front zone of already-placed items
        for item in placed_items:
            if item.get("mount_type", "floor") == "wall":
                continue  # 벽면 제품의 front zone은 무시
            fz = FRONT_ZONE_RULES.get(item["category"])
            if not fz:
                continue
            ifw, ifd = get_footprint(item["pw"], item["pd"], item["rotation"])
            item_wall = _get_wall_of_position(item["x"], item["y"], room_w, room_h)

            # 소파는 TV/TV거실장 전면 금지 깊이를 1000mm로 축소 (시청 위치)
            effective_depth = fz["depth"]
            if category == "소파" and item["category"] in ("TV", "TV거실장"):
                effective_depth = 1000

            front_rect = _get_front_zone_rect(
                item["x"], item["y"], ifw, ifd, item_wall, effective_depth
            )
            if front_rect and rects_overlap(rect, front_rect):
                score -= 600 * w["front_zone"]

        # Also check if already-placed items would block THIS product's front zone
        my_fz = FRONT_ZONE_RULES.get(category)
        if my_fz:
            my_wall = wall if wall != "center" else _get_wall_of_position(cx, cy, room_w, room_h)
            my_front = _get_front_zone_rect(cx, cy, fw, fd, my_wall, my_fz["depth"])
            if my_front:
                for orect in occupied:
                    if rects_overlap(my_front, orect):
                        score -= 600 * w["front_zone"]

    # ── TV WALL-CENTER BONUS ──
    # TV는 벽 중앙에 배치되는 것이 자연스러움
    if category in ("TV", "TV거실장"):
        if wall in ("north", "south"):
            wall_center = room_w / 2
            offset_from_center = abs(cx - wall_center)
            max_offset = room_w / 2
            # 중앙에 가까울수록 높은 보너스 (최대 +300)
            score += 300 * (1 - offset_from_center / max_offset) * w["center_bonus"]
        elif wall in ("east", "west"):
            wall_center = room_h / 2
            offset_from_center = abs(cy - wall_center)
            max_offset = room_h / 2
            score += 300 * (1 - offset_from_center / max_offset) * w["center_bonus"]

    # ── SOFA-TV CENTER ALIGNMENT BONUS ──
    # 소파 중앙점이 TV 중앙점과 정확히 마주보도록 (같은 X 또는 같은 Y)
    if category == "소파":
        for item in placed_items:
            if item["category"] in ("TV", "TV거실장"):
                tv_wall = _get_wall_of_position(item["x"], item["y"], room_w, room_h)
                if tv_wall in ("north", "south"):
                    # TV가 위/아래 벽 → 소파 X중앙 = TV X중앙
                    x_diff = abs(cx - item["x"])
                    if x_diff < 100:
                        score += 800 * w["center_bonus"]          # 거의 완벽 정렬
                    elif x_diff < 300:
                        score += 600 * w["center_bonus"]          # 근접 정렬
                    else:
                        max_diff = room_w / 2
                        alignment = max(0, 1 - x_diff / max_diff)
                        score += 400 * alignment * w["center_bonus"]
                elif tv_wall in ("east", "west"):
                    # TV가 좌/우 벽 → 소파 Y중앙 = TV Y중앙
                    y_diff = abs(cy - item["y"])
                    if y_diff < 100:
                        score += 800 * w["center_bonus"]
                    elif y_diff < 300:
                        score += 600 * w["center_bonus"]
                    else:
                        max_diff = room_h / 2
                        alignment = max(0, 1 - y_diff / max_diff)
                        score += 400 * alignment * w["center_bonus"]

    # ── PAIR RULES (relationship with already-placed items) ──
    for rule in PAIR_RULES:
        partner = None
        if rule["a"] == category:
            partner = next((i for i in placed_items if i["category"] == rule["b"]), None)
        elif rule["b"] == category:
            partner = next((i for i in placed_items if i["category"] == rule["a"]), None)
        if not partner:
            continue

        dist = _distance(cx, cy, partner["x"], partner["y"])
        partner_wall = _get_wall_of_position(partner["x"], partner["y"], room_w, room_h)

        if rule["rule"] == "adjacent":
            # Should be side by side (< 200mm gap between edges)
            pfw, pfd = get_footprint(partner["pw"], partner["pd"], partner["rotation"])
            prect = get_rect(partner["x"], partner["y"], pfw, pfd)
            gap = _rect_gap(rect, prect)
            if gap < 200:
                score += rule["bonus"] * w["pair_rule"]
            elif gap < 500:
                score += rule["bonus"] * 0.5 * w["pair_rule"]
            else:
                score -= 200 * w["pair_rule"]

        elif rule["rule"] == "facing":
            # Should be on opposite walls
            if wall != "center" and partner_wall != "center":
                if wall == _opposite_wall(partner_wall):
                    score += rule["bonus"] * w["pair_rule"]       # 마주보기 = 최고 (+1000)
                elif wall == partner_wall:
                    score -= 800 * w["pair_rule"]                 # 같은 벽 = 매우 나쁨
                else:
                    score -= 500 * w["pair_rule"]                 # 인접 벽 (대각선) = 나쁨

        elif rule["rule"] == "nearby":
            max_dist = rule["dist"]
            if dist < max_dist:
                score += rule["bonus"] * (1 - dist / max_dist) * w["pair_rule"]
            else:
                score -= 100 * w["pair_rule"]

        elif rule["rule"] == "apart":
            min_dist = rule["dist"]
            if dist < min_dist:
                score += rule["penalty"] * w["pair_rule"]  # negative = penalty

    # ── AVOID NEAR CATEGORIES ──
    for avoid_cat in profile.avoid_near_categories:
        for item in placed_items:
            if item["category"] == avoid_cat:
                dist = _distance(cx, cy, item["x"], item["y"])
                if dist < 500:
                    score -= 400
                elif dist < 1000:
                    score -= 150

    return score


def _get_front_zone_rect(cx, cy, fw, fd, wall, depth):
    """Get the rectangular front zone in front of a product."""
    if wall == "north":
        return (cx - fw / 2, cy + fd / 2, cx + fw / 2, cy + fd / 2 + depth)
    elif wall == "south":
        return (cx - fw / 2, cy - fd / 2 - depth, cx + fw / 2, cy - fd / 2)
    elif wall == "west":
        return (cx + fw / 2, cy - fd / 2, cx + fw / 2 + depth, cy + fd / 2)
    elif wall == "east":
        return (cx - fw / 2 - depth, cy - fd / 2, cx - fw / 2, cy + fd / 2)
    return None


def _rect_gap(r1, r2) -> float:
    """Minimum gap between two rectangles (0 if overlapping)."""
    dx = max(0, max(r1[0] - r2[2], r2[0] - r1[2]))
    dy = max(0, max(r1[1] - r2[3], r2[1] - r1[3]))
    return (dx ** 2 + dy ** 2) ** 0.5


# ═══════════════════════════════════════════════════
# 7. ROOM-LEVEL PLACEMENT
# ═══════════════════════════════════════════════════

def _sort_products_by_strategy(products, order: str):
    if order == "default":
        return sorted(products, key=lambda p: PROFILES.get(_get_profile_key(p), DEFAULT_PROFILE).priority)
    elif order == "size_desc":
        return sorted(products, key=lambda p: -((p["width_mm"] or 0) * (p["depth_mm"] or 0)))
    elif order == "size_asc":
        return sorted(products, key=lambda p: (p["width_mm"] or 0) * (p["depth_mm"] or 0))
    elif order == "appliance_first":
        return sorted(products, key=lambda p: (
            0 if p["product_type"] == "appliance" else 1,
            PROFILES.get(_get_profile_key(p), DEFAULT_PROFILE).priority
        ))
    elif order == "furniture_first":
        return sorted(products, key=lambda p: (
            0 if p["product_type"] == "furniture" else 1,
            PROFILES.get(_get_profile_key(p), DEFAULT_PROFILE).priority
        ))
    return products


def _get_mount_type(product) -> str:
    """제품의 mount_type을 안전하게 가져옴."""
    try:
        return product["mount_type"]
    except (KeyError, IndexError):
        return "floor"


def _get_profile_key(product) -> str:
    """mount_type에 따라 프로필 키를 결정."""
    category = product["category"]
    mount = _get_mount_type(product)
    if mount == "wall":
        wall_key = f"{category}_wall"
        if wall_key in PROFILES:
            return wall_key
    return category


def _get_adjacent_door_zones(current_room, all_rooms) -> list[tuple]:
    """프론트 getAdjacentDoorZones 포팅 — 인접 방의 문이 현재 방 벽에 닿으면 통행 구역 생성."""
    zones = []
    cr = current_room
    margin = 200
    depth = 600
    cr_x, cr_y = cr["x_mm"], cr["y_mm"]
    cr_w, cr_h = cr["width_mm"], cr["height_mm"]

    for other in all_rooms:
        if other.get("id") == cr.get("id"):
            continue
        or_x, or_y = other["x_mm"], other["y_mm"]
        or_w, or_h = other["width_mm"], other["height_mm"]
        for feat in (other.get("features") or []):
            if feat.get("type") != "door":
                continue
            offset = feat["offset"]
            dw = feat["width"]
            wall = feat["wall"]

            if wall in ("north", "south"):
                door_gx = or_x + offset
                door_gy = or_y if wall == "north" else or_y + or_h
                dx1, dx2 = door_gx, door_gx + dw
                overlap = max(0, min(dx2, cr_x + cr_w) - max(dx1, cr_x))
                if overlap <= 0:
                    continue
                if abs(door_gy - cr_y) < 5:
                    lx = max(0, dx1 - cr_x - margin)
                    rx = min(cr_w, dx2 - cr_x + margin)
                    zones.append((lx, 0, rx, depth))
                elif abs(door_gy - (cr_y + cr_h)) < 5:
                    lx = max(0, dx1 - cr_x - margin)
                    rx = min(cr_w, dx2 - cr_x + margin)
                    zones.append((lx, cr_h - depth, rx, cr_h))
            else:
                door_gx = or_x if wall == "west" else or_x + or_w
                door_gy = or_y + offset
                dy1, dy2 = door_gy, door_gy + dw
                overlap = max(0, min(dy2, cr_y + cr_h) - max(dy1, cr_y))
                if overlap <= 0:
                    continue
                if abs(door_gx - cr_x) < 5:
                    ty = max(0, dy1 - cr_y - margin)
                    by = min(cr_h, dy2 - cr_y + margin)
                    zones.append((0, ty, depth, by))
                elif abs(door_gx - (cr_x + cr_w)) < 5:
                    ty = max(0, dy1 - cr_y - margin)
                    by = min(cr_h, dy2 - cr_y + margin)
                    zones.append((cr_w - depth, ty, cr_w, by))
    return zones


def auto_place_products(room, features, products, weights=None, wall_order=None,
                        pre_sorted=False, diversity_k=1, all_rooms=None) -> dict:
    """Place products within a single room using greedy scoring.

    Args:
        pre_sorted: If True, skip internal priority sort (strategy already sorted)
        diversity_k: Pick randomly from top-k candidates (1=always best, 3=diverse)
    """
    import random as _rng

    room_w = room["width_mm"]
    room_h = room["height_mm"]
    features_list = [dict(f) for f in features]
    room_open_walls = set(room.get("open_walls") or [])

    if pre_sorted:
        sorted_products = list(products)  # Keep strategy sort order
    else:
        sorted_products = sorted(
            products,
            key=lambda p: PROFILES.get(_get_profile_key(p), DEFAULT_PROFILE).priority
        )

    # 인접 방 문 통행 구역을 미리 계산
    adjacent_door_zones = _get_adjacent_door_zones(room, all_rooms or [])

    # 바닥 제품과 벽면 제품의 occupied_rects 분리
    floor_occupied: list[tuple] = list(adjacent_door_zones)  # 인접 문 구역은 기본 차단
    wall_occupied: list[tuple] = []
    placed_items: list[dict] = []  # track category + position for relationship rules
    placements = []
    warnings = []
    walls = wall_order or ["north", "south", "east", "west"]

    for product in sorted_products:
        pw, pd = product["width_mm"], product["depth_mm"]
        if pw is None or pd is None:
            warnings.append(f"{product['name']}: 치수 정보 없음, 배치 불가")
            continue

        mount_type = _get_mount_type(product)
        is_wall_mount = mount_type == "wall"
        profile_key = _get_profile_key(product)
        profile = PROFILES.get(profile_key, DEFAULT_PROFILE)
        best_score = float("-inf")
        best_pos = None

        # 벽면 제품은 벽면끼리만 충돌, 바닥 제품은 바닥끼리만 충돌
        occupied_rects = wall_occupied if is_wall_mount else floor_occupied

        # preferred_walls가 있으면 wall_order 순서를 반영하되 preferred만 먼저 시도
        if profile.preferred_walls:
            # wall_order 순서 중 preferred에 있는 것만 먼저
            pw_set = set(profile.preferred_walls)
            target_walls = [w for w in walls if w in pw_set]
            if not target_walls:
                target_walls = profile.preferred_walls  # fallback
        else:
            target_walls = walls

        def _wall_rotations(wall_name):
            if wall_name in ("north", "south"):
                return [0, 90]
            return [90, 0]

        # Collect ALL valid candidates with scores (for top-k diversity)
        all_candidates = []

        # Center candidates (for "none" or "preferred") — 벽면 제품은 제외
        if not is_wall_mount and profile.wall_affinity in ("none", "preferred"):
            step = 200
            for rotation in [0, 90]:
                fw_c, fd_c = get_footprint(pw, pd, rotation)
                margin = max(profile.clearance_front_mm, profile.clearance_sides_mm)
                for cx in _range_float(fw_c / 2 + margin, room_w - fw_c / 2 - margin, step):
                    for cy in _range_float(fd_c / 2 + margin, room_h - fd_c / 2 - margin, step):
                        s = _score_candidate(
                            cx, cy, rotation, pw, pd, product["category"],
                            profile, room_w, room_h, features_list,
                            occupied_rects, placed_items, "center",
                            mount_type, weights, room_open_walls,
                        )
                        if profile.wall_affinity == "none":
                            center_dist = _distance(cx, cy, room_w / 2, room_h / 2)
                            max_dist = _distance(0, 0, room_w / 2, room_h / 2)
                            s += 150 * (1 - center_dist / max_dist)
                        if s > float("-inf"):
                            all_candidates.append((s, {"x": cx, "y": cy, "rotation": rotation, "wall": "center"}))

        # Wall candidates (for "required" or "preferred")
        if profile.wall_affinity in ("required", "preferred"):
            for wall in target_walls:
                for rotation in _wall_rotations(wall):
                    candidates = _get_wall_candidates(pw, pd, rotation, wall, room_w, room_h, profile)
                    for c in candidates:
                        s = _score_candidate(
                            c["x"], c["y"], rotation, pw, pd, product["category"],
                            profile, room_w, room_h, features_list,
                            occupied_rects, placed_items, wall,
                            mount_type, weights, room_open_walls,
                        )
                        if s > float("-inf"):
                            all_candidates.append((s, {"x": c["x"], "y": c["y"], "rotation": rotation, "wall": wall}))

            if not all_candidates and profile.preferred_walls:
                other_walls = [ww for ww in walls if ww not in target_walls]
                for wall in other_walls:
                    for rotation in _wall_rotations(wall):
                        candidates = _get_wall_candidates(pw, pd, rotation, wall, room_w, room_h, profile)
                        for c in candidates:
                            s = _score_candidate(
                                c["x"], c["y"], rotation, pw, pd, product["category"],
                                profile, room_w, room_h, features_list,
                                occupied_rects, placed_items, wall,
                                mount_type, weights, room_open_walls,
                            )
                            if s > float("-inf"):
                                all_candidates.append((s, {"x": c["x"], "y": c["y"], "rotation": rotation, "wall": wall}))

        # Select from top-k candidates for diversity
        if all_candidates:
            all_candidates.sort(key=lambda x: -x[0])
            top_k = all_candidates[:diversity_k]
            if diversity_k > 1 and len(top_k) > 1:
                # Weighted random: higher score = higher probability
                scores = [max(c[0], 0.01) for c in top_k]
                total_s = sum(scores)
                probs = [s / total_s for s in scores]
                chosen = _rng.choices(top_k, weights=probs, k=1)[0]
            else:
                chosen = top_k[0]
            best_score = chosen[0]
            best_pos = chosen[1]
        else:
            best_score = float("-inf")
            best_pos = None

        if best_pos and best_score > float("-inf"):
            fw, fd = get_display_footprint(pw, pd, best_pos["rotation"], mount_type)
            rect = get_rect(best_pos["x"], best_pos["y"], fw, fd)
            occupied_rects.append(rect)  # 해당 레이어(floor/wall)에만 추가
            placed_items.append({
                "category": product["category"],
                "x": best_pos["x"], "y": best_pos["y"],
                "pw": pw, "pd": pd, "rotation": best_pos["rotation"],
                "wall": best_pos["wall"],
                "mount_type": mount_type,
            })
            placements.append({
                "product_id": product["product_id"],
                "model": product["model"],
                "name": product["name"],
                "x_mm": best_pos["x"],
                "y_mm": best_pos["y"],
                "rotation": best_pos["rotation"],
                "pw": pw,
                "pd": pd,
                "category": product["category"],
            })
        else:
            warnings.append(f"{product['name']}: 배치할 공간이 부족합니다")

    return {"placements": placements, "warnings": warnings}


# ═══════════════════════════════════════════════════
# 8. FLOOR PLAN LEVEL PLACEMENT
# ═══════════════════════════════════════════════════

# ── 방 이름 → 서브타입 분류 ──
# DB의 room_type은 "bedroom"으로 통일되어 있지만,
# 방 이름으로 세분화하여 제품 배정을 더 정확하게 함.
#   master   = 안방 (침대, 옷장, 화장대, 의류관리기)
#   bedroom  = 침실, 침실1, 침실2 (침대, 옷장)
#   small    = 작은방, 작은방1, 작은방2 (책상, 책장, 유아동가구)
#   loft     = 다락/침실 (침대)

def _classify_room_subtype(room: dict) -> str:
    """room_type + name 기반으로 세분화된 서브타입 반환."""
    rt = room.get("room_type", "")
    name = room.get("name", "")

    if rt != "bedroom":
        return rt

    if "안방" in name:
        return "master"
    if "작은방" in name:
        return "small"
    if "다락" in name:
        return "loft"
    # 침실, 침실1, 침실2 등
    return "bedroom"


CATEGORY_ROOM_MAP: dict[str, list[str]] = {
    # Appliances
    "냉장고": ["kitchen"],
    "전기레인지": ["kitchen"],
    "오븐": ["kitchen"],
    "전자레인지": ["kitchen"],
    "식기세척기": ["kitchen"],
    "정수기": ["kitchen", "living"],
    "TV": ["living", "master", "bedroom"],
    "에어컨": ["living", "master", "bedroom"],
    "스탠바이미": ["living", "bedroom"],
    "세탁기": ["utility", "kitchen"],
    "워시타워": ["utility", "kitchen"],
    "워시콤보": ["utility", "kitchen"],
    "의류건조기": ["utility", "kitchen"],
    "의류관리기": ["master", "bedroom"],
    # Furniture — 안방 vs 작은방 구분
    "침대": ["master", "bedroom", "loft"],
    "소파": ["living"],
    "식탁·테이블": ["kitchen", "living"],
    # "의자"는 FOLLOW_PARTNER_MAP으로 처리
    "책장·수납장": ["small", "living", "bedroom"],
    "책상": ["small"],                          # 책상은 작은방 전용
    "선반": ["small", "living", "bedroom"],
    "옷장·행거": ["master", "bedroom"],
    "화장대·콘솔": ["master"],                   # 화장대는 안방 전용
    "TV거실장": ["living"],
    "유아동가구": ["small", "bedroom"],           # 유아동가구는 작은방 우선
}


    # 파트너 따라가기 규칙: 이 카테고리의 제품은 파트너가 배정된 방으로 따라감
FOLLOW_PARTNER_MAP: dict[str, list[str]] = {
    "의자": ["책상", "식탁·테이블", "화장대·콘솔"],
}


def auto_place_floor_plan(rooms, products, strategy=None) -> dict:
    """Auto-place products across ALL rooms in a floor plan."""
    import json

    # Resolve strategy parameters
    if strategy:
        order = strategy.get("order", "default")
        weights_key = strategy.get("weights", "default")
        strat_weights = WEIGHT_PRESETS.get(weights_key, WEIGHT_PRESETS["default"])
        wall_start = strategy.get("wall_start", "north")
        _all_walls = ["north", "south", "east", "west"]
        if wall_start in _all_walls:
            _all_walls.remove(wall_start)
            wall_order = [wall_start] + _all_walls
        else:
            wall_order = ["north", "south", "east", "west"]
    else:
        order = "default"
        strat_weights = None
        wall_order = None

    placeable_rooms = [r for r in rooms if r["is_placeable"]]
    type_to_rooms: dict[str, list] = {}
    for r in placeable_rooms:
        subtype = _classify_room_subtype(r)
        type_to_rooms.setdefault(subtype, []).append(r)

    room_products: dict[int, list] = {r["id"]: [] for r in placeable_rooms}
    follow_later: list = []  # 파트너 따라가기 대상 (나중에 배정)
    warnings = []

    # 방별 면적 및 사용량 추적
    room_area: dict[int, float] = {r["id"]: r["width_mm"] * r["height_mm"] for r in placeable_rooms}
    room_used: dict[int, float] = {r["id"]: 0.0 for r in placeable_rooms}
    room_by_id: dict[int, dict] = {r["id"]: r for r in placeable_rooms}

    def _get_product_footprint(product: dict) -> float:
        """제품의 바닥 면적 (mm²)."""
        pw = product.get("width_mm") or 500
        pd = product.get("depth_mm") or 500
        return max(pw, MIN_DISPLAY_DIM) * max(pd, MIN_DISPLAY_DIM)

    def _pick_best_room(candidates: list[dict], product: dict) -> dict | None:
        """후보 방 중 여유 공간이 가장 많은 방을 선택 (용량 기반 분산).

        방 선택 우선순위:
        1. 해당 카테고리의 '핵심 제품'이 아직 없는 방 (예: 침대 없는 침실)
        2. 여유 면적(총 면적 - 사용 면적)이 가장 큰 방
        """
        if not candidates:
            return None

        product_fp = _get_product_footprint(product)
        category = product["category"]

        # 핵심 제품 매핑: 이 카테고리가 방에 1개씩은 있어야 하는 것
        ESSENTIAL_MAP = {
            "침대": ["master", "bedroom", "loft"],
            "책상": ["small"],
            "옷장·행거": ["master", "bedroom"],
        }

        # 핵심 제품이면 아직 해당 카테고리가 없는 방을 우선
        if category in ESSENTIAL_MAP:
            empty_rooms = [
                r for r in candidates
                if not any(p["category"] == category for p in room_products[r["id"]])
            ]
            if empty_rooms:
                candidates = empty_rooms

        # 여유 면적 기준으로 정렬 (큰 순)
        def remaining_capacity(r: dict) -> float:
            return room_area[r["id"]] - room_used[r["id"]]

        best = max(candidates, key=remaining_capacity)

        # 공간이 부족하면 None 반환하지 않고 그래도 시도 (엔진이 배치 불가 판단)
        return best

    # 1단계: 일반 제품 먼저 방 배정
    for product in products:
        category = product["category"]

        # 파트너 따라가기 대상은 나중에 처리
        if category in FOLLOW_PARTNER_MAP:
            follow_later.append(product)
            continue

        target_types = CATEGORY_ROOM_MAP.get(category, ["living"])
        placed = False

        for rt in target_types:
            candidates = type_to_rooms.get(rt, [])
            if candidates:
                best_room = _pick_best_room(candidates, product)
                if best_room:
                    room_products[best_room["id"]].append(product)
                    room_used[best_room["id"]] += _get_product_footprint(product)
                    placed = True
                    break

        if not placed:
            if placeable_rooms:
                fallback = _pick_best_room(placeable_rooms, product)
                if fallback:
                    room_products[fallback["id"]].append(product)
                    room_used[fallback["id"]] += _get_product_footprint(product)
            else:
                warnings.append(f"{product['name']}: 배치 가능한 방이 없습니다")

    # 2단계: 파트너 따라가기 (의자 등)
    for product in follow_later:
        category = product["category"]
        partner_categories = FOLLOW_PARTNER_MAP[category]
        target_room_id = None

        # 파트너가 배정된 방 찾기
        for room_id, prods in room_products.items():
            for p in prods:
                if p["category"] in partner_categories:
                    target_room_id = room_id
                    break
            if target_room_id:
                break

        if target_room_id:
            room_products[target_room_id].append(product)
        elif placeable_rooms:
            # 파트너가 없으면 가장 큰 방에 배치
            fallback = max(placeable_rooms, key=lambda r: r["width_mm"] * r["height_mm"])
            room_products[fallback["id"]].append(product)
        else:
            warnings.append(f"{product['name']}: 배치 가능한 방이 없습니다")

    all_placements = []

    # 모든 방의 문 정보를 도면 절대좌표로 수집 (인접 방 문 체크용)
    all_doors_absolute = []
    for r in rooms:
        r_features = r["features"]
        if isinstance(r_features, str):
            r_features = json.loads(r_features)
        for feat in r_features:
            if feat.get("type") == "door":
                all_doors_absolute.append({
                    "room_id": r["id"],
                    "room_x": r["x_mm"],
                    "room_y": r["y_mm"],
                    "room_w": r["width_mm"],
                    "room_h": r["height_mm"],
                    "door": feat,
                })

    for room in placeable_rooms:
        prods = room_products.get(room["id"], [])
        if not prods:
            continue

        features = room["features"]
        if isinstance(features, str):
            features = json.loads(features)

        # 다른 방의 문이 이 방과 맞닿는 경우, 해당 문의 통행 구역을
        # 이 방의 로컬 좌표로 변환하여 features에 가상 door로 추가
        extra_features = list(features)
        for door_info in all_doors_absolute:
            if door_info["room_id"] == room["id"]:
                continue  # 자기 방 문은 이미 features에 있음

            # 다른 방 문의 통행 구역을 도면 절대좌표로 계산
            d = door_info["door"]
            dr_x = door_info["room_x"]
            dr_y = door_info["room_y"]
            dr_w = door_info["room_w"]
            dr_h = door_info["room_h"]
            d_wall = d["wall"]
            d_offset = d["offset"]
            d_width = d["width"]
            margin = 200
            depth = 800

            # 문의 통행 구역 (도면 절대좌표)
            if d_wall == "north":
                zone = (dr_x + d_offset - margin, dr_y - depth,
                        dr_x + d_offset + d_width + margin, dr_y)
            elif d_wall == "south":
                zone = (dr_x + d_offset - margin, dr_y + dr_h,
                        dr_x + d_offset + d_width + margin, dr_y + dr_h + depth)
            elif d_wall == "west":
                zone = (dr_x - depth, dr_y + d_offset - margin,
                        dr_x, dr_y + d_offset + d_width + margin)
            else:  # east
                zone = (dr_x + dr_w, dr_y + d_offset - margin,
                        dr_x + dr_w + depth, dr_y + d_offset + d_width + margin)

            # 이 통행 구역이 현재 방과 겹치는지 확인
            my_x1, my_y1 = room["x_mm"], room["y_mm"]
            my_x2 = my_x1 + room["width_mm"]
            my_y2 = my_y1 + room["height_mm"]

            # 겹침 체크
            if zone[0] < my_x2 and zone[2] > my_x1 and zone[1] < my_y2 and zone[3] > my_y1:
                # 겹치는 영역을 방 로컬 좌표로 변환하여 가상 blocked zone 추가
                local_x1 = max(0, zone[0] - my_x1)
                local_y1 = max(0, zone[1] - my_y1)
                local_x2 = min(room["width_mm"], zone[2] - my_x1)
                local_y2 = min(room["height_mm"], zone[3] - my_y1)

                # 가상 door feature로 추가 (통행 구역이 방 안에 겹치는 부분)
                # 가장 가까운 벽에 가상 문으로 등록
                blocked_w = local_x2 - local_x1
                blocked_h = local_y2 - local_y1

                if blocked_w > 0 and blocked_h > 0:
                    # 어느 벽에 가장 가까운지 판단
                    if local_y1 <= 1:
                        extra_features.append({
                            "type": "door", "wall": "north",
                            "offset": local_x1, "width": blocked_w,
                            "swing_dir": "inward", "_virtual": True,
                        })
                    elif local_y2 >= room["height_mm"] - 1:
                        extra_features.append({
                            "type": "door", "wall": "south",
                            "offset": local_x1, "width": blocked_w,
                            "swing_dir": "inward", "_virtual": True,
                        })
                    elif local_x1 <= 1:
                        extra_features.append({
                            "type": "door", "wall": "west",
                            "offset": local_y1, "width": blocked_h,
                            "swing_dir": "inward", "_virtual": True,
                        })
                    elif local_x2 >= room["width_mm"] - 1:
                        extra_features.append({
                            "type": "door", "wall": "east",
                            "offset": local_y1, "width": blocked_h,
                            "swing_dir": "inward", "_virtual": True,
                        })

        sorted_prods = _sort_products_by_strategy(prods, order)
        diversity_k = strategy.get("diversity_k", 1) if strategy else 1
        result = auto_place_products(
            room, extra_features, sorted_prods, strat_weights, wall_order,
            pre_sorted=(order != "default"), diversity_k=diversity_k,
            all_rooms=rooms,
        )

        for p in result["placements"]:
            p["room_id"] = room["id"]
            all_placements.append(p)

        warnings.extend(result.get("warnings", []))

    return {"placements": all_placements, "warnings": warnings}


# ═══════════════════════════════════════════════════
# 9. MULTIPLE LAYOUT GENERATION & METRICS
# ═══════════════════════════════════════════════════

def generate_multiple_layouts(rooms, products) -> list[dict]:
    """GA + SA 하이브리드 방식으로 다중 배치안 생성.

    Phase 1: Greedy 시드 생성 (5개 전략)
    Phase 2: GA 진화 (시드 + 돌연변이 인구 → 30세대 진화)
    Phase 3: 상위 5개를 적응형 SA로 미세 최적화
    Phase 4: 전 제품 배치된 것만 필터 → 상위 5개 → AI 평가
    """
    import time
    total_products = len(products)

    # ── Phase 1: Greedy 시드 생성 ──
    t0 = time.time()
    greedy_seeds = []
    partial_seeds = []  # 전체 배치 실패 시 fallback용

    for strategy in STRATEGIES:
        result = auto_place_floor_plan(rooms, products, strategy=strategy)
        placed_count = len(result["placements"])
        if placed_count >= total_products:
            greedy_seeds.append(result["placements"])
        elif placed_count > 0:
            partial_seeds.append((placed_count, result["placements"]))

    # 완전 배치가 없으면 가장 많이 배치한 것들을 시드로 사용 (fallback)
    if not greedy_seeds and partial_seeds:
        partial_seeds.sort(key=lambda x: x[0], reverse=True)
        best_count = partial_seeds[0][0]
        greedy_seeds = [ps[1] for ps in partial_seeds if ps[0] >= best_count]
        print(f"[Phase1] 완전 배치 불가 → 부분 배치 시드 사용 ({best_count}/{total_products}개 배치)")

    t_greedy = time.time() - t0
    print(f"[Phase1] Greedy 시드: {len(greedy_seeds)}개 ({t_greedy:.2f}s)")

    if not greedy_seeds:
        return []

    # ── Phase 2: GA 진화 ──
    t1 = time.time()
    ga_result = _ga_evolve(greedy_seeds, rooms, products,
                           population_size=20, generations=30)
    t_ga = time.time() - t1
    print(f"[Phase2] GA 완료: 최고={ga_result['best_score']:.1f}, "
          f"인구={len(ga_result['population'])}개 ({t_ga:.2f}s)")

    # ── Phase 3: 상위 5개 SA 미세 최적화 ──
    t2 = time.time()
    top_candidates = ga_result["top_n"]  # 이미 점수순 상위 5개

    final_layouts = []
    names = ["배치안 A", "배치안 B", "배치안 C", "배치안 D", "배치안 E"]
    descs = ["GA 진화 + SA 최적화", "GA 진화 + SA 최적화", "GA 진화 + SA 최적화",
             "GA 진화 + SA 최적화", "GA 진화 + SA 최적화"]

    # 완전 배치 가능 여부 추적 (부분 배치 fallback)
    has_complete = any(len(c) >= total_products for c in top_candidates)

    # SA 파라미터를 후보별로 다르게 → 다른 방향으로 탐색
    sa_params = [
        {"t_initial": 8.0,  "cooling_rate": 0.995, "max_iterations": 300},  # 보수적 (미세 조정)
        {"t_initial": 15.0, "cooling_rate": 0.990, "max_iterations": 400},  # 적극적 (큰 변화)
        {"t_initial": 25.0, "cooling_rate": 0.985, "max_iterations": 350},  # 매우 적극적
        {"t_initial": 10.0, "cooling_rate": 0.993, "max_iterations": 300},  # 중간
        {"t_initial": 20.0, "cooling_rate": 0.988, "max_iterations": 350},  # 적극적 변형
    ]

    for i, candidate in enumerate(top_candidates):
        params = sa_params[i % len(sa_params)]
        optimized = _sa_optimize_layout(candidate, rooms, products,
                                        t_initial=params["t_initial"],
                                        cooling_rate=params["cooling_rate"],
                                        max_iterations=params["max_iterations"],
                                        max_retries=5, reheat=True)

        # 완전 배치 가능한 결과가 있으면 불완전한 것은 제외
        if has_complete and len(optimized) < total_products:
            continue

        # 빈 결과만 제외
        if len(optimized) == 0:
            continue

        metrics = evaluate_layout_metrics(optimized, rooms)
        not_placed = total_products - len(optimized)
        warnings = []
        if not_placed > 0:
            placed_pids = {pl["product_id"] for pl in optimized}
            missing = [p for p in products if p["product_id"] not in placed_pids]
            missing_names = [p["name"] for p in missing]
            warnings.append(f"공간 부족으로 {not_placed}개 제품 미배치: {', '.join(missing_names)}")

        final_layouts.append({
            "name": names[i] if i < len(names) else f"배치안 {i+1}",
            "desc": descs[i] if i < len(descs) else "GA 진화 + SA 최적화",
            "placements": optimized,
            "warnings": warnings,
            "metrics": metrics,
        })

    t_sa = time.time() - t2
    print(f"[Phase3] SA 완료: {len(final_layouts)}개 ({t_sa:.2f}s)")

    # ── Phase 4: 점수순 정렬 + 전 제품 배치 필터 + 상위 5개 ──
    final_layouts.sort(key=lambda l: l["metrics"]["total"], reverse=True)
    final_layouts = final_layouts[:5]

    for idx, layout in enumerate(final_layouts):
        layout["id"] = idx

    total_time = time.time() - t0
    print(f"[layout] 최종: {len(final_layouts)}개 (총 {total_time:.2f}s)")
    return final_layouts


def evaluate_layout_metrics(placements, rooms) -> dict:
    """Evaluate a layout with multiple metrics (0-100 each)."""
    import json
    placeable_rooms = [r for r in rooms if r["is_placeable"]]

    # Build room lookup
    room_map = {}
    for r in placeable_rooms:
        features = r["features"]
        if isinstance(features, str):
            features = json.loads(features)
        room_map[r["id"]] = {"room": r, "features": features, "placements": []}

    for p in placements:
        rid = p.get("room_id")
        if rid in room_map:
            room_map[rid]["placements"].append(p)

    # Calculate per-room metrics and average
    space_scores, circ_scores, pair_scores, balance_scores, open_scores, front_scores = [], [], [], [], [], []

    for rid, data in room_map.items():
        r = data["room"]
        feats = data["features"]
        pls = data["placements"]
        rw, rh = r["width_mm"], r["height_mm"]

        if not pls:
            continue

        space_scores.append(_metric_space_usage(pls, rw, rh))
        circ_scores.append(_metric_circulation(pls, feats, rw, rh))
        pair_scores.append(_metric_pair_satisfaction(pls, rw, rh))
        balance_scores.append(_metric_wall_balance(pls, rw, rh))
        open_scores.append(_metric_center_openness(pls, rw, rh))
        front_scores.append(_metric_front_zone(pls, rw, rh))

    def _avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else 100.0

    space = _avg(space_scores)
    circulation = _avg(circ_scores)
    pair_sat = _avg(pair_scores)
    balance = _avg(balance_scores)
    openness = _avg(open_scores)
    front_zone = _avg(front_scores)

    total = round(
        space * 0.15 + circulation * 0.25 + pair_sat * 0.20 +
        balance * 0.10 + openness * 0.15 + front_zone * 0.15, 1
    )

    return {
        "space_usage": space,
        "circulation": circulation,
        "pair_satisfaction": pair_sat,
        "wall_balance": balance,
        "center_openness": openness,
        "front_zone": front_zone,
        "total": total,
    }


def _metric_space_usage(placements, room_w, room_h):
    room_area = room_w * room_h
    used = 0
    for p in placements:
        pw = p.get("pw", 0) or 0
        pd = p.get("pd", 0) or 0
        if pw == 0 or pd == 0:
            continue
        used += pw * pd
    ratio = used / room_area if room_area > 0 else 0
    if 0.15 <= ratio <= 0.45:
        return 100.0
    elif ratio < 0.15:
        return max(0, 100 - (0.15 - ratio) * 400)
    else:
        return max(0, 100 - (ratio - 0.45) * 250)


def _metric_circulation(placements, features, room_w, room_h):
    score = 100.0
    doors = [f for f in features if f.get("type") == "door"]
    for door in doors:
        dx, dy = _feature_position(door, room_w, room_h)
        for p in placements:
            px, py = p.get("x_mm", 0), p.get("y_mm", 0)
            dist = _distance(px, py, dx, dy)
            if dist < 500:
                score -= 12
            elif dist < 800:
                score -= 4
    return max(0, min(100, score))


def _metric_pair_satisfaction(placements, room_w, room_h):
    total = 0
    satisfied = 0
    cats = {}
    for p in placements:
        cat = p.get("category", "")
        if cat:
            cats[cat] = p

    for rule in PAIR_RULES:
        a = cats.get(rule["a"])
        b = cats.get(rule["b"])
        if not a or not b:
            continue
        total += 1
        dist = _distance(a.get("x_mm", 0), a.get("y_mm", 0), b.get("x_mm", 0), b.get("y_mm", 0))

        if rule["rule"] == "facing":
            wa = _get_wall_of_position(a.get("x_mm", 0), a.get("y_mm", 0), room_w, room_h)
            wb = _get_wall_of_position(b.get("x_mm", 0), b.get("y_mm", 0), room_w, room_h)
            if wa == _opposite_wall(wb):
                satisfied += 1
        elif rule["rule"] == "adjacent":
            if dist < 500:
                satisfied += 1
        elif rule["rule"] == "nearby":
            if dist < rule.get("dist", 1000):
                satisfied += 1
        elif rule["rule"] == "apart":
            if dist >= rule.get("dist", 500):
                satisfied += 1

    return round(satisfied / total * 100, 1) if total > 0 else 100.0


def _metric_wall_balance(placements, room_w, room_h):
    counts = {"north": 0, "south": 0, "east": 0, "west": 0}
    for p in placements:
        wall = _get_wall_of_position(p.get("x_mm", room_w / 2), p.get("y_mm", room_h / 2), room_w, room_h)
        counts[wall] += 1

    used_walls = [v for v in counts.values() if v > 0]
    if len(used_walls) <= 1:
        return 30.0

    avg = sum(used_walls) / len(used_walls)
    variance = sum((c - avg) ** 2 for c in used_walls) / len(used_walls)
    std = variance ** 0.5
    return max(0, min(100, round(100 - std * 20, 1)))


def _metric_center_openness(placements, room_w, room_h):
    cx1, cy1 = room_w * 0.3, room_h * 0.3
    cx2, cy2 = room_w * 0.7, room_h * 0.7
    center_area = (cx2 - cx1) * (cy2 - cy1)
    if center_area <= 0:
        return 100.0

    occupied = 0
    for p in placements:
        pw = p.get("pw", 0) or 0
        pd = p.get("pd", 0) or 0
        px, py = p.get("x_mm", 0), p.get("y_mm", 0)
        r = (px - pw / 2, py - pd / 2, px + pw / 2, py + pd / 2)
        # overlap area
        ox1 = max(r[0], cx1)
        oy1 = max(r[1], cy1)
        ox2 = min(r[2], cx2)
        oy2 = min(r[3], cy2)
        if ox1 < ox2 and oy1 < oy2:
            occupied += (ox2 - ox1) * (oy2 - oy1)

    free_ratio = 1 - (occupied / center_area)
    return max(0, min(100, round(free_ratio * 100, 1)))


def _metric_front_zone(placements, room_w, room_h):
    total = 0
    clear = 0
    for p in placements:
        cat = p.get("category", "")
        fz = FRONT_ZONE_RULES.get(cat)
        if not fz:
            continue
        total += 1
        pw = p.get("pw", 0) or 0
        pd = p.get("pd", 0) or 0
        px, py = p.get("x_mm", 0), p.get("y_mm", 0)
        fw, fd = get_footprint(pw, pd, p.get("rotation", 0))
        wall = _get_wall_of_position(px, py, room_w, room_h)
        front_rect = _get_front_zone_rect(px, py, fw, fd, wall, fz["depth"])
        if not front_rect:
            clear += 1
            continue
        blocked = False
        for other in placements:
            if other is p:
                continue
            opw = other.get("pw", 0) or 0
            opd = other.get("pd", 0) or 0
            ofw, ofd = get_footprint(opw, opd, other.get("rotation", 0))
            orect = get_rect(other.get("x_mm", 0), other.get("y_mm", 0), ofw, ofd)
            if rects_overlap(front_rect, orect):
                blocked = True
                break
        if not blocked:
            clear += 1
    return round(clear / total * 100, 1) if total > 0 else 100.0


# ═══════════════════════════════════════════════════
# 10. GA + ADAPTIVE SA HYBRID OPTIMIZATION
# ═══════════════════════════════════════════════════

import random as _evo_rng
import math as _evo_math
import copy as _evo_copy


# ── 공통 헬퍼 ──

def _evo_build_room_features_map(rooms) -> dict:
    """방별 features를 미리 파싱해서 캐시."""
    import json
    result = {}
    for r in rooms:
        features = r["features"]
        if isinstance(features, str):
            features = json.loads(features)
        result[r["id"]] = features
    return result


def _evo_build_room_lookup(rooms) -> dict:
    return {r["id"]: r for r in rooms}


def _evo_build_product_lookup(products) -> dict:
    return {p["model"]: dict(p) for p in products}


def _evo_get_others_in_room(state, room_id, exclude_model, product_lookup):
    """같은 방 내 다른 배치를 validate용 형태로 반환."""
    others = []
    for p in state:
        if p["room_id"] == room_id and p["model"] != exclude_model:
            prod = product_lookup.get(p["model"])
            mount = prod.get("mount_type", "floor") if prod else "floor"
            others.append({
                "id": p["model"],
                "x_mm": p["x_mm"], "y_mm": p["y_mm"],
                "rotation": p["rotation"],
                "pw": p.get("pw", 0), "pd": p.get("pd", 0),
                "mount_type": mount or "floor",
            })
    return others


def _evo_is_valid(x, y, rotation, product, room, features, others, all_rooms=None):
    return len(validate_single_placement(x, y, rotation, product, room, features, others, all_rooms=all_rooms)) == 0


def _evo_mutate_one(state, rooms_map, features_map, product_lookup):
    """제품 하나를 랜덤 이동 (shift/rotate/rewall/swap).
    Returns: (new_state, True) 또는 (None, False)
    """
    all_rooms_list = list(rooms_map.values())
    if not state:
        return None, False

    new_state = _evo_copy.deepcopy(state)
    idx = _evo_rng.randint(0, len(new_state) - 1)
    pl = new_state[idx]

    product = product_lookup.get(pl["model"])
    if not product:
        return None, False

    room = rooms_map.get(pl["room_id"])
    if not room:
        return None, False

    features = features_map.get(pl["room_id"], [])
    profile = PROFILES.get(_get_profile_key(product), DEFAULT_PROFILE)
    room_w, room_h = room["width_mm"], room["height_mm"]
    pw, pd = product["width_mm"], product["depth_mm"]
    if pw is None or pd is None:
        return None, False

    # 이동 종류: shift(55%), rewall(25%), rotate(10%), swap(10%)
    move = _evo_rng.choices(["shift", "rewall", "rotate", "swap"],
                            weights=[55, 25, 10, 10], k=1)[0]

    if move == "shift":
        # 방 크기의 20~40% 범위로 이동 (기존 250mm 고정 → 방 크기 비례)
        shift_x = max(400, room_w * 0.3)
        shift_y = max(400, room_h * 0.3)
        wall = _get_wall_of_position(pl["x_mm"], pl["y_mm"], room_w, room_h)
        if profile.wall_affinity == "required" and wall != "center":
            if wall in ("north", "south"):
                pl["x_mm"] = round(max(0, min(room_w, pl["x_mm"] + _evo_rng.gauss(0, shift_x))), 1)
            else:
                pl["y_mm"] = round(max(0, min(room_h, pl["y_mm"] + _evo_rng.gauss(0, shift_y))), 1)
        else:
            pl["x_mm"] = round(max(0, min(room_w, pl["x_mm"] + _evo_rng.gauss(0, shift_x))), 1)
            pl["y_mm"] = round(max(0, min(room_h, pl["y_mm"] + _evo_rng.gauss(0, shift_y))), 1)

    elif move == "rewall":
        walls = ["north", "south", "east", "west"]
        cur_wall = _get_wall_of_position(pl["x_mm"], pl["y_mm"], room_w, room_h)
        others_w = [w for w in walls if w != cur_wall]
        if not others_w:
            return None, False
        tw = _evo_rng.choice(others_w)
        rot = 0 if tw in ("north", "south") else 90
        cands = _get_wall_candidates(pw, pd, rot, tw, room_w, room_h, profile)
        if not cands:
            rot = 90 - rot
            cands = _get_wall_candidates(pw, pd, rot, tw, room_w, room_h, profile)
        if not cands:
            return None, False
        c = _evo_rng.choice(cands[:10])
        pl["x_mm"], pl["y_mm"], pl["rotation"] = c["x"], c["y"], rot

    elif move == "rotate":
        pl["rotation"] = 90 if pl["rotation"] == 0 else 0

    elif move == "swap":
        # 같은 방 내 다른 제품과 위치 교환
        same_room = [j for j, p in enumerate(new_state)
                     if p["room_id"] == pl["room_id"] and j != idx]
        if not same_room:
            return None, False
        j = _evo_rng.choice(same_room)
        # 위치만 교환
        new_state[idx]["x_mm"], new_state[j]["x_mm"] = new_state[j]["x_mm"], new_state[idx]["x_mm"]
        new_state[idx]["y_mm"], new_state[j]["y_mm"] = new_state[j]["y_mm"], new_state[idx]["y_mm"]
        new_state[idx]["rotation"], new_state[j]["rotation"] = new_state[j]["rotation"], new_state[idx]["rotation"]
        # 두 제품 모두 유효성 검사
        for check_idx in [idx, j]:
            cp = new_state[check_idx]
            cprod = product_lookup.get(cp["model"])
            if not cprod:
                return None, False
            croom = rooms_map.get(cp["room_id"])
            cfeats = features_map.get(cp["room_id"], [])
            cothers = _evo_get_others_in_room(new_state, cp["room_id"], cp["model"], product_lookup)
            if not _evo_is_valid(cp["x_mm"], cp["y_mm"], cp["rotation"], cprod, croom, cfeats, cothers, all_rooms_list):
                return None, False
        return new_state, True  # swap은 위에서 이미 검증 완료

    # 유효성 검사 (swap 제외)
    others = _evo_get_others_in_room(new_state, pl["room_id"], pl["model"], product_lookup)
    if _evo_is_valid(pl["x_mm"], pl["y_mm"], pl["rotation"], product, room, features, others, all_rooms_list):
        return new_state, True

    return None, False


# ── GA (유전 알고리즘) ──

def _ga_evolve(seeds, rooms, products, population_size=20, generations=30):
    """유전 알고리즘으로 배치안 집단을 진화시킨다.

    Args:
        seeds: Greedy 배치안 리스트 (초기 인구의 시드)
        rooms: 방 목록
        products: 제품 목록
        population_size: 인구 크기
        generations: 세대 수

    Returns:
        {"population": [...], "best_score": float, "top_n": [상위5개]}
    """
    placeable_rooms = [r for r in rooms if r.get("is_placeable", True)]
    rooms_map = _evo_build_room_lookup(placeable_rooms)
    features_map = _evo_build_room_features_map(placeable_rooms)
    product_lookup = _evo_build_product_lookup(products)

    # ── 초기 인구 구성 ──
    population = []

    # 시드 추가
    for s in seeds:
        score = evaluate_layout_metrics(s, rooms)["total"]
        population.append({"placements": _evo_copy.deepcopy(s), "score": score})

    # 시드를 돌연변이시켜서 나머지 인구 채우기
    attempts = 0
    max_attempts = population_size * 10
    while len(population) < population_size and attempts < max_attempts:
        attempts += 1
        base = _evo_rng.choice(seeds)
        # 3~6회 돌연변이 적용 (더 다양한 초기 인구)
        mutant = _evo_copy.deepcopy(base)
        valid = True
        for _ in range(_evo_rng.randint(3, 6)):
            result, ok = _evo_mutate_one(mutant, rooms_map, features_map, product_lookup)
            if ok:
                mutant = result
            else:
                valid = False
                break
        if valid:
            score = evaluate_layout_metrics(mutant, rooms)["total"]
            population.append({"placements": mutant, "score": score})

    print(f"[GA] 초기 인구: {len(population)}개")

    # ── 세대 진화 ──
    best_score_ever = max(p["score"] for p in population)

    for gen in range(generations):
        # 토너먼트 선택 + 교배 + 돌연변이로 자식 생성
        children = []
        target_children = population_size // 2

        for _ in range(target_children):
            # 토너먼트 선택 (3개 중 최고)
            parent_a = _ga_tournament_select(population, k=3)
            parent_b = _ga_tournament_select(population, k=3)

            # 교배
            child = _ga_crossover(parent_a["placements"], parent_b["placements"],
                                  rooms_map, features_map, product_lookup)
            if child is None:
                continue

            # 돌연변이 (30% 확률)
            if _evo_rng.random() < 0.3:
                mutated, ok = _evo_mutate_one(child, rooms_map, features_map, product_lookup)
                if ok:
                    child = mutated

            score = evaluate_layout_metrics(child, rooms)["total"]
            children.append({"placements": child, "score": score})

        # 부모 + 자식 합쳐서 상위 population_size개만 생존
        combined = population + children
        combined.sort(key=lambda x: x["score"], reverse=True)
        population = combined[:population_size]

        gen_best = population[0]["score"]
        if gen_best > best_score_ever:
            best_score_ever = gen_best

    # 상위 5개 반환 (다양성 보장)
    population.sort(key=lambda x: x["score"], reverse=True)
    diverse_top = _ga_select_diverse_top_n(population, n=5, min_diff=800.0)
    top_n = [p["placements"] for p in diverse_top]

    return {
        "population": population,
        "best_score": best_score_ever,
        "top_n": top_n,
    }


def _ga_tournament_select(population, k=3):
    """토너먼트 선택: k개 중 최고 점수 개체."""
    selected = _evo_rng.sample(population, min(k, len(population)))
    return max(selected, key=lambda x: x["score"])


def _ga_crossover(parent_a, parent_b, rooms_map, features_map, product_lookup):
    """방 단위 교배: 일부 방은 A에서, 나머지는 B에서 가져옴."""
    # 방 ID 목록 추출
    rooms_a = {}
    for p in parent_a:
        rooms_a.setdefault(p["room_id"], []).append(p)
    rooms_b = {}
    for p in parent_b:
        rooms_b.setdefault(p["room_id"], []).append(p)

    all_room_ids = list(set(list(rooms_a.keys()) + list(rooms_b.keys())))
    if not all_room_ids:
        return None

    # 각 방을 A 또는 B에서 랜덤 선택
    child_placements = []
    used_models = set()

    for rid in all_room_ids:
        source = _evo_rng.choice([rooms_a, rooms_b])
        room_pls = source.get(rid, [])
        for p in room_pls:
            if p["model"] not in used_models:
                child_placements.append(_evo_copy.deepcopy(p))
                used_models.add(p["model"])

    # A와 B 모두에서 빠진 제품 보충 (어느 한쪽에서 가져오기)
    for p in parent_a + parent_b:
        if p["model"] not in used_models:
            child_placements.append(_evo_copy.deepcopy(p))
            used_models.add(p["model"])

    # 자식의 유효성 검증 (겹침 체크)
    for pl in child_placements:
        product = product_lookup.get(pl["model"])
        room = rooms_map.get(pl["room_id"])
        if not product or not room:
            continue
        features = features_map.get(pl["room_id"], [])
        others = _evo_get_others_in_room(child_placements, pl["room_id"], pl["model"], product_lookup)
        if not _evo_is_valid(pl["x_mm"], pl["y_mm"], pl["rotation"], product, room, features, others, list(rooms_map.values())):
            # 겹치면 돌연변이로 새 위치 찾기
            temp_state = _evo_copy.deepcopy(child_placements)
            for _ in range(5):
                result, ok = _evo_mutate_one(temp_state, rooms_map, features_map, product_lookup)
                if ok:
                    child_placements = result
                    break

    return child_placements


def _ga_deduplicate(population, min_diff=300.0):
    """너무 비슷한 배치안 제거. 좌표 차이 합이 min_diff 미만이면 중복."""
    unique = []
    for p in population:
        is_dup = False
        for u in unique:
            diff = _ga_layout_distance(p["placements"], u["placements"])
            if diff < min_diff:
                is_dup = True
                break
        if not is_dup:
            unique.append(p)
    return unique


def _ga_select_diverse_top_n(population, n=5, min_diff=800.0):
    """점수 + 다양성을 동시에 고려하여 상위 N개를 선택.

    1순위: 전체 최고 점수 후보
    2~N순위: 이미 선택된 배치안들과 최소 min_diff 이상 차이나는 것 중 점수 최고
    min_diff를 점진적으로 완화하면서 N개를 채움.
    """
    if not population:
        return []

    sorted_pop = sorted(population, key=lambda x: x["score"], reverse=True)
    selected = [sorted_pop[0]]  # 1위는 무조건 포함

    for threshold in [min_diff, min_diff * 0.6, min_diff * 0.3, 100.0, 0.0]:
        if len(selected) >= n:
            break
        for candidate in sorted_pop:
            if any(id(candidate) == id(s) for s in selected):
                continue
            # 이미 선택된 모든 배치안과의 최소 거리 계산
            min_dist = min(
                _ga_layout_distance(candidate["placements"], s["placements"])
                for s in selected
            )
            if min_dist >= threshold:
                selected.append(candidate)
                if len(selected) >= n:
                    break

    return selected


def _ga_layout_distance(pls_a, pls_b):
    """두 배치안의 총 좌표 차이. 방 이동/회전에 높은 가중치."""
    map_b = {p["model"]: p for p in pls_b}
    total = 0.0
    count = 0
    for pa in pls_a:
        pb = map_b.get(pa["model"])
        if pb:
            total += abs(pa["x_mm"] - pb["x_mm"]) + abs(pa["y_mm"] - pb["y_mm"])
            if pa["rotation"] != pb["rotation"]:
                total += 500  # 회전 다르면 큰 거리
            if pa["room_id"] != pb["room_id"]:
                total += 2000  # 방이 다르면 매우 큰 거리
            count += 1
        else:
            total += 2000
    return total


# ── 적응형 SA (재가열 포함) ──

def _sa_optimize_layout(initial_placements, rooms, products,
                        t_initial=15.0, cooling_rate=0.995,
                        max_iterations=500, max_retries=5,
                        reheat=False):
    """적응형 시뮬레이티드 어닐링. reheat=True면 막힐 때 재가열."""
    placeable_rooms = [r for r in rooms if r.get("is_placeable", True)]
    rooms_map = _evo_build_room_lookup(placeable_rooms)
    features_map = _evo_build_room_features_map(placeable_rooms)
    product_lookup = _evo_build_product_lookup(products)

    state = _evo_copy.deepcopy(initial_placements)
    current_score = evaluate_layout_metrics(state, rooms)["total"]
    best_state = _evo_copy.deepcopy(state)
    best_score = current_score
    initial_score = current_score

    t = t_initial
    no_improve = 0
    reheat_count = 0
    max_reheats = 3 if reheat else 0

    for iteration in range(max_iterations):
        # 이웃 생성
        neighbor = None
        for _ in range(max_retries):
            cand, ok = _evo_mutate_one(state, rooms_map, features_map, product_lookup)
            if ok:
                neighbor = cand
                break

        if neighbor is None:
            t *= cooling_rate
            no_improve += 1
        else:
            n_score = evaluate_layout_metrics(neighbor, rooms)["total"]
            delta = n_score - current_score

            if delta > 0 or (t > 0.01 and _evo_rng.random() < _evo_math.exp(delta / t)):
                state = neighbor
                current_score = n_score
                if current_score > best_score:
                    best_state = _evo_copy.deepcopy(state)
                    best_score = current_score
                    no_improve = 0
                else:
                    no_improve += 1
            else:
                no_improve += 1

            t *= cooling_rate

        # 재가열: 50회 개선 없으면 온도 다시 올리기
        if reheat and no_improve >= 50 and reheat_count < max_reheats:
            t = t_initial * (0.7 ** (reheat_count + 1))  # 점점 낮은 온도로 재가열
            state = _evo_copy.deepcopy(best_state)  # 최고 상태에서 다시 시작
            current_score = best_score
            no_improve = 0
            reheat_count += 1

        # 종료 조건
        if no_improve > 80 and (not reheat or reheat_count >= max_reheats):
            break

    print(f"[SA] {initial_score:.1f} → {best_score:.1f} "
          f"(iter={iteration+1}, reheats={reheat_count})")
    return best_state
