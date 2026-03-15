from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
import os
from typing import List, Dict, Any, Optional
import logging
import json
import asyncio

logger = logging.getLogger(__name__)

class MultiLLMService:
    """Strategic LLM usage:
    - Claude Sonnet 4: ALL text-based AI operations (regulatory analysis, task generation, chat, gap analysis)
    - Gemini 2.5 Flash: Evidence evaluation, document comparison, PDF analysis (multimodal)
    """
    
    def __init__(self):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not self.api_key:
            logger.error("EMERGENT_LLM_KEY not found")
    
    async def analyze_regulatory_circular_claude(self, text: str, circular_title: str) -> Dict[str, Any]:
        """Use Claude for deep regulatory analysis"""
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"regulatory_analysis_{circular_title[:20]}",
                system_message="You are an expert regulatory compliance analyst specializing in Indian financial regulations (RBI, SEBI, FIU-IND, NPCI)."
            ).with_model("anthropic", "claude-sonnet-4-20250514")
            
            prompt = f"""Analyze this regulatory circular comprehensively:

Title: {circular_title}

Circular Text:
{text[:8000]}

Provide:
1. Executive Summary (3-4 sentences)
2. Key Changes (bullet points)
3. Organization Impact (how it affects the entity)
4. Technical Impact (IT/system changes needed)
5. Operational Impact (process changes needed)
6. Departments Affected (list)
7. Compliance Timeline (deadlines)
8. References to Previous Circulars (if any)

Return as JSON with keys: summary, key_changes, org_impact, technical_impact, operational_impact, departments_affected, timeline, references"""
            
            message = UserMessage(text=prompt)
            response = await chat.send_message(message)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.warning("Claude response not JSON, parsing manually")
                return {
                    "summary": response[:500],
                    "key_changes": [],
                    "org_impact": "Requires manual review",
                    "technical_impact": "Requires manual review",
                    "operational_impact": "Requires manual review",
                    "departments_affected": ["Legal", "Compliance"],
                    "timeline": "Review circular for deadlines",
                    "references": []
                }
        except Exception as e:
            logger.error(f"Claude analysis error: {str(e)}")
            return self._fallback_analysis(text)
    
    async def generate_tasks_gpt(self, gaps: List[Dict[str, Any]], circular_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use Claude for task generation from compliance gaps"""
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id="task_generation",
                system_message="You are an AI project manager creating actionable compliance tasks for Indian financial institutions (NBFCs, banks). Generate specific, actionable tasks with clear ownership."
            ).with_model("anthropic", "claude-sonnet-4-20250514")
            
            prompt = f"""Generate actionable tasks for these compliance gaps:

Gaps:
{json.dumps(gaps[:10], indent=2)}

Circular Context:
{json.dumps(circular_info, indent=2)}

For each gap, create a task with:
- title: Clear, actionable title
- description: Specific steps to address the gap
- department: Which department should handle it
- priority: Critical/High/Medium/Low
- estimated_days: How long it will take

Return JSON array of tasks."""
            
            message = UserMessage(text=prompt)
            response = await chat.send_message(message)
            
            try:
                tasks = json.loads(response)
                return tasks if isinstance(tasks, list) else []
            except json.JSONDecodeError:
                return self._fallback_tasks(gaps)
        except Exception as e:
            logger.error(f"GPT task generation error: {str(e)}")
            return self._fallback_tasks(gaps)
    
    async def evaluate_evidence_gemini(self, evidence_file_path: str, control_requirement: str) -> Dict[str, Any]:
        """Use Gemini for multimodal evidence evaluation"""
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id="evidence_evaluation",
                system_message="You are an audit AI evaluating compliance evidence against regulatory requirements."
            ).with_model("gemini", "gemini-2.5-flash")
            
            # For PDF evidence
            file_content = FileContentWithMimeType(
                file_path=evidence_file_path,
                mime_type="application/pdf"
            )
            
            prompt = f"""Evaluate this evidence file against the control requirement:

Control Requirement:
{control_requirement}

Analyze and provide:
1. Compliance Score (0-100)
2. What's Good (strengths of the evidence)
3. What's Missing (gaps in the evidence)
4. Suggestions for Improvement
5. Overall Assessment

Return as JSON with keys: score, strengths, gaps, suggestions, assessment"""
            
            message = UserMessage(text=prompt, file_contents=[file_content])
            response = await chat.send_message(message)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return self._fallback_evidence_score()
        except Exception as e:
            logger.error(f"Gemini evidence evaluation error: {str(e)}")
            return self._fallback_evidence_score()
    
    async def analyze_gap_detailed(self, policy_clause: str, regulation_clause: str) -> Dict[str, Any]:
        """Enhanced gap analysis using Claude for better reasoning"""
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id="gap_analysis_detailed",
                system_message="You are a compliance auditor performing clause-level gap analysis."
            ).with_model("anthropic", "claude-sonnet-4-20250514")
            
            prompt = f"""Perform detailed gap analysis:

POLICY CLAUSE:
{policy_clause}

REGULATION REQUIREMENT:
{regulation_clause}

Analyze:
1. Gap Type: missing | weak | conflicting | compliant | partial
2. Severity: Critical | High | Medium | Low
3. Confidence Score: 0.0 to 1.0 (how confident you are)
4. Detailed Explanation: What's the gap?
5. Suggested Fix: Specific remediation steps
6. Legal Citations: Any relevant legal references
7. Risk Level: What's the risk if not addressed?

Return JSON with keys: gap_type, severity, confidence_score, explanation, suggested_fix, legal_citations, risk_level"""
            
            message = UserMessage(text=prompt)
            response = await chat.send_message(message)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return self._fallback_gap_analysis()
        except Exception as e:
            logger.error(f"Gap analysis error: {str(e)}")
            return self._fallback_gap_analysis()
    
    async def smart_task_assignment(self, task: Dict[str, Any], team_workload: Dict[str, int]) -> Dict[str, Any]:
        """Use Claude to intelligently assign tasks based on workload"""
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id="smart_assignment",
                system_message="You are an AI workload balancer optimizing task assignments for compliance teams."
            ).with_model("anthropic", "claude-sonnet-4-20250514")
            
            prompt = f"""Assign this task to the most suitable person:

Task:
{json.dumps(task, indent=2)}

Current Team Workload:
{json.dumps(team_workload, indent=2)}

Consider:
- Current workload balance
- Task priority and complexity
- Department expertise
- Deadline proximity

Return JSON with: recommended_assignee, reason, workload_after_assignment"""
            
            message = UserMessage(text=prompt)
            response = await chat.send_message(message)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"recommended_assignee": "unassigned", "reason": "Manual assignment needed"}
        except Exception as e:
            logger.error(f"Smart assignment error: {str(e)}")
            return {"recommended_assignee": "unassigned", "reason": "Error in assignment"}
    
    async def analyze_los_lms_data(self, record_data: Dict[str, Any], regulations: List[str]) -> Dict[str, Any]:
        """Analyze LOS/LMS data for compliance issues using Claude"""
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id="los_lms_analysis",
                system_message="You are a compliance AI analyzing loan/lending data for regulatory violations in the Indian financial sector."
            ).with_model("anthropic", "claude-sonnet-4-20250514")
            
            prompt = f"""Analyze this LOS/LMS record for compliance issues:

Record Data:
{json.dumps(record_data, indent=2)}

Applicable Regulations:
{json.dumps(regulations, indent=2)}

Identify:
1. Compliance Issues (list)
2. Risk Level: Critical | High | Medium | Low
3. Specific Violations
4. Recommended Actions

Return JSON with keys: issues, risk_level, violations, recommended_actions"""
            
            message = UserMessage(text=prompt)
            response = await chat.send_message(message)
            
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"issues": [], "risk_level": "Low", "violations": [], "recommended_actions": []}
        except Exception as e:
            logger.error(f"LOS/LMS analysis error: {str(e)}")
            return {"issues": [], "risk_level": "Low", "violations": [], "recommended_actions": []}
    
    async def chat_response(self, user_message: str, context: List[Dict[str, str]]) -> str:
        """NeoGPT-style contextual chat using Claude"""
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id="neogpt_chat",
                system_message="You are CompliAI, a BFSI-focused compliance AI assistant specializing in Indian financial regulations (RBI, SEBI, NPCI, FIU-IND). You help with regulatory queries, compliance questions, and policy guidance."
            ).with_model("anthropic", "claude-sonnet-4-20250514")
            
            # Build context
            context_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in context[-5:]])
            
            prompt = f"""Previous conversation:
{context_text}

User: {user_message}

Provide helpful, accurate compliance guidance. If you're not sure, say so and recommend consulting a compliance expert."""
            
            message = UserMessage(text=prompt)
            response = await chat.send_message(message)
            return response
        except Exception as e:
            logger.error(f"Chat error: {str(e)}")
            return "I apologize, but I'm having trouble processing your request. Please try again."
    
    def _fallback_analysis(self, text: str) -> Dict[str, Any]:
        return {
            "summary": text[:300],
            "key_changes": ["Manual review required"],
            "org_impact": "Review required",
            "technical_impact": "Review required",
            "operational_impact": "Review required",
            "departments_affected": ["Compliance"],
            "timeline": "Check circular for deadlines",
            "references": []
        }
    
    def _fallback_tasks(self, gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{
            "title": f"Address {gap.get('gap_type', 'compliance')} gap",
            "description": gap.get('description', 'Review and address this gap'),
            "department": "Compliance",
            "priority": gap.get('severity', 'Medium'),
            "estimated_days": 7
        } for gap in gaps[:5]]
    
    def _fallback_evidence_score(self) -> Dict[str, Any]:
        return {
            "score": 50,
            "strengths": ["Evidence uploaded"],
            "gaps": ["Requires manual review"],
            "suggestions": ["Have compliance team review the evidence"],
            "assessment": "Manual evaluation needed"
        }
    
    def _fallback_gap_analysis(self) -> Dict[str, Any]:
        return {
            "gap_type": "unknown",
            "severity": "Medium",
            "confidence_score": 0.5,
            "explanation": "Unable to perform automated analysis",
            "suggested_fix": "Manual review required",
            "legal_citations": [],
            "risk_level": "Moderate"
        }
