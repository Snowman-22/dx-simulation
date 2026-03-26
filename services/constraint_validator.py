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
    # Sliding doors have no swing zone
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


def get_door_passage_zone(door: dict, room_width: float, room_height: float):
    """문 앞 통행 구역: 문 너비 + 양옆 여유, 깊이.
    미닫이문은 스윙 없이 옆으로 밀리므로 통행 구역을 줄임.
    사람이 지나다닐 수 있도록 이 영역에는 가전/가구를 배치하면 안 됨."""
    wall = door["wall"]
    offset = door["offset"]
    dw = door["width"]
    is_slide = door.get("door_type") == "slide"
    margin = 200 if is_slide else 400    # 문 양옆 여유
    depth = 500 if is_slide else 1200    # 통행 깊이 (소파 등 대형 가구 차단)

    if wall == "north":
        return (max(0, offset - margin), 0,
                min(room_width, offset + dw + margin), depth)
    elif wall == "south":
        return (max(0, offset - margin), room_height - depth,
                min(room_width, offset + dw + margin), room_height)
    elif wall == "west":
        return (0, max(0, offset - margin),
                depth, min(room_height, offset + dw + margin))
    else:
        return (room_width - depth, max(0, offset - margin),
                room_width, min(room_height, offset + dw + margin))


def get_door_entry_zone(door: dict, room_width: float, room_height: float):
    """문 진입 방향(바깥쪽) 통행 구역.
    문이 있는 벽의 반대쪽(방 안쪽)에서 문으로 접근하는 경로."""
    wall = door["wall"]
    offset = door["offset"]
    dw = door["width"]
    is_slide = door.get("door_type") == "slide"
    margin = 100 if is_slide else 200
    depth = 200 if is_slide else 500

    # 문이 벽에 있으면 방 안쪽에서 접근하는 구역
    if wall == "north":
        return (max(0, offset - margin), 0,
                min(room_width, offset + dw + margin), depth)
    elif wall == "south":
        return (max(0, offset - margin), room_height - depth,
                min(room_width, offset + dw + margin), room_height)
    elif wall == "west":
        return (0, max(0, offset - margin),
                depth, min(room_height, offset + dw + margin))
    else:
        return (room_width - depth, max(0, offset - margin),
                room_width, min(room_height, offset + dw + margin))


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

    return violations
