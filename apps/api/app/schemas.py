from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterInput(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_]{3,24}$")
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class Profile(BaseModel):
    id: str
    username: str
    xp: int = 0
    public_leaderboard: bool = False


class ProfileUpdate(BaseModel):
    public_leaderboard: bool | None = None


class UploadSignInput(BaseModel):
    content_type: Literal["image/jpeg", "image/png", "image/webp"]


class UploadSignOutput(BaseModel):
    key: str
    upload_url: str
    method: Literal["PUT"] = "PUT"


class DiscoveryInput(BaseModel):
    image_key: str
    client_capture_id: str = Field(min_length=8, max_length=100)
    session_id: str | None = None
    challenge_id: str | None = None


class Discovery(BaseModel):
    id: str
    status: str
    created_at: datetime
    image_url: str | None = None
    common_name: str | None = None
    scientific_name: str | None = None
    category: str | None = None
    species_id: str | None = None
    uncertainty: str | None = None
    guidance: str | None = None
    xp_awarded: int = 0
    session_id: str | None = None


class HuntInput(BaseModel):
    duration_minutes: Literal[10, 20, 30] = 20


class FocusSignal(BaseModel):
    kind: Literal["hidden", "visible", "pagehide"]
    client_at: datetime | None = None


class SpeciesRequirement(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    kind: Literal["species"]
    species_id: str
    count: Literal[1] = 1


class CategoryRequirement(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    kind: Literal["taxon_category"]
    category: Literal["plant", "bird", "insect", "butterfly", "flowering_plant", "tree"]
    distinct_species: int = Field(ge=0, default=0)
    count: int = Field(ge=1, le=5, default=1)


class TraitRequirement(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    kind: Literal["visual_trait"]
    trait_code: Literal["serrated_leaf", "yellow_flower", "five_petals", "striped_wing"]
    count: int = Field(ge=1, le=5, default=1)
    distinct_observations: bool = True


Requirement = Annotated[
    SpeciesRequirement | CategoryRequirement | TraitRequirement,
    Field(discriminator="kind"),
]


class ChallengeInput(BaseModel):
    friend_id: str
    duration_minutes: Literal[15, 20, 30] = 20
    requirements: list[Requirement] = Field(min_length=3, max_length=5)


class FriendRequestInput(BaseModel):
    username: str


class CaptureRegistration(BaseModel):
    client_capture_id: str = Field(min_length=8, max_length=100)
