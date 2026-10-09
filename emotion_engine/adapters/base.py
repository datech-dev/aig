"""
Base Output Adapter abstraction.
"""

from typing import Dict, Any, Optional
from ..models import ResponsePlan
from ..interfaces import OutputAdapterProtocol


class BaseOutputAdapter(OutputAdapterProtocol):
    """
    Abstract base class for all output adapters.
    Ensures gracefully degraded execution if third-party providers or media are unavailable.
    """

    async def format_output(
        self,
        text_response: str,
        plan: ResponsePlan,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Transforms raw text response and ResponsePlan into channel-specific payload.
        """
        raise NotImplementedError("Subclasses must implement format_output")
