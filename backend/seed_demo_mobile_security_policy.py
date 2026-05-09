"""
Seed a realistic, content-rich Mobile App Security & Device Binding Policy.

Why this exists
---------------
The default `seed_test_policies.py` seeds policies with EMPTY `clauses: []`,
which makes gap analysis trivially return "100% missing" for every NPCI
clause. That kills the demo.

This script seeds ONE comprehensive policy whose clauses deliberately:
- Cover SOME of NPCI's device binding / RASP requirements (so gap analysis
  shows green / partial wins).
- OMIT a few important controls (e.g. Frida hook detection, screen-share
  app blocking) so the demo can show concrete missing gaps + remediation
  tasks.

Run:
    cd backend
    python seed_demo_mobile_security_policy.py            # Dry run
    python seed_demo_mobile_security_policy.py --apply    # Insert into DB

After this, run gap analysis with:
- Policy:   "Mobile App Security & Device Binding Policy v3.0 (Demo)"
- Regulation: any processed NPCI device-binding / UPI security circular

The result will show a realistic mix of compliant + partial + missing.
"""

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(ROOT_DIR / ".env")


POLICY_TITLE = "Mobile App Security & Device Binding Policy v3.0 (Demo)"
POLICY_DEPARTMENT = "Information Technology"

# These two are resolved at runtime by `_resolve_owner` so the seeded policy
# is owned by a REAL user and matches their organization. The gap-analysis
# endpoint requires `policy.user_id == current_user.user_id`, so a hardcoded
# placeholder makes the policy invisible to the actual demo operator.
DEFAULT_POLICY_ORG = os.environ.get("DEMO_ORG", "")  # blank => infer from user
DEFAULT_POLICY_USER_ID = os.environ.get("DEMO_USER_ID", "")  # blank => infer
DEMO_USER_EMAIL = os.environ.get("DEMO_USER_EMAIL", "")  # optional; pick by email


# Each clause has rich semantic metadata so the gap-analysis engine can match
# them against NPCI regulation clauses without an LLM having to re-extract
# anything. Every clause covers a real-world UPI / mobile-banking control.
CLAUSES = [
    # ---------------- COVERED: Device Binding ----------------
    {
        "title": "DEVICE BINDING WITH SIM VERIFICATION",
        "section": "1.1",
        "text": (
            "All UPI and mobile banking app activations shall be bound to the "
            "customer's registered mobile number through outbound SMS-OTP "
            "verification triggered from the device. The SIM serial (ICCID) "
            "and IMSI captured at activation are stored server-side as the "
            "binding fingerprint. Re-binding is mandatory whenever the SIM "
            "is changed, the device is reset, or the app is reinstalled."
        ),
        "requirement_type": "mandatory",
        "subject_category": "technology_security",
        "criticality": "high",
        "tags": ["device-binding", "sim-binding", "upi", "mandatory"],
        "keywords": ["device", "binding", "sim", "icc id", "imsi", "otp", "upi"],
        "key_obligations": [
            "Bind app instance to registered mobile number via outbound SMS-OTP",
            "Capture and store SIM serial / IMSI as the binding fingerprint server-side",
            "Force re-binding on SIM change, device reset or app reinstall",
        ],
        "implementation_evidence": [
            "BindingService.java enforces SMS-OTP at activation for every device",
            "Server-side `device_bindings` table stores ICCID + IMSI + device fingerprint",
            "Re-binding event is automatically triggered by SIM-change webhook from telco",
        ],
        "processes_described": [
            "App activation flow with outbound SMS-OTP",
            "SIM swap detection and forced re-binding workflow",
        ],
        "compliance_indicators": [
            "Production logs of outbound SMS-OTP at every activation",
            "Server-side binding records audited weekly",
        ],
        "regulatory_references": [
            "NPCI OC-193 Standardisation of Device Binding for UPI Applications",
            "NPCI UPI Procedural Guidelines",
        ],
    },
    # ---------------- COVERED: Hardware-backed key storage ----------------
    {
        "title": "HARDWARE-BACKED KEY STORAGE",
        "section": "2.1",
        "text": (
            "Cryptographic keys used for device binding, transaction signing "
            "and PIN protection shall be generated and stored in hardware-"
            "backed secure storage - Android Keystore (StrongBox where "
            "available) on Android and the Secure Enclave on iOS. Keys "
            "shall never be exportable from the secure element. Use of the "
            "private key is gated behind biometric or device-credential "
            "authentication."
        ),
        "requirement_type": "mandatory",
        "subject_category": "technology_security",
        "criticality": "high",
        "tags": ["secure-storage", "keystore", "secure-enclave", "biometric", "mandatory"],
        "keywords": ["keystore", "secure", "enclave", "key", "biometric", "strongbox"],
        "key_obligations": [
            "Generate device-binding keys inside Android Keystore / iOS Secure Enclave",
            "Mark keys as non-exportable",
            "Require biometric / device-credential authentication for key use",
        ],
        "implementation_evidence": [
            "Android: KeyGenParameterSpec configured with setIsStrongBoxBacked(true) and setUserAuthenticationRequired(true)",
            "iOS: SecKeyGeneratePair with kSecAttrTokenIDSecureEnclave and biometric ACL",
        ],
        "processes_described": [
            "Key generation lifecycle for device-binding keys",
            "Biometric-gated transaction signing flow",
        ],
        "compliance_indicators": [
            "Source-code review evidence of Keystore / Secure Enclave usage",
            "Penetration-test report confirming keys cannot be extracted",
        ],
        "regulatory_references": [
            "RBI Master Direction on Digital Payment Security Controls (2021) - Application Security",
            "NPCI UPI Common Library specifications",
        ],
    },
    # ---------------- COVERED: TLS + Cert pinning ----------------
    {
        "title": "TLS AND CERTIFICATE PINNING",
        "section": "3.1",
        "text": (
            "All app-to-server communication for UPI, banking and identity "
            "APIs shall use TLS 1.2 or higher with strict certificate "
            "pinning. The app pins the leaf certificate plus one backup "
            "intermediate certificate. Pin rotation is performed via a "
            "signed configuration push. User-installed root CAs shall not "
            "be trusted for any banking endpoint."
        ),
        "requirement_type": "mandatory",
        "subject_category": "technology_security",
        "criticality": "high",
        "tags": ["tls", "certificate-pinning", "secure-communication", "mandatory"],
        "keywords": ["tls", "certificate", "pinning", "ca", "mitm"],
        "key_obligations": [
            "Enforce TLS 1.2+ for all banking endpoints",
            "Pin leaf + backup intermediate certificate",
            "Reject user-installed CAs for banking traffic",
        ],
        "implementation_evidence": [
            "OkHttp CertificatePinner configured for *.bank.example.com",
            "iOS NSURLSession evaluator rejects untrusted anchors",
            "Network-security-config blocks user CAs (Android 7+)",
        ],
        "processes_described": [
            "Cert pin rotation via signed config push",
            "MITM attempt detection during runtime",
        ],
        "compliance_indicators": [
            "Network penetration-test report (annual) confirming pinning",
            "Cert-pin rotation playbook on file",
        ],
        "regulatory_references": [
            "RBI Master Direction on Digital Payment Security Controls (2021)",
            "NPCI Technical Specifications for UPI",
        ],
    },
    # ---------------- COVERED: Screen capture block ----------------
    {
        "title": "SCREEN CAPTURE BLOCKING",
        "section": "4.1",
        "text": (
            "All sensitive screens - UPI PIN entry, OTP, beneficiary "
            "addition, and transaction confirmation - shall set "
            "FLAG_SECURE on Android and disable screen recording on iOS. "
            "Screenshots and screen recordings are blocked, and the app "
            "switches to a blank placeholder when sent to the background."
        ),
        "requirement_type": "mandatory",
        "subject_category": "technology_security",
        "criticality": "high",
        "tags": ["screen-capture", "flag-secure", "ux-security", "mandatory"],
        "keywords": ["screen", "capture", "recording", "screenshot", "flag_secure"],
        "key_obligations": [
            "Set FLAG_SECURE on PIN, OTP and confirmation screens",
            "Mask app preview when backgrounded",
        ],
        "implementation_evidence": [
            "PinActivity.onCreate sets WindowManager.LayoutParams.FLAG_SECURE",
            "iOS appWillResignActive replaces UIWindow with a blur view",
        ],
        "processes_described": [
            "Sensitive-screen lifecycle hardening",
        ],
        "compliance_indicators": [
            "QA test cases verifying screenshots fail on PIN screen",
            "Penetration-test confirmation",
        ],
        "regulatory_references": [
            "NPCI UPI App Security Standards",
        ],
    },
    # ---------------- PARTIAL: Root detection (only Android, no Magisk-Hide) ----------------
    {
        "title": "ROOT DETECTION (ANDROID)",
        "section": "5.1",
        "text": (
            "The Android app implements basic root detection by checking "
            "for the presence of `su` binary and known root-management "
            "package names (com.topjohnwu.magisk, eu.chainfire.supersu). "
            "If detected, the user is shown a warning but transactions are "
            "still permitted with a soft warning. iOS jailbreak detection "
            "is NOT yet implemented and is tracked as a roadmap item."
        ),
        "requirement_type": "recommended",
        "subject_category": "technology_security",
        "criticality": "high",
        "tags": ["root-detection", "android", "partial", "roadmap"],
        "keywords": ["root", "su", "magisk", "supersu", "android"],
        "key_obligations": [
            "Detect rooted Android using su binary check + package list scan",
            "Show user warning on detection",
        ],
        "implementation_evidence": [
            "RootDetector.kt checks /system/bin/su, /system/xbin/su and Magisk package",
        ],
        "processes_described": [
            "Root detection at app start",
        ],
        "compliance_indicators": [
            "Root-detection log entries from production telemetry",
        ],
        "regulatory_references": [
            "NPCI UPI Risk Management circulars",
        ],
    },
    # ---------------- PARTIAL: Emulator detection (basic only) ----------------
    {
        "title": "EMULATOR DETECTION",
        "section": "5.2",
        "text": (
            "The app performs basic emulator detection using build "
            "fingerprint properties (Build.FINGERPRINT contains 'generic' "
            "or 'sdk') at launch. Detection on production-grade emulators "
            "(Genymotion, BlueStacks) using sensor / GL renderer signals "
            "is not implemented. Detected emulators trigger a warning "
            "banner but do not block transactions."
        ),
        "requirement_type": "recommended",
        "subject_category": "technology_security",
        "criticality": "medium",
        "tags": ["emulator-detection", "android", "partial"],
        "keywords": ["emulator", "qemu", "genymotion", "fingerprint"],
        "key_obligations": [
            "Detect emulator via Build.FINGERPRINT signals",
        ],
        "implementation_evidence": [
            "EmulatorChecker.java checks fingerprint and brand strings",
        ],
        "processes_described": [
            "Emulator detection at launch",
        ],
        "compliance_indicators": [
            "Emulator-detection counters in observability dashboard",
        ],
        "regulatory_references": [
            "NPCI UPI App Security Standards",
        ],
    },
    # ---------------- COVERED: Audit logging ----------------
    {
        "title": "AUDIT LOGGING OF SECURITY EVENTS",
        "section": "6.1",
        "text": (
            "All security-relevant events - device binding, re-binding, "
            "root / emulator detection, certificate pinning failures, "
            "biometric prompts and transaction approvals - are logged "
            "with a tamper-evident hash chain and retained for 8 years "
            "in the central audit store, exceeding the 6-year RBI "
            "retention requirement."
        ),
        "requirement_type": "mandatory",
        "subject_category": "audit_compliance",
        "criticality": "high",
        "tags": ["audit-log", "retention", "tamper-evident", "mandatory"],
        "keywords": ["audit", "log", "retention", "tamper", "hash"],
        "key_obligations": [
            "Log every security-relevant event with hash-chained tamper-evidence",
            "Retain logs for 8 years",
        ],
        "implementation_evidence": [
            "Central audit-log service writes SHA-256 chained records",
            "Cold-storage retention of 8 years configured in S3 lifecycle policy",
        ],
        "processes_described": [
            "Daily audit-log ingestion and integrity verification",
        ],
        "compliance_indicators": [
            "Quarterly internal-audit verification of hash chain integrity",
        ],
        "regulatory_references": [
            "RBI Master Direction on Digital Payment Security Controls (2021)",
            "NPCI UPI Risk Management circulars",
        ],
    },
    # ---------------- WEAK: Server-side risk engine (mentioned but vague) ----------------
    {
        "title": "TRANSACTION RISK SCORING",
        "section": "7.1",
        "text": (
            "Transactions over Rs. 50,000 may be reviewed by the fraud "
            "team based on velocity rules. Real-time scoring of every "
            "transaction using device, location and behavioural signals "
            "is under evaluation but not yet rolled out."
        ),
        "requirement_type": "recommended",
        "subject_category": "fraud_prevention",
        "criticality": "high",
        "tags": ["risk-engine", "fraud", "weak", "roadmap"],
        "keywords": ["risk", "scoring", "fraud", "transaction"],
        "key_obligations": [
            "Review high-value transactions via velocity rules",
        ],
        "implementation_evidence": [
            "Velocity-rule engine exists for transactions over Rs. 50,000",
        ],
        "processes_described": [
            "Manual fraud-team review of high-value transactions",
        ],
        "compliance_indicators": [
            "Daily fraud-review reports",
        ],
        "regulatory_references": [
            "RBI circular on Fraud Risk Management",
        ],
    },
    # ---------------- COVERED: User awareness ----------------
    {
        "title": "CUSTOMER SECURITY AWARENESS",
        "section": "8.1",
        "text": (
            "Customers receive in-app security tips covering screen-share "
            "scams, OTP-sharing fraud, and SIM swap social-engineering on "
            "first launch and quarterly thereafter. SMS and email "
            "advisories are pushed when industry-wide scam patterns are "
            "reported by NPCI."
        ),
        "requirement_type": "mandatory",
        "subject_category": "training_awareness",
        "criticality": "medium",
        "tags": ["awareness", "training", "fraud-prevention"],
        "keywords": ["awareness", "tips", "sms", "scam", "training"],
        "key_obligations": [
            "Show in-app security tips on first launch + quarterly",
            "Push SMS / email advisories on industry alerts",
        ],
        "implementation_evidence": [
            "AwarenessNotificationService schedules quarterly campaigns",
        ],
        "processes_described": [
            "Customer awareness notification rollout cycle",
        ],
        "compliance_indicators": [
            "Campaign delivery reports",
        ],
        "regulatory_references": [
            "NPCI Risk Management Best Practices for UPI",
        ],
    },
    # ---------------- INTENTIONAL GAP MARKERS via OMISSION ----------------
    # These topics are deliberately NOT in the policy so gap analysis
    # surfaces them as MISSING:
    # - Hooking framework detection (Frida / Xposed)
    # - Screen-sharing app blocking (AnyDesk / TeamViewer)
    # - Overlay / accessibility-abuse detection
    # - Magisk-Hide / Zygisk detection
    # - Anti-debug
    # - Code obfuscation (R8 / native)
    # - Proxy / VPN injection detection
]


def _build_clause(clause_data: dict) -> dict:
    """Convert a clause-data dict into the schema we store in MongoDB."""
    return {
        "clause_id": str(uuid.uuid4()),
        "text": clause_data["text"],
        "original_text": clause_data["text"],
        "section": clause_data.get("section"),
        "page_number": None,
        "reference_circulars": clause_data.get("regulatory_references", []),
        "metadata": None,
        "title": clause_data.get("title"),
        "content": clause_data["text"],
        "tags": clause_data.get("tags", []),
        "requirement_type": clause_data.get("requirement_type", "mandatory"),
        "subject_category": clause_data.get("subject_category", "technology_security"),
        "key_obligations": clause_data.get("key_obligations", []),
        "semantic_summary": clause_data.get("text")[:240],
        "entities_involved": ["Bank", "Customer", "InfoSec Team", "Engineering"],
        "keywords": clause_data.get("keywords", []),
        "compliance_indicators": clause_data.get("compliance_indicators", []),
        "criticality": clause_data.get("criticality", "high"),
        "implementation_evidence": clause_data.get("implementation_evidence", []),
        "processes_described": clause_data.get("processes_described", []),
        "regulatory_references": clause_data.get("regulatory_references", []),
        "compliance_checklist": [],
    }


def _build_policy(now: datetime, user_id: str, organization: str) -> dict:
    """Build the full policy document for the given owner."""
    clauses = [_build_clause(c) for c in CLAUSES]
    return {
        "id": str(uuid.uuid4()),
        "title": POLICY_TITLE,
        "policy_type": "InfoSec",  # closest enum match
        "status": "Approved",
        "version": "3.0",
        "file_url": None,
        "file_name": None,
        "clauses": clauses,
        "summary": (
            "Comprehensive policy covering device binding, hardware-backed key "
            "storage, TLS pinning, screen-capture blocking, root / emulator "
            "detection, audit logging, transaction risk and customer "
            "awareness. Some advanced RASP controls (hook detection, "
            "overlay detection, screen-share blocking) are deliberately "
            "scoped out of v3.0 and are roadmap items for v4.0."
        ),
        "impact_organization": (
            "Applies to all engineering, InfoSec, fraud and product teams "
            "owning UPI / mobile banking applications."
        ),
        "impact_technical": (
            "Mandates use of hardware-backed key storage, TLS pinning and "
            "FLAG_SECURE across all sensitive screens."
        ),
        "impact_operational": (
            "Drives the SIM-swap re-binding playbook, the fraud-team "
            "manual review workflow and the customer-awareness campaign "
            "calendar."
        ),
        "key_areas": [
            "Device Binding",
            "Secure Storage",
            "Secure Communication",
            "Screen Capture",
            "Root / Emulator Detection",
            "Audit Logging",
            "Fraud Risk",
            "Customer Awareness",
        ],
        "user_id": user_id,
        "organization": organization,
        "department": POLICY_DEPARTMENT,
        "charter_id": None,
        "linked_regulations": [],
        "versions": [],
        "audit_trail": [],
        "approval_history": [],
        "created_at": (now - timedelta(days=45)).isoformat(),
        "updated_at": (now - timedelta(days=2)).isoformat(),
    }


async def _resolve_owner(db) -> tuple[str, str]:
    """Pick (user_id, organization) for the seeded policy.

    Resolution order:
        1. Explicit env / CLI overrides (DEMO_USER_ID + DEMO_ORG).
        2. DEMO_USER_EMAIL → look up that user.
        3. The single non-system user in the DB (typical local dev case).
        4. Hard error if ambiguous.
    """
    if DEFAULT_POLICY_USER_ID and DEFAULT_POLICY_ORG:
        return DEFAULT_POLICY_USER_ID, DEFAULT_POLICY_ORG

    if DEMO_USER_EMAIL:
        user = await db.users.find_one({"email": DEMO_USER_EMAIL}, {"id": 1, "organization": 1, "_id": 0})
        if not user:
            raise RuntimeError(f"DEMO_USER_EMAIL={DEMO_USER_EMAIL!r} not found in users collection")
        return user["id"], (DEFAULT_POLICY_ORG or user.get("organization") or "Default")

    # Auto-pick the only real user, ignoring synthetic 'system' rows.
    candidates = []
    async for u in db.users.find(
        {"id": {"$nin": [None, "", "system"]}},
        {"id": 1, "email": 1, "organization": 1, "_id": 0},
    ):
        candidates.append(u)
    if not candidates:
        raise RuntimeError("No real users found in the DB; create a user first or pass DEMO_USER_ID + DEMO_ORG.")
    if len(candidates) > 1:
        emails = ", ".join(c.get("email", "?") for c in candidates)
        raise RuntimeError(
            f"Multiple users present ({len(candidates)}): {emails}. "
            "Re-run with DEMO_USER_EMAIL=<email> (or DEMO_USER_ID=<id> + DEMO_ORG=<org>) "
            "to disambiguate which one should own the seeded demo policy."
        )
    chosen = candidates[0]
    return chosen["id"], (DEFAULT_POLICY_ORG or chosen.get("organization") or "Default")


async def _store_clauses_in_qdrant(policy: dict, qdrant_url: str):
    """Best-effort: also push policy clauses into Qdrant policy_clauses collection."""
    try:
        from qdrant_client import QdrantClient
        from services.vector_service import VectorService
        from services.multi_llm_service_new import MultiLLMService

        client = QdrantClient(url=qdrant_url, timeout=10)
        llm_service = MultiLLMService()
        vector = VectorService(qdrant_client=client, llm_service=llm_service)

        clauses_for_vector = []
        for c in policy["clauses"]:
            clauses_for_vector.append({
                "clause_id": c["clause_id"],
                "text": c["text"],
                "original_text": c["original_text"],
                "section": c["section"],
                "title": c["title"],
                "requirement_type": c["requirement_type"],
                "subject_category": c["subject_category"],
                "criticality": c["criticality"],
                "tags": c["tags"],
                "keywords": c["keywords"],
            })

        stored = await vector.store_policy_clauses(
            policy_id=policy["id"],
            clauses=clauses_for_vector,
            organization=policy.get("organization", "Default"),
            user_id=policy.get("user_id", "system"),
        )
        print(f"  Stored {stored} policy clause embeddings in Qdrant policy_clauses collection")
    except Exception as e:
        print(f"  WARNING: Could not push embeddings to Qdrant ({e}); gap analysis will fall back to MongoDB-only matching.")


async def main(apply: bool):
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "compli-ai")
    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"=== Demo Mobile Security Policy Seed (db={db_name}) ===")
    user_id, org = await _resolve_owner(db)
    print(f"Resolved owner: user_id={user_id}  organization={org}\n")

    existing = await db.policies.find_one({"title": POLICY_TITLE})
    if existing:
        print(f"Policy '{POLICY_TITLE}' already exists.")
        print(f"  id={existing.get('id')}  user_id={existing.get('user_id')}  org={existing.get('organization')}")
        if existing.get("user_id") != user_id or existing.get("organization") != org:
            print(
                "  -> NOTE: existing policy is owned by a DIFFERENT user/org than the resolved demo owner. "
                "Re-running with --apply will delete it and re-seed under the correct owner."
            )
        if not apply:
            print("DRY RUN - re-run with --apply to delete and re-seed.")
            client.close()
            return
        await db.policies.delete_one({"id": existing["id"]})
        print("  Deleted existing policy. Will re-insert.")

    policy = _build_policy(datetime.now(timezone.utc), user_id=user_id, organization=org)
    print(f"Built policy with {len(policy['clauses'])} clauses, total text length: "
          f"{sum(len(c['text']) for c in policy['clauses'])} chars.")
    print()
    print("Clause titles:")
    for c in policy["clauses"]:
        print(f"  - [{c['section']}] {c['title']} ({c['criticality']} / {c['requirement_type']})")
    print()

    if not apply:
        print("DRY RUN - re-run with --apply to actually insert.")
        client.close()
        return

    await db.policies.insert_one(policy)
    print(f"Inserted policy with id={policy['id']}.")
    print()
    print("Pushing clause embeddings to Qdrant (best-effort)...")
    await _store_clauses_in_qdrant(policy, qdrant_url)
    print()
    print("DONE.")
    print(f"  Policy title:  {POLICY_TITLE}")
    print(f"  Policy id:     {policy['id']}")
    print(f"  Owner:         user_id={user_id}  org={org}")
    print(f"  Clauses:       {len(policy['clauses'])}")
    print()
    print("Use this policy in Gap Analysis against any processed NPCI device-")
    print("binding / UPI security circular for the demo.")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually insert into MongoDB (default is dry run)")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
