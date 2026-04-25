from typing import Literal

from pydantic import BaseModel, Field

CurlPattern = Literal["straight", "wavy", "curly", "coily"]
ScalpCondition = Literal["oily", "dry", "flaky", "sensitive", "balanced"]
Density = Literal["thin", "medium", "thick"]
StrandThickness = Literal["fine", "medium", "coarse"]
DryingMethod = Literal["air_dry", "blow_dry"]
Concern = Literal[
    "frizz", "breakage", "thinning", "dandruff",
    "dryness", "dullness", "flatness", "irritation",
]
Goal = Literal[
    "definition", "volume", "strength", "length", "scalp_health", "shine",
]
ProductAbsorption = Literal["soaks", "sits", "greasy", "unsure"]
WashFrequency = Literal["daily", "2_3_days", "weekly", "less"]
Climate = Literal["humid", "dry", "cold", "mixed"]


class HairProfile(BaseModel):
    """Validated quiz answers — one HairProfile per hair_intakes row."""

    curl_pattern: CurlPattern
    scalp_condition: ScalpCondition
    density: Density
    strand_thickness: StrandThickness
    drying_method: DryingMethod
    concerns: list[Concern] = Field(max_length=3)
    goals: list[Goal] = Field(min_length=1)
    product_absorption: ProductAbsorption
    wash_frequency: WashFrequency
    climate: Climate


class HairProfileSubmission(BaseModel):
    quiz_version: int
    profile: HairProfile
