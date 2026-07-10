from enum import Enum

'''
Enums
'''

class AttributeType(str, Enum):
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    CATEGORICAL = "categorical"


class GenerationMode(str, Enum):
    HOMOGENEOUS = "homogeneous"
    HETEROGENEOUS = "heterogeneous"


class PopulationMethod(str, Enum):
    """How a heterogeneous attribute's values get filled in.

    DISTRIBUTION and MANUAL are the two paths under "interactive entry"
    in the wizard. BULK_UPLOAD defers population to an external file.
    """
    DISTRIBUTION = "distribution"
    MANUAL = "manual"
    BULK_UPLOAD = "bulk_upload"


class PopulationStatus(str, Enum):
    """Tracks where an agent type sits in the wizard, independent of
    whether the CLI or web renderer is driving it. This is the field
    that should back the "[not configured]" / "[2 types defined]" /
    "pending import" tags shown in the menu.
    """
    NOT_CONFIGURED = "not_configured"
    SCHEMA_ONLY = "schema_only"  # heterogeneous: attributes defined, values not yet
    PENDING_IMPORT = "pending_import"  # heterogeneous + bulk upload: template written, file not loaded
    COMPLETE = "complete"