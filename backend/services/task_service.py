"""
Task Lifecycle Management Service

Handles:
- Task creation and assignment
- Time tracking (start/stop timer)
- Status transitions with validation
- Evidence linking
- AI Review for compliance checking
- Manual approval workflow
- Recurring task generation
- Priority escalation
- Activity logging
- Email reminder preparation

Author: CompliAI
"""

import anthropic
import os
import re
import json
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)


class TaskService:
    """
    Comprehensive task lifecycle management service.
    """
    
    # Valid status transitions
    STATUS_TRANSITIONS = {
        "Open": ["In Progress", "Closed"],
        "In Progress": ["Open", "Pending Evidence", "Closed"],
        "Pending Evidence": ["In Progress", "AI Review"],
        "AI Review": ["Manual Review", "In Progress", "Rejected"],
        "Manual Review": ["Completed", "Rejected", "In Progress"],
        "Completed": ["Closed"],
        "Rejected": ["In Progress", "Open"],
        "Closed": []
    }
    
    # Priority escalation rules (days before due date -> new priority)
    ESCALATION_RULES = {
        "Low": [(7, "Medium"), (3, "High"), (1, "Critical")],
        "Medium": [(3, "High"), (1, "Critical")],
        "High": [(1, "Critical")],
        "Critical": []
    }
    
    def __init__(self, db=None):
        """Initialize with database connection."""
        self.db = db
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        if self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("ANTHROPIC_API_KEY not set - AI review disabled")
        self.model = "claude-sonnet-4-20250514"
    
    # =========================================================================
    # ACTIVITY LOGGING
    # =========================================================================
    
    def _create_activity(
        self, 
        activity_type: str, 
        user_id: str, 
        user_name: str,
        details: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create an activity log entry."""
        return {
            "id": str(uuid.uuid4()),
            "type": activity_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "user_name": user_name,
            "details": details or {}
        }
    
    async def add_activity(
        self, 
        task_id: str, 
        activity_type: str,
        user_id: str,
        user_name: str,
        details: Dict[str, Any] = None
    ):
        """Add activity to task's activity log."""
        activity = self._create_activity(activity_type, user_id, user_name, details)
        
        await self.db.tasks.update_one(
            {"id": task_id},
            {
                "$push": {"activities": activity},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        return activity
    
    # =========================================================================
    # STATUS MANAGEMENT
    # =========================================================================
    
    def can_transition(self, current_status: str, new_status: str) -> bool:
        """Check if status transition is valid."""
        allowed = self.STATUS_TRANSITIONS.get(current_status, [])
        return new_status in allowed
    
    async def change_status(
        self,
        task_id: str,
        new_status: str,
        user_id: str,
        user_name: str,
        notes: str = None
    ) -> Tuple[bool, str]:
        """
        Change task status with validation.
        
        Returns:
            Tuple of (success, message)
        """
        task = await self.db.tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            return False, "Task not found"
        
        current_status = task.get("status", "Open")
        
        if not self.can_transition(current_status, new_status):
            return False, f"Cannot transition from '{current_status}' to '{new_status}'"
        
        # Stop timer if running
        update_data = {
            "status": new_status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if task.get("timer_running"):
            update_data["timer_running"] = False
            if task.get("timer_started_at"):
                # Calculate duration
                start = datetime.fromisoformat(task["timer_started_at"])
                duration = int((datetime.now(timezone.utc) - start).total_seconds() / 60)
                update_data["$inc"] = {"total_time_minutes": duration}
        
        # Add activity
        activity = self._create_activity(
            "status_changed", 
            user_id, 
            user_name,
            {"from": current_status, "to": new_status, "notes": notes}
        )
        
        await self.db.tasks.update_one(
            {"id": task_id},
            {
                "$set": update_data,
                "$push": {"activities": activity}
            }
        )
        
        return True, f"Status changed to {new_status}"
    
    # =========================================================================
    # ASSIGNMENT
    # =========================================================================
    
    async def assign_task(
        self,
        task_id: str,
        member_id: str,
        member_name: str,
        department_id: str = None,
        department_name: str = None,
        assigner_id: str = None,
        assigner_name: str = None
    ) -> Tuple[bool, str]:
        """Assign task to a team member."""
        task = await self.db.tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            return False, "Task not found"
        
        old_assignee = task.get("assigned_to")
        
        update_data = {
            "assigned_to": member_name,
            "assigned_member_id": member_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if department_id:
            update_data["department_id"] = department_id
            update_data["department"] = department_name
        
        activity = self._create_activity(
            "assigned",
            assigner_id or "system",
            assigner_name or "System",
            {"from": old_assignee, "to": member_name, "member_id": member_id}
        )
        
        await self.db.tasks.update_one(
            {"id": task_id},
            {
                "$set": update_data,
                "$push": {"activities": activity}
            }
        )
        
        return True, f"Task assigned to {member_name}"
    
    # =========================================================================
    # TIME TRACKING
    # =========================================================================
    
    async def start_timer(
        self,
        task_id: str,
        user_id: str,
        user_name: str
    ) -> Tuple[bool, str]:
        """Start the timer for a task."""
        task = await self.db.tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            return False, "Task not found"
        
        if task.get("timer_running"):
            return False, "Timer is already running"
        
        now = datetime.now(timezone.utc)
        
        activity = self._create_activity(
            "timer_started",
            user_id,
            user_name,
            {"started_at": now.isoformat()}
        )
        
        await self.db.tasks.update_one(
            {"id": task_id},
            {
                "$set": {
                    "timer_running": True,
                    "timer_started_at": now.isoformat(),
                    "status": "In Progress",  # Auto-start progress
                    "updated_at": now.isoformat()
                },
                "$push": {"activities": activity}
            }
        )
        
        return True, "Timer started"
    
    async def stop_timer(
        self,
        task_id: str,
        user_id: str,
        user_name: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Stop the timer and record time entry."""
        task = await self.db.tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            return False, {"error": "Task not found"}
        
        if not task.get("timer_running"):
            return False, {"error": "Timer is not running"}
        
        start_time = datetime.fromisoformat(task["timer_started_at"])
        end_time = datetime.now(timezone.utc)
        duration_minutes = int((end_time - start_time).total_seconds() / 60)
        
        time_entry = {
            "id": str(uuid.uuid4()),
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "duration_minutes": duration_minutes,
            "user_id": user_id,
            "user_name": user_name
        }
        
        new_total = task.get("total_time_minutes", 0) + duration_minutes
        
        activity = self._create_activity(
            "timer_stopped",
            user_id,
            user_name,
            {"duration_minutes": duration_minutes, "total_time": new_total}
        )
        
        await self.db.tasks.update_one(
            {"id": task_id},
            {
                "$set": {
                    "timer_running": False,
                    "timer_started_at": None,
                    "total_time_minutes": new_total,
                    "updated_at": end_time.isoformat()
                },
                "$push": {
                    "time_entries": time_entry,
                    "activities": activity
                }
            }
        )
        
        return True, {
            "duration_minutes": duration_minutes,
            "total_time_minutes": new_total,
            "time_entry": time_entry
        }
    
    # =========================================================================
    # EVIDENCE MANAGEMENT
    # =========================================================================
    
    async def add_evidence(
        self,
        task_id: str,
        evidence_id: str,
        user_id: str,
        user_name: str
    ) -> Tuple[bool, str]:
        """Link evidence to a task."""
        task = await self.db.tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            return False, "Task not found"
        
        evidence = await self.db.evidence.find_one({"id": evidence_id}, {"_id": 0})
        if not evidence:
            return False, "Evidence not found"
        
        activity = self._create_activity(
            "evidence_added",
            user_id,
            user_name,
            {"evidence_id": evidence_id, "evidence_title": evidence.get("title")}
        )
        
        await self.db.tasks.update_one(
            {"id": task_id},
            {
                "$addToSet": {"evidence_ids": evidence_id},
                "$push": {"activities": activity},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        
        # Update evidence to link back to task
        await self.db.evidence.update_one(
            {"id": evidence_id},
            {"$set": {"task_id": task_id}}
        )
        
        return True, "Evidence linked to task"
    
    # =========================================================================
    # SUBMIT FOR REVIEW
    # =========================================================================
    
    async def submit_for_review(
        self,
        task_id: str,
        user_id: str,
        user_name: str,
        evidence_ids: List[str] = None,
        notes: str = None
    ) -> Tuple[bool, str]:
        """Submit task for AI review."""
        task = await self.db.tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            return False, "Task not found"
        
        # Add any new evidence
        if evidence_ids:
            for eid in evidence_ids:
                if eid not in task.get("evidence_ids", []):
                    await self.add_evidence(task_id, eid, user_id, user_name)
        
        # Change status to AI Review
        success, msg = await self.change_status(
            task_id, "AI Review", user_id, user_name, notes
        )
        
        if success:
            # Trigger AI review asynchronously
            await self._perform_ai_review(task_id, user_id, user_name)
        
        return success, "Task submitted for AI review"
    
    async def _perform_ai_review(
        self,
        task_id: str,
        user_id: str,
        user_name: str
    ):
        """Perform AI review of task completion and evidence."""
        task = await self.db.tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            return
        
        # Get linked evidence
        evidence_list = []
        for eid in task.get("evidence_ids", []):
            ev = await self.db.evidence.find_one({"id": eid}, {"_id": 0})
            if ev:
                evidence_list.append(ev)
        
        # Get source gap/regulation info if available
        source_context = ""
        if task.get("gap_id"):
            gap = await self.db.gap_analyses.find_one(
                {"enhanced_report.gap_results.regulation_clause_id": task.get("clause_id")},
                {"_id": 0}
            )
            if gap:
                source_context = f"This task was created from a gap analysis."
        
        if task.get("regulation_id"):
            reg = await self.db.regulations.find_one({"id": task["regulation_id"]}, {"_id": 0, "title": 1})
            if reg:
                source_context += f"\nRegulation: {reg.get('title')}"
        
        # Prepare context for AI
        task_context = f"""
Task Title: {task.get('title')}
Task Description: {task.get('description')}
Compliance Indicators to Check: {', '.join(task.get('compliance_indicators', []))}
Unfulfilled Indicators: {', '.join(task.get('unfulfilled_indicators', []))}
{source_context}

Evidence Submitted:
"""
        for ev in evidence_list:
            task_context += f"\n- {ev.get('title')}: {ev.get('description', 'No description')}"
            task_context += f"\n  File: {ev.get('file_name')}"
            if ev.get('ai_validation_notes'):
                task_context += f"\n  Previous AI Notes: {ev.get('ai_validation_notes')}"
        
        # Call AI for review
        if self.client:
            try:
                system_prompt = """You are a compliance auditor reviewing task completion.
Assess if the evidence submitted is sufficient to mark the task as complete and the related compliance requirement as addressed.

Return JSON:
{
    "is_sufficient": true/false,
    "confidence": 0.0-1.0,
    "compliance_status": "compliant" | "partially_compliant" | "non_compliant",
    "summary": "Brief summary of your assessment",
    "gaps_remaining": ["List of any remaining gaps or issues"],
    "recommendations": ["Specific recommendations if not sufficient"],
    "evidence_quality": "excellent" | "good" | "fair" | "poor"
}"""

                user_prompt = f"""Review this task completion:

{task_context}

Assess whether:
1. The evidence is sufficient to address the task requirements
2. The compliance indicators are now fulfilled
3. Any gaps remain that need attention

Provide your assessment in JSON format."""

                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=2048,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                
                result_text = response.content[0].text
                
                # Parse JSON
                clean = result_text.strip()
                if clean.startswith("```"):
                    clean = re.sub(r'^```(?:json)?\n?', '', clean)
                    clean = re.sub(r'\n?```$', '', clean)
                
                ai_result = json.loads(clean)
                
            except Exception as e:
                logger.error(f"AI review failed: {e}")
                ai_result = {
                    "is_sufficient": False,
                    "confidence": 0.0,
                    "compliance_status": "unknown",
                    "summary": "AI review failed - manual review required",
                    "gaps_remaining": ["AI review could not be completed"],
                    "recommendations": ["Please proceed with manual review"],
                    "evidence_quality": "unknown"
                }
        else:
            ai_result = {
                "is_sufficient": True,
                "confidence": 0.5,
                "compliance_status": "unknown",
                "summary": "AI review not available - proceeding to manual review",
                "gaps_remaining": [],
                "recommendations": [],
                "evidence_quality": "unknown"
            }
        
        # Update task with AI review result
        activity = self._create_activity(
            "ai_reviewed",
            "system",
            "AI Reviewer",
            ai_result
        )
        
        # Determine next status
        next_status = "Manual Review"
        if not ai_result.get("is_sufficient") and ai_result.get("confidence", 0) > 0.8:
            # High confidence rejection - could optionally auto-reject
            pass
        
        await self.db.tasks.update_one(
            {"id": task_id},
            {
                "$set": {
                    "ai_review_result": ai_result,
                    "ai_reviewed_at": datetime.now(timezone.utc).isoformat(),
                    "status": next_status,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                },
                "$push": {"activities": activity}
            }
        )
    
    # =========================================================================
    # MANUAL APPROVAL
    # =========================================================================
    
    async def approve_task(
        self,
        task_id: str,
        reviewer_id: str,
        reviewer_name: str,
        notes: str = None
    ) -> Tuple[bool, str]:
        """Approve task after manual review."""
        task = await self.db.tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            return False, "Task not found"
        
        if task.get("status") != "Manual Review":
            return False, "Task must be in Manual Review status to approve"
        
        activity = self._create_activity(
            "approved",
            reviewer_id,
            reviewer_name,
            {"notes": notes}
        )
        
        # Stop timer if running
        if task.get("timer_running"):
            await self.stop_timer(task_id, reviewer_id, reviewer_name)
        
        await self.db.tasks.update_one(
            {"id": task_id},
            {
                "$set": {
                    "status": "Completed",
                    "reviewer_id": reviewer_id,
                    "reviewer_name": reviewer_name,
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                },
                "$push": {"activities": activity}
            }
        )
        
        # Update related gap/policy compliance status if applicable
        await self._update_compliance_status(task)
        
        return True, "Task approved and marked as completed"
    
    async def reject_task(
        self,
        task_id: str,
        reviewer_id: str,
        reviewer_name: str,
        reason: str
    ) -> Tuple[bool, str]:
        """Reject task with reason."""
        task = await self.db.tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            return False, "Task not found"
        
        if task.get("status") not in ["AI Review", "Manual Review"]:
            return False, "Task must be in review status to reject"
        
        activity = self._create_activity(
            "rejected",
            reviewer_id,
            reviewer_name,
            {"reason": reason}
        )
        
        await self.db.tasks.update_one(
            {"id": task_id},
            {
                "$set": {
                    "status": "Rejected",
                    "rejection_reason": reason,
                    "reviewer_id": reviewer_id,
                    "reviewer_name": reviewer_name,
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                },
                "$push": {"activities": activity}
            }
        )
        
        return True, "Task rejected"
    
    async def _update_compliance_status(self, task: Dict[str, Any]):
        """Update compliance status of related gap/policy after task completion."""
        # This would update the gap analysis result or policy to reflect
        # that this specific requirement is now addressed
        if task.get("gap_id"):
            # Mark the specific gap as resolved
            pass  # Implement based on your gap tracking structure
        
        if task.get("clause_id") and task.get("policy_id"):
            # Could update clause compliance status
            pass
    
    # =========================================================================
    # COMMENTS
    # =========================================================================
    
    async def add_comment(
        self,
        task_id: str,
        content: str,
        user_id: str,
        user_name: str,
        user_email: str = None,
        mentions: List[str] = None
    ) -> Dict[str, Any]:
        """Add a comment to a task."""
        comment = {
            "id": str(uuid.uuid4()),
            "task_id": task_id,
            "content": content,
            "user_id": user_id,
            "user_name": user_name,
            "user_email": user_email,
            "mentions": mentions or [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.db.task_comments.insert_one(comment)
        
        # Add activity
        activity = self._create_activity(
            "comment_added",
            user_id,
            user_name,
            {"comment_id": comment["id"], "preview": content[:100]}
        )
        
        await self.db.tasks.update_one(
            {"id": task_id},
            {
                "$push": {"activities": activity},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
        
        return comment
    
    async def get_comments(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all comments for a task."""
        comments = await self.db.task_comments.find(
            {"task_id": task_id},
            {"_id": 0}
        ).sort("created_at", 1).to_list(1000)
        return comments
    
    # =========================================================================
    # ESCALATION
    # =========================================================================
    
    async def check_and_escalate(self) -> List[Dict[str, Any]]:
        """
        Check all tasks for escalation needs.
        Should be run periodically (e.g., daily cron job).
        """
        escalated = []
        now = datetime.now(timezone.utc)
        
        # Find tasks with due dates that haven't been completed
        tasks = await self.db.tasks.find(
            {
                "status": {"$nin": ["Completed", "Closed"]},
                "due_date": {"$ne": None}
            },
            {"_id": 0}
        ).to_list(10000)
        
        for task in tasks:
            due_date = datetime.fromisoformat(task["due_date"].replace("Z", "+00:00")) if isinstance(task["due_date"], str) else task["due_date"]
            days_until_due = (due_date - now).days
            current_priority = task.get("priority", "Medium")
            
            # Check if overdue
            if days_until_due < 0:
                if not task.get("is_overdue"):
                    await self.db.tasks.update_one(
                        {"id": task["id"]},
                        {"$set": {"is_overdue": True}}
                    )
            
            # Check escalation rules
            rules = self.ESCALATION_RULES.get(current_priority, [])
            for threshold, new_priority in rules:
                if days_until_due <= threshold:
                    # Escalate
                    escalation = {
                        "from": current_priority,
                        "to": new_priority,
                        "reason": f"Due in {days_until_due} days",
                        "timestamp": now.isoformat()
                    }
                    
                    activity = self._create_activity(
                        "escalated",
                        "system",
                        "Auto-Escalation",
                        escalation
                    )
                    
                    await self.db.tasks.update_one(
                        {"id": task["id"]},
                        {
                            "$set": {
                                "priority": new_priority,
                                "original_priority": task.get("original_priority") or current_priority,
                                "updated_at": now.isoformat()
                            },
                            "$push": {
                                "escalation_history": escalation,
                                "activities": activity
                            }
                        }
                    )
                    
                    escalated.append({
                        "task_id": task["id"],
                        "title": task["title"],
                        "from": current_priority,
                        "to": new_priority
                    })
                    break
        
        return escalated
    
    # =========================================================================
    # RECURRING TASKS
    # =========================================================================
    
    async def generate_recurring_tasks(self) -> List[Dict[str, Any]]:
        """
        Generate next occurrence of recurring tasks.
        Should be run periodically.
        """
        generated = []
        now = datetime.now(timezone.utc)
        
        # Find recurring tasks that need new instances
        recurring = await self.db.tasks.find(
            {
                "is_recurring": True,
                "parent_task_id": None,  # Only parent tasks
                "$or": [
                    {"next_occurrence": {"$lte": now.isoformat()}},
                    {"next_occurrence": None}
                ]
            },
            {"_id": 0}
        ).to_list(1000)
        
        for parent in recurring:
            # Create new task instance
            new_task = {
                **parent,
                "id": str(uuid.uuid4()),
                "parent_task_id": parent["id"],
                "status": "Open",
                "activities": [],
                "time_entries": [],
                "total_time_minutes": 0,
                "evidence_ids": [],
                "ai_review_result": None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
            
            # Calculate next due date based on recurrence
            recurrence_type = parent.get("recurrence_type", "monthly")
            config = parent.get("recurrence_config", {})
            
            if parent.get("due_date"):
                last_due = datetime.fromisoformat(parent["due_date"].replace("Z", "+00:00")) if isinstance(parent["due_date"], str) else parent["due_date"]
            else:
                last_due = now
            
            if recurrence_type == "daily":
                new_due = last_due + timedelta(days=config.get("interval", 1))
            elif recurrence_type == "weekly":
                new_due = last_due + timedelta(weeks=config.get("interval", 1))
            elif recurrence_type == "monthly":
                new_due = last_due.replace(month=last_due.month + config.get("interval", 1))
            elif recurrence_type == "quarterly":
                new_due = last_due.replace(month=last_due.month + 3)
            elif recurrence_type == "yearly":
                new_due = last_due.replace(year=last_due.year + 1)
            else:
                new_due = last_due + timedelta(days=30)
            
            new_task["due_date"] = new_due.isoformat()
            
            # Remove _id if present
            new_task.pop("_id", None)
            
            await self.db.tasks.insert_one(new_task)
            
            # Update parent with next occurrence
            next_next = new_due + timedelta(days=30)  # Approximate
            await self.db.tasks.update_one(
                {"id": parent["id"]},
                {"$set": {"next_occurrence": next_next.isoformat()}}
            )
            
            generated.append({
                "parent_id": parent["id"],
                "new_task_id": new_task["id"],
                "due_date": new_due.isoformat()
            })
        
        return generated
    
    # =========================================================================
    # EMAIL REMINDERS (Preparation - actual sending configured later)
    # =========================================================================
    
    async def get_pending_reminders(self) -> List[Dict[str, Any]]:
        """
        Get list of tasks that need reminder emails.
        Returns data structure ready for email service.
        """
        reminders = []
        now = datetime.now(timezone.utc)
        
        tasks = await self.db.tasks.find(
            {
                "status": {"$nin": ["Completed", "Closed"]},
                "due_date": {"$ne": None},
                "assigned_member_id": {"$ne": None}
            },
            {"_id": 0}
        ).to_list(10000)
        
        for task in tasks:
            due_date = datetime.fromisoformat(task["due_date"].replace("Z", "+00:00")) if isinstance(task["due_date"], str) else task["due_date"]
            days_until_due = (due_date - now).days
            
            reminder_days = task.get("reminder_days", [1, 0])
            
            for reminder_day in reminder_days:
                if days_until_due == reminder_day:
                    # Check if reminder already sent today
                    last_reminder = task.get("last_reminder_sent")
                    if last_reminder:
                        last = datetime.fromisoformat(last_reminder.replace("Z", "+00:00")) if isinstance(last_reminder, str) else last_reminder
                        if (now - last).days < 1:
                            continue
                    
                    # Get assignee email
                    member = await self.db.department_members.find_one(
                        {"id": task["assigned_member_id"]},
                        {"_id": 0, "email": 1, "name": 1}
                    )
                    
                    if member and member.get("email"):
                        reminder = {
                            "task_id": task["id"],
                            "task_title": task["title"],
                            "assignee_email": member["email"],
                            "assignee_name": member["name"],
                            "due_date": due_date.isoformat(),
                            "days_until_due": days_until_due,
                            "priority": task.get("priority"),
                            "reminder_type": "due_today" if days_until_due == 0 else f"due_in_{days_until_due}_days"
                        }
                        reminders.append(reminder)
                        
                        # Mark reminder as sent
                        await self.db.tasks.update_one(
                            {"id": task["id"]},
                            {"$set": {"last_reminder_sent": now.isoformat()}}
                        )
        
        # Also check for overdue tasks
        overdue = await self.db.tasks.find(
            {
                "status": {"$nin": ["Completed", "Closed"]},
                "is_overdue": True,
                "assigned_member_id": {"$ne": None}
            },
            {"_id": 0}
        ).to_list(1000)
        
        for task in overdue:
            member = await self.db.department_members.find_one(
                {"id": task["assigned_member_id"]},
                {"_id": 0, "email": 1, "name": 1}
            )
            
            if member and member.get("email"):
                due_date = datetime.fromisoformat(task["due_date"].replace("Z", "+00:00")) if isinstance(task["due_date"], str) else task["due_date"]
                days_overdue = (now - due_date).days
                
                reminders.append({
                    "task_id": task["id"],
                    "task_title": task["title"],
                    "assignee_email": member["email"],
                    "assignee_name": member["name"],
                    "due_date": due_date.isoformat(),
                    "days_overdue": days_overdue,
                    "priority": task.get("priority"),
                    "reminder_type": "overdue"
                })
        
        return reminders
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    async def get_task_stats(self, user_id: str = None, organization: str = None) -> Dict[str, Any]:
        """Get task statistics for dashboard."""
        query = {}
        if user_id:
            query["user_id"] = user_id
        if organization:
            query["organization"] = organization
        
        all_tasks = await self.db.tasks.find(query, {"_id": 0}).to_list(10000)
        
        stats = {
            "total": len(all_tasks),
            "by_status": {},
            "by_priority": {},
            "by_department": {},
            "overdue": 0,
            "due_today": 0,
            "due_this_week": 0,
            "avg_completion_time_hours": 0,
            "completion_rate": 0
        }
        
        now = datetime.now(timezone.utc)
        completed_times = []
        
        for task in all_tasks:
            # By status
            status = task.get("status", "Open")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            
            # By priority
            priority = task.get("priority", "Medium")
            stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
            
            # By department
            dept = task.get("department", "Unassigned")
            stats["by_department"][dept] = stats["by_department"].get(dept, 0) + 1
            
            # Due date checks
            if task.get("due_date") and status not in ["Completed", "Closed"]:
                due = datetime.fromisoformat(task["due_date"].replace("Z", "+00:00")) if isinstance(task["due_date"], str) else task["due_date"]
                days = (due - now).days
                
                if days < 0:
                    stats["overdue"] += 1
                elif days == 0:
                    stats["due_today"] += 1
                elif days <= 7:
                    stats["due_this_week"] += 1
            
            # Completion time
            if status == "Completed" and task.get("total_time_minutes"):
                completed_times.append(task["total_time_minutes"])
        
        # Calculate averages
        if completed_times:
            stats["avg_completion_time_hours"] = round(sum(completed_times) / len(completed_times) / 60, 1)
        
        completed = stats["by_status"].get("Completed", 0) + stats["by_status"].get("Closed", 0)
        if stats["total"] > 0:
            stats["completion_rate"] = round(completed / stats["total"] * 100, 1)

        return stats

    # =========================================================================
    # AI-POWERED TASK ASSIGNMENT
    # =========================================================================

    async def calculate_member_workload(self, member_id: str) -> float:
        """
        Calculate current workload score for a team member.
        Returns: 0.0 (completely free) to 100.0 (fully loaded)
        """
        # Count active tasks (not Completed or Closed)
        active_statuses = ["Open", "In Progress", "Pending Evidence", "AI Review", "Manual Review"]

        active_tasks = await self.db.tasks.count_documents({
            "assigned_member_id": member_id,
            "status": {"$in": active_statuses}
        })

        # Calculate workload score (simple linear: 10 points per task, capped at 100)
        workload_score = min(active_tasks * 10, 100)

        return workload_score

    async def suggest_task_assignment(
        self,
        task_id: str,
        department_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Use AI to suggest the best team member for a task based on:
        - Current workload
        - Expertise match
        - Role suitability
        - Historical performance

        Returns: {
            "suggested_member": {...},
            "reasoning": "...",
            "workload_comparison": [{member, workload_score}],
            "confidence": 0.85
        }
        """
        if not self.client:
            raise ValueError("AI assignment requires ANTHROPIC_API_KEY")

        # Get the task
        task = await self.db.tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Get department members
        if department_id:
            dept_query = {"id": department_id}
        elif task.get("department_id"):
            dept_query = {"id": task["department_id"]}
        else:
            # No department specified - use organization-wide members
            dept_query = {"organization": task.get("organization")}

        # Get department(s)
        departments = await self.db.departments.find(dept_query, {"_id": 0}).to_list(100)
        if not departments:
            raise ValueError("No department found for task assignment")

        # Collect all member IDs from departments
        member_ids = []
        for dept in departments:
            member_ids.extend(dept.get("members", []))

        if not member_ids:
            raise ValueError("No members found in department(s)")

        # Get member details
        members = await self.db.department_members.find(
            {"id": {"$in": member_ids}, "can_be_assigned_tasks": True},
            {"_id": 0}
        ).to_list(100)

        if not members:
            raise ValueError("No assignable members found")

        # Calculate workload for each member
        member_workloads = []
        for member in members:
            workload = await self.calculate_member_workload(member["id"])

            # Update member's workload_score in database
            await self.db.department_members.update_one(
                {"id": member["id"]},
                {"$set": {"workload_score": workload, "active_tasks": int(workload / 10)}}
            )

            member_workloads.append({
                "member_id": member["id"],
                "name": member["name"],
                "email": member["email"],
                "title": member["title"],
                "role": member["role"],
                "expertise_areas": member.get("expertise_areas", []),
                "workload_score": workload,
                "active_tasks": int(workload / 10)
            })

        # Sort by workload (lowest first)
        member_workloads.sort(key=lambda x: x["workload_score"])

        # Prepare context for AI
        task_context = f"""
Task Details:
- Title: {task.get('title')}
- Description: {task.get('description')}
- Priority: {task.get('priority', 'MEDIUM')}
- Department: {task.get('department', 'Not specified')}
- Tags: {', '.join(task.get('tags', []))}
"""

        members_context = "Available Team Members:\n\n"
        for m in member_workloads:
            members_context += f"""
{m['name']} ({m['title']})
- Role: {m['role']}
- Current Workload: {m['workload_score']}/100 ({m['active_tasks']} active tasks)
- Expertise: {', '.join(m['expertise_areas']) if m['expertise_areas'] else 'General'}
---
"""

        # AI Assignment Prompt
        prompt = f"""{task_context}

{members_context}

Based on the task requirements and team member profiles, suggest the best person to assign this task to.

Consider:
1. **Workload Balance**: Prefer members with lower current workload
2. **Expertise Match**: Match task requirements to member expertise areas
3. **Role Suitability**: Consider if the role is appropriate for the task priority/complexity
4. **Fair Distribution**: Avoid overloading any single person

Respond in JSON format:
{{
    "suggested_member_id": "member_id_here",
    "suggested_member_name": "name_here",
    "reasoning": "Brief explanation (2-3 sentences)",
    "confidence": 0.85,
    "alternative_members": ["id1", "id2"]
}}
"""

        try:
            # Call Claude AI for assignment suggestion
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse AI response
            response_text = response.content[0].text

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                ai_suggestion = json.loads(json_match.group())
            else:
                # Fallback to lowest workload
                ai_suggestion = {
                    "suggested_member_id": member_workloads[0]["member_id"],
                    "suggested_member_name": member_workloads[0]["name"],
                    "reasoning": "Selected member with lowest current workload",
                    "confidence": 0.7
                }

            # Find the suggested member details
            suggested = next(
                (m for m in member_workloads if m["member_id"] == ai_suggestion["suggested_member_id"]),
                member_workloads[0]
            )

            return {
                "success": True,
                "suggested_member": {
                    "member_id": suggested["member_id"],
                    "name": suggested["name"],
                    "email": suggested["email"],
                    "title": suggested["title"],
                    "role": suggested["role"],
                    "workload_score": suggested["workload_score"],
                    "active_tasks": suggested["active_tasks"]
                },
                "reasoning": ai_suggestion.get("reasoning", "AI analysis completed"),
                "confidence": ai_suggestion.get("confidence", 0.75),
                "workload_comparison": member_workloads,
                "alternative_members": [
                    m for m in member_workloads
                    if m["member_id"] in ai_suggestion.get("alternative_members", [])
                ]
            }

        except Exception as e:
            logger.error(f"AI assignment failed: {str(e)}", exc_info=True)
            # Fallback: suggest member with lowest workload
            suggested = member_workloads[0]
            return {
                "success": True,
                "suggested_member": {
                    "member_id": suggested["member_id"],
                    "name": suggested["name"],
                    "email": suggested["email"],
                    "title": suggested["title"],
                    "role": suggested["role"],
                    "workload_score": suggested["workload_score"],
                    "active_tasks": suggested["active_tasks"]
                },
                "reasoning": f"Automatic suggestion: {suggested['name']} has the lowest current workload ({suggested['workload_score']}/100)",
                "confidence": 0.65,
                "workload_comparison": member_workloads,
                "alternative_members": member_workloads[1:3] if len(member_workloads) > 1 else []
            }
