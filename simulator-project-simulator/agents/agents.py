from attributeDefinition import AttributeDefinition
from models import GenerationMode, PopulationMethod, PopulationStatus

from pydantic import BaseModel, Field, model_validator

class AgentType(BaseModel):
    '''
    Define the types of agents here. User designs what the agent looks like.
    '''
    name: str
    count: int
    generation_mode: GenerationMode
    attributes: list[AttributeDefinition] = Field(default_factory=list)

    # Only meaningful when generation_mode is HETEROGENEOUS and at least one
    # attribute uses BULK_UPLOAD. Tracks the template/import handoff without
    # this model needing to know anything about file I/O.
    bulk_upload_template_path: str | None = None

    @model_validator(mode="after")
    def _check_count(self) -> "AgentType":
        if self.count < 0:
            raise ValueError(f"agent type '{self.name}': count must be >= 0, got {self.count}")
        return self

    @model_validator(mode="after")
    def _check_duplicate_attribute_names(self) -> "AgentType":
        names = [a.name for a in self.attributes]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"agent type '{self.name}': duplicate attribute names: {sorted(dupes)}")
        return self

    @property
    def status(self) -> PopulationStatus:
        """Derives the wizard-menu status from current state, rather than
        storing it redundantly (avoids it drifting out of sync with the
        actual attribute data)."""
        if not self.attributes:
            return PopulationStatus.NOT_CONFIGURED

        if self.generation_mode == GenerationMode.HOMOGENEOUS:
            # Homogeneous: schema = values, so defined attributes == complete.
            return PopulationStatus.COMPLETE

        # Heterogeneous
        if any(a.population_method == PopulationMethod.BULK_UPLOAD for a in self.attributes):
            if self.bulk_upload_template_path is None:
                return PopulationStatus.SCHEMA_ONLY
            return PopulationStatus.PENDING_IMPORT  # template written, not yet loaded back

        if all(a.population_method is not None for a in self.attributes):
            return PopulationStatus.COMPLETE

        return PopulationStatus.SCHEMA_ONLY