import json
import random
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from db import get_db
from models import (
    FloorPlanOut, FloorPlanRoomOut, SessionCreate, SessionOut,
    AutoPlaceRequest, AutoPlaceResponse, PlacementOut, ProductOut,
)


class GenerateLayoutsRequest(BaseModel):
    product_ids: list[int]


class ApplyLayoutPlacement(BaseModel):
    room_id: int
    product_id: int
    x_mm: float
    y_mm: float
    rotation: int = 0


class ApplyLayoutRequest(BaseModel):
    layout_id: int
    placements: list[ApplyLayoutPlacement]

router = APIRouter(prefix="/api", tags=["floor_plans"])

# 제품 조회용 기본 쿼리 (별칭으로 하위 서비스 호환성 유지)
# PostgreSQL 컬럼 매핑 (별칭으로 하위 서비스 호환성 유지):
#   product_category → category (세부), category → product_type (대분류)
_PRODUCT_SELECT = """
    SELECT p.product_id, p.model_id AS model, p.product_name AS name,
           p.product_category AS category, p.category AS product_type, p.brand,
           p.original_price AS list_price, p.discount_rate,
           p.discount_price AS price, p.review_score,
           p.review_cnt AS review_count, p.product_url AS url,
           p.product_image_url AS image_url,
           ps.width AS width_mm, ps.height AS height_mm, ps.depth AS depth_mm,
           COALESCE(pp.is_placeable, true) AS is_placeable,
           COALESCE(pp.mount_type, 'floor') AS mount_type
    FROM product p
    LEFT JOIN product_spec ps ON p.product_id = ps.product_id
    LEFT JOIN product_placement_info pp ON p.product_id = pp.product_id
"""


# --- Floor Plans ---

@router.get("/floor-plans", response_model=list[FloorPlanOut])
def list_floor_plans():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM floor_plan WHERE is_active = true ORDER BY floor_plan_id")
        plans = cur.fetchall()
        result = []
        for p in plans:
            rooms = _get_rooms(conn, p["floor_plan_id"])
            result.append(_plan_to_out(p, rooms))
        return result


@router.get("/floor-plans/{plan_id}", response_model=FloorPlanOut)
def get_floor_plan(plan_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM floor_plan WHERE floor_plan_id = %s", (plan_id,))
        p = cur.fetchone()
        if not p:
            raise HTTPException(404, "Floor plan not found")
        rooms = _get_rooms(conn, plan_id)
        return _plan_to_out(p, rooms)


# --- Sessions (placement_group) ---

@router.post("/sessions", response_model=SessionOut)
def create_session(body: SessionCreate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT floor_plan_id FROM floor_plan WHERE floor_plan_id = %s", (body.floor_plan_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Floor plan not found")
        cur.execute(
            "INSERT INTO placement_group (user_id, floor_plan_id, group_name) "
            "VALUES (%s, %s, %s) RETURNING group_id",
            (body.user_id, body.floor_plan_id, body.session_name),
        )
        group_id = cur.fetchone()["group_id"]
        return _get_session_out(conn, group_id)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: int):
    with get_db() as conn:
        return _get_session_out(conn, session_id)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT group_id FROM placement_group WHERE group_id = %s", (session_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Session not found")
        cur.execute("DELETE FROM placement_group WHERE group_id = %s", (session_id,))
        return {"ok": True}


# --- Random Test Set ---

TEST_SET_CONFIGS = {
    "small": {
        "appliance": [("냉장고", 1), ("전기레인지", 1), ("에어컨", 1), ("세탁기", 1)],
        "furniture": [("침대", 1), ("책상", 1), ("의자", 1), ("옷장·행거", 1)],
    },
    "medium": {
        "appliance": [
            ("냉장고", 1), ("전기레인지", 1), ("TV", 1), ("에어컨", 1),
            ("세탁기", 1), ("의류건조기", 1), ("정수기", 1), ("광파오븐/전자레인지", 1),
        ],
        "furniture": [
            ("침대", 1), ("소파", 1), ("식탁·테이블", 1),
            ("의자", 2), ("책상", 1), ("옷장·행거", 1),
        ],
    },
    "large": {
        "appliance": [
            ("냉장고", 1), ("전기레인지", 1), ("TV", 1), ("에어컨", 1),
            ("세탁기", 1), ("의류건조기", 1), ("식기세척기", 1), ("정수기", 1),
            ("의류관리기", 1), ("광파오븐/전자레인지", 1),
        ],
        "furniture": [
            ("침대", 1), ("소파", 1), ("식탁·테이블", 1),
            ("의자", 2), ("책상", 1), ("옷장·행거", 1), ("화장대·콘솔", 1),
        ],
    },
}


@router.get("/floor-plans/{plan_id}/test-set")
def get_test_set(plan_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM floor_plan WHERE floor_plan_id = %s", (plan_id,))
        plan = cur.fetchone()
        if not plan:
            raise HTTPException(404, "Floor plan not found")

        area = plan["total_area_m2"] or 0
        if area < 40:
            size = "small"
        elif area < 70:
            size = "medium"
        else:
            size = "large"

        config = TEST_SET_CONFIGS[size]
        selected = []

        for product_type in ("appliance", "furniture"):
            for category, count in config[product_type]:
                cur.execute(
                    f"{_PRODUCT_SELECT} WHERE p.product_category = %s AND LOWER(p.category) = LOWER(%s) "
                    f"AND COALESCE(pp.is_placeable, true) = true",
                    (category, product_type),
                )
                rows = cur.fetchall()
                if rows:
                    ids = [r["product_id"] for r in rows]
                    picked = random.sample(ids, min(count, len(ids)))
                    selected.extend(picked)

        return {"size": size, "product_ids": selected, "count": len(selected)}


# --- Floor Plan Level Auto-Place ---

@router.post("/sessions/{session_id}/auto-place", response_model=AutoPlaceResponse)
def auto_place_floor_plan(session_id: int, body: AutoPlaceRequest):
    with get_db() as conn:
        cur = conn.cursor()
        session = _get_session_row(cur, session_id)
        plan_id = session["floor_plan_id"]

        cur.execute(
            "SELECT * FROM floor_plan_room WHERE floor_plan_id = %s ORDER BY room_id", (plan_id,)
        )
        rooms = cur.fetchall()

        # 기존 배치 삭제
        cur.execute("DELETE FROM placement WHERE group_id = %s", (session_id,))

        # 제품 조회
        products = []
        for pid in body.product_ids:
            cur.execute(f"{_PRODUCT_SELECT} WHERE p.product_id = %s AND COALESCE(pp.is_placeable, true) = true", (pid,))
            p = cur.fetchone()
            if p:
                products.append(dict(p))

        # 자동 배치 실행
        from services.placement_engine import auto_place_floor_plan as _engine
        rooms_dicts = [dict(r) for r in rooms]
        # features 파싱 (jsonb → 이미 dict/list)
        for rd in rooms_dicts:
            rd["features"] = rd["features"] if isinstance(rd["features"], list) else []
            # 호환성: id 필드 추가
            rd["id"] = rd["room_id"]
        result = _engine(rooms_dicts, products)

        # 저장 및 검증
        from services.constraint_validator import validate_single_placement
        placed = []
        for p in result["placements"]:
            cur.execute("SELECT * FROM floor_plan_room WHERE room_id = %s", (p["room_id"],))
            room = cur.fetchone()
            features = room["features"] if isinstance(room["features"], list) else []

            # 제품 조회
            cur.execute(f"{_PRODUCT_SELECT} WHERE p.model_id = %s", (p["model"],))
            product = cur.fetchone()
            if not product:
                continue
            product_id = product["product_id"]

            # 기존 배치 조회
            cur.execute(
                "SELECT pl.*, ps.width AS pw, ps.depth AS pd, pr.category, "
                "COALESCE(pp.mount_type, 'floor') AS mount_type "
                "FROM placement pl "
                "JOIN product pr ON pl.product_id = pr.product_id "
                "LEFT JOIN product_spec ps ON pl.product_id = ps.product_id "
                "LEFT JOIN product_placement_info pp ON pl.product_id = pp.product_id "
                "WHERE pl.group_id = %s AND pl.room_id = %s",
                (session_id, p["room_id"]),
            )
            existing = cur.fetchall()

            violations = validate_single_placement(
                p["x_mm"], p["y_mm"], p["rotation"],
                product, room, features, existing
            )
            is_valid = len(violations) == 0

            cur.execute(
                "INSERT INTO placement (group_id, room_id, product_id, x_mm, y_mm, rotation, is_valid, violations) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING placement_id",
                (session_id, p["room_id"], product_id, p["x_mm"], p["y_mm"], p["rotation"],
                 is_valid, json.dumps(violations, ensure_ascii=False)),
            )
            new_id = cur.fetchone()["placement_id"]
            product_out = ProductOut(
                product_id=product["product_id"],
                model_id=product["model"],
                name=product["name"],
                category=product["category"],
                product_type=product.get("product_type", "appliance"),
                brand=product.get("brand"),
                list_price=product.get("list_price"),
                discount_rate=product.get("discount_rate"),
                price=product.get("price"),
                review_score=product.get("review_score"),
                review_count=product.get("review_count"),
                url=product.get("url"),
                image_url=product.get("image_url"),
                width_mm=product.get("width_mm"),
                height_mm=product.get("height_mm"),
                depth_mm=product.get("depth_mm"),
                is_placeable=product.get("is_placeable", True),
                mount_type=product.get("mount_type", "floor"),
            )
            placed.append(PlacementOut(
                id=new_id, session_id=session_id, room_id=p["room_id"],
                product_id=product_id, x_mm=p["x_mm"], y_mm=p["y_mm"],
                rotation=p["rotation"], is_valid=is_valid, violations=violations,
                product=product_out,
            ))

        return AutoPlaceResponse(placements=placed, warnings=result.get("warnings", []))


# --- AI Explanation ---

@router.post("/sessions/{session_id}/explain")
def explain_placement(session_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        session = _get_session_row(cur, session_id)

        cur.execute("SELECT * FROM floor_plan WHERE floor_plan_id = %s", (session["floor_plan_id"],))
        plan = cur.fetchone()
        if not plan:
            raise HTTPException(404, "Floor plan not found")

        cur.execute(
            "SELECT * FROM floor_plan_room WHERE floor_plan_id = %s ORDER BY room_id",
            (plan["floor_plan_id"],),
        )
        rooms = cur.fetchall()

        rooms_data = []
        for room in rooms:
            features = room["features"] if isinstance(room["features"], list) else []

            cur.execute(
                "SELECT pl.x_mm, pl.y_mm, pl.rotation, "
                "pr.product_name AS product_name, pr.category, pr.model_id AS model "
                "FROM placement pl JOIN product pr ON pl.product_id = pr.product_id "
                "WHERE pl.group_id = %s AND pl.room_id = %s ORDER BY pl.placement_id",
                (session_id, room["room_id"]),
            )
            placements = cur.fetchall()

            room_dict = dict(room)
            room_dict["id"] = room_dict["room_id"]
            rooms_data.append({
                "room": room_dict,
                "features": features,
                "placements": [dict(pl) for pl in placements],
            })

        plan_dict = dict(plan)
        plan_dict["id"] = plan_dict["floor_plan_id"]
        from services.ai_explanation import generate_explanation_stream

        def event_stream():
            for chunk in generate_explanation_stream(plan_dict, rooms_data):
                yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")


# --- Helpers ---

def _get_rooms(conn, plan_id: int) -> list[FloorPlanRoomOut]:
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM floor_plan_room WHERE floor_plan_id = %s ORDER BY room_id", (plan_id,)
    )
    return [_room_to_out(r) for r in cur.fetchall()]


def _room_to_out(r) -> FloorPlanRoomOut:
    features = r["features"] if isinstance(r["features"], list) else []
    return FloorPlanRoomOut(
        id=r["room_id"], floor_plan_id=r["floor_plan_id"],
        name=r["name"], room_type=r["room_type"],
        x_mm=r["x_mm"], y_mm=r["y_mm"],
        width_mm=r["width_mm"], height_mm=r["height_mm"],
        is_placeable=bool(r["is_placeable"]),
        features=features,
    )


def _plan_to_out(p, rooms: list[FloorPlanRoomOut]) -> FloorPlanOut:
    return FloorPlanOut(
        id=p["floor_plan_id"], name=p["name"], category=p["category"],
        total_area_m2=p["total_area_m2"],
        total_width_mm=p["total_width_mm"], total_height_mm=p["total_height_mm"],
        thumbnail_url=p["thumbnail_url"], is_active=bool(p["is_active"]),
        rooms=rooms,
    )


def _get_session_row(cur, session_id: int):
    cur.execute("SELECT * FROM placement_group WHERE group_id = %s", (session_id,))
    s = cur.fetchone()
    if not s:
        raise HTTPException(404, "Session not found")
    return s


def _get_session_out(conn, session_id: int) -> SessionOut:
    cur = conn.cursor()
    s = _get_session_row(cur, session_id)
    cur.execute("SELECT * FROM floor_plan WHERE floor_plan_id = %s", (s["floor_plan_id"],))
    p = cur.fetchone()
    rooms = _get_rooms(conn, s["floor_plan_id"])
    floor_plan = _plan_to_out(p, rooms) if p else None
    return SessionOut(
        id=s["group_id"], floor_plan_id=s["floor_plan_id"],
        session_name=s["group_name"], floor_plan=floor_plan,
    )


# --- Multi-Layout Generation & Application ---

@router.post("/sessions/{session_id}/generate-layouts")
def generate_layouts(session_id: int, body: GenerateLayoutsRequest):
    with get_db() as conn:
        cur = conn.cursor()
        session = _get_session_row(cur, session_id)
        floor_plan_id = session["floor_plan_id"]

        cur.execute("SELECT * FROM floor_plan_room WHERE floor_plan_id = %s", (floor_plan_id,))
        rooms = [dict(r) for r in cur.fetchall()]
        for r in rooms:
            r["features"] = r["features"] if isinstance(r["features"], list) else []
            r["id"] = r["room_id"]

        products = []
        for pid in body.product_ids:
            cur.execute(f"{_PRODUCT_SELECT} WHERE p.product_id = %s AND COALESCE(pp.is_placeable, true) = true", (pid,))
            p = cur.fetchone()
            if p:
                products.append(dict(p))

        if not products:
            raise HTTPException(400, "No valid products found")

        from services.placement_engine import generate_multiple_layouts
        from services.ai_evaluator import evaluate_layouts_with_ai

        layouts = generate_multiple_layouts(rooms, products)

        # 엔진 결과에 product 정보 추가 (model → 전체 product 정보)
        model_to_product = {p["model"]: p for p in products}
        for layout in layouts:
            enriched = []
            for pl in layout.get("placements", []):
                product = model_to_product.get(pl.get("model"))
                if not product:
                    continue
                pl["product_id"] = product["product_id"]
                pl["product"] = {
                    "product_id": product["product_id"],
                    "model_id": product["model"],
                    "name": product["name"],
                    "category": product["category"],
                    "product_type": product.get("product_type", "appliance"),
                    "brand": product.get("brand"),
                    "list_price": product.get("list_price"),
                    "discount_rate": product.get("discount_rate"),
                    "price": product.get("price"),
                    "image_url": product.get("image_url"),
                    "width_mm": product.get("width_mm"),
                    "height_mm": product.get("height_mm"),
                    "depth_mm": product.get("depth_mm"),
                    "is_placeable": product.get("is_placeable", True),
                    "mount_type": product.get("mount_type", "floor"),
                }
                enriched.append(pl)
            layout["placements"] = enriched

        ai_eval = evaluate_layouts_with_ai(layouts, rooms)

        return {"layouts": layouts, "ai_evaluation": ai_eval}


@router.post("/sessions/{session_id}/apply-layout")
def apply_layout(session_id: int, body: ApplyLayoutRequest):
    with get_db() as conn:
        cur = conn.cursor()
        _get_session_row(cur, session_id)

        cur.execute("DELETE FROM placement WHERE group_id = %s", (session_id,))

        placed = []
        for p in body.placements:
            cur.execute(
                "INSERT INTO placement (group_id, room_id, product_id, x_mm, y_mm, rotation, is_valid, violations) "
                "VALUES (%s, %s, %s, %s, %s, %s, true, '[]'::jsonb) RETURNING placement_id",
                (session_id, p.room_id, p.product_id, p.x_mm, p.y_mm, p.rotation),
            )
            new_id = cur.fetchone()["placement_id"]
            placed.append({
                "id": new_id, "session_id": session_id,
                "room_id": p.room_id, "product_id": p.product_id,
                "x_mm": p.x_mm, "y_mm": p.y_mm,
                "rotation": p.rotation, "is_valid": True, "violations": [],
            })

        return {"ok": True, "placements": placed}


# --- 3D Image Generation (DALL-E 3) ---

ROOM_TYPE_KR = {
    "living": "거실", "kitchen": "주방", "bedroom": "침실",
    "bathroom": "욕실", "utility": "세탁실/유틸리티", "balcony": "발코니",
}

def _wall_label(wall: str, room_w: float, room_h: float, x: float, y: float) -> str:
    """배치 좌표를 기반으로 벽/위치 설명을 생성."""
    cx, cy = room_w / 2, room_h / 2
    near_left = x < room_w * 0.25
    near_right = x > room_w * 0.75
    near_top = y < room_h * 0.25
    near_bottom = y > room_h * 0.75

    parts = []
    if near_top:
        parts.append("north wall")
    elif near_bottom:
        parts.append("south wall")
    if near_left:
        parts.append("west side")
    elif near_right:
        parts.append("east side")
    if not parts:
        parts.append("center")
    return ", ".join(parts)


INTERIOR_STYLE_MAP = {
    "모던/미니멀(화이트&블랙)": "Modern minimalist style: white and black color scheme, sleek furniture, clean lines, marble or glossy surfaces, monochrome accents.",
    "내추럴/우드(따뜻하고 편안한)": "Natural wood style: warm wood tones throughout, cozy and comfortable atmosphere, rattan/woven textures, indoor plants, soft earth-tone fabrics.",
    "컬러풀/포인트(개성있는)": "Colorful accent style: bold color pops on furniture and decor, unique personality-driven design, vibrant cushions and art pieces, playful patterns.",
}


def _build_3d_prompt(plan, rooms, placements_by_room, interior_style: str | None = None) -> str:
    """배치 데이터를 기반으로 상세 3D 프롬프트를 생성."""
    area = plan["total_area_m2"] or 0
    plan_name = plan["name"] if isinstance(plan["name"], str) else str(plan["name"])
    total_w = round(plan["total_width_mm"] / 1000, 1)
    total_h = round(plan["total_height_mm"] / 1000, 1)

    # 인테리어 스타일 설명
    style_desc = INTERIOR_STYLE_MAP.get(
        interior_style or "",
        "Modern Korean interior style: warm wood flooring, white walls, natural daylight from windows.",
    )

    lines = [
        f"Create a photorealistic 3D interior rendering of a {area}m² Korean apartment ({plan_name}).",
        f"The apartment is {total_w}m wide and {total_h}m deep.",
        f"Interior design: {style_desc}",
        "Top-down bird's-eye view from directly above (90-degree angle), showing all rooms clearly.",
        "",
        "ROOM LAYOUT AND FURNITURE PLACEMENT:",
    ]

    ROOM_TYPE_DESC = {
        "living": "living room",
        "kitchen": "kitchen",
        "bedroom": "bedroom",
        "bathroom": "bathroom",
        "utility": "utility/laundry room",
        "balcony": "balcony",
    }

    FEATURE_DESC = {
        "door": "door",
        "window": "window",
        "water_hookup": "water supply point",
        "gas_line": "gas line",
        "fixture": "built-in fixture",
    }

    WALL_KR = {"north": "north", "south": "south", "east": "east", "west": "west"}

    # 가구가 있는 방을 먼저, 없는 방은 간략하게
    SKIP_TYPES = {"bathroom", "balcony"}  # 가구 없으면 생략할 방 유형
    rooms_with_furniture = []
    rooms_without = []

    for room in rooms:
        room_id = room["room_id"] if "room_id" in room else room.get("id")
        pls = placements_by_room.get(room_id, [])
        if pls:
            rooms_with_furniture.append((room, pls))
        else:
            rooms_without.append(room)

    for room, pls in rooms_with_furniture:
        room_name = room.get("name", "")
        room_type = room.get("room_type", "")
        w_m = round(room["width_mm"] / 1000, 1)
        h_m = round(room["height_mm"] / 1000, 1)
        type_desc = ROOM_TYPE_DESC.get(room_type, room_type)

        # 창문만 간략히 표시
        features = room.get("features", [])
        if not isinstance(features, list):
            features = []
        windows = [f for f in features if f.get("type") == "window"]
        window_str = f", {len(windows)} window(s)" if windows else ""

        items = []
        for pl in pls:
            name = pl.get("name", "")
            cat = pl.get("category", "")
            if not cat:
                prod = pl.get("product")
                cat = prod.get("category", "unknown") if prod else "unknown"
                name = name or (prod.get("name", "") if prod else "")
            label = cat if cat else name  # 카테고리만 사용 (간결)
            pos_desc = _wall_label("", room["width_mm"], room["height_mm"], pl.get("x_mm", 0), pl.get("y_mm", 0))
            items.append(f"{label} ({pos_desc})")

        items_str = ", ".join(items)
        lines.append(f"- {room_name} ({w_m}x{h_m}m{window_str}): {items_str}")

    # 빈 방은 한 줄로 요약 (작은 방은 생략)
    non_skip = [r for r in rooms_without if r.get("room_type", "") not in SKIP_TYPES]
    if non_skip:
        names = [r.get("name", "") for r in non_skip]
        lines.append(f"- Other rooms (empty): {', '.join(names)}")

    lines.append("")
    lines.append("CRITICAL: You MUST exactly replicate the furniture positions shown in the attached 2D floor plan image. Every piece of furniture must be placed in the same location as the 2D layout - do NOT move, rearrange, or reposition any item.")
    lines.append("IMPORTANT: Match the exact room positions, proportions, and wall features (windows, doors) from the attached 2D floor plan.")
    lines.append("Show windows with natural light coming in, doors in correct positions, and all furniture exactly where shown in the 2D plan.")
    lines.append("Photorealistic quality, soft ambient lighting, no text or labels or annotations.")

    return "\n".join(lines)


class OtherPlacement(BaseModel):
    product_id: int
    x_mm: float
    y_mm: float
    rotation: int = 0


class ValidateMoveRequest(BaseModel):
    product_id: int
    x_mm: float
    y_mm: float
    rotation: int = 0
    others: list[OtherPlacement] = []  # 같은 방의 다른 제품 현재 위치


@router.post("/sessions/{session_id}/rooms/{room_id}/validate-move")
def validate_move(session_id: int, room_id: int, body: ValidateMoveRequest):
    """드래그 완료 시 단일 제품 배치 검증. 프론트에서 전달한 현재 상태 기반."""
    from services.constraint_validator import validate_single_placement

    with get_db() as conn:
        cur = conn.cursor()
        _get_session_row(cur, session_id)

        cur.execute("SELECT * FROM floor_plan_room WHERE room_id = %s", (room_id,))
        room = cur.fetchone()
        if not room:
            raise HTTPException(404, "Room not found")

        features = room["features"] if isinstance(room["features"], list) else []

        cur.execute(f"{_PRODUCT_SELECT} WHERE p.product_id = %s", (body.product_id,))
        product = cur.fetchone()
        if not product:
            raise HTTPException(404, "Product not found")

        # 프론트에서 전달한 같은 방의 다른 제품들로 others 구성
        others_for_validate = []
        for o in body.others:
            cur.execute(f"{_PRODUCT_SELECT} WHERE p.product_id = %s", (o.product_id,))
            o_prod = cur.fetchone()
            if o_prod:
                others_for_validate.append({
                    "id": o.product_id,
                    "x_mm": o.x_mm, "y_mm": o.y_mm,
                    "rotation": o.rotation,
                    "pw": o_prod["width_mm"], "pd": o_prod["depth_mm"],
                    "category": o_prod["category"],
                    "mount_type": o_prod.get("mount_type", "floor"),
                })

        violations = validate_single_placement(
            body.x_mm, body.y_mm, body.rotation,
            product, room, features, others_for_validate,
        )

        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
        }


class Generate3DRequest(BaseModel):
    canvas_image: str | None = None  # Base64 PNG of 2D canvas (optional)
    interior_style: str | None = None  # 인테리어 스타일 (모던/미니멀, 내추럴/우드, 컬러풀/포인트)


@router.post("/sessions/{session_id}/generate-3d")
def generate_3d_image(session_id: int, body: Generate3DRequest | None = None):
    """현재 배치 상태를 기반으로 gpt-image-1 이미지 생성 (2D 캔버스 참조)."""
    import base64
    import io
    from openai import OpenAI
    from services.ai_explanation import OPENAI_API_KEY

    with get_db() as conn:
        cur = conn.cursor()
        session = _get_session_row(cur, session_id)
        plan_id = session["floor_plan_id"]

        cur.execute("SELECT * FROM floor_plan WHERE floor_plan_id = %s", (plan_id,))
        plan = cur.fetchone()
        if not plan:
            raise HTTPException(404, "Floor plan not found")

        cur.execute("SELECT * FROM floor_plan_room WHERE floor_plan_id = %s ORDER BY room_id", (plan_id,))
        rooms = cur.fetchall()

        cur.execute(
            "SELECT pl.room_id, pl.x_mm, pl.y_mm, pl.rotation, "
            "p.product_category AS category, p.product_name AS name "
            "FROM placement pl "
            "JOIN product p ON pl.product_id = p.product_id "
            "WHERE pl.group_id = %s",
            (session_id,),
        )
        all_pls = cur.fetchall()

        placements_by_room = {}
        for pl in all_pls:
            rid = pl["room_id"]
            placements_by_room.setdefault(rid, []).append(dict(pl))

    interior_style = body.interior_style if body else None
    prompt = _build_3d_prompt(dict(plan), [dict(r) for r in rooms], placements_by_room, interior_style)

    client = OpenAI(api_key=OPENAI_API_KEY)

    # Canvas 이미지가 있으면 참조 이미지로 함께 전송
    canvas_b64 = body.canvas_image if body else None
    if canvas_b64 and canvas_b64.startswith("data:"):
        canvas_b64 = canvas_b64.split(",", 1)[1]

    try:
        result_b64 = None

        # 1차: Canvas 이미지가 있으면 Responses API로 시도
        if canvas_b64:
            try:
                full_prompt = (
                    "Look at this 2D floor plan image carefully. Generate a photorealistic 3D interior rendering "
                    "that exactly matches this floor plan layout. Every room and every piece of furniture must be "
                    "in the exact same position as shown. "
                    f"{prompt}"
                )
                data_url = f"data:image/png;base64,{canvas_b64}"
                response = client.responses.create(
                    model="gpt-4o",
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_image", "image_url": data_url},
                                {"type": "input_text", "text": full_prompt},
                            ],
                        },
                    ],
                    tools=[{"type": "image_generation", "size": "1536x1024", "quality": "medium"}],
                )
                for item in response.output:
                    if item.type == "image_generation_call" and item.result:
                        result_b64 = item.result
                        break
            except Exception as e:
                print(f"[3D] Responses API failed, falling back to gpt-image-1: {e}")

        # 2차: Responses API 실패 또는 Canvas 없으면 gpt-image-1 직접 생성
        if not result_b64:
            response = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size="1536x1024",
                quality="medium",
                n=1,
            )
            result_b64 = response.data[0].b64_json

        if result_b64:
            image_url = f"data:image/png;base64,{result_b64}"
        else:
            image_url = response.data[0].url

        return {"image_url": image_url, "prompt": prompt}
    except Exception as e:
        raise HTTPException(500, f"Image generation failed: {str(e)}")


# ──────────────────────────────────────────────
#  스냅샷 저장 / 조회
# ──────────────────────────────────────────────

class SaveSnapshotRequest(BaseModel):
    snapshot_2d: str | None = None      # Base64 PNG
    snapshot_3d_url: str | None = None  # DALL-E image URL


@router.get("/snapshots")
def list_snapshots(user_id: int = None):
    """저장된 스냅샷이 있는 세션 목록 조회."""
    with get_db() as conn:
        cur = conn.cursor()
        params = []
        query_extra = ""
        if user_id is not None:
            query_extra = " AND pg.user_id = %s"
            params.append(user_id)
        full_query = """
            SELECT pg.group_id, pg.group_name, pg.saved_at, pg.user_id,
                   pg.snapshot_2d IS NOT NULL AS has_2d,
                   pg.snapshot_3d_url IS NOT NULL AS has_3d,
                   pg.snapshot_2d,
                   pg.snapshot_3d_url,
                   fp.name AS floor_plan_name, fp.category, fp.total_area_m2
            FROM placement_group pg
            JOIN floor_plan fp ON fp.floor_plan_id = pg.floor_plan_id
            WHERE (pg.snapshot_2d IS NOT NULL OR pg.snapshot_3d_url IS NOT NULL)
        """ + query_extra + " ORDER BY pg.saved_at DESC NULLS LAST"
        cur.execute(full_query, params)
        rows = cur.fetchall()
        return [
            {
                "session_id": r["group_id"],
                "session_name": r["group_name"],
                "floor_plan_name": r["floor_plan_name"],
                "category": r["category"],
                "area_m2": float(r["total_area_m2"]) if r["total_area_m2"] else None,
                "has_2d": r["has_2d"],
                "has_3d": r["has_3d"],
                "snapshot_2d": r["snapshot_2d"],
                "snapshot_3d_url": r["snapshot_3d_url"],
                "saved_at": r["saved_at"].isoformat() if r["saved_at"] else None,
            }
            for r in rows
        ]


@router.put("/sessions/{session_id}/snapshot")
def save_snapshot(session_id: int, body: SaveSnapshotRequest):
    """2D / 3D 스냅샷을 placement_group에 저장."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT group_id FROM placement_group WHERE group_id = %s", (session_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Session not found")

        updates = []
        values = []
        if body.snapshot_2d is not None:
            updates.append("snapshot_2d = %s")
            values.append(body.snapshot_2d)
        if body.snapshot_3d_url is not None:
            updates.append("snapshot_3d_url = %s")
            values.append(body.snapshot_3d_url)

        if not updates:
            raise HTTPException(400, "No data to save")

        updates.append("saved_at = NOW()")
        values.append(session_id)

        cur.execute(
            f"UPDATE placement_group SET {', '.join(updates)} WHERE group_id = %s",
            values,
        )
        conn.commit()
        return {"message": "Snapshot saved", "session_id": session_id}


@router.get("/sessions/{session_id}/snapshot")
def get_snapshot(session_id: int):
    """저장된 스냅샷 조회."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT snapshot_2d, snapshot_3d_url, saved_at "
            "FROM placement_group WHERE group_id = %s",
            (session_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Session not found")
        return {
            "session_id": session_id,
            "snapshot_2d": row["snapshot_2d"],
            "snapshot_3d_url": row["snapshot_3d_url"],
            "saved_at": row["saved_at"],
        }


# ──────────────────────────────────────────────
#  보유 가전 → 대표 제품 ID 조회
# ──────────────────────────────────────────────

# 챗봇 라벨 → DB 카테고리 매핑
LABEL_TO_CATEGORY = {
    "세탁기": "세탁기",
    "에어컨": "에어컨",
    "냉장고": "냉장고",
    "TV": "TV",
    "전자레인지": "광파오븐/전자레인지",
    "청소기": "청소기",
    "공기청정기": "공기청정기",
    "식기세척기": "식기세척기",
    "건조기": "의류건조기",
    "정수기": "정수기",
    "스타일러": "의류관리기",
    "인덕션": "전기레인지",
    "가습기": "가습기",
    "제습기": "제습기",
    "오븐": "광파오븐/전자레인지",
}


class OwnedApplianceRequest(BaseModel):
    labels: list[str]  # ["세탁기", "TV", ...]


@router.post("/representative-products")
def get_representative_products(body: OwnedApplianceRequest):
    """보유 가전 라벨 목록 → 카테고리별 중간 크기 대표 제품 ID 반환."""
    with get_db() as conn:
        cur = conn.cursor()
        result = []

        for label in body.labels:
            category = LABEL_TO_CATEGORY.get(label, label)
            # 카테고리 내 배치 가능한 제품을 크기 순으로 정렬 후 중간값 선택
            cur.execute(
                "SELECT p.product_id, p.product_name AS name, "
                "ps.width AS width_mm, ps.depth AS depth_mm "
                "FROM product p "
                "LEFT JOIN product_spec ps ON p.product_id = ps.product_id "
                "LEFT JOIN product_placement_info pp ON p.product_id = pp.product_id "
                "WHERE p.product_category = %s "
                "AND LOWER(p.category) = 'appliance' "
                "AND COALESCE(pp.is_placeable, true) = true "
                "AND ps.width IS NOT NULL AND ps.depth IS NOT NULL "
                "ORDER BY (ps.width * ps.depth)",
                (category,),
            )
            rows = cur.fetchall()
            if rows:
                mid = len(rows) // 2
                row = rows[mid]
                result.append({
                    "label": label,
                    "category": category,
                    "product_id": row["product_id"],
                    "name": row["name"],
                    "width_mm": row["width_mm"],
                    "depth_mm": row["depth_mm"],
                })

        return result
