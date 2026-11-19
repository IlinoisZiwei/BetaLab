"""Explicit measured geometry; no inferred intrinsics or reused Trial2 angles."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class RootFrame(Model):
    plane_id: str
    origin_cm: Point3
    u_axis: Point3
    v_axis: Point3

class Join(Model):
    parent: str
    child: str
    parent_edge_cm: tuple[Point2, Point2]
    child_edge_cm: tuple[Point2, Point2]
    fold_deg: float = Field(ge=-179, le=179)

class Intrinsics(Model):
    fx: float = Field(gt=0)
    fy: float = Field(gt=0)
    cx: float = Field(ge=0)
    cy: float = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    distortion: tuple[float, float, float, float, float]
    provenance: str = Field(min_length=3, max_length=1000)

class Observation(Model):
    plane_id: str
    uv_cm: Point2
    pixel: Point2
    role: Literal['fit', 'check'] = 'fit'

class CameraFrame(Model):
    frame: int = Field(ge=0, strict=True)
    observations: list[Observation] = Field(min_length=8, max_length=200)

class WorldReview(Model):
    base_version: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    calibration_version: str = Field(pattern=r'^[a-f0-9]{64}$')
    contact_version: str = Field(pattern=r'^[a-f0-9]{64}$')
    root: RootFrame
    joins: list[Join] = Field(max_length=11)
    intrinsics: Intrinsics
    cameras: list[CameraFrame] = Field(min_length=1, max_length=1350)
    fixed_camera_confirmed: bool = False
    measurements_confirmed: bool = False
    notes: str = Field(min_length=3, max_length=3000)

    @model_validator(mode='after')
    def unique(self):
        if len({c.frame for c in self.cameras}) != len(self.cameras):
            raise ValueError('Duplicate camera frame')
        if len({j.child for j in self.joins}) != len(self.joins):
            raise ValueError('A panel must have one parent')
        if not self.measurements_confirmed:
            raise ValueError('Confirm measured inputs before saving global alignment')
        return self
