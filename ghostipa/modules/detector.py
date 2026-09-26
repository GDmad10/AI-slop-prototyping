"""GHOST APP DETECTOR (§13) — orchestrates metadata + state + verdicts."""
from __future__ import annotations

from dataclasses import dataclass

from ghostipa.core.confidence import Confidence, Verdict
from ghostipa.core.database import AppRecord, ResearchDB
from ghostipa.core.research_log import ResearchLog
from ghostipa.core.state_machine import AppState, StateMachine
from ghostipa.modules.metadata import lookup_by_apple_id, normalize_apple_metadata, search_by_term


@dataclass
class GhostReport:
    app: str
    developer: str
    bundle_id: str
    apple_id: str
    public_listing: str
    metadata: str
    purchase_record: str
    historical_versions: str
    official_distribution: str
    package: str
    installation: str
    reason: str
    confidence: str

    def render(self) -> str:
        return (
            "GHOST APP REPORT\n\n"
            f"Application: {self.app}\n"
            f"Developer: {self.developer}\n"
            f"Bundle ID: {self.bundle_id}\n"
            f"Apple ID: {self.apple_id}\n\n"
            f"Public listing: {self.public_listing}\n"
            f"Metadata: {self.metadata}\n"
            f"Purchase record: {self.purchase_record}\n"
            f"Historical versions: {self.historical_versions}\n"
            f"Official distribution: {self.official_distribution}\n"
            f"Package: {self.package}\n"
            f"Installation: {self.installation}\n\n"
            f"Reason: {self.reason}\n"
            f"Confidence: {self.confidence}\n"
        )


def detect(name: str = "", apple_id: str = "", bundle_id: str = "",
           country: str = "us", db: ResearchDB | None = None,
           log: ResearchLog | None = None) -> tuple[GhostReport, StateMachine, AppRecord]:
    """Run the §4 state machine over live Apple metadata. Never claims loss without evidence."""
    sm = StateMachine()
    log = log or ResearchLog()
    db = db or ResearchDB()

    raw: dict | None = None
    if apple_id:
        log.log("SEARCH", "Apple metadata", apple_id)
        res = lookup_by_apple_id(apple_id, country)
        if res.found:
            raw = res.raw
            log.log("RESULT", "Apple metadata", "Application record found")
        else:
            log.log("RESULT", "Apple metadata", "No public record", error=res.error)
    elif name or bundle_id:
        term = name or bundle_id
        log.log("SEARCH", "Apple metadata", term)
        hits = search_by_term(term, country)
        if bundle_id:
            hits = [h for h in hits if h.get("bundleId", "").lower() == bundle_id.lower()]
        if hits:
            raw = hits[0]
            log.log("RESULT", "Apple metadata", f"{len(hits)} hit(s), best match kept")
        else:
            log.log("RESULT", "Apple metadata", "No public listing — record may be delisted, not deleted")

    if raw:
        sm.advance(AppState.APP_RECORD_FOUND)
        meta = normalize_apple_metadata(raw)
        sm.advance(AppState.PUBLIC_LISTED)
        record = AppRecord(
            name=meta["name"], bundle_id=meta["bundle_id"], apple_id=meta["apple_id"],
            developer=meta["developer"], status="PUBLIC_LISTED",
            metadata_found=True, source="Apple metadata", extra=meta,
        )
        report = GhostReport(
            app=record.name, developer=record.developer,
            bundle_id=record.bundle_id, apple_id=record.apple_id,
            public_listing="YES", metadata="FOUND",
            purchase_record="UNKNOWN", historical_versions="NOT FOUND",
            official_distribution="AVAILABLE", package="UNKNOWN",
            installation="UNKNOWN",
            reason="Public listing found; check purchase history + device compatibility for install.",
            confidence=Confidence.HIGH.value,
        )
    else:
        # Not visible ≠ gone (§4, §28): check the local preservation DB for history.
        key = apple_id or bundle_id or (name or "").replace(" ", "_")
        prior = db.load(key) if key else None
        if prior is not None:
            sm.advance(AppState.APP_RECORD_FOUND)
            sm.advance(AppState.DELISTED)
            sm.advance(AppState.DISTRIBUTION_CHECK)
            record = prior
            record.status = "DELISTED"
            report = GhostReport(
                app=prior.name, developer=prior.developer,
                bundle_id=prior.bundle_id, apple_id=prior.apple_id,
                public_listing="NO", metadata="FOUND",
                purchase_record="UNKNOWN",
                historical_versions="FOUND" if prior.historical_versions else "NOT FOUND",
                official_distribution="UNKNOWN", package="UNKNOWN",
                installation="UNKNOWN",
                reason=("Delisted from public search but preserved in local research DB. "
                        "Check purchase history for redownload rights."),
                confidence=Confidence.MEDIUM.value,
            )
        else:
            sm.advance(AppState.PACKAGE_NOT_FOUND)
            record = AppRecord(name=name or key or "unknown", bundle_id=bundle_id,
                               apple_id=apple_id, status="UNKNOWN",
                               metadata_found=False, source="Apple metadata")
            report = GhostReport(
                app=record.name, developer="", bundle_id=bundle_id,
                apple_id=apple_id, public_listing="NO", metadata="NOT FOUND",
                purchase_record="UNKNOWN", historical_versions="NOT FOUND",
                official_distribution="UNKNOWN", package="UNKNOWN",
                installation="UNKNOWN",
                reason=("No public record and no local history. Verdict: "
                        f"{Verdict.UNKNOWN.value} — not proven lost, not proven present. "
                        "Try web-archive + multilingual search modules."),
                confidence=Confidence.UNKNOWN.value,
            )
    db.save(record)
    return report, sm, record
