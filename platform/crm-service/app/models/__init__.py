from .audit import CRMAuditEvent
from .comments import CRMComment
from .contacts import CRMContact
from .deals import CRMDeal
from .pipelines import CRMPipeline, CRMPipelineStage
from .tasks import CRMTask

__all__ = [
    "CRMAuditEvent",
    "CRMComment",
    "CRMContact",
    "CRMDeal",
    "CRMPipeline",
    "CRMPipelineStage",
    "CRMTask",
]
