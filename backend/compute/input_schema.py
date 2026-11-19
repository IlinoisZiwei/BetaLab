"""Validated owner review input; dimensions are cm, image points are pixels."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Point = tuple[float, float]
class Plane(BaseModel):
    model_config = ConfigDict(extra='forbid',allow_inf_nan=False)
    id: str = Field(min_length=1,max_length=60)
    polygon: list[Point] = Field(min_length=3,max_length=30)
    grid_corners: list[Point] = Field(min_length=4,max_length=4)
    horizontal_steps: int = Field(ge=1,le=100)
    vertical_steps: int = Field(ge=1,le=100)
    angle_from_horizontal_deg: float | None = Field(default=None,ge=0,le=180)
    note: str = Field(min_length=1,max_length=1000)

class CalibrationReview(BaseModel):
    model_config = ConfigDict(extra='forbid',allow_inf_nan=False)
    base_version: str | None = None
    grid_spacing_cm: Literal[14.3] = 14.3
    reference_frame: int = Field(ge=0)
    selected_hold_ids: list[str] = Field(min_length=1,max_length=500)
    planes: list[Plane] = Field(min_length=1,max_length=12)
    identity_confirmed: bool = False
    contact_reviewed: bool = False
    notes: str = Field(min_length=1,max_length=3000)
    @model_validator(mode='after')
    def unique(self):
        if len(set(self.selected_hold_ids))!=len(self.selected_hold_ids):raise ValueError('Duplicate hold IDs')
        if len({p.id for p in self.planes})!=len(self.planes):raise ValueError('Duplicate plane IDs')
        # Confirmation must not silently promote unchanged automatic contacts.
        if self.contact_reviewed:raise ValueError('Use the separate contact-review endpoint; keep calibration contact_reviewed=false')
        return self
