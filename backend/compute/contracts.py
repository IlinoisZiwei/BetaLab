"""Versioned boundary for A/B/C. All lengths in cm, timestamps in seconds.

Joint/contact convention references CIS5810 Beta_Translator, commit
ff85726da2fbbd2616c409b01d6c03833ab62ce9: beta_translator/trials.py,
body_legs.py and trial1_technique_pipeline.py (notebook section 8D).
These are interface definitions, not a port of the technique optimizer.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

Identifier = str

class Body(Model):
    height_cm: float = Field(ge=100, le=230)
    arm_span_cm: float = Field(ge=80, le=260)
    provenance: Literal['user_input', 'manual_correction', 'estimated']

class Calibration(Model):
    version: str = Field(min_length=1)
    grid_spacing_cm: Literal[14.3] = 14.3
    grid_axes_equal: Literal[True] = True
    reference_frame: int = Field(ge=0)
    geometry_status: Literal['assumed', 'reviewed'] = 'assumed'
    coordinate_system: Literal['wall_xyz_cm_y_up'] = 'wall_xyz_cm_y_up'
    evidence_key: str = Field(min_length=1)

class SourceRequest(Model):
    schema_version: Literal[1] = 1
    kind: Literal['analyze'] = 'analyze'
    video_id: str = Field(min_length=1)
    route_id: str = Field(min_length=1)
    calibration: Calibration
    uploader_body: Body | None = None

class GenerationRequest(Model):
    schema_version: Literal[1] = 1
    kind: Literal['generate'] = 'generate'
    video_id: str = Field(min_length=1)
    source_analysis_id: str = Field(min_length=1)
    source_analysis_version: str = Field(min_length=1)
    target_body: Body
    preserve_contact_order: Literal[True] = True
    preserve_contact_timing: Literal[True] = True
    compare_techniques: bool = False
    technique_limit: int = Field(default=3, ge=1, le=3)

    @model_validator(mode='after')
    def user_measurements(self):
        if self.target_body.provenance == 'estimated':
            raise ValueError('Target measurements require user input or manual correction')
        return self

class Artifact(Model):
    storage_key: str = Field(min_length=1, pattern=r'^[A-Za-z0-9_-]+(?:/[A-Za-z0-9_.-]+)+$')
    media_type: str
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    @model_validator(mode='after')
    def no_traversal(self):
        if any(p in ('.', '..') for p in self.storage_key.split('/')):
            raise ValueError('Storage key cannot traverse directories')
        return self

class Suggestion(Model):
    video_id: str
    at_seconds: float = Field(ge=0)
    observed_movement: str
    technique: str
    explanation: str
    evidence: Literal['example', 'model_candidate', 'insufficient']

class Moment(Model):
    """A model diagnostic, not an observed technique recommendation."""
    id: str
    kind: Literal['contact_gap', 'unconfirmed_contact']
    frame: int = Field(ge=0)
    at_seconds: float = Field(ge=0)
    end_frame: int = Field(ge=0)
    limb: Literal['left_hand', 'right_hand', 'left_foot', 'right_foot']
    title: str
    explanation: str
    media: Literal['video'] = 'video'
    gap_cm: float | None = Field(default=None, ge=0)

class Quality(Model):
    evidence: Literal['sufficient', 'low_confidence', 'insufficient']
    geometry_status: Literal['assumed', 'reviewed']
    physical_validation: Literal[False] = False
    check_scope: Literal['none', 'geometry_only', 'full_model'] = 'none'
    warnings: list[str] = Field(default_factory=list)

class Result(Model):
    schema_version: Literal[1] = 1
    kind: Literal['analyze', 'generate']
    is_mock: bool
    algorithm_version: str
    source_analysis_version: str
    calibration_version: str
    source_video_id: str
    frame_count: int = Field(gt=0)
    fps: float = Field(gt=0)
    quality: Quality
    original_body: Body | None = None
    target_body: Body | None = None
    # Analysis artifacts: holds, skeleton, alignment, contacts; generation: video, diagnostics.
    artifacts: dict[str, Artifact] = Field(default_factory=dict)
    baseline_status: Literal['not_requested', 'not_checked', 'passed', 'failed', 'insufficient_evidence']
    technique_status: Literal['not_requested', 'blocked', 'compared', 'no_improvement']
    suggestions: list[Suggestion] = Field(default_factory=list)
    moments: list[Moment] = Field(default_factory=list)

    @model_validator(mode='after')
    def consistency(self):
        for moment in self.moments:
            if not moment.frame <= moment.end_frame < self.frame_count or abs(moment.at_seconds-moment.frame/self.fps)>1e-6:
                raise ValueError('Diagnostic moment does not match native frame time')
        if self.technique_status in ('compared', 'no_improvement') and self.baseline_status != 'passed':
            raise ValueError('Compare techniques only after baseline passes model checks')
        if self.quality.evidence == 'insufficient' and self.baseline_status == 'passed':
            raise ValueError('Insufficient evidence cannot pass baseline checks')
        if not self.is_mock and self.quality.evidence != 'insufficient':
            required = {'holds', 'skeleton', 'alignment', 'contacts'} if self.kind == 'analyze' else {'diagnostics'}
            if self.kind == 'generate' and self.baseline_status == 'passed':
                required.add('video')
            if not required.issubset(self.artifacts):
                raise ValueError('Missing required real result artifacts')
        if self.kind == 'generate' and self.target_body is None:
            raise ValueError('Generation must identify target body measurements')
        if any(s.at_seconds > (self.frame_count - 1) / self.fps for s in self.suggestions):
            raise ValueError('Suggestion lies outside native video time axis')
        if self.is_mock and self.artifacts:
            raise ValueError('Mock must not present real-looking generated artifacts')
        return self

class Error(Model):
    code: Literal['INVALID_INPUT', 'SOURCE_UNAVAILABLE', 'STALE_ANALYSIS',
                  'INSUFFICIENT_EVIDENCE', 'WORKER_FAILED', 'INTERRUPTED']
    message: str
    retryable: bool

class Task(Model):
    schema_version: Literal[1] = 1
    id: str
    owner_id: str
    source_video_id: str
    kind: Literal['analyze', 'generate']
    state: Literal['queued', 'running', 'succeeded', 'failed']
    stage: str
    is_mock: bool
    attempt: int = Field(default=1, ge=1)
    retry_of: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    result: Result | None = None
    error: Error | None = None

    @model_validator(mode='after')
    def terminal_payload(self):
        if (self.state == 'succeeded') != (self.result is not None):
            raise ValueError('Only succeeded tasks have a result')
        if (self.state == 'failed') != (self.error is not None):
            raise ValueError('Only failed tasks have an error')
        if self.result and (self.result.kind != self.kind or self.result.is_mock != self.is_mock
                            or self.result.source_video_id != self.source_video_id):
            raise ValueError('Task/result identity mismatch')
        return self

class Notification(Model):
    id: str
    owner_id: str
    task_id: str
    event: Literal['task_succeeded', 'task_failed']
    created_at: str
    read_at: str | None = None
    is_mock: bool
