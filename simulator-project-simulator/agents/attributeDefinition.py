from pydantic import BaseModel, model_validator

from .models import AttributeType, PopulationMethod
from .distributions import Distribution

class AttributeDefinition(BaseModel):
    name: str
    type: AttributeType

    # Only set once a population method has been chosen for this attribute.
    # None means "schema defined, not yet populated" — the SCHEMA_ONLY state
    # from the sub-flow diagram.
    population_method: PopulationMethod | None = None
    distribution: Distribution | None = None

    @model_validator(mode="after")
    def _check_distribution_matches_method(self) -> "AttributeDefinition":
        if self.population_method == PopulationMethod.DISTRIBUTION and self.distribution is None:
            raise ValueError(f"attribute '{self.name}': population_method is 'distribution' but no distribution is set")
        if self.population_method != PopulationMethod.DISTRIBUTION and self.distribution is not None:
            raise ValueError(
                f"attribute '{self.name}': distribution is set but population_method is '{self.population_method}'")
        return self