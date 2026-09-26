"""Ghost IPA Installer — state machine (§4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AppState(str, Enum):
    UNKNOWN = "UNKNOWN"
    APP_RECORD_FOUND = "APP_RECORD_FOUND"
    PUBLIC_LISTED = "PUBLIC_LISTED"
    DELISTED = "DELISTED"
    DEVELOPER_REMOVED = "DEVELOPER_REMOVED"
    APPLE_REMOVED = "APPLE_REMOVED"
    REGION_RESTRICTED = "REGION_RESTRICTED"
    PURCHASE_RECORD_FOUND = "PURCHASE_RECORD_FOUND"
    DISTRIBUTION_CHECK = "DISTRIBUTION_CHECK"
    PACKAGE_AVAILABLE = "PACKAGE_AVAILABLE"
    PACKAGE_UNAVAILABLE = "PACKAGE_UNAVAILABLE"
    PACKAGE_NOT_FOUND = "PACKAGE_NOT_FOUND"
    PACKAGE_CORRUPTED = "PACKAGE_CORRUPTED"
    ENCRYPTED_PACKAGE = "ENCRYPTED_PACKAGE"
    ACCOUNT_REQUIRED = "ACCOUNT_REQUIRED"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INSTALLATION_CHECK = "INSTALLATION_CHECK"
    INSTALLABLE = "INSTALLABLE"
    NOT_INSTALLABLE = "NOT_INSTALLABLE"
    DEVICE_INCOMPATIBLE = "DEVICE_INCOMPATIBLE"
    IOS_VERSION_INCOMPATIBLE = "IOS_VERSION_INCOMPATIBLE"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


# Allowed forward edges. Terminal-ish states have no outgoing edges.
_TRANSITIONS: dict[AppState, set[AppState]] = {
    AppState.UNKNOWN: {
        AppState.APP_RECORD_FOUND, AppState.PACKAGE_NOT_FOUND,
        AppState.REGION_RESTRICTED, AppState.UNKNOWN_ERROR,
    },
    AppState.APP_RECORD_FOUND: {
        AppState.PUBLIC_LISTED, AppState.DELISTED,
        AppState.DEVELOPER_REMOVED, AppState.APPLE_REMOVED,
        AppState.REGION_RESTRICTED,
    },
    AppState.PUBLIC_LISTED: {AppState.DISTRIBUTION_CHECK, AppState.PURCHASE_RECORD_FOUND},
    AppState.DELISTED: {
        AppState.PURCHASE_RECORD_FOUND, AppState.DEVELOPER_REMOVED,
        AppState.APPLE_REMOVED, AppState.REGION_RESTRICTED,
        AppState.DISTRIBUTION_CHECK,
    },
    AppState.DEVELOPER_REMOVED: {AppState.PURCHASE_RECORD_FOUND, AppState.DISTRIBUTION_CHECK},
    AppState.APPLE_REMOVED: {AppState.PURCHASE_RECORD_FOUND, AppState.DISTRIBUTION_CHECK},
    AppState.REGION_RESTRICTED: {AppState.PURCHASE_RECORD_FOUND, AppState.DISTRIBUTION_CHECK},
    AppState.PURCHASE_RECORD_FOUND: {AppState.DISTRIBUTION_CHECK, AppState.ACCOUNT_REQUIRED},
    AppState.ACCOUNT_REQUIRED: {AppState.AUTHENTICATION_REQUIRED, AppState.DISTRIBUTION_CHECK},
    AppState.AUTHENTICATION_REQUIRED: {AppState.DISTRIBUTION_CHECK},
    AppState.DISTRIBUTION_CHECK: {
        AppState.PACKAGE_AVAILABLE, AppState.PACKAGE_UNAVAILABLE,
        AppState.PACKAGE_NOT_FOUND, AppState.ACCOUNT_REQUIRED,
        AppState.AUTHENTICATION_REQUIRED, AppState.NOT_AUTHORIZED,
        AppState.UNKNOWN_ERROR,
    },
    AppState.PACKAGE_AVAILABLE: {AppState.INSTALLATION_CHECK, AppState.ENCRYPTED_PACKAGE, AppState.PACKAGE_CORRUPTED},
    AppState.ENCRYPTED_PACKAGE: {AppState.INSTALLATION_CHECK, AppState.NOT_INSTALLABLE},
    AppState.PACKAGE_CORRUPTED: {AppState.NOT_INSTALLABLE},
    AppState.INSTALLATION_CHECK: {
        AppState.INSTALLABLE, AppState.NOT_INSTALLABLE,
        AppState.DEVICE_INCOMPATIBLE, AppState.IOS_VERSION_INCOMPATIBLE,
        AppState.SIGNATURE_INVALID, AppState.NOT_AUTHORIZED,
    },
}


@dataclass
class StateMachine:
    """Tracks one app's preservation/installation state (§4)."""

    state: AppState = AppState.UNKNOWN
    history: list[str] = field(default_factory=lambda: [AppState.UNKNOWN.value])
    documented_reason: str | None = None   # verified removal reason (§14)
    possible_reason: str | None = None     # unverified hypothesis (§14)

    def advance(self, nxt: AppState) -> bool:
        allowed = _TRANSITIONS.get(self.state, set())
        if nxt in allowed or nxt == AppState.UNKNOWN_ERROR:
            self.state = nxt
            self.history.append(nxt.value)
            return True
        return False

    def force(self, nxt: AppState) -> None:
        """Unconditional jump (used for terminal reports)."""
        self.state = nxt
        self.history.append(nxt.value)

    def set_reasons(self, documented: str | None = None, possible: str | None = None) -> None:
        if documented is not None:
            self.documented_reason = documented
        if possible is not None:
            self.possible_reason = possible
