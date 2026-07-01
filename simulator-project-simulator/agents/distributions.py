from pydantic import BaseModel, Field, model_validator
from typing import Annotated, Literal, Union

# ---------------------------------------------------------------------------
# Distribution specs
# ---------------------------------------------------------------------------
# Discriminated union keyed on `kind`, so JSON/YAML round-trips unambiguously
# and Pydantic can validate "unknown distribution types" per the acceptance
# criteria, rather than accepting an arbitrary dict.

class FixedDistribution(BaseModel):
    kind: Literal["fixed"] = "fixed"
    value: float | int | bool | str


class UniformDistribution(BaseModel):
    kind: Literal["uniform"] = "uniform"
    low: float
    high: float

    @model_validator(mode="after")
    def _check_bounds(self) -> "UniformDistribution":
        if self.low > self.high:
            raise ValueError(f"uniform distribution: low ({self.low}) must be <= high ({self.high})")
        return self

class BinomialDistribution(BaseModel):
    kind: Literal["binomial"] = "binomial"
    n: int
    prob: float

    @model_validator(mode="after")
    def _check_bounds(self) -> "BinomialDistribution":
        if self.prob > 1 or self.prob < 0:
            raise ValueError(f"binomial distribution: probability must be between 0 and 1, got {self.prob}")
        return self

class PoissonDistribution(BaseModel):
    kind: Literal["poisson"] = "poisson"
    prob: float  # lambda
    exp_num_event: int  # k

    @model_validator(mode="after")
    def _check_bounds(self) -> "PoissonDistribution":
        if self.prob > 1 or self.prob < 0:
            raise ValueError(f"poisson distribution: probability must be between 0 and 1, got {self.prob}")
        return self

class NormalDistribution(BaseModel):
    kind: Literal["normal"] = "normal"
    mean: float
    stddev: float

    @model_validator(mode="after")
    def _check_stddev(self) -> "NormalDistribution":
        if self.stddev < 0:
            raise ValueError(f"normal distribution: stddev must be >= 0, got {self.stddev}")
        return self


class CategoricalDistribution(BaseModel):
    kind: Literal["categorical"] = "categorical"
    weights: dict[str, float]

    @model_validator(mode="after")
    def _check_weights(self) -> "CategoricalDistribution":
        if not self.weights:
            raise ValueError("categorical distribution: weights must not be empty")
        if any(w < 0 for w in self.weights.values()):
            raise ValueError("categorical distribution: weights must be >= 0")
        return self


Distribution = Annotated[
    Union[FixedDistribution, UniformDistribution, BinomialDistribution, PoissonDistribution, NormalDistribution, CategoricalDistribution],
    Field(discriminator="kind"),
]