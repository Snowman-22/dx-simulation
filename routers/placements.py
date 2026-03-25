import json
from fastapi import APIRouter, HTTPException
from db import get_db
from models import (
    PlacementCreate, PlacementUpdate, PlacementOut, ProductOut,
    AutoPlaceRequest, AutoPlaceResponse, ValidationResult,
)

router = APIRouter(
    prefix="/api/sessions/{session_id}/rooms/{room_id}/placements",
    tags=["placements"],
)

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


@router.get("", response_model=list[PlacementOut])
def list_placements(session_id: int, room_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        _ensure(cur, session_id, room_id)
        cur.execute(
            "SELECT pl.placement_id, pl.group_id, pl.room_id, pl.product_id, "
            "pl.x_mm, pl.y_mm, pl.rotation, pl.is_valid, pl.violations, "
            "pr.product_name, pr.category, pr.product_category, pr.brand, "
            "pr.product_image_url, pr.model_id, "
            "ps.width AS pw, ps.height AS ph, ps.depth AS pd, "
            "pr.discount_price, pr.original_price, pr.discount_rate, "
            "pr.review_score, pr.review_cnt, pr.product_url, "
            "COALESCE(pp.is_placeable, true) AS is_placeable, "
            "COALESCE(pp.mount_type, 'floor') AS mount_type "
            "FROM placement pl "
            "JOIN product pr ON pl.product_id = pr.product_id "
            "LEFT JOIN product_spec ps ON pl.product_id = ps.product_id "
            "LEFT JOIN product_placement_info pp ON pl.product_id = pp.product_id "
            "WHERE pl.group_id = %s AND pl.room_id = %s ORDER BY pl.placement_id",
            (session_id, room_id),
        )
        rows = cur.fetchall()
        return [_row_to_placement(r) for r in rows]


@router.post("", response_model=PlacementOut)
def create_placement(session_id: int, room_id: int, body: PlacementCreate):
    with get_db() as conn:
        cur = conn.cursor()
        _ensure(cur, session_id, room_id)

        cur.execute(f"{_PRODUCT_SELECT} WHERE p.product_id = %s", (body.product_id,))
        product = cur.fetchone()
        if not product:
            raise HTTPException(404, "Product not found")

        cur.execute("SELECT * FROM floor_plan_room WHERE room_id = %s", (room_id,))
        room = cur.fetchone()
        others = _get_other_placements(cur, session_id, room_id)

        from services.constraint_validator import validate_single_placement
        features = room["features"] if isinstance(room["features"], list) else []
        violations = validate_single_placement(
            body.x_mm, body.y_mm, body.rotation,
            product, room, features, others
        )
        is_valid = len(violations) == 0

        if not is_valid:
            raise HTTPException(400, detail={"message": "배치 제약 위반", "violations": violations})

        cur.execute(
            "INSERT INTO placement (group_id, room_id, product_id, x_mm, y_mm, rotation, is_valid, violations) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING placement_id",
            (session_id, room_id, body.product_id, body.x_mm, body.y_mm,
             body.rotation, True, json.dumps([], ensure_ascii=False)),
        )
        new_id = cur.fetchone()["placement_id"]
        return PlacementOut(
            id=new_id, session_id=session_id, room_id=room_id,
            product_id=body.product_id, x_mm=body.x_mm, y_mm=body.y_mm,
            rotation=body.rotation, is_valid=True, violations=[],
        )


@router.put("/{placement_id}", response_model=PlacementOut)
def update_placement(session_id: int, room_id: int, placement_id: int, body: PlacementUpdate):
    with get_db() as conn:
        cur = conn.cursor()
        _ensure(cur, session_id, room_id)
        cur.execute(
            "SELECT * FROM placement WHERE placement_id = %s AND group_id = %s AND room_id = %s",
            (placement_id, session_id, room_id),
        )
        pl = cur.fetchone()
        if not pl:
            raise HTTPException(404, "Placement not found")

        cur.execute(f"{_PRODUCT_SELECT} WHERE p.product_id = %s", (pl["product_id"],))
        product = cur.fetchone()
        cur.execute("SELECT * FROM floor_plan_room WHERE room_id = %s", (room_id,))
        room = cur.fetchone()
        others = _get_other_placements(cur, session_id, room_id, exclude_id=placement_id)

        from services.constraint_validator import validate_single_placement
        features = room["features"] if isinstance(room["features"], list) else []
        violations = validate_single_placement(
            body.x_mm, body.y_mm, body.rotation,
            product, room, features, others
        )
        is_valid = len(violations) == 0

        if not is_valid:
            raise HTTPException(400, detail={"message": "배치 제약 위반", "violations": violations})

        cur.execute(
            "UPDATE placement SET x_mm=%s, y_mm=%s, rotation=%s, is_valid=%s, violations=%s "
            "WHERE placement_id=%s",
            (body.x_mm, body.y_mm, body.rotation, True,
             json.dumps([], ensure_ascii=False), placement_id),
        )
        return PlacementOut(
            id=placement_id, session_id=session_id, room_id=room_id,
            product_id=pl["product_id"], x_mm=body.x_mm, y_mm=body.y_mm,
            rotation=body.rotation, is_valid=True, violations=[],
        )


@router.delete("/{placement_id}")
def delete_placement(session_id: int, room_id: int, placement_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        _ensure(cur, session_id, room_id)
        cur.execute(
            "SELECT placement_id FROM placement WHERE placement_id = %s AND group_id = %s AND room_id = %s",
            (placement_id, session_id, room_id),
        )
        if not cur.fetchone():
            raise HTTPException(404, "Placement not found")
        cur.execute("DELETE FROM placement WHERE placement_id = %s", (placement_id,))
        return {"ok": True}


@router.post("/auto-place", response_model=AutoPlaceResponse)
def auto_place(session_id: int, room_id: int, body: AutoPlaceRequest):
    with get_db() as conn:
        cur = conn.cursor()
        _ensure(cur, session_id, room_id)
        cur.execute("SELECT * FROM floor_plan_room WHERE room_id = %s", (room_id,))
        room = cur.fetchone()
        features = room["features"] if isinstance(room["features"], list) else []

        # 이 방의 기존 배치 삭제
        cur.execute(
            "DELETE FROM placement WHERE group_id = %s AND room_id = %s",
            (session_id, room_id),
        )

        products = []
        for pid in body.product_ids:
            cur.execute(f"{_PRODUCT_SELECT} WHERE p.product_id = %s AND COALESCE(pp.is_placeable, true) = true", (pid,))
            p = cur.fetchone()
            if p:
                products.append(p)

        from services.placement_engine import auto_place_products
        room_dict = dict(room)
        room_dict["id"] = room_dict["room_id"]
        result = auto_place_products(room_dict, features, products)

        placed = []
        for p in result["placements"]:
            from services.constraint_validator import validate_single_placement
            existing = _get_other_placements(cur, session_id, room_id)

            # model(model_id)로 product_id 조회
            cur.execute(f"{_PRODUCT_SELECT} WHERE p.model_id = %s", (p["model"],))
            product = cur.fetchone()
            if not product:
                continue
            product_id = product["product_id"]

            violations = validate_single_placement(
                p["x_mm"], p["y_mm"], p["rotation"],
                product, room, features, existing
            )
            is_valid = len(violations) == 0

            cur.execute(
                "INSERT INTO placement (group_id, room_id, product_id, x_mm, y_mm, rotation, is_valid, violations) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING placement_id",
                (session_id, room_id, product_id, p["x_mm"], p["y_mm"], p["rotation"],
                 is_valid, json.dumps(violations, ensure_ascii=False)),
            )
            new_id = cur.fetchone()["placement_id"]
            placed.append(PlacementOut(
                id=new_id, session_id=session_id, room_id=room_id,
                product_id=product_id, x_mm=p["x_mm"], y_mm=p["y_mm"],
                rotation=p["rotation"], is_valid=is_valid, violations=violations,
            ))

        return AutoPlaceResponse(placements=placed, warnings=result.get("warnings", []))


@router.post("/validate", response_model=list[ValidationResult])
def validate_placements(session_id: int, room_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        _ensure(cur, session_id, room_id)
        cur.execute("SELECT * FROM floor_plan_room WHERE room_id = %s", (room_id,))
        room = cur.fetchone()
        features = room["features"] if isinstance(room["features"], list) else []

        cur.execute(
            "SELECT pl.*, ps.width AS pw, ps.depth AS pd, pr.category, "
            "COALESCE(pp.mount_type, 'floor') AS mount_type "
            "FROM placement pl "
            "JOIN product pr ON pl.product_id = pr.product_id "
            "LEFT JOIN product_spec ps ON pl.product_id = ps.product_id "
            "LEFT JOIN product_placement_info pp ON pl.product_id = pp.product_id "
            "WHERE pl.group_id = %s AND pl.room_id = %s ORDER BY pl.placement_id",
            (session_id, room_id),
        )
        all_pl = cur.fetchall()

        from services.constraint_validator import validate_single_placement
        results = []
        for pl in all_pl:
            others = [o for o in all_pl if o["placement_id"] != pl["placement_id"]]
            cur.execute(f"{_PRODUCT_SELECT} WHERE p.product_id = %s", (pl["product_id"],))
            product = cur.fetchone()
            violations = validate_single_placement(
                pl["x_mm"], pl["y_mm"], pl["rotation"],
                product, room, features, others
            )
            is_valid = len(violations) == 0
            cur.execute(
                "UPDATE placement SET is_valid=%s, violations=%s WHERE placement_id=%s",
                (is_valid, json.dumps(violations, ensure_ascii=False), pl["placement_id"]),
            )
            results.append(ValidationResult(
                placement_id=pl["placement_id"], is_valid=is_valid, violations=violations
            ))
        return results


# --- Helpers ---

def _ensure(cur, session_id: int, room_id: int):
    cur.execute("SELECT * FROM placement_group WHERE group_id = %s", (session_id,))
    s = cur.fetchone()
    if not s:
        raise HTTPException(404, "Session not found")
    cur.execute(
        "SELECT * FROM floor_plan_room WHERE room_id = %s AND floor_plan_id = %s",
        (room_id, s["floor_plan_id"]),
    )
    if not cur.fetchone():
        raise HTTPException(404, "Room not found in this floor plan")


def _get_other_placements(cur, session_id, room_id, exclude_id=None):
    q = (
        "SELECT pl.*, ps.width AS pw, ps.depth AS pd, pr.category, "
        "COALESCE(pp.mount_type, 'floor') AS mount_type "
        "FROM placement pl "
        "JOIN product pr ON pl.product_id = pr.product_id "
        "LEFT JOIN product_spec ps ON pl.product_id = ps.product_id "
        "LEFT JOIN product_placement_info pp ON pl.product_id = pp.product_id "
        "WHERE pl.group_id = %s AND pl.room_id = %s"
    )
    params = [session_id, room_id]
    if exclude_id:
        q += " AND pl.placement_id != %s"
        params.append(exclude_id)
    cur.execute(q, params)
    return cur.fetchall()


def _row_to_placement(row) -> PlacementOut:
    violations = []
    if row["violations"]:
        if isinstance(row["violations"], list):
            violations = row["violations"]
        elif isinstance(row["violations"], str):
            try:
                violations = json.loads(row["violations"])
            except (json.JSONDecodeError, TypeError):
                pass

    product = ProductOut(
        product_id=row["product_id"],
        model_id=row["model_id"],
        name=row["product_name"],
        category=row["category"],
        product_type=row["product_category"] or "appliance",
        brand=row["brand"],
        image_url=row["product_image_url"],
        width_mm=row["pw"],
        height_mm=row["ph"],
        depth_mm=row["pd"],
        price=row["discount_price"],
        list_price=row["original_price"],
        discount_rate=row["discount_rate"],
        review_score=row["review_score"],
        review_count=row["review_cnt"],
        url=row["product_url"],
        is_placeable=bool(row["is_placeable"]) if row["is_placeable"] is not None else True,
        mount_type=row["mount_type"] or "floor",
    )

    return PlacementOut(
        id=row["placement_id"], session_id=row["group_id"], room_id=row["room_id"],
        product_id=row["product_id"], x_mm=row["x_mm"], y_mm=row["y_mm"],
        rotation=row["rotation"], is_valid=bool(row["is_valid"]),
        violations=violations, product=product,
    )
