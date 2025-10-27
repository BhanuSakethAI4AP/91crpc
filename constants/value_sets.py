"""
Purpose: Centralized enum definitions for 91CrPC system.
All value sets used across the application for status tracking, roles, and types.
"""

from enum import Enum


# ========== Operator Types ==========
class OperatorType(str, Enum):
    """Types of operators that can receive CrPC requests."""
    TELECOM = "Telecom"
    BANK = "Bank"
    ISP = "ISP"


# ========== Request Status ==========
class CrpcRequestStatus(str, Enum):
    """Status values for main CrPC requests."""
    ON_APPROVAL_QUEUE = "OnApprovalQueue"
    APPROVED = "Approved"
    REJECT = "Reject"
    CLOSED = "Closed"
    SENT = "sent"  # Added from your data model


class LineItemRequestStatus(str, Enum):
    """Status values for individual line items in request pipelines."""
    ON_APPROVAL_QUEUE = "OnApprovalQueue"
    APPROVED = "Approved"
    REJECT = "Reject"
    FLAGGED_AS_VIP = "FlagedAsVIP"
    APPROVED_BY_SHO = "ApprovedbySHO"  # Added from your data model


class ConsolidatedCrpcRequestStatus(str, Enum):
    """Status for consolidated dispatch packets."""
    DOWNLOADED = "Downloaded"
    NOT_DOWNLOADED = "NotDownloaded"
    DOWNLOADED_LOWER = "downloaded"  # Added from your data model (lowercase variant)


class DataReceivedStatus(str, Enum):
    """Status for received data from operators."""
    MAPPED = "Mapped"
    CONFLICT = "Conflict"


# ========== Approval Chain ==========
class ApprovalRole(str, Enum):
    """Roles in the approval workflow hierarchy."""
    IO = "IO"
    SHO = "SHO"
    CI = "CI"
    DSP = "DSP"
    ADMIN_ASP = "Admin ASP"
    SP = "SP"


class ApprovalChainStatus(str, Enum):
    """Status values for approval chain tracking."""
    APPROVED_BY_SHO = "ApprovedbySHO"
    APPROVED_BY_CI = "ApprovedbyCI"
    APPROVED_BY_DSP = "ApprovedbyDSP"
    APPROVED_BY_ASP = "ApprovedbyASP"
    ACK_BY_IT_CORE = "AckByITCore"
    REJECT = "Reject"
    FLAGGED_AS_VIP = "FlagedAsVIP"
    APPROVED = "Approved"  # Added from your data model


# ========== Dispatch & Communication ==========
class DispatchMode(str, Enum):
    """Methods for dispatching consolidated requests to operators."""
    EMAIL = "Email"
    SMS = "SMS"


class RejectReason(str, Enum):
    """Predefined reasons for request rejection."""
    VIP_NUMBER = "VIP Number ....."
    # Add more reasons as needed


# ========== Helper Functions ==========
def get_enum_values(enum_class: type[Enum]) -> list[str]:
    """
    Get all values from an enum class.
    
    Args:
        enum_class: The enum class to extract values from
        
    Returns:
        List of enum values as strings
        
    Example:
        >>> get_enum_values(OperatorType)
        ['Telecom', 'Bank', 'ISP']
    """
    return [item.value for item in enum_class]


def validate_enum_value(enum_class: type[Enum], value: str) -> bool:
    """
    Check if a value is valid for a given enum.
    
    Args:
        enum_class: The enum class to check against
        value: The value to validate
        
    Returns:
        True if valid, False otherwise
        
    Example:
        >>> validate_enum_value(OperatorType, "Telecom")
        True
        >>> validate_enum_value(OperatorType, "Invalid")
        False
    """
    return value in get_enum_values(enum_class)
