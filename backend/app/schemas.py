from pydantic import BaseModel, EmailStr, Field


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    remember: bool = False


class ShipmentIn(BaseModel):
    reference: str | None = Field(default=None, max_length=60)
    importer: str = Field(min_length=2, max_length=200)
    exporter: str = Field(min_length=2, max_length=200)
    origin: str = Field(min_length=2, max_length=100)
    destination: str = Field(min_length=2, max_length=100)
    port: str = Field(min_length=2, max_length=160)
    carrier: str = Field(min_length=2, max_length=120)
    container_number: str = Field(min_length=4, max_length=40)
    product_description: str = Field(min_length=3, max_length=2000)


class FieldEdit(BaseModel):
    value: str = Field(max_length=500)


class HsReviewIn(BaseModel):
    action: str  # approve | edit | reject | reanalyze
    hs_code: str | None = None
    note: str | None = Field(default=None, max_length=1000)


class DecisionIn(BaseModel):
    action: str  # approve | reject | edit | reanalyze
    note: str | None = Field(default=None, max_length=1000)


class ShipmentUpdateIn(BaseModel):
    importer: str | None = Field(default=None, max_length=200)
    exporter: str | None = Field(default=None, max_length=200)
    origin: str | None = Field(default=None, max_length=100)
    destination: str | None = Field(default=None, max_length=100)
    port: str | None = Field(default=None, max_length=160)
    carrier: str | None = Field(default=None, max_length=120)
    container_number: str | None = Field(default=None, max_length=40)
    product_description: str | None = Field(default=None, max_length=2000)


class InconsistencyActionIn(BaseModel):
    action: str  # apply | resolve_all | dismiss | reopen
    field: str | None = None
    chosen_value: str | None = None
    doc_name: str | None = None
    note: str | None = None
