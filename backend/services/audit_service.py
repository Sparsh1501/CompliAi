import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import AuditControl, AuditSession, Evidence
from services.multi_llm_service_new import MultiLLMService
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class AuditService:
    def __init__(self):
        self.llm_service = MultiLLMService()
    
    async def create_external_audit_controls(self, regulator: str, audit_scope: str) -> List[AuditControl]:
        """Pre-populate controls based on regulatory guidelines"""
        # RBI audit controls template
        rbi_controls = [
            AuditControl(
                control_name="KYC Compliance",
                control_description="Verify KYC process adherence as per RBI KYC Master Directions",
                category="Customer Due Diligence",
                weightage=10.0,
                evidence_required=["KYC policy document", "Sample KYC records", "Audit trail logs"]
            ),
            AuditControl(
                control_name="AML Program",
                control_description="Assess AML/CFT framework effectiveness",
                category="Anti-Money Laundering",
                weightage=10.0,
                evidence_required=["AML policy", "Transaction monitoring reports", "STR/CTR records"]
            ),
            AuditControl(
                control_name="Information Security",
                control_description="Evaluate IT security controls and cyber resilience",
                category="Technology Risk",
                weightage=8.0,
                evidence_required=["InfoSec policy", "Vulnerability assessment reports", "Incident logs"]
            ),
            AuditControl(
                control_name="Outsourcing Management",
                control_description="Review outsourcing arrangements and risk management",
                category="Operational Risk",
                weightage=7.0,
                evidence_required=["Outsourcing policy", "Vendor contracts", "Risk assessments"]
            ),
            AuditControl(
                control_name="Fair Practices Code",
                control_description="Check adherence to fair practices in lending",
                category="Consumer Protection",
                weightage=8.0,
                evidence_required=["Fair practices policy", "Customer complaints register", "KFS disclosures"]
            ),
            AuditControl(
                control_name="Board Oversight",
                control_description="Evaluate board-level governance and oversight",
                category="Governance",
                weightage=7.0,
                evidence_required=["Board meeting minutes", "Risk committee reports", "Audit committee notes"]
            )
        ]
        
        # SEBI audit controls template
        sebi_controls = [
            AuditControl(
                control_name="Client Asset Protection",
                control_description="Verify segregation and protection of client assets",
                category="Asset Management",
                weightage=10.0,
                evidence_required=["Custodian reports", "Reconciliation statements", "Asset register"]
            ),
            AuditControl(
                control_name="Trade Execution",
                control_description="Review trade execution quality and best execution policy",
                category="Trading Operations",
                weightage=8.0,
                evidence_required=["Best execution policy", "Trade logs", "Price comparison reports"]
            ),
            AuditControl(
                control_name="Disclosure Compliance",
                control_description="Check timely and accurate regulatory disclosures",
                category="Regulatory Reporting",
                weightage=9.0,
                evidence_required=["Disclosure schedule", "Filed reports", "Acknowledgments"]
            )
        ]
        
        if "RBI" in regulator.upper():
            return rbi_controls
        elif "SEBI" in regulator.upper():
            return sebi_controls
        else:
            # Default controls
            return rbi_controls[:3]
    
    async def evaluate_control(self, control: AuditControl, evidence_list: List[Evidence]) -> Dict[str, Any]:
        """Evaluate a control against submitted evidence using AI"""
        if not evidence_list:
            return {
                "compliance_score": 0.0,
                "status": "No Evidence",
                "findings": "No evidence submitted for this control",
                "recommendations": "Upload required evidence documents"
            }
        
        # Use Gemini to evaluate evidence
        evaluation_results = []
        for evidence in evidence_list:
            if evidence.file_url:
                result = await self.llm_service.evaluate_evidence_gemini(
                    evidence.file_url,
                    control.control_description
                )
                evaluation_results.append(result)
        
        # Aggregate scores
        if evaluation_results:
            avg_score = sum(r.get('score', 0) for r in evaluation_results) / len(evaluation_results)
            all_strengths = []
            all_gaps = []
            all_suggestions = []
            
            for result in evaluation_results:
                all_strengths.extend(result.get('strengths', []))
                all_gaps.extend(result.get('gaps', []))
                all_suggestions.extend(result.get('suggestions', []))
            
            status = "Compliant" if avg_score >= 80 else "Partially Compliant" if avg_score >= 60 else "Non-Compliant"
            
            return {
                "compliance_score": avg_score,
                "status": status,
                "findings": f"Evidence shows {status.lower()} status. Strengths: {', '.join(all_strengths[:3])}. Gaps: {', '.join(all_gaps[:3])}",
                "recommendations": '; '.join(all_suggestions[:3]) if all_suggestions else "Continue monitoring"
            }
        else:
            return {
                "compliance_score": 50.0,
                "status": "Requires Review",
                "findings": "Evidence requires manual evaluation",
                "recommendations": "Have compliance team review the submitted evidence"
            }
    
    async def generate_audit_report(self, audit_session: AuditSession, controls_evaluation: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive audit report"""
        total_score = 0
        total_weightage = 0
        
        for i, control in enumerate(audit_session.controls):
            if i < len(controls_evaluation):
                eval_result = controls_evaluation[i]
                score = eval_result.get('compliance_score', 0)
                total_score += score * control.weightage
                total_weightage += control.weightage
        
        overall_score = (total_score / total_weightage) if total_weightage > 0 else 0
        
        # Count by status
        compliant_count = sum(1 for e in controls_evaluation if e.get('status') == 'Compliant')
        partially_compliant = sum(1 for e in controls_evaluation if e.get('status') == 'Partially Compliant')
        non_compliant = sum(1 for e in controls_evaluation if e.get('status') == 'Non-Compliant')
        
        return {
            "overall_score": round(overall_score, 2),
            "total_controls": len(audit_session.controls),
            "compliant_controls": compliant_count,
            "partially_compliant_controls": partially_compliant,
            "non_compliant_controls": non_compliant,
            "summary": f"Audit completed with overall score of {overall_score:.1f}%. {compliant_count} controls fully compliant, {non_compliant} require immediate attention.",
            "recommendations": self._generate_recommendations(controls_evaluation),
            "control_details": controls_evaluation
        }
    
    def _generate_recommendations(self, controls_evaluation: List[Dict[str, Any]]) -> List[str]:
        recommendations = []
        
        for eval in controls_evaluation:
            if eval.get('status') == 'Non-Compliant':
                recommendations.append(f"Priority: {eval.get('recommendations', 'Address compliance gap')}")
        
        if not recommendations:
            recommendations.append("Maintain current compliance standards")
            recommendations.append("Continue regular monitoring and assessments")
        
        return recommendations[:5]
