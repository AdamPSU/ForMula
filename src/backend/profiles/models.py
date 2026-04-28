from typing import Literal

from pydantic import BaseModel, Field, field_validator

CurlPattern = Literal["straight", "wavy", "curly", "coily"]
ScalpCondition = Literal["oily", "dry", "flaky", "sensitive", "balanced"]
Density = Literal["thin", "medium", "thick"]
StrandThickness = Literal["fine", "medium", "coarse"]
ChemicalTreatment = Literal[
    "none",
    "color_treated",
    "bleached_highlighted",
    "relaxed_or_permed",
    "multiple",
]
HeatToolFrequency = Literal["never", "occasional", "weekly", "frequent"]
Concern = Literal[
    "frizz", "breakage", "thinning", "dandruff",
    "dryness", "dullness", "flatness", "irritation",
]
Goal = Literal[
    "definition", "volume", "strength", "length", "scalp_health", "shine",
]
ProductAbsorption = Literal["soaks", "medium", "sits", "greasy", "unsure"]
WashFrequency = Literal["daily", "2_3_days", "weekly", "less"]
Climate = Literal["humid", "dry", "cold", "mixed"]


class HairProfile(BaseModel):
    """Validated quiz answers — one HairProfile per hair_intakes row."""

    curl_pattern: CurlPattern
    scalp_condition: ScalpCondition
    density: Density
    strand_thickness: StrandThickness
    chemical_treatment: ChemicalTreatment
    heat_tool_frequency: HeatToolFrequency
    concerns: list[Concern] = Field(max_length=3)
    goals: list[Goal] = Field(min_length=1)
    product_absorption: ProductAbsorption
    wash_frequency: WashFrequency
    climate: Climate
    story: str | None = Field(default=None, max_length=800)

    @field_validator("story", mode="before")
    @classmethod
    def _strip_story(cls, v: object) -> object:
        # Treat blank / whitespace-only as None so `serialize_profile`
        # cleanly omits the line — same positives-only discipline as
        # chemical_treatment != "none", heat_tool_frequency != "never".
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class HairProfileSubmission(BaseModel):
    quiz_version: int
    profile: HairProfile
