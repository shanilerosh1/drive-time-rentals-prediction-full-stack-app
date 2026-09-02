from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models import Inspection, Vehicle
from app.schemas.common import Message, Page
from app.schemas.vehicle import VehicleCreate, VehicleRead, VehicleUpdate, VehicleWithStats

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=Page[VehicleWithStats])
def list_vehicles(
    db: DbSession,
    _: CurrentUser,
    search: str | None = Query(default=None, description="Match registration, make or model"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[VehicleWithStats]:
    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                Vehicle.registration.ilike(pattern),
                Vehicle.make.ilike(pattern),
                Vehicle.model.ilike(pattern),
            )
        )

    total = db.execute(select(func.count()).select_from(Vehicle).where(*filters)).scalar_one()

    # One grouped query for the counts rather than a query per row.
    stats_stmt = (
        select(
            Inspection.vehicle_id,
            func.count(Inspection.id),
            func.max(Inspection.created_at),
        )
        .group_by(Inspection.vehicle_id)
    )
    stats = {row[0]: (row[1], row[2]) for row in db.execute(stats_stmt).all()}

    vehicles = (
        db.execute(
            select(Vehicle)
            .where(*filters)
            .order_by(Vehicle.registration)
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

    items = []
    for vehicle in vehicles:
        count, last = stats.get(vehicle.id, (0, None))
        item = VehicleWithStats.model_validate(vehicle)
        item.inspection_count = count
        item.last_inspected_at = last
        items.append(item)

    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle(payload: VehicleCreate, db: DbSession, _: CurrentUser) -> Vehicle:
    existing = db.execute(
        select(Vehicle).where(Vehicle.registration == payload.registration)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle {payload.registration} is already on the fleet.",
        )
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/{vehicle_id}", response_model=VehicleRead)
def read_vehicle(vehicle_id: int, db: DbSession, _: CurrentUser) -> Vehicle:
    return _get_or_404(db, vehicle_id)


@router.patch("/{vehicle_id}", response_model=VehicleRead)
def update_vehicle(
    vehicle_id: int, payload: VehicleUpdate, db: DbSession, _: CurrentUser
) -> Vehicle:
    vehicle = _get_or_404(db, vehicle_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", response_model=Message)
def delete_vehicle(vehicle_id: int, db: DbSession, _: AdminUser) -> Message:
    """Admin only: this cascades to the vehicle's inspection history."""
    vehicle = _get_or_404(db, vehicle_id)
    registration = vehicle.registration
    db.delete(vehicle)
    db.commit()
    return Message(detail=f"Vehicle {registration} and its inspection history were deleted.")


def _get_or_404(db, vehicle_id: int) -> Vehicle:
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found.")
    return vehicle
