"""Human contact intervals on the sampled analysis-video timeline."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

LIMBS = ('left_hand', 'right_hand', 'left_foot', 'right_foot')

class ContactInterval(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    limb: Literal['left_hand', 'right_hand', 'left_foot', 'right_foot']
    state: Literal['hold', 'free', 'unknown'] = 'hold'
    hold_id: str | None = Field(default=None, min_length=1, max_length=100)
    start_frame: int = Field(ge=0, strict=True)
    release_frame: int = Field(gt=0, strict=True)
    note: str = Field(default='', max_length=500)

    @model_validator(mode='after')
    def valid_interval(self):
        if self.release_frame <= self.start_frame:
            raise ValueError('Release frame must be after contact start')
        if (self.state == 'hold') != (self.hold_id is not None):
            raise ValueError('Only hold contacts require a hold ID')
        return self

class ContactReview(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    base_version: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    intervals: list[ContactInterval] = Field(max_length=5000)
    confirmed: bool = False
    notes: str = Field(min_length=1, max_length=3000)
