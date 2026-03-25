from __future__ import annotations
from pydantic import BaseModel
from typing import Literal, Any


# --- Products ---

class ProductOut(BaseModel):
    product_id: int
    model_id: str
    name: str
    category: str
    product_type: str = "appliance"
    brand: str | None = None
    list_price: float | None = None
    discount_rate: int | None = None
    price: float | None = None
    review_score: float | None = None
    review_count: int | None = None
    url: str | None = None
    image_url: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    depth_mm: float | None = None
    is_placeable: bool = True
    mount_type: str = "floor"


class CategoryOut(BaseModel):
    category: str
    count: int


# --- Floor Plans ---

class FloorPlanRoomOut(BaseModel):
    id: int
    floor_plan_id: int
    name: str
    room_type: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    is_placeable: bool = True
    features: list[dict] = []


class FloorPlanOut(BaseModel):
    id: int
    name: str
    category: str
    total_area_m2: float | None = None
    total_width_mm: float
    total_height_mm: float
    thumbnail_url: str | None = None
    is_active: bool = True
    rooms: list[FloorPlanRoomOut] = []


# --- Sessions (placement_group) ---

class SessionCreate(BaseModel):
    floor_plan_id: int
    session_name: str = "새 배치"
    user_id: int = 1


class SessionOut(BaseModel):
    id: int
    floor_plan_id: int
    session_name: str
    floor_plan: FloorPlanOut | None = None


# --- Placements ---

class PlacementCreate(BaseModel):
    product_id: int
    x_mm: float
    y_mm: float
    rotation: Literal[0, 90, 180, 270] = 0


class PlacementUpdate(BaseModel):
    x_mm: float
    y_mm: float
    rotation: Literal[0, 90, 180, 270] = 0


class PlacementOut(BaseModel):
    id: int
    session_id: int
    room_id: int
    product_id: int
    x_mm: float
    y_mm: float
    rotation: int
    is_valid: bool = True
    violations: list[str] = []
    product: ProductOut | None = None


class AutoPlaceRequest(BaseModel):
    product_ids: list[int]


class AutoPlaceResponse(BaseModel):
    placements: list[PlacementOut]
    warnings: list[str] = []


class ValidationResult(BaseModel):
    placement_id: int
    is_valid: bool
    violations: list[str] = []
