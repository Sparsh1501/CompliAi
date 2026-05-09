"""
Device Binding & RASP Advisor Service
=====================================

Provides structured, actionable recommendations on Device Binding and Runtime
Application Self-Protection (RASP) controls for UPI / Mobile Banking apps,
grounded in NPCI circular content already scraped + processed in this system.

The service combines three data sources:

1. Curated NPCI knowledge base (built-in, always available even before any
   circular is scraped) - authoritative requirements derived from public
   circulars such as:
   - OC-193 Standardisation of Device Binding for UPI Applications
   - OC-153 Common Frauds & Risk Management Best Practices for UPI
   - UPI App Security Standards
   - Common UPI fraud risk management circulars (mule accounts, fraud detection)

2. Dynamic clauses extracted from actual scraped circulars
   (npci_circular_clauses + regulations collections) - filtered by
   security/binding/fraud keywords so the advisor surfaces real text.

3. Optional gap-analysis data - when policies have been uploaded and gap
   analysis has been run, the advisor reports which RASP / device binding
   controls already exist and which are missing.

The output is always structured the same way so the React UI can render
deterministic cards / tables.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Curated knowledge base
# ---------------------------------------------------------------------------
# These are the canonical NPCI / RBI requirements for device binding and
# RASP. They are intentionally written as concise, citation-friendly bullets
# and are mapped to specific RASP capabilities. This is the safety net that
# keeps the advisor useful even before any circular is scraped.

CONTROL_AREAS: List[Dict[str, Any]] = [
    {
        "area_id": "device_binding",
        "title": "Device Binding & SIM Binding",
        "description": (
            "Establish a verified one-to-one binding between the customer's "
            "registered mobile number, SIM and the physical device on which "
            "the UPI / mobile banking app is activated."
        ),
        "npci_basis": [
            "OC-193 - Standardisation of Device Binding for UPI Applications",
            "NPCI UPI Procedural Guidelines - section on device binding",
        ],
        "requirements": [
            "Bind the UPI app instance to a unique device identifier (Android ID / iOS DeviceCheck token / Play Integrity attestation).",
            "Verify the SIM serial / IMSI matches the registered mobile number via an outbound SMS-OTP or silent SMS at registration.",
            "Re-bind whenever the SIM, device or app is replaced, with a fresh verification step.",
            "Store the binding fingerprint server-side; never trust client-only state.",
            "Revoke the binding immediately on customer-initiated logout, password reset or SIM swap event.",
        ],
        "rasp_capabilities": [
            "device_attestation",
            "sim_binding_check",
            "app_integrity",
        ],
    },
    {
        "area_id": "tamper_detection",
        "title": "Application Tampering & Integrity Protection",
        "description": (
            "Detect runtime tampering, repackaging or code injection so that "
            "modified app builds cannot transact."
        ),
        "npci_basis": [
            "NPCI UPI App Security Standards",
            "RBI Master Direction on Digital Payment Security Controls (2021) - section on application security",
        ],
        "requirements": [
            "Detect modified APK / IPA signatures (signing certificate pinning).",
            "Detect runtime hooking frameworks (Frida, Xposed, Cydia Substrate).",
            "Detect code injection / dynamic library loading from untrusted paths.",
            "Self-terminate the session when tamper is detected and report the event server-side for fraud analytics.",
            "Use code obfuscation + native-side anti-debug to slow reverse engineering.",
        ],
        "rasp_capabilities": [
            "tamper_detection",
            "hook_detection",
            "anti_debug",
            "code_obfuscation",
            "signing_cert_pinning",
        ],
    },
    {
        "area_id": "rooted_jailbroken",
        "title": "Rooted / Jailbroken Device Detection",
        "description": (
            "Block UPI transactions from devices whose security model has "
            "been compromised by root or jailbreak."
        ),
        "npci_basis": [
            "NPCI UPI Risk Management circulars",
            "RBI Master Direction on Digital Payment Security Controls (2021)",
        ],
        "requirements": [
            "Detect rooted Android (su binary, Magisk, custom recovery) and jailbroken iOS (Cydia, Sileo, palera1n).",
            "Block high-value transactions on rooted/jailbroken devices; allow read-only access only with explicit consent.",
            "Use multiple detection signals (filesystem, system properties, library scan) - not a single check.",
            "Forward detection events to fraud monitoring with device fingerprint.",
        ],
        "rasp_capabilities": [
            "root_detection",
            "jailbreak_detection",
            "magisk_hide_detection",
        ],
    },
    {
        "area_id": "emulator_screen_capture",
        "title": "Emulator, Screen Capture & Overlay Protection",
        "description": (
            "Prevent UPI flows from running inside emulators or being "
            "observed via screen recording / overlay attacks."
        ),
        "npci_basis": [
            "NPCI UPI App Security Standards",
            "Common UPI fraud advisories (overlay & screen-share scams)",
        ],
        "requirements": [
            "Detect Android emulators (qemu props, build.fingerprint signals) and iOS simulators.",
            "Set FLAG_SECURE on all sensitive screens (PIN entry, beneficiary add, transaction confirmation) to block screenshots & screen recording.",
            "Detect active accessibility services and overlay windows during sensitive flows; pause UI and warn the user.",
            "Detect screen-sharing apps (AnyDesk, TeamViewer, RustDesk) and block transactions while they are running.",
        ],
        "rasp_capabilities": [
            "emulator_detection",
            "screen_capture_block",
            "overlay_detection",
            "screen_share_detection",
        ],
    },
    {
        "area_id": "secure_communication",
        "title": "Secure Communication & Certificate Pinning",
        "description": (
            "All UPI / banking traffic must use TLS 1.2+ with certificate "
            "pinning to prevent MITM, even on a compromised network."
        ),
        "npci_basis": [
            "RBI Master Direction on Digital Payment Security Controls (2021)",
            "NPCI Technical Specifications for UPI",
        ],
        "requirements": [
            "Enforce TLS 1.2+; reject plaintext and TLS 1.0/1.1.",
            "Pin the server leaf or intermediate certificate; rotate via signed config push.",
            "Refuse to operate when a user-installed CA is in the trust chain for the UPI APIs.",
            "Detect proxy / VPN injection on the same socket and stop the transaction.",
        ],
        "rasp_capabilities": [
            "certificate_pinning",
            "user_ca_block",
            "proxy_detection",
        ],
    },
    {
        "area_id": "secure_storage",
        "title": "Secure Storage of Credentials & Keys",
        "description": (
            "UPI PIN, mPIN, device-binding keys and cryptographic material "
            "must never leave hardware-backed secure storage."
        ),
        "npci_basis": [
            "NPCI UPI Common Library (CL) specifications",
            "RBI Master Direction on Digital Payment Security Controls (2021)",
        ],
        "requirements": [
            "Store device-binding private keys in Android Keystore / iOS Secure Enclave; never export them.",
            "Never log, print or persist UPI PIN / mPIN in clear text - even in crash reports.",
            "Wipe in-memory secrets immediately after use; use char[] buffers, not String.",
            "Bind cryptographic keys to user authentication (biometric / device passcode) where supported.",
        ],
        "rasp_capabilities": [
            "secure_keystore",
            "memory_wipe",
            "biometric_binding",
        ],
    },
    {
        "area_id": "fraud_telemetry",
        "title": "Fraud Telemetry & Server-Side Risk Engine",
        "description": (
            "RASP signals are only useful if they reach a real-time risk "
            "engine that can decline transactions and trigger step-up auth."
        ),
        "npci_basis": [
            "NPCI Risk Management Best Practices for UPI",
            "RBI circulars on Fraud Risk Management & Common Fraud Avoidance",
        ],
        "requirements": [
            "Stream every RASP detection (root, hook, overlay, emulator, tamper) to the server with device fingerprint and txn context.",
            "Run a real-time scoring model that can decline / step-up / soft-block before debit instruction is sent to NPCI.",
            "Maintain an immutable audit log of detection events for 6+ years per RBI norms.",
            "Provide a feedback loop so confirmed-fraud cases retrain the risk model.",
        ],
        "rasp_capabilities": [
            "telemetry_streaming",
            "server_side_risk_engine",
            "audit_logging",
        ],
    },
]


# RASP capability catalog - reverse index from capability_id to a human label.
RASP_CAPABILITY_CATALOG: Dict[str, Dict[str, str]] = {
    "device_attestation": {
        "label": "Device Attestation",
        "description": "Use Play Integrity / DeviceCheck / SafetyNet equivalent to attest device identity & integrity.",
    },
    "sim_binding_check": {
        "label": "SIM Binding",
        "description": "Verify SIM serial / IMSI matches the registered mobile number via outbound or silent SMS-OTP.",
    },
    "app_integrity": {
        "label": "App Integrity / Signing Verification",
        "description": "Verify the running APK/IPA was signed with the official certificate; refuse repackaged builds.",
    },
    "tamper_detection": {
        "label": "Tamper Detection",
        "description": "Detect modified DEX / Mach-O code, native lib swaps, and runtime patching.",
    },
    "hook_detection": {
        "label": "Hook / Frida / Xposed Detection",
        "description": "Detect Frida-server, Xposed, Cydia Substrate or custom hooking attempts.",
    },
    "anti_debug": {
        "label": "Anti-Debug",
        "description": "Detect attached debuggers (gdb, lldb, JDWP) and self-terminate sensitive flows.",
    },
    "code_obfuscation": {
        "label": "Code Obfuscation",
        "description": "Use R8/ProGuard + native obfuscation; remove logs and reflection strings from release builds.",
    },
    "signing_cert_pinning": {
        "label": "Signing Certificate Pinning",
        "description": "Validate the app's own signing certificate at runtime to block rebuilds.",
    },
    "root_detection": {
        "label": "Root Detection",
        "description": "Detect Android root (su, Magisk, custom recovery, ro.debuggable) using multiple signals.",
    },
    "jailbreak_detection": {
        "label": "Jailbreak Detection",
        "description": "Detect iOS jailbreak (Cydia, Sileo, palera1n, sandbox escape).",
    },
    "magisk_hide_detection": {
        "label": "Magisk-Hide / Zygisk Detection",
        "description": "Detect hide-techniques used to mask root from standard checks.",
    },
    "emulator_detection": {
        "label": "Emulator / Simulator Detection",
        "description": "Detect QEMU, Genymotion, Android Studio emulator and iOS simulator.",
    },
    "screen_capture_block": {
        "label": "Screen Capture / Recording Block",
        "description": "Set FLAG_SECURE on PIN, OTP and txn-confirm screens; block screenshots and recordings.",
    },
    "overlay_detection": {
        "label": "Overlay / Accessibility Abuse Detection",
        "description": "Detect malicious overlay windows and abusive accessibility services during sensitive flows.",
    },
    "screen_share_detection": {
        "label": "Screen-Sharing App Detection",
        "description": "Detect AnyDesk, TeamViewer, RustDesk and similar; block UPI flows while they run.",
    },
    "certificate_pinning": {
        "label": "TLS Certificate Pinning",
        "description": "Pin the leaf or intermediate certificate of bank / NPCI APIs.",
    },
    "user_ca_block": {
        "label": "User-Installed CA Block",
        "description": "Refuse to trust user-installed root CAs for UPI / banking endpoints.",
    },
    "proxy_detection": {
        "label": "Proxy / VPN Injection Detection",
        "description": "Detect proxies / VPNs intercepting UPI traffic; stop the transaction.",
    },
    "secure_keystore": {
        "label": "Hardware-backed Keystore",
        "description": "Store device-binding keys in Android Keystore / iOS Secure Enclave; never export.",
    },
    "memory_wipe": {
        "label": "Secret Memory Wipe",
        "description": "Zeroize PIN / mPIN buffers immediately after cryptographic use.",
    },
    "biometric_binding": {
        "label": "Biometric-bound Keys",
        "description": "Require biometric / device-passcode auth to use binding keys.",
    },
    "telemetry_streaming": {
        "label": "RASP Telemetry Streaming",
        "description": "Forward every detection event to the server-side risk engine in real-time.",
    },
    "server_side_risk_engine": {
        "label": "Server-side Risk Engine",
        "description": "Score and block / step-up transactions based on RASP signals before NPCI debit.",
    },
    "audit_logging": {
        "label": "Detection Audit Log",
        "description": "Tamper-evident log of all detection events retained for 6+ years.",
    },
}


# Keyword bundle used to find security-relevant circulars and clauses.
SECURITY_KEYWORDS = [
    "device binding",
    "device-binding",
    "device bind",
    "rasp",
    "runtime application",
    "root detection",
    "rooted",
    "jailbreak",
    "jailbroken",
    "tamper",
    "tampering",
    "integrity",
    "obfuscation",
    "hook",
    "frida",
    "xposed",
    "emulator",
    "screen recording",
    "screen capture",
    "screen-share",
    "screen sharing",
    "anydesk",
    "teamviewer",
    "overlay",
    "fraud risk management",
    "fraud risk",
    "common fraud",
    "mule",
    "sim binding",
    "sim swap",
    "secure storage",
    "keystore",
    "secure enclave",
    "certificate pinning",
    "tls",
    "mitm",
    "mobile banking security",
    "upi app security",
    "upi security",
    "app security",
    "common library",
    "cl spec",
]


def _matches_security_topic(text: Optional[str]) -> bool:
    """Return True if the given text mentions any device-binding/RASP keyword."""
    if not text:
        return False
    lower = text.lower()
    return any(kw in lower for kw in SECURITY_KEYWORDS)


class DeviceBindingAdvisorService:
    """Aggregates device-binding / RASP guidance from NPCI circulars + curated KB."""

    def __init__(self, db, vector_service=None, llm_service=None):
        self.db = db
        self.vector_service = vector_service
        self.llm_service = llm_service
        self.circulars_collection = db["npci_circulars"]
        self.clauses_collection = db["npci_circular_clauses"]
        self.regulations_collection = db["regulations"]
        self.gap_analyses_collection = db["gap_analyses"]

    # ---------------- helpers ----------------

    async def _find_relevant_circulars(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Pull processed NPCI circulars whose title mentions any security keyword.
        Falls back to scanning extracted clauses if title-search returns nothing.
        """
        circulars: List[Dict[str, Any]] = []
        seen_ids: set = set()

        # 1. Title search (case-insensitive substring)
        title_pattern = "|".join(re.escape(kw) for kw in SECURITY_KEYWORDS)
        try:
            cursor = self.circulars_collection.find({
                "title": {"$regex": title_pattern, "$options": "i"},
            }).sort("year", -1).limit(limit)
            async for doc in cursor:
                doc_id = str(doc.get("_id"))
                if doc_id in seen_ids:
                    continue
                seen_ids.add(doc_id)
                circulars.append({
                    "_id": doc_id,
                    "npci_id": doc.get("npci_id"),
                    "title": doc.get("title", ""),
                    "product": doc.get("product", ""),
                    "product_label": doc.get("product_label", ""),
                    "year": doc.get("year", ""),
                    "pdf_url": doc.get("pdf_url", ""),
                    "processing_status": doc.get("processing_status"),
                    "clause_count": doc.get("clause_count", 0),
                    "summary": (doc.get("raw_text") or "")[:400] if doc.get("raw_text") else None,
                })
        except Exception as e:
            logger.warning(f"[DeviceBindingAdvisor] Circular title search failed: {e}")

        # 2. If nothing found by title, scan clauses for keywords and bubble up
        #    their parent circulars.
        if not circulars:
            try:
                cursor = self.clauses_collection.aggregate([
                    {"$match": {
                        "$or": [
                            {"clause_text": {"$regex": title_pattern, "$options": "i"}},
                            {"category": {"$regex": "security|fraud|technical", "$options": "i"}},
                        ],
                    }},
                    {"$group": {"_id": "$circular_id", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": limit},
                ])
                circular_ids = []
                async for doc in cursor:
                    if doc.get("_id"):
                        circular_ids.append(doc["_id"])

                if circular_ids:
                    from bson import ObjectId
                    object_ids = []
                    for cid in circular_ids:
                        try:
                            object_ids.append(ObjectId(cid))
                        except Exception:
                            continue
                    if object_ids:
                        async for doc in self.circulars_collection.find({"_id": {"$in": object_ids}}):
                            doc_id = str(doc.get("_id"))
                            if doc_id in seen_ids:
                                continue
                            seen_ids.add(doc_id)
                            circulars.append({
                                "_id": doc_id,
                                "npci_id": doc.get("npci_id"),
                                "title": doc.get("title", ""),
                                "product": doc.get("product", ""),
                                "product_label": doc.get("product_label", ""),
                                "year": doc.get("year", ""),
                                "pdf_url": doc.get("pdf_url", ""),
                                "processing_status": doc.get("processing_status"),
                                "clause_count": doc.get("clause_count", 0),
                            })
            except Exception as e:
                logger.warning(f"[DeviceBindingAdvisor] Clause-based circular discovery failed: {e}")

        return circulars

    async def _find_relevant_clauses(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return up to `limit` extracted NPCI clauses matching security keywords."""
        title_pattern = "|".join(re.escape(kw) for kw in SECURITY_KEYWORDS)
        clauses: List[Dict[str, Any]] = []
        try:
            cursor = self.clauses_collection.find({
                "$or": [
                    {"clause_text": {"$regex": title_pattern, "$options": "i"}},
                    {"key_requirements": {"$elemMatch": {"$regex": title_pattern, "$options": "i"}}},
                ],
            }).limit(limit)
            async for doc in cursor:
                clauses.append({
                    "clause_id": doc.get("clause_id"),
                    "circular_id": doc.get("circular_id"),
                    "circular_reference": doc.get("circular_reference", ""),
                    "clause_text": (doc.get("clause_text") or "")[:1200],
                    "category": doc.get("category"),
                    "compliance_impact": doc.get("compliance_impact"),
                    "product": doc.get("product"),
                    "key_requirements": doc.get("key_requirements", []),
                    "entities": doc.get("entities", []),
                })
        except Exception as e:
            logger.warning(f"[DeviceBindingAdvisor] Clause search failed: {e}")
        return clauses

    async def _summarize_with_llm(
        self,
        clauses: List[Dict[str, Any]],
        focus: str = "device binding and RASP precautions for UPI / mobile banking apps",
    ) -> Optional[str]:
        """
        Optionally generate an LLM-written executive summary of the supplied
        clauses. Returns None on any failure - the curated knowledge base is
        always available as a fallback.
        """
        if not clauses or not self.llm_service:
            return None

        try:
            from services.llm_provider import get_llm_provider
            provider = get_llm_provider()
            if provider is None:
                return None

            # Build a condensed context (cap size).
            ctx_lines: List[str] = []
            for c in clauses[:25]:
                ref = c.get("circular_reference") or ""
                txt = (c.get("clause_text") or "").strip()
                if not txt:
                    continue
                ctx_lines.append(f"[{ref}] {txt[:600]}")
            if not ctx_lines:
                return None

            context_block = "\n\n".join(ctx_lines)

            system_prompt = (
                "You are a payments security architect advising a regulated "
                "Indian fintech (UPI / mobile banking). Summarise the supplied "
                "NPCI circular clauses into a crisp executive briefing on "
                f"{focus}. Use plain English, mention specific controls "
                "(device binding, RASP, root/jailbreak detection, screen "
                "capture block, certificate pinning, secure storage), and "
                "call out any deadlines if present. Limit to 5 short "
                "paragraphs."
            )
            user_prompt = (
                f"Source clauses (truncated):\n\n{context_block[:6000]}\n\n"
                "Produce the briefing now."
            )

            summary = await provider.generate(
                system=system_prompt,
                prompt=user_prompt,
                max_tokens=1024,
                temperature=0.2,
            )
            if summary and summary.strip():
                return summary.strip()
        except Exception as e:
            logger.info(f"[DeviceBindingAdvisor] LLM summary skipped: {e}")
        return None

    async def _coverage_from_latest_gap_analysis(
        self,
        organization: str,
    ) -> Dict[str, Any]:
        """
        If the org has run gap analysis, pull the most recent report and try
        to mark which RASP capabilities are already covered by their policy.
        Always returns a dict (with empty mappings on failure).
        """
        coverage: Dict[str, str] = {}  # capability_id -> 'covered' | 'partial' | 'missing'
        latest = None
        try:
            latest = await self.gap_analyses_collection.find_one(
                {"organization": organization},
                sort=[("created_at", -1)],
            )
        except Exception as e:
            logger.warning(f"[DeviceBindingAdvisor] Could not fetch latest gap analysis: {e}")

        if not latest:
            return {"coverage": coverage, "analysis_id": None}

        gaps = latest.get("gaps") or latest.get("enhanced_report", {}).get("gaps") or []
        text_buckets: Dict[str, List[str]] = {"covered": [], "partial": [], "missing": []}
        for g in gaps:
            gap_type = (g.get("gap_type") or "").lower()
            blob_parts = [
                g.get("regulation_text", ""),
                g.get("regulation_title", ""),
                g.get("gap_description", ""),
                " ".join(g.get("covered_elements", []) or []),
                " ".join(g.get("missing_elements", []) or []),
            ]
            blob = " ".join(p for p in blob_parts if p).lower()
            if not blob:
                continue
            if gap_type in ("compliant", "exceeds"):
                text_buckets["covered"].append(blob)
            elif gap_type in ("partial", "weak"):
                text_buckets["partial"].append(blob)
            else:
                text_buckets["missing"].append(blob)

        # Map RASP capability keywords to which bucket they appear in.
        for cap_id, meta in RASP_CAPABILITY_CATALOG.items():
            keywords = [cap_id.replace("_", " "), meta["label"].lower()]
            for status in ("covered", "partial", "missing"):
                if any(kw in entry for entry in text_buckets[status] for kw in keywords):
                    # Choose the worst status mentioned to be conservative
                    if status == "missing":
                        coverage[cap_id] = "missing"
                        break
                    elif status == "partial" and coverage.get(cap_id) != "missing":
                        coverage[cap_id] = "partial"
                    elif status == "covered" and cap_id not in coverage:
                        coverage[cap_id] = "covered"

        return {
            "coverage": coverage,
            "analysis_id": latest.get("id"),
            "policy_id": latest.get("policy_id"),
            "regulation_id": latest.get("regulation_id"),
            "compliance_score": latest.get("compliance_score"),
            "created_at": (
                latest.get("created_at").isoformat()
                if hasattr(latest.get("created_at"), "isoformat")
                else latest.get("created_at")
            ),
        }

    # ---------------- public API ----------------

    async def get_advisor_report(
        self,
        organization: str = "system",
        include_summary: bool = True,
    ) -> Dict[str, Any]:
        """
        Build the full advisor report - relevant circulars, structured
        precautions per control area, RASP capability checklist, and (when
        available) live coverage data from the most recent gap analysis.
        """
        circulars = await self._find_relevant_circulars(limit=20)
        clauses = await self._find_relevant_clauses(limit=60)

        # Summary - try LLM, fall back to a deterministic blurb.
        summary: Optional[str] = None
        if include_summary:
            summary = await self._summarize_with_llm(clauses)
        if not summary:
            summary = (
                "NPCI requires every UPI / mobile banking app to enforce a "
                "verified device + SIM binding before any transaction is "
                "permitted, complemented by a runtime application self-"
                "protection (RASP) layer that detects rooted / jailbroken "
                "devices, tampering, hooking frameworks, screen-recording, "
                "overlay attacks and screen-sharing tools. Detection events "
                "must reach a server-side risk engine in real time so high-"
                "risk transactions can be declined or stepped-up before the "
                "debit instruction is sent to NPCI. The seven control areas "
                "below summarise the controls and the specific RASP "
                "capabilities required to satisfy NPCI's UPI security and "
                "fraud risk management circulars."
            )

        # Build per-area output and aggregate the unique RASP capabilities.
        seen_caps: set = set()
        capability_list: List[Dict[str, Any]] = []
        for area in CONTROL_AREAS:
            for cap_id in area["rasp_capabilities"]:
                if cap_id in seen_caps:
                    continue
                seen_caps.add(cap_id)
                meta = RASP_CAPABILITY_CATALOG.get(cap_id, {})
                capability_list.append({
                    "capability_id": cap_id,
                    "label": meta.get("label", cap_id.replace("_", " ").title()),
                    "description": meta.get("description", ""),
                    "control_area": area["area_id"],
                })

        # Coverage from most recent gap analysis (if any).
        coverage_payload = await self._coverage_from_latest_gap_analysis(organization)
        coverage = coverage_payload.get("coverage", {})

        # Group dynamic clauses under the most likely control area.
        clause_buckets: Dict[str, List[Dict[str, Any]]] = {area["area_id"]: [] for area in CONTROL_AREAS}
        for clause in clauses:
            blob = (
                (clause.get("clause_text") or "")
                + " "
                + " ".join(clause.get("key_requirements", []) or [])
            ).lower()
            best_area = None
            for area in CONTROL_AREAS:
                # crude: if any keyword from the area's title appears, attribute it
                tokens = re.split(r"[^\w]+", area["title"].lower())
                if any(t and t in blob for t in tokens if len(t) > 4):
                    best_area = area["area_id"]
                    break
            if not best_area:
                # Default: device_binding for SIM/binding, tamper_detection for
                # tamper/hook, etc - else first area.
                if "rooted" in blob or "jailbreak" in blob or "root" in blob:
                    best_area = "rooted_jailbroken"
                elif "tamper" in blob or "hook" in blob or "obfusc" in blob:
                    best_area = "tamper_detection"
                elif "emulator" in blob or "screen" in blob or "overlay" in blob:
                    best_area = "emulator_screen_capture"
                elif "tls" in blob or "certificate" in blob or "mitm" in blob:
                    best_area = "secure_communication"
                elif "keystore" in blob or "secure storage" in blob or "enclave" in blob:
                    best_area = "secure_storage"
                elif "fraud" in blob or "risk management" in blob:
                    best_area = "fraud_telemetry"
                else:
                    best_area = "device_binding"
            clause_buckets[best_area].append({
                "clause_id": clause.get("clause_id"),
                "circular_id": clause.get("circular_id"),
                "circular_reference": clause.get("circular_reference"),
                "clause_text": clause.get("clause_text"),
                "category": clause.get("category"),
                "compliance_impact": clause.get("compliance_impact"),
                "key_requirements": clause.get("key_requirements", []),
            })

        control_areas_out = []
        for area in CONTROL_AREAS:
            caps = []
            for cap_id in area["rasp_capabilities"]:
                meta = RASP_CAPABILITY_CATALOG.get(cap_id, {})
                caps.append({
                    "capability_id": cap_id,
                    "label": meta.get("label", cap_id),
                    "description": meta.get("description", ""),
                    "coverage_status": coverage.get(cap_id, "unknown"),
                })
            control_areas_out.append({
                "area_id": area["area_id"],
                "title": area["title"],
                "description": area["description"],
                "npci_basis": area["npci_basis"],
                "requirements": area["requirements"],
                "rasp_capabilities": caps,
                "supporting_clauses": clause_buckets.get(area["area_id"], [])[:6],
            })

        # Capability-level summary card
        capability_summary = []
        for cap in capability_list:
            capability_summary.append({
                **cap,
                "coverage_status": coverage.get(cap["capability_id"], "unknown"),
            })

        # Stats card
        total_caps = len(capability_summary)
        covered = sum(1 for c in capability_summary if c["coverage_status"] == "covered")
        partial = sum(1 for c in capability_summary if c["coverage_status"] == "partial")
        missing = sum(1 for c in capability_summary if c["coverage_status"] == "missing")
        unknown = total_caps - covered - partial - missing
        readiness_pct = round((covered + 0.5 * partial) / total_caps * 100, 1) if total_caps else 0.0

        # Top recommended actions (deterministic ranking)
        recommended_actions: List[Dict[str, Any]] = []
        priority_order = [
            "device_binding",
            "rooted_jailbroken",
            "tamper_detection",
            "emulator_screen_capture",
            "secure_communication",
            "secure_storage",
            "fraud_telemetry",
        ]
        for area_id in priority_order:
            area = next((a for a in CONTROL_AREAS if a["area_id"] == area_id), None)
            if not area:
                continue
            for req in area["requirements"][:2]:
                recommended_actions.append({
                    "control_area": area["title"],
                    "action": req,
                    "rasp_capabilities": area["rasp_capabilities"][:3],
                    "criticality": "High" if area_id in ("device_binding", "rooted_jailbroken", "tamper_detection") else "Medium",
                })

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "organization": organization,
            "summary": summary,
            "stats": {
                "total_capabilities": total_caps,
                "covered": covered,
                "partial": partial,
                "missing": missing,
                "unknown": unknown,
                "readiness_pct": readiness_pct,
                "relevant_circulars": len(circulars),
                "supporting_clauses": len(clauses),
            },
            "circulars": circulars,
            "control_areas": control_areas_out,
            "capability_checklist": capability_summary,
            "recommended_actions": recommended_actions,
            "latest_gap_analysis": {
                "analysis_id": coverage_payload.get("analysis_id"),
                "policy_id": coverage_payload.get("policy_id"),
                "regulation_id": coverage_payload.get("regulation_id"),
                "compliance_score": coverage_payload.get("compliance_score"),
                "created_at": coverage_payload.get("created_at"),
            } if coverage_payload.get("analysis_id") else None,
        }

    async def aggregate_evidences_for_circular(self, circular_id: str) -> Dict[str, Any]:
        """
        Roll up all "what evidence is required" data for a single NPCI
        circular - useful for the demo's Point #2 (evidence rollup).

        Pulls clauses, extracts unique requirements, entities, categories
        and (best-effort) maps each requirement to a likely evidence type.
        """
        from bson import ObjectId

        try:
            object_id = ObjectId(circular_id)
        except Exception:
            return {"error": "invalid circular id"}

        circular = await self.circulars_collection.find_one({"_id": object_id})
        if not circular:
            return {"error": "circular not found"}

        clauses = []
        async for doc in self.clauses_collection.find({"circular_id": circular_id}):
            doc["_id"] = str(doc["_id"])
            clauses.append(doc)

        # Aggregate
        all_requirements: List[str] = []
        all_entities: set = set()
        all_categories: Dict[str, int] = {}
        impact_counts = {"high": 0, "medium": 0, "low": 0}
        for c in clauses:
            for r in (c.get("key_requirements") or []):
                if r and isinstance(r, str):
                    all_requirements.append(r.strip())
            for e in (c.get("entities") or []):
                if e and isinstance(e, str):
                    all_entities.add(e.strip())
            cat = c.get("category") or "General"
            all_categories[cat] = all_categories.get(cat, 0) + 1
            impact = (c.get("compliance_impact") or "medium").lower()
            if impact in impact_counts:
                impact_counts[impact] += 1

        # Map requirements to evidence types deterministically.
        evidence_items: List[Dict[str, Any]] = []
        seen_text: set = set()
        for req in all_requirements:
            key = req.lower().strip()
            if key in seen_text or len(key) < 10:
                continue
            seen_text.add(key)
            ev_type = _infer_evidence_type(req)
            evidence_items.append({
                "requirement": req,
                "evidence_type": ev_type["evidence_type"],
                "verification_method": ev_type["verification_method"],
                "mandatory": True,
                "owner_function": ev_type["owner_function"],
            })

        return {
            "circular_id": circular_id,
            "npci_id": circular.get("npci_id"),
            "title": circular.get("title"),
            "product": circular.get("product"),
            "product_label": circular.get("product_label"),
            "year": circular.get("year"),
            "processing_status": circular.get("processing_status"),
            "stats": {
                "clauses": len(clauses),
                "unique_requirements": len(evidence_items),
                "entities": sorted(list(all_entities)),
                "categories": all_categories,
                "impact": impact_counts,
            },
            "evidence_items": evidence_items,
        }


# ---------------------------------------------------------------------------
# Heuristic mapping requirement → evidence type
# ---------------------------------------------------------------------------
def _infer_evidence_type(requirement_text: str) -> Dict[str, str]:
    """Return a deterministic evidence-type guess for a requirement."""
    t = requirement_text.lower()

    if any(k in t for k in ["report", "submit", "filing", "return"]):
        return {
            "evidence_type": "report",
            "verification_method": "Verify periodic submission to NPCI / RBI in audit logs.",
            "owner_function": "Compliance / Reporting",
        }
    if any(k in t for k in ["log", "audit trail", "monitor", "monitoring"]):
        return {
            "evidence_type": "record",
            "verification_method": "Sample audit logs covering 30/60/90-day windows.",
            "owner_function": "InfoSec / Operations",
        }
    if any(k in t for k in ["train", "awareness", "communicate"]):
        return {
            "evidence_type": "training",
            "verification_method": "Training attendance + acknowledgement records.",
            "owner_function": "HR / Compliance",
        }
    if any(k in t for k in ["control", "block", "detect", "prevent", "rasp", "binding", "encrypt", "tls", "certificate"]):
        return {
            "evidence_type": "control",
            "verification_method": "Technical configuration screenshots + test evidence (penetration test, RASP detection logs).",
            "owner_function": "InfoSec / Engineering",
        }
    if any(k in t for k in ["procedure", "process", "workflow", "sop"]):
        return {
            "evidence_type": "process",
            "verification_method": "Documented SOP + walkthrough interview.",
            "owner_function": "Operations",
        }
    return {
        "evidence_type": "document",
        "verification_method": "Approved policy / circular acknowledgement on file.",
        "owner_function": "Compliance",
    }
