"""
Multi-LLM Service - Direct SDK Integration
Replaces emergentintegrations with direct OpenAI, Anthropic, and Google AI SDKs
"""
import os
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import warnings
warnings.filterwarnings("ignore", message=".*huggingface_hub.*")
warnings.filterwarnings("ignore", message=".*token.*")
import logging as _hf_logging
_hf_logging.getLogger("huggingface_hub").setLevel(_hf_logging.ERROR)
from typing import List, Dict, Any, Optional
import logging
import json
import asyncio
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import google.generativeai as genai
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class MultiLLMService:
    """Strategic LLM usage - CLAUDE SONNET 4 FOR EVERYTHING:
    - Claude Sonnet 4: ALL text-based AI operations (regulatory analysis, task generation, gap analysis, chat)
    - Gemini 2.0 Flash: Evidence evaluation, document comparison, PDF analysis (multimodal only)
    """
    
    # Model selection
    OPUS_MODEL = "claude-sonnet-4-20250514"  # Using Sonnet for cost efficiency
    SONNET_MODEL = "claude-sonnet-4-20250514"  # Fast + cost-effective - for extraction, tasks, chat
    
    def __init__(self):
        # Initialize API keys
        self.openai_key = os.environ.get('OPENAI_API_KEY')
        self.anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
        self.google_key = os.environ.get('GOOGLE_API_KEY')
        
        # Initialize clients
        self.openai_client = AsyncOpenAI(api_key=self.openai_key) if self.openai_key else None
        self.anthropic_client = AsyncAnthropic(api_key=self.anthropic_key) if self.anthropic_key else None
        
        if self.google_key:
            genai.configure(api_key=self.google_key)
        
        # Check if at least one provider is configured
        if not any([self.openai_key, self.anthropic_key, self.google_key]):
            logger.error("No LLM API keys found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY")
        
        # Default provider
        self.default_provider = os.environ.get('DEFAULT_LLM_PROVIDER', 'openai')

    def _get_db(self):
        """Get the MongoDB database instance from the server module."""
        try:
            import sys
            srv = sys.modules.get('__main__') or sys.modules.get('server')
            return getattr(srv, 'db', None) if srv else None
        except Exception:
            return None
    
    async def _stream_anthropic(self, model: str, max_tokens: int, system: str, messages: list) -> tuple:
        """
        Helper to call Anthropic with streaming (required for requests > 10 min).
        Returns (response_text, input_tokens, output_tokens).
        """
        response_text = ""
        input_tokens = 0
        output_tokens = 0
        async with self.anthropic_client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages
        ) as stream:
            async for text in stream.text_stream:
                response_text += text
            final_message = await stream.get_final_message()
            input_tokens = final_message.usage.input_tokens
            output_tokens = final_message.usage.output_tokens
        return response_text, input_tokens, output_tokens

    async def analyze_regulatory_circular_claude(self, text: str, circular_title: str) -> Dict[str, Any]:
        """Analyze regulatory circular using selected LLM provider (respects USE_LOCAL_LLM toggle)"""
        import time
        start_time = time.time()

        # Check if we should use local LLM (Ollama) instead of Claude
        use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"

        if use_local:
            return await self._analyze_regulatory_circular_local(text, circular_title)
        
        if not self.anthropic_client:
            logger.error("Anthropic not configured - ANTHROPIC_API_KEY required")
            return self._fallback_analysis(text)
        
        try:
            # Comprehensive prompt for quality analysis with Sonnet 4.5
            prompt = f"""Analyze this regulatory circular comprehensively:

Title: {circular_title}

Circular Text:
{text[:15000]}

Provide a thorough analysis and return as JSON with these keys:
- summary: Executive summary (3-4 sentences covering scope, key requirements, and compliance timeline)
- key_changes: List of key regulatory changes (specific bullet points)
- org_impact: Detailed organizational impact (governance, policies, reporting)
- technical_impact: IT/system changes needed (specific systems, integrations)
- operational_impact: Process changes needed (workflows, procedures, controls)
- departments_affected: List of affected departments
- timeline: Key compliance deadlines with dates if available
- references: References to previous circulars, acts, or regulations"""
            
            logger.info("="*60)
            logger.info("[REGULATORY ANALYSIS - SONNET 4.5 (quality)]")
            logger.info(f"  Title: {circular_title}")
            logger.info(f"  Text length: {len(text)} chars (using first 15000)")
            
            response_text, input_tokens, output_tokens = await self._stream_anthropic(
                model=self.OPUS_MODEL,
                max_tokens=4096,
                system="You are an expert regulatory compliance analyst specializing in Indian financial regulations (RBI, SEBI, FIU-IND, NPCI). Provide thorough, accurate analysis with specific actionable insights. Return only valid JSON.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            elapsed = time.time() - start_time
            
            # Calculate cost estimate for Opus
            input_cost = input_tokens * 0.015 / 1000
            output_cost = output_tokens * 0.075 / 1000
            total_cost = input_cost + output_cost
            
            logger.info(f"  Time: {elapsed:.2f}s")
            logger.info(f"  Input tokens: {input_tokens}")
            logger.info(f"  Output tokens: {output_tokens}")
            logger.info(f"  Est. cost: ${total_cost:.4f}")
            logger.info("="*60)
            
            try:
                # Clean response
                clean = response_text.strip()
                if clean.startswith("```"):
                    clean = clean.split("```")[1]
                    if clean.startswith("json"):
                        clean = clean[4:]
                return json.loads(clean)
            except json.JSONDecodeError:
                logger.warning("Claude response not JSON, parsing manually")
                return {
                    "summary": response_text[:500],
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
    
    async def analyze_policy_document(self, text: str, policy_title: str) -> Dict[str, Any]:
        """Analyze a policy document using selected LLM provider (respects USE_LOCAL_LLM toggle)."""
        import time
        start_time = time.time()

        # Check if we should use local LLM
        use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"

        if use_local:
            return await self._analyze_policy_document_local(text, policy_title)
        
        if not self.anthropic_client:
            logger.error("Anthropic not configured - ANTHROPIC_API_KEY required")
            return {}
        
        try:
            prompt = f"""Analyze this internal policy document comprehensively:

Title: {policy_title}

Policy Text:
{text[:15000]}

Provide a thorough analysis and return as JSON with these keys:
- summary: Executive summary of the policy (3-4 sentences covering purpose, scope, key requirements, and applicability)
- key_areas: List of key compliance/policy areas covered (e.g., ["Customer Due Diligence", "Transaction Monitoring", "Record Keeping"])
- org_impact: How this policy affects the organization's governance, structure, and reporting obligations
- technical_impact: IT/system changes or requirements implied by this policy (systems, tools, integrations)
- operational_impact: Process and workflow changes required to comply with this policy (procedures, controls, training)
- department: Primary department responsible (Compliance, Legal, IT, Operations, Risk Management, Finance, Internal Audit, HR)
- risk_level: Overall compliance risk level if this policy is not followed (Critical/High/Medium/Low)
- related_regulations: List of external regulations this policy likely maps to (e.g., RBI KYC Master Direction, PMLA 2002)"""

            logger.info("="*60)
            logger.info("[POLICY ANALYSIS - SONNET 4]")
            logger.info(f"  Title: {policy_title}")
            logger.info(f"  Text length: {len(text)} chars (using first 15000)")
            
            response_text, input_tokens, output_tokens = await self._stream_anthropic(
                model=self.SONNET_MODEL,
                max_tokens=4096,
                system="You are an expert compliance and policy analyst specialising in Indian financial regulations (RBI, SEBI, NBFC). Analyze this internal policy document and provide a thorough impact assessment. Return only valid JSON.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            elapsed = time.time() - start_time
            
            logger.info(f"  Time: {elapsed:.2f}s")
            logger.info(f"  Input tokens: {input_tokens}")
            logger.info(f"  Output tokens: {output_tokens}")
            logger.info("="*60)
            
            try:
                clean = response_text.strip()
                if clean.startswith("```"):
                    clean = clean.split("```")[1]
                    if clean.startswith("json"):
                        clean = clean[4:]
                return json.loads(clean)
            except json.JSONDecodeError:
                logger.warning("Claude policy analysis response not JSON, returning raw text")
                return {
                    "summary": response_text[:500],
                    "key_areas": [],
                    "org_impact": "Requires manual review",
                    "technical_impact": "Requires manual review",
                    "operational_impact": "Requires manual review",
                    "department": "Compliance",
                    "risk_level": "Medium",
                    "related_regulations": []
                }
        except Exception as e:
            logger.error(f"Claude policy analysis error: {str(e)}")
            return {}
    
    # GPT fallback removed - Claude Sonnet 4 is primary for all text operations
    
    async def generate_tasks_gpt(self, gaps: List[Dict[str, Any]], circular_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use Claude Sonnet 4 for task generation from compliance gaps"""
        if not self.anthropic_client:
            logger.warning("Anthropic not configured, using fallback")
            return self._fallback_tasks(gaps)
        
        try:
            prompt = f"""Generate actionable tasks for these compliance gaps:

Gaps:
{json.dumps(gaps[:10], indent=2)}

Circular Context:
{json.dumps(circular_info, indent=2)}

For each gap, create a task with:
- title: Clear, actionable title
- description: Specific steps to address the gap
- department: Which department should handle it (Compliance, Legal, IT, Operations, Risk Management, Finance, Internal Audit, HR)
- priority: Critical/High/Medium/Low
- estimated_days: How long it will take

Return JSON object with key 'tasks' containing array of tasks."""
            
            response_text, _, _ = await self._stream_anthropic(
                model=self.OPUS_MODEL,
                max_tokens=4096,
                system="You are an AI project manager creating actionable compliance tasks for Indian financial institutions (NBFCs, banks). Create specific, actionable tasks with clear ownership and realistic timelines. Return only valid JSON.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            try:
                # Clean response
                clean = response_text.strip()
                if clean.startswith("```"):
                    clean = clean.split("```")[1]
                    if clean.startswith("json"):
                        clean = clean[4:]
                result = json.loads(clean)
                tasks = result.get('tasks', []) if isinstance(result, dict) else result
                return tasks if isinstance(tasks, list) else []
            except json.JSONDecodeError:
                logger.warning("Claude task generation response not valid JSON")
                return self._fallback_tasks(gaps)
        except Exception as e:
            logger.error(f"Claude task generation error: {str(e)}")
            return self._fallback_tasks(gaps)
    
    async def evaluate_evidence_gemini(self, evidence_file_path: str, control_requirement: str) -> Dict[str, Any]:
        """Use Gemini for multimodal evidence evaluation"""
        if not self.google_key:
            logger.warning("Google AI not configured, using fallback")
            return self._fallback_evidence_score()
        
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
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
            
            # For PDF evidence, upload the file
            if os.path.exists(evidence_file_path):
                sample_file = genai.upload_file(path=evidence_file_path)
                response = model.generate_content([prompt, sample_file])
                genai.delete_file(sample_file.name)
            else:
                response = model.generate_content(prompt)
            
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                return self._fallback_evidence_score()
        except Exception as e:
            logger.error(f"Gemini evidence evaluation error: {str(e)}")
            return self._fallback_evidence_score()
    
    async def analyze_gap_detailed(self, policy_clause: str, regulation_clause: str) -> Dict[str, Any]:
        """Enhanced gap analysis using Claude Sonnet 4 for better reasoning"""
        if not self.anthropic_client:
            logger.error("Anthropic not configured - ANTHROPIC_API_KEY required")
            return self._fallback_gap_analysis()
        
        try:
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
            
            response_text, _, _ = await self._stream_anthropic(
                model=self.OPUS_MODEL,
                max_tokens=2048,
                system="You are a compliance auditor performing clause-level gap analysis.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                return self._fallback_gap_analysis()
        except Exception as e:
            logger.error(f"Gap analysis error: {str(e)}")
            return self._fallback_gap_analysis()
    
    # GPT fallback for gap analysis removed - Claude is primary
    
    async def smart_task_assignment(self, task: Dict[str, Any], team_workload: Dict[str, int]) -> Dict[str, Any]:
        """Use Claude Sonnet 4 to intelligently assign tasks based on workload"""
        if not self.anthropic_client:
            return {"recommended_assignee": "unassigned", "reason": "Anthropic not configured"}
        
        try:
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
            
            response_text, _, _ = await self._stream_anthropic(
                model=self.OPUS_MODEL,
                max_tokens=1024,
                system="You are an AI workload balancer optimizing task assignments for compliance teams. Return only valid JSON.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            try:
                clean = response_text.strip()
                if clean.startswith("```"):
                    clean = clean.split("```")[1]
                    if clean.startswith("json"):
                        clean = clean[4:]
                return json.loads(clean)
            except json.JSONDecodeError:
                return {"recommended_assignee": "unassigned", "reason": "Could not parse response"}
        except Exception as e:
            logger.error(f"Smart assignment error: {str(e)}")
            return {"recommended_assignee": "unassigned", "reason": "Error in assignment"}
    
    async def analyze_los_lms_data(self, record_data: Dict[str, Any], regulations: List[str]) -> Dict[str, Any]:
        """Analyze LOS/LMS data for compliance issues using Claude Sonnet 4"""
        if not self.anthropic_client:
            return {"issues": [], "risk_level": "Low", "violations": [], "recommended_actions": []}
        
        try:
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
            
            response_text, _, _ = await self._stream_anthropic(
                model=self.OPUS_MODEL,
                max_tokens=2048,
                system="You are a compliance AI analyzing loan/lending data for regulatory violations in the Indian financial sector. Return only valid JSON.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            try:
                clean = response_text.strip()
                if clean.startswith("```"):
                    clean = clean.split("```")[1]
                    if clean.startswith("json"):
                        clean = clean[4:]
                return json.loads(clean)
            except json.JSONDecodeError:
                return {"issues": [], "risk_level": "Low", "violations": [], "recommended_actions": []}
        except Exception as e:
            logger.error(f"LOS/LMS analysis error: {str(e)}")
            return {"issues": [], "risk_level": "Low", "violations": [], "recommended_actions": []}
    
    async def chat_response(self, user_message: str, context: List[Dict[str, str]]) -> str:
        """CompliAI contextual chat using Claude Sonnet 4"""
        if not self.anthropic_client:
            return "Chat service is not available. Please configure ANTHROPIC_API_KEY."
        
        try:
            # Build conversation history for Claude
            messages = []
            
            # Add context (last 5 messages)
            for msg in context[-5:]:
                role = "user" if msg['role'] == 'user' else "assistant"
                messages.append({"role": role, "content": msg['content']})
            
            messages.append({"role": "user", "content": user_message})
            
            response_text, _, _ = await self._stream_anthropic(
                model=self.OPUS_MODEL,
                max_tokens=2048,
                system="You are CompliAI, a BFSI-focused compliance AI assistant specializing in Indian financial regulations (RBI, SEBI, NPCI, FIU-IND, IRDAI). You help with regulatory queries, compliance questions, policy guidance, KYC/AML requirements, and audit preparation. Be accurate, cite regulations when possible, and recommend consulting compliance experts for critical decisions.",
                messages=messages
            )
            
            return response_text
        except Exception as e:
            logger.error(f"Chat error: {str(e)}")
            return "I apologize, but I'm having trouble processing your request. Please try again."
    
    # Fallback methods
    async def generate_embeddings(self, text: str) -> List[float]:
        """
        Generate text embeddings using local sentence-transformers model.
        Uses all-MiniLM-L6-v2 which produces 384-dimensional vectors.
        No API key required - runs entirely locally.

        Args:
            text: Text to generate embeddings for

        Returns:
            List of floats representing the embedding vector (384 dimensions)
        """
        try:
            if not hasattr(self, '_embedding_model') or self._embedding_model is None:
                logger.info("Loading local embedding model (all-MiniLM-L6-v2)...")
                self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Embedding model loaded successfully")

            # Run synchronous model in thread pool to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            truncated = text[:8000]
            embedding = await loop.run_in_executor(
                None, lambda: self._embedding_model.encode(truncated).tolist()
            )

            logger.debug(f"Generated embedding for text (length: {len(text)}, dims: {len(embedding)})")
            return embedding

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return [0.1] * 384

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

    async def _analyze_regulatory_circular_local(self, text: str, circular_title: str) -> Dict[str, Any]:
        """Use local Ollama LLM for regulatory analysis (when USE_LOCAL_LLM=true)."""
        import time
        start_time = time.time()

        try:
            from services.llm_provider import get_llm_provider, log_llm_cost

            provider = get_llm_provider()
            provider_name = provider.get_provider_name()

            system_prompt = (
                "You are an expert regulatory compliance analyst specializing in Indian financial regulations "
                "(RBI, SEBI, FIU-IND, NPCI). Provide thorough, accurate analysis with specific actionable insights. "
                "Return only valid JSON."
            )
            user_prompt = f"""Analyze this regulatory circular comprehensively:

Title: {circular_title}

Circular Text:
{text[:10000]}

Provide a thorough analysis and return as JSON with these keys:
- summary: Executive summary (3-4 sentences covering scope, key requirements, and compliance timeline)
- key_changes: List of key regulatory changes (specific bullet points)
- org_impact: Detailed organizational impact (governance, policies, reporting) as a string
- technical_impact: IT/system changes needed (specific systems, integrations) as a string
- operational_impact: Process changes needed (workflows, procedures, controls) as a string
- departments_affected: List of affected departments
- timeline: Key compliance deadlines with dates if available
- references: References to previous circulars, acts, or regulations"""

            logger.info("=" * 60)
            logger.info(f"[REGULATORY ANALYSIS - LOCAL LLM ({provider_name})]")
            logger.info(f"  Title: {circular_title}")
            logger.info(f"  Text length: {len(text)} chars (using first 10000)")

            try:
                result = await provider.generate_json(
                    system=system_prompt,
                    prompt=user_prompt,
                    max_tokens=4096,
                )
            except (ValueError, Exception):
                # generate_json failed, try generate + manual parse
                response_text = await provider.generate(
                    system=system_prompt,
                    prompt=user_prompt,
                    max_tokens=4096,
                    temperature=0.3,
                )
                clean = response_text.strip()
                if clean.startswith("```"):
                    clean = clean.split("```")[1]
                    if clean.startswith("json"):
                        clean = clean[4:]
                try:
                    result = json.loads(clean)
                except json.JSONDecodeError:
                    logger.warning("Local LLM response not valid JSON, using fallback")
                    return self._fallback_analysis(text)

            elapsed = time.time() - start_time
            logger.info(f"  Time: {elapsed:.2f}s")
            logger.info(f"  Provider: {provider_name}")
            logger.info("=" * 60)

            await log_llm_cost(
                db=self._get_db(),
                provider=provider_name,
                operation="regulatory_analysis",
                model=provider.model if hasattr(provider, 'model') else "",
            )

            return result

        except Exception as e:
            logger.error(f"Local LLM analysis error: {str(e)}")
            return self._fallback_analysis(text)

    async def _analyze_policy_document_local(self, text: str, policy_title: str) -> Dict[str, Any]:
        """Use local Ollama LLM for policy analysis (when USE_LOCAL_LLM=true)."""
        import time
        start_time = time.time()

        try:
            from services.llm_provider import get_llm_provider, log_llm_cost

            provider = get_llm_provider()
            provider_name = provider.get_provider_name()

            system_prompt = (
                "You are an expert compliance and policy analyst specializing in Indian financial regulations "
                "(RBI, SEBI, NBFC). Analyze this internal policy document and provide a thorough impact assessment. "
                "Return only valid JSON."
            )
            user_prompt = f"""Analyze this internal policy document comprehensively:

Title: {policy_title}

Policy Text:
{text[:10000]}

Provide a thorough analysis and return as JSON with these keys:
- summary: Executive summary of the policy (3-4 sentences)
- key_areas: List of key compliance/policy areas covered
- org_impact: How this policy affects the organization as a string
- technical_impact: IT/system changes or requirements as a string
- operational_impact: Process and workflow changes required as a string
- department: Primary department responsible
- risk_level: Overall compliance risk level (Critical/High/Medium/Low)
- related_regulations: List of external regulations this policy likely maps to"""

            logger.info("=" * 60)
            logger.info(f"[POLICY ANALYSIS - LOCAL LLM ({provider_name})]")
            logger.info(f"  Title: {policy_title}")

            try:
                result = await provider.generate_json(
                    system=system_prompt,
                    prompt=user_prompt,
                    max_tokens=4096,
                )
            except (ValueError, Exception):
                response_text = await provider.generate(
                    system=system_prompt,
                    prompt=user_prompt,
                    max_tokens=4096,
                    temperature=0.3,
                )
                clean = response_text.strip()
                if clean.startswith("```"):
                    clean = clean.split("```")[1]
                    if clean.startswith("json"):
                        clean = clean[4:]
                try:
                    result = json.loads(clean)
                except json.JSONDecodeError:
                    return {}

            elapsed = time.time() - start_time
            logger.info(f"  Time: {elapsed:.2f}s | Provider: {provider_name}")
            logger.info("=" * 60)

            await log_llm_cost(
                db=self._get_db(),
                provider=provider_name,
                operation="policy_analysis",
                model=provider.model if hasattr(provider, 'model') else "",
            )

            return result

        except Exception as e:
            logger.error(f"Local LLM policy analysis error: {str(e)}")
            return {}
    
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
