import csv
import os

EXCLUDED_APPLIANCE_CATEGORIES = {"노트북", "모니터", "가습기", "제습기", "공기청정기", "청소기"}
WALL_MOUNT_SUBCATEGORIES = {"벽걸이형"}
EXCLUDED_FURNITURE_CATEGORIES = {"매트리스·토퍼", "아웃도어가구", "트롤리"}

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CSV_APPLIANCE_PATH = os.path.join(_DATA_DIR, "product_가전_03201147.csv")
CSV_FURNITURE_PATH = os.path.join(_DATA_DIR, "product(가구, 크기 없는 제품은 제외)_파생컬럼O (1).csv")


def _parse_float(val: str) -> float | None:
    if not val or not val.strip():
        return None
    try:
        return float(val.strip())
    except (ValueError, TypeError):
        return None


def _parse_int(val: str) -> int | None:
    f = _parse_float(val)
    return int(f) if f is not None else None


def _is_placeable_appliance(category: str, width: float | None, depth: float | None) -> bool:
    if not category or category.strip() in EXCLUDED_APPLIANCE_CATEGORIES:
        return False
    if width is None or depth is None:
        return False
    if width <= 0 or depth <= 0:
        return False
    return True


def import_appliances(conn):
    """Import appliance products from single CSV (table + spec combined)."""
    resolved = os.path.normpath(CSV_APPLIANCE_PATH)

    rows = []
    with open(resolved, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = row.get("model", "").strip()
            name = row.get("name", "").strip()
            category = row.get("category", "").strip()
            if not model or not name:
                continue

            width = _parse_float(row.get("w", ""))
            height = _parse_float(row.get("h", ""))
            depth = _parse_float(row.get("d", ""))

            sub_category = row.get("subCategory", "").strip()
            mount_type = "wall" if sub_category in WALL_MOUNT_SUBCATEGORIES else "floor"

            rows.append((
                model, name, category, "appliance", "LG",
                _parse_float(row.get("listPrice", "")),
                row.get("할인율", "").strip() or None,
                _parse_float(row.get("price", "")),
                _parse_float(row.get("reviewScore", "")),
                _parse_int(row.get("reviewCount", "")),
                row.get("url", "").strip() or None,
                row.get("imageUrl", "").strip() or None,
                width, height, depth,
                1 if _is_placeable_appliance(category, width, depth) else 0,
                mount_type,
            ))

    conn.executemany("""
        INSERT OR REPLACE INTO products
        (model, name, category, product_type, brand, list_price, discount_rate, price,
         review_score, review_count, url, image_url,
         width_mm, height_mm, depth_mm, is_placeable, mount_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    count = conn.execute(
        "SELECT COUNT(*) FROM products WHERE product_type='appliance' AND is_placeable=1"
    ).fetchone()[0]
    print(f"[data_import] Appliances: {len(rows)} imported, {count} placeable")


def import_furniture(conn):
    """Import furniture products from single combined CSV."""
    resolved = os.path.normpath(CSV_FURNITURE_PATH)
    rows = []
    with open(resolved, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = row.get("제품ID", "").strip()
            name = row.get("제품명", "").strip()
            category = row.get("대분류", "").strip()
            brand = row.get("브랜드", "").strip() or None
            if not pid or not name or not category:
                continue

            width = _parse_float(row.get("가로_W(mm)", ""))
            depth = _parse_float(row.get("깊이_D(mm)", ""))
            height = _parse_float(row.get("높이_H(mm)", ""))

            is_excluded = category in EXCLUDED_FURNITURE_CATEGORIES
            has_dims = width is not None and depth is not None and width > 0 and depth > 0
            placeable = 1 if (not is_excluded and has_dims) else 0

            rows.append((
                pid, name, category, "furniture", brand,
                _parse_float(row.get("정가", "")),
                row.get("할인율", "").strip() or None,
                _parse_float(row.get("판매가", "")),
                _parse_float(row.get("리뷰점수", "")),
                _parse_int(row.get("리뷰수", "")),
                row.get("제품URL", "").strip() or None,
                row.get("이미지URL", "").strip() or None,
                width, height, depth,
                placeable,
            ))

    conn.executemany("""
        INSERT OR REPLACE INTO products
        (model, name, category, product_type, brand, list_price, discount_rate, price,
         review_score, review_count, url, image_url,
         width_mm, height_mm, depth_mm, is_placeable)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    count = conn.execute(
        "SELECT COUNT(*) FROM products WHERE product_type='furniture' AND is_placeable=1"
    ).fetchone()[0]
    print(f"[data_import] Furniture: {len(rows)} imported, {count} placeable")


def seed_floor_plans(conn):
    """Seed 3 sample floor plans with rooms and features."""
    import json

    existing = conn.execute("SELECT COUNT(*) FROM floor_plans").fetchone()[0]
    if existing > 0:
        print(f"[seed] Floor plans already exist ({existing}), skipping")
        return

    PLANS = [
        # ── 1. 원룸 8평 ──
        {
            "name": "원룸 8평",
            "category": "원룸",
            "total_area_m2": 26.4,
            "total_width_mm": 6000,
            "total_height_mm": 4400,
            "rooms": [
                {
                    "name": "거실/침실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 4000, "height_mm": 4400,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "south", "offset": 1500, "width": 900, "swing_dir": "inward"},
                        {"type": "window", "wall": "north", "offset": 800, "width": 1800},
                        {"type": "window", "wall": "east", "offset": 1000, "width": 1200},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 4000, "y_mm": 0, "width_mm": 2000, "height_mm": 2800,
                    "is_placeable": 1,
                    "features": [
                        {"type": "water_hookup", "wall": "east", "offset": 400, "width": 200},
                        {"type": "gas_line", "wall": "east", "offset": 1200, "width": 100},
                    ],
                },
                {
                    "name": "화장실", "room_type": "bathroom",
                    "x_mm": 4000, "y_mm": 2800, "width_mm": 2000, "height_mm": 1600,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 200, "width": 700, "swing_dir": "inward"},
                    ],
                },
            ],
        },
        # ── 2. 투룸 오피스텔 15평 ──
        {
            "name": "투룸 오피스텔 15평",
            "category": "오피스텔",
            "total_area_m2": 49.5,
            "total_width_mm": 9000,
            "total_height_mm": 5500,
            "rooms": [
                {
                    "name": "거실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 5000, "height_mm": 3800,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "south", "offset": 2000, "width": 900, "swing_dir": "inward"},
                        {"type": "window", "wall": "north", "offset": 1000, "width": 2400},
                    ],
                },
                {
                    "name": "침실", "room_type": "bedroom",
                    "x_mm": 5000, "y_mm": 0, "width_mm": 4000, "height_mm": 3400,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 200, "width": 800, "swing_dir": "inward"},
                        {"type": "window", "wall": "east", "offset": 800, "width": 1800},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 0, "y_mm": 3800, "width_mm": 3500, "height_mm": 1700,
                    "is_placeable": 1,
                    "features": [
                        {"type": "water_hookup", "wall": "south", "offset": 800, "width": 200},
                        {"type": "gas_line", "wall": "south", "offset": 1800, "width": 100},
                    ],
                },
                {
                    "name": "현관", "room_type": "utility",
                    "x_mm": 3500, "y_mm": 3800, "width_mm": 1500, "height_mm": 1700,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "south", "offset": 300, "width": 900, "swing_dir": "outward"},
                        {"type": "door", "wall": "north", "offset": 300, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "화장실", "room_type": "bathroom",
                    "x_mm": 5000, "y_mm": 3400, "width_mm": 2000, "height_mm": 2100,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 200, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "세탁실", "room_type": "utility",
                    "x_mm": 7000, "y_mm": 3400, "width_mm": 2000, "height_mm": 2100,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 400, "width": 700, "swing_dir": "inward"},
                        {"type": "water_hookup", "wall": "east", "offset": 600, "width": 200},
                    ],
                },
            ],
        },
        # ── 3. 아파트 24평형 A타입 ──
        {
            "name": "아파트 24평형 A타입",
            "category": "아파트",
            "total_area_m2": 79.2,
            "total_width_mm": 11000,
            "total_height_mm": 8000,
            "rooms": [
                {
                    "name": "거실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 6000, "height_mm": 4500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 500, "width": 3000},
                        {"type": "door", "wall": "south", "offset": 4500, "width": 900, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 6000, "y_mm": 0, "width_mm": 5000, "height_mm": 3000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 1500, "width": 1500},
                        {"type": "water_hookup", "wall": "east", "offset": 500, "width": 200},
                        {"type": "gas_line", "wall": "east", "offset": 1500, "width": 100},
                    ],
                },
                {
                    "name": "안방", "room_type": "bedroom",
                    "x_mm": 0, "y_mm": 4500, "width_mm": 4500, "height_mm": 3500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 3500, "width": 800, "swing_dir": "inward"},
                        {"type": "window", "wall": "south", "offset": 1000, "width": 2000},
                    ],
                },
                {
                    "name": "작은방", "room_type": "bedroom",
                    "x_mm": 6000, "y_mm": 3000, "width_mm": 3500, "height_mm": 3000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 200, "width": 800, "swing_dir": "inward"},
                        {"type": "window", "wall": "east", "offset": 500, "width": 1500},
                    ],
                },
                {
                    "name": "세탁실/발코니", "room_type": "utility",
                    "x_mm": 6000, "y_mm": 6000, "width_mm": 2500, "height_mm": 2000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 800, "width": 800, "door_type": "slide"},
                        {"type": "water_hookup", "wall": "south", "offset": 400, "width": 200},
                    ],
                },
                {
                    "name": "화장실1", "room_type": "bathroom",
                    "x_mm": 4500, "y_mm": 4500, "width_mm": 1500, "height_mm": 2000,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 300, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "화장실2", "room_type": "bathroom",
                    "x_mm": 9500, "y_mm": 3000, "width_mm": 1500, "height_mm": 2000,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 300, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "현관", "room_type": "utility",
                    "x_mm": 8500, "y_mm": 6000, "width_mm": 2500, "height_mm": 2000,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "east", "offset": 500, "width": 900, "swing_dir": "outward"},
                        {"type": "door", "wall": "west", "offset": 500, "width": 800, "swing_dir": "inward"},
                    ],
                },
            ],
        },
        # ── 4. 빌라 투룸 12평 ──
        {
            "name": "빌라 투룸 12평",
            "category": "빌라",
            "total_area_m2": 39.6,
            "total_width_mm": 8000,
            "total_height_mm": 5000,
            "rooms": [
                {
                    "name": "거실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 4500, "height_mm": 3200,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "south", "offset": 1500, "width": 900, "swing_dir": "inward"},
                        {"type": "window", "wall": "north", "offset": 800, "width": 2000},
                    ],
                },
                {
                    "name": "침실", "room_type": "bedroom",
                    "x_mm": 4500, "y_mm": 0, "width_mm": 3500, "height_mm": 3200,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 200, "width": 800, "swing_dir": "inward"},
                        {"type": "window", "wall": "east", "offset": 700, "width": 1500},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 0, "y_mm": 3200, "width_mm": 4500, "height_mm": 1800,
                    "is_placeable": 1,
                    "features": [
                        {"type": "water_hookup", "wall": "south", "offset": 800, "width": 200},
                        {"type": "gas_line", "wall": "south", "offset": 2200, "width": 100},
                    ],
                },
                {
                    "name": "화장실", "room_type": "bathroom",
                    "x_mm": 4500, "y_mm": 3200, "width_mm": 2000, "height_mm": 1800,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 400, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "현관", "room_type": "utility",
                    "x_mm": 6500, "y_mm": 3200, "width_mm": 1500, "height_mm": 1800,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "east", "offset": 400, "width": 900, "swing_dir": "outward"},
                        {"type": "door", "wall": "west", "offset": 400, "width": 700, "swing_dir": "inward"},
                    ],
                },
            ],
        },
        # ── 5. 쓰리룸 오피스텔 20평 ──
        {
            "name": "쓰리룸 오피스텔 20평",
            "category": "오피스텔",
            "total_area_m2": 66.0,
            "total_width_mm": 10000,
            "total_height_mm": 6500,
            "rooms": [
                {
                    "name": "거실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 5000, "height_mm": 4000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "south", "offset": 3500, "width": 900, "swing_dir": "inward"},
                        {"type": "window", "wall": "north", "offset": 1000, "width": 2500},
                    ],
                },
                {
                    "name": "침실1", "room_type": "bedroom",
                    "x_mm": 5000, "y_mm": 0, "width_mm": 3500, "height_mm": 3500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 200, "width": 800, "swing_dir": "inward"},
                        {"type": "window", "wall": "north", "offset": 800, "width": 1500},
                    ],
                },
                {
                    "name": "화장실", "room_type": "bathroom",
                    "x_mm": 8500, "y_mm": 0, "width_mm": 1500, "height_mm": 2000,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 600, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 0, "y_mm": 4000, "width_mm": 5000, "height_mm": 2500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "water_hookup", "wall": "south", "offset": 1000, "width": 200},
                        {"type": "gas_line", "wall": "south", "offset": 2500, "width": 100},
                        {"type": "window", "wall": "west", "offset": 500, "width": 1500},
                    ],
                },
                {
                    "name": "침실2", "room_type": "bedroom",
                    "x_mm": 5000, "y_mm": 3500, "width_mm": 3500, "height_mm": 3000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 200, "width": 800, "swing_dir": "inward"},
                        {"type": "window", "wall": "east", "offset": 600, "width": 1500},
                    ],
                },
                {
                    "name": "세탁실", "room_type": "utility",
                    "x_mm": 8500, "y_mm": 2000, "width_mm": 1500, "height_mm": 2000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 300, "width": 700, "swing_dir": "inward"},
                        {"type": "water_hookup", "wall": "east", "offset": 1200, "width": 200},
                    ],
                },
                {
                    "name": "현관", "room_type": "utility",
                    "x_mm": 8500, "y_mm": 4000, "width_mm": 1500, "height_mm": 2500,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "east", "offset": 600, "width": 900, "swing_dir": "outward"},
                        {"type": "door", "wall": "west", "offset": 600, "width": 800, "swing_dir": "inward"},
                    ],
                },
            ],
        },
        # ── 6. 아파트 34평형 B타입 ──
        # 배치: 북쪽=창문(거실+주방), 동쪽=현관, 서쪽=안방
        # 현관→복도→거실/안방/작은방/화장실 연결
        {
            "name": "아파트 34평형 B타입",
            "category": "아파트",
            "total_area_m2": 112.2,
            "total_width_mm": 12000,
            "total_height_mm": 9000,
            "rooms": [
                {
                    "name": "거실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 6500, "height_mm": 4500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 500, "width": 3500},
                        {"type": "door", "wall": "south", "offset": 200, "width": 900, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "주방/식당", "room_type": "kitchen",
                    "x_mm": 6500, "y_mm": 0, "width_mm": 5500, "height_mm": 3000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 1500, "width": 2000},
                        {"type": "water_hookup", "wall": "east", "offset": 500, "width": 200},
                        {"type": "gas_line", "wall": "east", "offset": 1500, "width": 100},
                    ],
                },
                {
                    "name": "작은방1", "room_type": "bedroom",
                    "x_mm": 6500, "y_mm": 3000, "width_mm": 3000, "height_mm": 3500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 200, "width": 800, "swing_dir": "inward"},
                        {"type": "window", "wall": "east", "offset": 800, "width": 1500},
                    ],
                },
                {
                    "name": "화장실2", "room_type": "bathroom",
                    "x_mm": 9500, "y_mm": 3000, "width_mm": 2500, "height_mm": 2000,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 500, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "안방", "room_type": "bedroom",
                    "x_mm": 0, "y_mm": 4500, "width_mm": 4500, "height_mm": 4500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 3500, "width": 800, "swing_dir": "inward"},
                        {"type": "window", "wall": "south", "offset": 1000, "width": 2500},
                        {"type": "window", "wall": "west", "offset": 1000, "width": 2000},
                    ],
                },
                {
                    "name": "화장실1", "room_type": "bathroom",
                    "x_mm": 4500, "y_mm": 4500, "width_mm": 2000, "height_mm": 2000,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 500, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "세탁실/발코니", "room_type": "utility",
                    "x_mm": 4500, "y_mm": 6500, "width_mm": 2000, "height_mm": 2500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 500, "width": 800, "door_type": "slide"},
                        {"type": "water_hookup", "wall": "east", "offset": 1500, "width": 200},
                    ],
                },
                {
                    "name": "현관", "room_type": "utility",
                    "x_mm": 9500, "y_mm": 5000, "width_mm": 2500, "height_mm": 2500,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "east", "offset": 800, "width": 900, "swing_dir": "outward"},
                        {"type": "door", "wall": "west", "offset": 200, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "작은방2", "room_type": "bedroom",
                    "x_mm": 6500, "y_mm": 6500, "width_mm": 3000, "height_mm": 2500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 200, "width": 800, "swing_dir": "inward"},
                        {"type": "window", "wall": "south", "offset": 600, "width": 1500},
                    ],
                },
            ],
        },
    ]

    for plan in PLANS:
        cur = conn.execute(
            "INSERT INTO floor_plans (name, category, total_area_m2, total_width_mm, total_height_mm) "
            "VALUES (?, ?, ?, ?, ?)",
            (plan["name"], plan["category"], plan["total_area_m2"],
             plan["total_width_mm"], plan["total_height_mm"]),
        )
        plan_id = cur.lastrowid

        for room in plan["rooms"]:
            conn.execute(
                "INSERT INTO floor_plan_rooms "
                "(floor_plan_id, name, room_type, x_mm, y_mm, width_mm, height_mm, "
                " is_placeable, features) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (plan_id, room["name"], room["room_type"],
                 room["x_mm"], room["y_mm"], room["width_mm"], room["height_mm"],
                 room["is_placeable"],
                 json.dumps(room["features"], ensure_ascii=False)),
            )

    print(f"[seed] Created {len(PLANS)} floor plans")


def seed_builtin_officetel(conn):
    """Add a modern officetel floor plan with built-in fixtures."""
    import json

    existing = conn.execute(
        "SELECT COUNT(*) FROM floor_plans WHERE name = '신축 오피스텔 10평 (빌트인)'"
    ).fetchone()[0]
    if existing > 0:
        return

    # ── 신축 오피스텔 10평 (빌트인) ──
    # 6500 x 5000mm = 32.5m² (~10평)
    # 최신 오피스텔: 싱크대, 붙박이장, 신발장 등 기본 설비 포함
    plan = {
        "name": "신축 오피스텔 10평 (빌트인)",
        "category": "오피스텔",
        "total_area_m2": 32.5,
        "total_width_mm": 6500,
        "total_height_mm": 5000,
        "rooms": [
            # 거실/침실 (원룸형 스튜디오)
            {
                "name": "거실/침실", "room_type": "living",
                "x_mm": 0, "y_mm": 0, "width_mm": 4000, "height_mm": 3500,
                "is_placeable": 1,
                "features": [
                    {"type": "window", "wall": "north", "offset": 500, "width": 2500},
                    {"type": "door", "wall": "south", "offset": 3000, "width": 800, "swing_dir": "inward"},
                    # 붙박이장 (동쪽 벽, 깊이 600mm)
                    {"type": "fixture", "wall": "east", "offset": 500, "width": 2000, "depth": 600, "label": "붙박이장"},
                ],
            },
            # 주방 (빌트인 싱크대 + 가스레인지)
            {
                "name": "주방", "room_type": "kitchen",
                "x_mm": 4000, "y_mm": 0, "width_mm": 2500, "height_mm": 2500,
                "is_placeable": 1,
                "features": [
                    {"type": "window", "wall": "east", "offset": 500, "width": 1200},
                    {"type": "water_hookup", "wall": "north", "offset": 800, "width": 200},
                    {"type": "gas_line", "wall": "north", "offset": 1800, "width": 100},
                    # 싱크대+조리대 (북쪽 벽, 깊이 600mm)
                    {"type": "fixture", "wall": "north", "offset": 200, "width": 2100, "depth": 600, "label": "싱크대/조리대"},
                ],
            },
            # 욕실
            {
                "name": "욕실", "room_type": "bathroom",
                "x_mm": 4000, "y_mm": 2500, "width_mm": 2500, "height_mm": 2500,
                "is_placeable": 0,
                "features": [
                    {"type": "door", "wall": "west", "offset": 200, "width": 700, "door_type": "slide"},
                ],
            },
            # 현관
            {
                "name": "현관", "room_type": "utility",
                "x_mm": 0, "y_mm": 3500, "width_mm": 2000, "height_mm": 1500,
                "is_placeable": 0,
                "features": [
                    {"type": "door", "wall": "south", "offset": 400, "width": 900, "swing_dir": "outward"},
                    {"type": "door", "wall": "north", "offset": 500, "width": 800, "swing_dir": "inward"},
                    # 신발장 (동쪽 벽, 깊이 350mm)
                    {"type": "fixture", "wall": "east", "offset": 100, "width": 1200, "depth": 350, "label": "신발장"},
                ],
            },
            # 드레스룸/수납
            {
                "name": "드레스룸", "room_type": "utility",
                "x_mm": 2000, "y_mm": 3500, "width_mm": 2000, "height_mm": 1500,
                "is_placeable": 0,
                "features": [
                    {"type": "door", "wall": "north", "offset": 200, "width": 800, "swing_dir": "inward"},
                    # 붙박이장 (남쪽 벽 전체, 깊이 600mm)
                    {"type": "fixture", "wall": "south", "offset": 0, "width": 2000, "depth": 600, "label": "붙박이장"},
                ],
            },
        ],
    }

    cur = conn.execute(
        "INSERT INTO floor_plans (name, category, total_area_m2, total_width_mm, total_height_mm) "
        "VALUES (?, ?, ?, ?, ?)",
        (plan["name"], plan["category"], plan["total_area_m2"],
         plan["total_width_mm"], plan["total_height_mm"]),
    )
    plan_id = cur.lastrowid

    for room in plan["rooms"]:
        conn.execute(
            "INSERT INTO floor_plan_rooms "
            "(floor_plan_id, name, room_type, x_mm, y_mm, width_mm, height_mm, "
            " is_placeable, features) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (plan_id, room["name"], room["room_type"],
             room["x_mm"], room["y_mm"], room["width_mm"], room["height_mm"],
             room["is_placeable"],
             json.dumps(room["features"], ensure_ascii=False)),
        )

    print(f"[seed] Created built-in officetel floor plan (id={plan_id})")


def seed_jachui_plans(conn):
    """2030 자취생 맞춤 도면 10종 — 다양한 구조."""
    import json

    PLANS = [
        # ── 1. 원룸 6평 (복층형) ──
        # 아래층 거실/주방 + 위층 다락 침실
        {
            "name": "원룸 6평 (복층형)",
            "category": "원룸",
            "total_area_m2": 20.0,
            "total_width_mm": 5000,
            "total_height_mm": 4000,
            "rooms": [
                {
                    "name": "1층 거실/주방", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 3000, "height_mm": 4000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 300, "width": 2000},
                        {"type": "door", "wall": "south", "offset": 1000, "width": 800, "swing_dir": "inward"},
                        {"type": "water_hookup", "wall": "east", "offset": 3200, "width": 200},
                        {"type": "gas_line", "wall": "east", "offset": 3600, "width": 100},
                    ],
                },
                {
                    "name": "2층 다락/침실", "room_type": "bedroom",
                    "x_mm": 3000, "y_mm": 0, "width_mm": 2000, "height_mm": 2500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "east", "offset": 400, "width": 1200},
                        {"type": "door", "wall": "west", "offset": 200, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "욕실", "room_type": "bathroom",
                    "x_mm": 3000, "y_mm": 2500, "width_mm": 2000, "height_mm": 1500,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 200, "width": 700, "swing_dir": "inward"},
                    ],
                },
            ],
        },
        # ── 3. 원룸 7평 (ㄱ자 주방분리형) ──
        # 주방이 옆으로 분리된 ㄱ자 구조
        {
            "name": "원룸 7평 (ㄱ자 주방분리)",
            "category": "원룸",
            "total_area_m2": 23.0,
            "total_width_mm": 5000,
            "total_height_mm": 4600,
            "rooms": [
                {
                    "name": "거실/침실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 3500, "height_mm": 3200,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 500, "width": 2200},
                        {"type": "door", "wall": "east", "offset": 200, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 3500, "y_mm": 0, "width_mm": 1500, "height_mm": 3200,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "east", "offset": 800, "width": 1000},
                        {"type": "water_hookup", "wall": "north", "offset": 500, "width": 200},
                        {"type": "gas_line", "wall": "north", "offset": 1000, "width": 100},
                    ],
                },
                {
                    "name": "현관", "room_type": "utility",
                    "x_mm": 0, "y_mm": 3200, "width_mm": 1500, "height_mm": 1400,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "south", "offset": 300, "width": 900, "swing_dir": "outward"},
                    ],
                },
                {
                    "name": "욕실", "room_type": "bathroom",
                    "x_mm": 1500, "y_mm": 3200, "width_mm": 2000, "height_mm": 1400,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 200, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "세탁공간", "room_type": "utility",
                    "x_mm": 3500, "y_mm": 3200, "width_mm": 1500, "height_mm": 1400,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 300, "width": 700, "door_type": "slide"},
                        {"type": "water_hookup", "wall": "east", "offset": 400, "width": 200},
                    ],
                },
            ],
        },
        # ── 4. 원룸 7평 (와이드형) ──
        # 가로로 넓고 세로가 짧은 파노라마 구조
        {
            "name": "원룸 7평 (와이드형)",
            "category": "원룸",
            "total_area_m2": 22.8,
            "total_width_mm": 6000,
            "total_height_mm": 3800,
            "rooms": [
                {
                    "name": "거실/침실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 6000, "height_mm": 2500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 500, "width": 4500},
                        {"type": "door", "wall": "south", "offset": 4500, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 0, "y_mm": 2500, "width_mm": 2500, "height_mm": 1300,
                    "is_placeable": 1,
                    "features": [
                        {"type": "water_hookup", "wall": "south", "offset": 600, "width": 200},
                        {"type": "gas_line", "wall": "south", "offset": 1500, "width": 100},
                    ],
                },
                {
                    "name": "욕실", "room_type": "bathroom",
                    "x_mm": 2500, "y_mm": 2500, "width_mm": 1500, "height_mm": 1300,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 300, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "현관", "room_type": "utility",
                    "x_mm": 4000, "y_mm": 2500, "width_mm": 2000, "height_mm": 1300,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "east", "offset": 300, "width": 900, "swing_dir": "outward"},
                    ],
                },
            ],
        },
        # ── 5. 1.5룸 9평 (침실분리형) ──
        # 침실이 벽으로 분리된 1.5룸 구조
        # 현관은 거실 아래, 욕실은 침실 아래 (침실에서 접근)
        {
            "name": "1.5룸 9평 (침실분리형)",
            "category": "오피스텔",
            "total_area_m2": 29.7,
            "total_width_mm": 5500,
            "total_height_mm": 5400,
            "rooms": [
                {
                    "name": "거실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 3000, "height_mm": 3000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 300, "width": 2000},
                        {"type": "door", "wall": "east", "offset": 200, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "침실", "room_type": "bedroom",
                    "x_mm": 3000, "y_mm": 0, "width_mm": 2500, "height_mm": 3000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "east", "offset": 500, "width": 1500},
                        {"type": "door", "wall": "west", "offset": 200, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 0, "y_mm": 3000, "width_mm": 2000, "height_mm": 2400,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "west", "offset": 500, "width": 1200},
                        {"type": "water_hookup", "wall": "south", "offset": 600, "width": 200},
                        {"type": "gas_line", "wall": "south", "offset": 1400, "width": 100},
                    ],
                },
                {
                    "name": "현관", "room_type": "utility",
                    "x_mm": 2000, "y_mm": 3000, "width_mm": 1000, "height_mm": 2400,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "south", "offset": 50, "width": 900, "swing_dir": "outward"},
                        {"type": "door", "wall": "north", "offset": 100, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "욕실", "room_type": "bathroom",
                    "x_mm": 3000, "y_mm": 3000, "width_mm": 2500, "height_mm": 2400,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 400, "width": 700, "swing_dir": "inward"},
                    ],
                },
            ],
        },
        # ── 6. 오피스텔 8평 (ㄴ자 복도형) ──
        # 복도를 따라 방이 배치된 ㄴ자 구조
        {
            "name": "오피스텔 8평 (ㄴ자 복도형)",
            "category": "오피스텔",
            "total_area_m2": 26.4,
            "total_width_mm": 5500,
            "total_height_mm": 4800,
            "rooms": [
                {
                    "name": "거실/침실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 3500, "height_mm": 3200,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 500, "width": 2500},
                        {"type": "window", "wall": "west", "offset": 500, "width": 1800},
                        {"type": "door", "wall": "south", "offset": 2700, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "드레스룸", "room_type": "utility",
                    "x_mm": 3500, "y_mm": 0, "width_mm": 2000, "height_mm": 1600,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "south", "offset": 500, "width": 700, "swing_dir": "inward"},
                        {"type": "fixture", "wall": "north", "offset": 200, "width": 1600, "depth": 600, "label": "붙박이장"},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 3500, "y_mm": 1600, "width_mm": 2000, "height_mm": 1600,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "east", "offset": 300, "width": 800},
                        {"type": "water_hookup", "wall": "north", "offset": 400, "width": 200},
                        {"type": "gas_line", "wall": "north", "offset": 1200, "width": 100},
                        {"type": "fixture", "wall": "north", "offset": 100, "width": 1800, "depth": 550, "label": "싱크대"},
                    ],
                },
                {
                    "name": "현관", "room_type": "utility",
                    "x_mm": 0, "y_mm": 3200, "width_mm": 2000, "height_mm": 1600,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "south", "offset": 400, "width": 900, "swing_dir": "outward"},
                        {"type": "fixture", "wall": "west", "offset": 200, "width": 1000, "depth": 350, "label": "신발장"},
                    ],
                },
                {
                    "name": "욕실", "room_type": "bathroom",
                    "x_mm": 2000, "y_mm": 3200, "width_mm": 1500, "height_mm": 1600,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 300, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "발코니", "room_type": "balcony",
                    "x_mm": 3500, "y_mm": 3200, "width_mm": 2000, "height_mm": 1600,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 300, "width": 800, "door_type": "slide"},
                        {"type": "water_hookup", "wall": "east", "offset": 500, "width": 200},
                    ],
                },
            ],
        },
        # ── 7. 투룸 빌라 10평 ──
        # 거실과 침실 완전 분리
        {
            "name": "투룸 빌라 10평",
            "category": "빌라",
            "total_area_m2": 32.5,
            "total_width_mm": 6500,
            "total_height_mm": 5000,
            "rooms": [
                {
                    "name": "거실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 3500, "height_mm": 3000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 500, "width": 2200},
                        {"type": "door", "wall": "east", "offset": 200, "width": 800, "swing_dir": "inward"},
                        {"type": "door", "wall": "south", "offset": 1500, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "침실", "room_type": "bedroom",
                    "x_mm": 3500, "y_mm": 0, "width_mm": 3000, "height_mm": 3000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "east", "offset": 500, "width": 1800},
                        {"type": "door", "wall": "west", "offset": 200, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 0, "y_mm": 3000, "width_mm": 3500, "height_mm": 2000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "water_hookup", "wall": "south", "offset": 800, "width": 200},
                        {"type": "gas_line", "wall": "south", "offset": 2000, "width": 100},
                        {"type": "window", "wall": "west", "offset": 400, "width": 1000},
                    ],
                },
                {
                    "name": "욕실", "room_type": "bathroom",
                    "x_mm": 3500, "y_mm": 3000, "width_mm": 1500, "height_mm": 2000,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 400, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "현관", "room_type": "utility",
                    "x_mm": 5000, "y_mm": 3000, "width_mm": 1500, "height_mm": 2000,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "east", "offset": 500, "width": 900, "swing_dir": "outward"},
                        {"type": "door", "wall": "north", "offset": 200, "width": 800, "door_type": "slide"},
                    ],
                },
            ],
        },
        # ── 8. 투룸 오피스텔 11평 (빌트인) ──
        # 신축 오피스텔, 빌트인 설비 포함
        {
            "name": "투룸 오피스텔 11평 (빌트인)",
            "category": "오피스텔",
            "total_area_m2": 36.4,
            "total_width_mm": 6500,
            "total_height_mm": 5600,
            "rooms": [
                {
                    "name": "거실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 3500, "height_mm": 3200,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 300, "width": 2500},
                        {"type": "door", "wall": "east", "offset": 200, "width": 800, "swing_dir": "inward"},
                        {"type": "door", "wall": "south", "offset": 2500, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "침실", "room_type": "bedroom",
                    "x_mm": 3500, "y_mm": 0, "width_mm": 3000, "height_mm": 3200,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "east", "offset": 600, "width": 1800},
                        {"type": "door", "wall": "west", "offset": 200, "width": 800, "swing_dir": "inward"},
                        {"type": "fixture", "wall": "west", "offset": 1200, "width": 1800, "depth": 600, "label": "붙박이장"},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 0, "y_mm": 3200, "width_mm": 3500, "height_mm": 2400,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "west", "offset": 500, "width": 1200},
                        {"type": "water_hookup", "wall": "south", "offset": 800, "width": 200},
                        {"type": "gas_line", "wall": "south", "offset": 2000, "width": 100},
                        {"type": "fixture", "wall": "south", "offset": 200, "width": 2800, "depth": 600, "label": "싱크대/조리대"},
                    ],
                },
                {
                    "name": "욕실", "room_type": "bathroom",
                    "x_mm": 3500, "y_mm": 3200, "width_mm": 1500, "height_mm": 2400,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "west", "offset": 400, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "현관", "room_type": "utility",
                    "x_mm": 5000, "y_mm": 3200, "width_mm": 1500, "height_mm": 2400,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "east", "offset": 600, "width": 900, "swing_dir": "outward"},
                        {"type": "door", "wall": "north", "offset": 200, "width": 800, "door_type": "slide"},
                        {"type": "fixture", "wall": "west", "offset": 200, "width": 1800, "depth": 350, "label": "신발장"},
                    ],
                },
            ],
        },
        # ── 10. 미니 쓰리룸 14평 ──
        # 룸메이트와 공유 가능한 3룸 구조
        {
            "name": "미니 쓰리룸 14평 (쉐어하우스)",
            "category": "빌라",
            "total_area_m2": 45.0,
            "total_width_mm": 7500,
            "total_height_mm": 6000,
            "rooms": [
                {
                    "name": "거실", "room_type": "living",
                    "x_mm": 0, "y_mm": 0, "width_mm": 4000, "height_mm": 3500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 500, "width": 2500},
                        {"type": "window", "wall": "west", "offset": 800, "width": 1500},
                        {"type": "door", "wall": "south", "offset": 3000, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "주방", "room_type": "kitchen",
                    "x_mm": 4000, "y_mm": 0, "width_mm": 3500, "height_mm": 2000,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "north", "offset": 800, "width": 1500},
                        {"type": "water_hookup", "wall": "east", "offset": 400, "width": 200},
                        {"type": "gas_line", "wall": "east", "offset": 1200, "width": 100},
                    ],
                },
                {
                    "name": "방1", "room_type": "bedroom",
                    "x_mm": 4000, "y_mm": 2000, "width_mm": 3500, "height_mm": 1500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "east", "offset": 200, "width": 1000},
                        {"type": "door", "wall": "west", "offset": 200, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "방2", "room_type": "bedroom",
                    "x_mm": 0, "y_mm": 3500, "width_mm": 3000, "height_mm": 2500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "window", "wall": "south", "offset": 500, "width": 1500},
                        {"type": "door", "wall": "north", "offset": 200, "width": 800, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "욕실", "room_type": "bathroom",
                    "x_mm": 3000, "y_mm": 3500, "width_mm": 2000, "height_mm": 2500,
                    "is_placeable": 0,
                    "features": [
                        {"type": "door", "wall": "north", "offset": 400, "width": 700, "swing_dir": "inward"},
                    ],
                },
                {
                    "name": "현관/세탁", "room_type": "utility",
                    "x_mm": 5000, "y_mm": 3500, "width_mm": 2500, "height_mm": 2500,
                    "is_placeable": 1,
                    "features": [
                        {"type": "door", "wall": "east", "offset": 800, "width": 900, "swing_dir": "outward"},
                        {"type": "door", "wall": "north", "offset": 200, "width": 800, "door_type": "slide"},
                        {"type": "water_hookup", "wall": "south", "offset": 500, "width": 200},
                    ],
                },
            ],
        },
    ]

    created = 0
    for plan in PLANS:
        exists = conn.execute(
            "SELECT COUNT(*) FROM floor_plans WHERE name = ?", (plan["name"],)
        ).fetchone()[0]
        if exists > 0:
            continue

        cur = conn.execute(
            "INSERT INTO floor_plans (name, category, total_area_m2, total_width_mm, total_height_mm) "
            "VALUES (?, ?, ?, ?, ?)",
            (plan["name"], plan["category"], plan["total_area_m2"],
             plan["total_width_mm"], plan["total_height_mm"]),
        )
        plan_id = cur.lastrowid
        for room in plan["rooms"]:
            conn.execute(
                "INSERT INTO floor_plan_rooms "
                "(floor_plan_id, name, room_type, x_mm, y_mm, width_mm, height_mm, "
                " is_placeable, features) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (plan_id, room["name"], room["room_type"],
                 room["x_mm"], room["y_mm"], room["width_mm"], room["height_mm"],
                 room["is_placeable"],
                 json.dumps(room["features"], ensure_ascii=False)),
            )
        created += 1

    if created > 0:
        print(f"[seed] Created {created} 자취생 floor plans")
