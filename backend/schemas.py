from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TraitFilter(BaseModel):
    name: str
    breakpoint: int = Field(ge=1)


class SearchRequest(BaseModel):
    set_number: str = Field(default="17")
    level: int = Field(ge=1, le=12)
    carry: Optional[str] = None
    include_units: List[str] = Field(default_factory=list)
    exclude_units: List[str] = Field(default_factory=list)
    exclude_costs: List[int] = Field(default_factory=list)
    cost_1_count: Optional[int] = Field(default=None, ge=0)
    cost_2_count: Optional[int] = Field(default=None, ge=0)
    cost_3_count: Optional[int] = Field(default=None, ge=0)
    cost_4_count: Optional[int] = Field(default=None, ge=0)
    cost_5_count: Optional[int] = Field(default=None, ge=0)
    cost_1_min: Optional[int] = Field(default=None, ge=0)
    cost_1_max: Optional[int] = Field(default=None, ge=0)
    cost_2_min: Optional[int] = Field(default=None, ge=0)
    cost_2_max: Optional[int] = Field(default=None, ge=0)
    cost_3_min: Optional[int] = Field(default=None, ge=0)
    cost_3_max: Optional[int] = Field(default=None, ge=0)
    cost_4_min: Optional[int] = Field(default=None, ge=0)
    cost_4_max: Optional[int] = Field(default=None, ge=0)
    cost_5_min: Optional[int] = Field(default=None, ge=0)
    cost_5_max: Optional[int] = Field(default=None, ge=0)
    mecha_transform_min: Optional[int] = Field(default=None, ge=0, le=3)
    mecha_transform_max: Optional[int] = Field(default=None, ge=0, le=3)
    enable_anima_trait: bool = False
    trait_filters: List[TraitFilter] = Field(default_factory=list)
    max_unused_traits: int = Field(default=2, ge=0, le=3)
    trait_plus1: Optional[str] = None
    sort_by: Literal["score", "cost"] = "score"
    limit: int = Field(default=20, ge=1, le=1000)
    min_tanks: float = Field(default=2)
    min_damage: float = Field(default=2)
    max_role_diff: float = Field(default=2)
    role_balance_weight: float = Field(default=8)
    refresh: bool = False


class SearchResponse(BaseModel):
    meta: Dict
    results: List[Dict]


class MetaResponse(BaseModel):
    meta: Dict


class UnitsResponse(BaseModel):
    meta: Dict
    units: List[Dict]


class TraitsResponse(BaseModel):
    meta: Dict
    traits: List[Dict]


class BootstrapResponse(BaseModel):
    meta: Dict
    units: List[Dict]
    traits: List[Dict]


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthStatusResponse(BaseModel):
    authenticated: bool
    username: Optional[str] = None
