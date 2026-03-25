from fastapi import APIRouter, Query
from db import get_db
from models import ProductOut, CategoryOut

router = APIRouter(prefix="/api", tags=["products"])

# 제품 조회 기본 쿼리 (product + product_spec + product_placement_info JOIN)
# PostgreSQL 컬럼 매핑:
#   category = 대분류 (furniture/APPLIANCE) → product_type으로 사용
#   product_category = 세부 카테고리 (냉장고, 소파 등) → category로 사용
_PRODUCT_SELECT = """
    SELECT p.product_id, p.model_id,
           p.product_name, p.product_category AS category,
           p.category AS product_type, p.brand,
           p.original_price, p.discount_rate,
           p.discount_price, p.review_score,
           p.review_cnt, p.product_url,
           p.product_image_url,
           ps.width AS width_mm, ps.height AS height_mm, ps.depth AS depth_mm,
           COALESCE(pp.is_placeable, true) AS is_placeable,
           COALESCE(pp.mount_type, 'floor') AS mount_type
    FROM product p
    LEFT JOIN product_spec ps ON p.product_id = ps.product_id
    LEFT JOIN product_placement_info pp ON p.product_id = pp.product_id
"""


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    placeable_only: bool = True,
    product_type: str | None = None,
):
    with get_db() as conn:
        cur = conn.cursor()
        conditions = []
        params = []
        if placeable_only:
            conditions.append("COALESCE(pp.is_placeable, true) = true")
        if product_type:
            conditions.append("LOWER(p.category) = LOWER(%s)")
            params.append(product_type)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cur.execute(
            f"SELECT p.product_category AS category, COUNT(*) as count "
            f"FROM product p "
            f"LEFT JOIN product_placement_info pp ON p.product_id = pp.product_id "
            f"{where} GROUP BY p.product_category ORDER BY count DESC",
            params,
        )
        rows = cur.fetchall()
        return [CategoryOut(category=r["category"], count=r["count"]) for r in rows]


@router.get("/products", response_model=list[ProductOut])
def list_products(
    category: str | None = None,
    search: str | None = None,
    product_type: str | None = None,
    placeable_only: bool = True,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    conditions = []
    params = []

    if placeable_only:
        conditions.append("COALESCE(pp.is_placeable, true) = true")
    if product_type:
        conditions.append("LOWER(p.category) = LOWER(%s)")
        params.append(product_type)
    if category:
        conditions.append("p.product_category = %s")
        params.append(category)
    if search:
        conditions.append("(p.product_name ILIKE %s OR p.model_id ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * per_page

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"{_PRODUCT_SELECT} {where} ORDER BY p.category, p.product_name "
            f"LIMIT %s OFFSET %s",
            params + [per_page, offset],
        )
        rows = cur.fetchall()
        return [_row_to_product(r) for r in rows]


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"{_PRODUCT_SELECT} WHERE p.product_id = %s", (product_id,))
        row = cur.fetchone()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(404, "Product not found")
        return _row_to_product(row)


def _row_to_product(row) -> ProductOut:
    # SELECT에서 별칭 적용됨: product_category AS category, category AS product_type
    return ProductOut(
        product_id=row["product_id"],
        model_id=row["model_id"],
        name=row["product_name"],
        category=row["category"],          # 별칭: product_category → category
        product_type=row["product_type"] or "appliance",  # 별칭: category → product_type
        brand=row["brand"],
        list_price=row["original_price"],
        discount_rate=row["discount_rate"],
        price=row["discount_price"],
        review_score=row["review_score"],
        review_count=row["review_cnt"],
        url=row["product_url"],
        image_url=row["product_image_url"],
        width_mm=row["width_mm"],
        height_mm=row["height_mm"],
        depth_mm=row["depth_mm"],
        is_placeable=bool(row["is_placeable"]) if row["is_placeable"] is not None else True,
        mount_type=row["mount_type"] or "floor",
    )
