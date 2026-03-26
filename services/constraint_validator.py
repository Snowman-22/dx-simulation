"""
Constraint validation for product placements.
All coordinates in mm. Room origin (0,0) is top-left of each room.
Walls: north=top (y=0), south=bottom (y=room_height), west=left (x=0), east=right (x=room_width).
Features come as JSON list from floor_plan_rooms.features.
"""
from __future__ import annotations

CLEARANCE_PROFILES: dict[str, dict] = {
    "냉장고": {"front": 800, "back": 50, "sides": 50},
    "세탁기": {"front": 700, "back": 50, "sides": 30},
    "워시타워": {"front": 700, "back": 50, "sides": 30},
    "워시콤보": {"front": 700, "back": 50, "sides": 30},
    "의류건조기": {"front": 700, "back": 50, "sides": 30},
    "의류관리기": {"front": 600, "back": 50, "sides": 50},
    "에어컨": {"front": 1000, "back": 50, "sides": 200},
    "TV": {"front": 2000, "back": 50, "sides": 100},
    "스탠바이미": {"front": 500, "back": 0, "sides": 100},
    "전기레인지": {"front": 600, "back": 0, "sides": 100},
    "광파오븐/전자레인지": {"front": 400, "back": 100, "sides": 100},
    "식기세척기": {"front": 700, "back": 50, "sides": 0},
    "정수기": {"front": 400, "back": 50, "sides": 50},
}
DEFAULT_CLEARANCE = {"front": 300, "back": 50, "sides": 50}


def get_footprint(width_mm: float, depth_mm: float, rotation: int) -> tuple[float, float]:
    if rotation in (0, 180):
        return (width_mm, depth_mm)
    return (depth_mm, width_mm)


def get_rect(x: float, y: float, w: float, d: float) -> tuple[float, float, float, float]:
    return (x - w / 2, y - d / 2, x + w / 2, y + d / 2)


def rects_overlap(r1, r2) -> bool:
    return not (r1[2] <= r2[0] or r2[2] <= r1[0] or r1[3] <= r2[1] or r2[3] <= r1[1])


def get_door_swing_rect(door: dict, room_width: float, room_height: float):
    """문 열림 아크 — 미닫이문은 없음, 여닫이문은 문 너비만큼."""
    if door.get("door_type") == "slide":
        return (0, 0, 0, 0)
    wall = door["wall"]
    offset = door["offset"]
    dw = door["width"]
    if wall == "north":
        return (offset, 0, offset + dw, dw)
    elif wall == "south":
        return (offset, room_height - dw, offset + dw, room_height)
    elif wall == "west":
        return (0, offset, dw, offset + dw)
    else:
        return (room_width - dw, offset, room_width, offset + dw)


def get_door_clearance_zone(door: dict, room_width: float, room_height: float):
    """문 통행 구역 — 프론트와 동일한 규칙.
    여닫이: margin 80mm, depth 400mm / 미닫이: margin 50mm, depth 200mm."""
    wall = door["wall"]
    offset = door["offset"]
    dw = door["width"]
    is_slide = door.get("door_type") == "slide"
    side_margin = 50 if is_slide else 80
    front_depth = 200 if is_slide else 400

    if wall == "north":
        return (max(0, offset - side_margin), 0,
                min(room_width, offset + dw + side_margin), front_depth)
    elif wall == "south":
        return (max(0, offset - side_margin), room_height - front_depth,
                min(room_width, offset + dw + side_margin), room_height)
    elif wall == "west":
        return (0, max(0, offset - side_margin),
                front_depth, min(room_height, offset + dw + side_margin))
    else:
        return (room_width - front_depth, max(0, offset - side_margin),
                room_width, min(room_height, offset + dw + side_margin))


def get_door_passage_zone(door: dict, room_width: float, room_height: float):
    """하위 호환용 — get_door_clearance_zone과 동일."""
    return get_door_clearance_zone(door, room_width, room_height)


def get_door_entry_zone(door: dict, room_width: float, room_height: float):
    """하위 호환용 — get_door_clearance_zone과 동일."""
    return get_door_clearance_zone(door, room_width, room_height)


def get_window_zone(window: dict, room_width: float, room_height: float):
    wall = window["wall"]
    offset = window["offset"]
    ww = window["width"]
    clearance = 300

    if wall == "north":
        return (offset, 0, offset + ww, clearance)
    elif wall == "south":
        return (offset, room_height - clearance, offset + ww, room_height)
    elif wall == "west":
        return (0, offset, clearance, offset + ww)
    else:
        return (room_width - clearance, offset, room_width, offset + ww)


def get_fixture_zone(fixture: dict, room_width: float, room_height: float):
    """빌트인 설비(싱크대, 붙박이장, 신발장) 영역.
    벽에서 depth만큼 돌출된 직사각형 영역."""
    wall = fixture["wall"]
    offset = fixture["offset"]
    fw = fixture["width"]
    depth = fixture.get("depth", 600)

    if wall == "north":
        return (offset, 0, offset + fw, depth)
    elif wall == "south":
        return (offset, room_height - depth, offset + fw, room_height)
    elif wall == "west":
        return (0, offset, depth, offset + fw)
    else:
        return (room_width - depth, offset, room_width, offset + fw)


def validate_single_placement(
    x: float, y: float, rotation: int,
    product, room, features: list[dict], other_placements,
    all_rooms: list | None = None,
) -> list[str]:
    """Validate a single placement. Returns list of violation messages."""
    violations = []
    pw, pd = product["width_mm"], product["depth_mm"]
    if pw is None or pd is None:
        return ["치수 정보 없음"]

    fw, fd = get_footprint(pw, pd, rotation)
    rect = get_rect(x, y, fw, fd)
    room_w, room_h = room["width_mm"], room["height_mm"]

    # 1. Boundary check (open_walls 방향은 스킵)
    open_walls = set(room.get("open_walls") or [])
    out_west = rect[0] < -1 and "west" not in open_walls
    out_north = rect[1] < -1 and "north" not in open_walls
    out_east = rect[2] > room_w + 1 and "east" not in open_walls
    out_south = rect[3] > room_h + 1 and "south" not in open_walls
    if out_west or out_north or out_east or out_south:
        violations.append("방 경계를 벗어남")

    # 1-1. 투명벽(open_walls) 통행 구역 (300mm)
    open_wall_margin = 300
    for wall in open_walls:
        if wall == "north":
            zone = (0, 0, room_w, open_wall_margin)
        elif wall == "south":
            zone = (0, room_h - open_wall_margin, room_w, room_h)
        elif wall == "west":
            zone = (0, 0, open_wall_margin, room_h)
        elif wall == "east":
            zone = (room_w - open_wall_margin, 0, room_w, room_h)
        else:
            continue
        if rects_overlap(rect, zone):
            violations.append(f"개방 공간 통행 구역 침범 ({wall})")

    # 2. Overlap check (같은 mount_type끼리만 충돌 검사)
    try:
        my_mount = product["mount_type"]
    except (KeyError, IndexError):
        my_mount = "floor"
    for other in other_placements:
        try:
            other_mount = other["mount_type"]
        except (KeyError, IndexError):
            other_mount = "floor"
        if my_mount != other_mount:
            continue  # 벽면↔바닥은 충돌하지 않음
        opw = other["pw"] if "pw" in other.keys() else other.get("width_mm", 0)
        opd = other["pd"] if "pd" in other.keys() else other.get("depth_mm", 0)
        if opw is None or opd is None:
            continue
        ofw, ofd = get_footprint(opw, opd, other["rotation"])
        orect = get_rect(other["x_mm"], other["y_mm"], ofw, ofd)
        if rects_overlap(rect, orect):
            violations.append(f"다른 제품과 겹침 (ID: {other['id']})")

    # 3. Door clearance — 벽면 제품은 벽 상단 설치이므로 문/창문 검사 스킵
    if my_mount != "wall":
        for feat in features:
            if feat.get("type") == "door":
                door_rect = get_door_swing_rect(feat, room_w, room_h)
                if rects_overlap(rect, door_rect):
                    violations.append(f"문 열림 공간 침범 ({feat['wall']}벽)")
                passage_rect = get_door_passage_zone(feat, room_w, room_h)
                if rects_overlap(rect, passage_rect):
                    violations.append(f"문 통행 구역 침범 ({feat['wall']}벽)")
                entry_rect = get_door_entry_zone(feat, room_w, room_h)
                if rects_overlap(rect, entry_rect):
                    violations.append(f"문 진입 구역 침범 ({feat['wall']}벽)")

        # 4. Window clearance
        for feat in features:
            if feat.get("type") == "window":
                win_zone = get_window_zone(feat, room_w, room_h)
                if rects_overlap(rect, win_zone):
                    violations.append(f"창문 앞 공간 침범 ({feat['wall']}벽)")

    # 5. Built-in fixture clearance (싱크대, 붙박이장, 신발장 등)
    for feat in features:
        if feat.get("type") == "fixture":
            fix_zone = get_fixture_zone(feat, room_w, room_h)
            if rects_overlap(rect, fix_zone):
                label = feat.get("label", "빌트인 설비")
                violations.append(f"빌트인 설비 영역 침범 ({label}, {feat['wall']}벽)")

    # 6. 인접 방 문 통행 구역 (프론트와 동일 로직)
    if all_rooms and my_mount != "wall":
        adj_margin = 80
        adj_depth = 400
        cr_x, cr_y = room.get("x_mm", 0), room.get("y_mm", 0)
        cr_w, cr_h = room_w, room_h
        room_id = room.get("id") or room.get("room_id")

        for other in all_rooms:
            other_id = other.get("id") or other.get("room_id")
            if other_id == room_id:
                continue
            or_x, or_y = other.get("x_mm", 0), other.get("y_mm", 0)
            or_w, or_h = other.get("width_mm", 0), other.get("height_mm", 0)
            for ofeat in (other.get("features") or []):
                if ofeat.get("type") != "door":
                    continue
                o_offset = ofeat["offset"]
                o_dw = ofeat["width"]
                o_wall = ofeat["wall"]

                if o_wall in ("north", "south"):
                    door_gx = or_x + o_offset
                    door_gy = or_y if o_wall == "north" else or_y + or_h
                    dx1, dx2 = door_gx, door_gx + o_dw
                    overlap = max(0, min(dx2, cr_x + cr_w) - max(dx1, cr_x))
                    if overlap <= 0:
                        continue
                    if abs(door_gy - cr_y) < 5:
                        lx = max(0, dx1 - cr_x - adj_margin)
                        rx = min(cr_w, dx2 - cr_x + adj_margin)
                        if rects_overlap(rect, (lx, 0, rx, adj_depth)):
                            violations.append("인접 방 문 통행 구역 침범")
                    elif abs(door_gy - (cr_y + cr_h)) < 5:
                        lx = max(0, dx1 - cr_x - adj_margin)
                        rx = min(cr_w, dx2 - cr_x + adj_margin)
                        if rects_overlap(rect, (lx, cr_h - adj_depth, rx, cr_h)):
                            violations.append("인접 방 문 통행 구역 침범")
                else:
                    door_gx = or_x if o_wall == "west" else or_x + or_w
                    door_gy = or_y + o_offset
                    dy1, dy2 = door_gy, door_gy + o_dw
                    overlap = max(0, min(dy2, cr_y + cr_h) - max(dy1, cr_y))
                    if overlap <= 0:
                        continue
                    if abs(door_gx - cr_x) < 5:
                        ty = max(0, dy1 - cr_y - adj_margin)
                        by = min(cr_h, dy2 - cr_y + adj_margin)
                        if rects_overlap(rect, (0, ty, adj_depth, by)):
                            violations.append("인접 방 문 통행 구역 침범")
                    elif abs(door_gx - (cr_x + cr_w)) < 5:
                        ty = max(0, dy1 - cr_y - adj_margin)
                        by = min(cr_h, dy2 - cr_y + adj_margin)
                        if rects_overlap(rect, (cr_w - adj_depth, ty, cr_w, by)):
                            violations.append("인접 방 문 통행 구역 침범")

    return violations
