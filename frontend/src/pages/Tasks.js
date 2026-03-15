import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { ScrollArea } from "../components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "../components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "../components/ui/alert-dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../components/ui/dropdown-menu";
import { useFormDirtyTracking } from "../hooks/useFormDirtyTracking";
import {
  Plus, Search, Filter, Clock, User, Calendar, AlertTriangle,
  CheckCircle, Play, Pause, Upload, MessageSquare, Bot,
  ArrowRight, ChevronRight, FileText, History, XCircle,
  LayoutGrid, List, RefreshCw, Timer, TrendingUp, AlertCircle, Target,
  Link2, ExternalLink, BookOpen, Shield, Scale, Download,
  Copy, Trash2, Users, CheckSquare
} from "lucide-react";
import { tasksApi, departmentsApi, evidenceApi } from "../lib/api";
import { format, formatDistanceToNow, isPast, isToday, differenceInHours } from "date-fns";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";

// Status configuration with colors and icons
const STATUS_CONFIG = {
  open: { label: "Open", color: "bg-gray-100 text-gray-700 border-gray-300", icon: Target },
  in_progress: { label: "In Progress", color: "bg-blue-100 text-blue-700 border-blue-300", icon: Play },
  pending_evidence: { label: "Pending Evidence", color: "bg-amber-100 text-amber-700 border-amber-300", icon: Upload },
  ai_review: { label: "AI Review", color: "bg-purple-100 text-purple-700 border-purple-300", icon: Bot },
  manual_review: { label: "Manual Review", color: "bg-teal-100 text-teal-700 border-teal-300", icon: User },
  completed: { label: "Completed", color: "bg-emerald-100 text-emerald-700 border-emerald-300", icon: CheckCircle },
  rejected: { label: "Rejected", color: "bg-red-100 text-red-700 border-red-300", icon: XCircle },
  closed: { label: "Closed", color: "bg-gray-100 text-gray-600 border-gray-300", icon: CheckCircle }
};

const PRIORITY_CONFIG = {
  critical: { label: "Critical", color: "bg-red-600 text-white" },
  high: { label: "High", color: "bg-amber-500 text-white" },
  medium: { label: "Medium", color: "bg-blue-500 text-white" },
  low: { label: "Low", color: "bg-emerald-500 text-white" }
};

// Kanban column configuration
const KANBAN_COLUMNS = [
  { id: "open", title: "Open", statuses: ["open"] },
  { id: "in_progress", title: "In Progress", statuses: ["in_progress"] },
  { id: "evidence", title: "Evidence", statuses: ["pending_evidence"] },
  { id: "ai_review", title: "AI Review", statuses: ["ai_review"] },
  { id: "review", title: "Manual Review", statuses: ["manual_review"] },
  { id: "done", title: "Done", statuses: ["completed", "rejected", "closed"] }
];

// Task Card Component
const TaskCard = ({ task, onClick }) => {
  const statusConfig = STATUS_CONFIG[task.status] || STATUS_CONFIG.open;
  const priorityConfig = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
  const isOverdue = task.due_date && isPast(new Date(task.due_date)) && !["completed", "closed"].includes(task.status);
  const isDueToday = task.due_date && isToday(new Date(task.due_date));
  
  return (
    <div 
      className={`shiny-card cursor-pointer mb-3 rounded-lg border transition-all hover:shadow-md ${isOverdue ? 'border-l-4 border-l-red-500' : isDueToday ? 'border-l-4 border-l-amber-500' : ''}`}
      onClick={() => onClick(task)}
      data-testid={`task-card-${task._id || task.id}`}
    >
      <div className="p-3">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h4 className="font-medium text-sm line-clamp-2">{task.title}</h4>
          <Badge className={`${priorityConfig.color} text-xs shrink-0`}>
            {priorityConfig.label}
          </Badge>
        </div>
        
        {task.description && (
          <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{task.description}</p>
        )}
        
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          {task.department_name && (
            <span className="flex items-center gap-1 text-teal-600 font-medium">
              <Target className="h-3 w-3" />
              {task.department_name}
            </span>
          )}
          
          {task.assigned_to_name && (
            <span className="flex items-center gap-1">
              <User className="h-3 w-3" />
              {task.assigned_to_name}
            </span>
          )}
          
          {task.due_date && (
            <span className={`flex items-center gap-1 ${isOverdue ? 'text-red-600' : isDueToday ? 'text-amber-600' : ''}`}>
              <Calendar className="h-3 w-3" />
              {format(new Date(task.due_date), "MMM d")}
            </span>
          )}
          
          {task.is_timer_running && (
            <span className="flex items-center gap-1 text-emerald-600 font-medium">
              <Timer className="h-3 w-3 animate-pulse" />
              Active
            </span>
          )}
          
          {task.time_spent_minutes > 0 && (
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {Math.round(task.time_spent_minutes / 60)}h
            </span>
          )}
        </div>
        
        {task.ai_review_result && (
          <div className="mt-2 pt-2 border-t">
            <span className={`text-xs flex items-center gap-1 ${task.ai_review_result.is_compliant ? 'text-emerald-600' : 'text-amber-600'}`}>
              <Bot className="h-3 w-3" />
              AI: {task.ai_review_result.is_compliant ? 'Compliant' : 'Needs Review'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

// Kanban Column Component
const KanbanColumn = ({ column, tasks, onTaskClick }) => {
  const columnTasks = tasks.filter(t => column.statuses.includes(t.status));
  
  return (
    <div className="kanban-column" data-testid={`kanban-column-${column.id}`}>
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-200">
        <h3 className="font-semibold text-sm text-gray-700">{column.title}</h3>
        <Badge variant="secondary" className="text-xs bg-white">{columnTasks.length}</Badge>
      </div>
      <ScrollArea className="h-[400px]">
        <div className="pr-1 space-y-2">
          {columnTasks.map(task => (
            <TaskCard key={task._id || task.id} task={task} onClick={onTaskClick} />
          ))}
          {columnTasks.length === 0 && (
            <div className="text-center py-8 text-muted-foreground text-sm">
              No tasks
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

// Stats Cards Component
const StatsCards = ({ stats }) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
      <div className="stats-card">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">Total Tasks</p>
            <p className="text-2xl font-bold text-gray-900">{stats.total || 0}</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <Target className="h-5 w-5 text-emerald-600" />
          </div>
        </div>
      </div>
      
      <div className="stats-card border-l-4 border-l-red-500">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">Overdue</p>
            <p className="text-2xl font-bold text-red-600">{stats.overdue || 0}</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
            <AlertCircle className="h-5 w-5 text-red-600" />
          </div>
        </div>
      </div>
      
      <div className="stats-card border-l-4 border-l-amber-500">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">Due Today</p>
            <p className="text-2xl font-bold text-amber-600">{stats.due_today || 0}</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
            <Calendar className="h-5 w-5 text-amber-600" />
          </div>
        </div>
      </div>
      
      <div className="stats-card">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">Due This Week</p>
            <p className="text-2xl font-bold text-gray-900">{stats.due_this_week || 0}</p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
            <Clock className="h-5 w-5 text-blue-600" />
          </div>
        </div>
      </div>
      
      <div className="stats-card border-l-4 border-l-emerald-500">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">Completion Rate</p>
            <p className="text-2xl font-bold text-emerald-600">
              {stats.completion_rate ? `${Math.round(stats.completion_rate)}%` : '0%'}
            </p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center">
            <TrendingUp className="h-5 w-5 text-emerald-600" />
          </div>
        </div>
      </div>
      
      <div className="stats-card">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">Avg Time</p>
            <p className="text-2xl font-bold text-gray-900">
              {stats.avg_time_to_complete ? `${Math.round(stats.avg_time_to_complete / 60)}h` : '-'}
            </p>
          </div>
          <div className="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
            <Timer className="h-5 w-5 text-indigo-600" />
          </div>
        </div>
      </div>
    </div>
  );
};

// Task Detail Modal Component
const TaskDetailModal = ({ task, open, onClose, onUpdate, members }) => {
  const [activeTab, setActiveTab] = useState("details");
  const [comment, setComment] = useState("");
  const [comments, setComments] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [linkedClauses, setLinkedClauses] = useState([]);
  const [linkedEvidence, setLinkedEvidence] = useState([]);
  const [dependencies, setDependencies] = useState({ blocks: [], blocked_by: [], related: [] });
  const [dependencyGraph, setDependencyGraph] = useState({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [evidenceDescription, setEvidenceDescription] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [taskNotFound, setTaskNotFound] = useState(false); // Feature #194: Track deleted/not-found tasks
  const { user} = useAuth();
  const navigate = useNavigate();

  // Feature #193: Prevent stale task detail responses
  const detailRequestIdRef = useRef(0);

  useEffect(() => {
    if (task && open) {
      setTaskNotFound(false); // Reset not-found state when opening new task
      loadTaskDetails();
      setEditTitle(task.title || "");
      setEditDescription(task.description || "");
      setIsEditing(false);
    }
  }, [task, open]);

  const loadTaskDetails = async () => {
    if (!task) return;
    const requestId = ++detailRequestIdRef.current;
    setLoading(true);
    setTaskNotFound(false);
    try {
      // Fetch enriched task details from the detail endpoint
      const detailRes = await tasksApi.getById(task._id || task.id);

      // Feature #193: Only update state if this is still the latest request
      if (requestId !== detailRequestIdRef.current) return;

      // The detail endpoint returns { task, evidence, comments, source_info, linked_clauses, timeline }
      if (detailRes) {
        setComments(detailRes.comments || []);
        setTimeline(detailRes.timeline || []);
        setLinkedClauses(detailRes.linked_clauses || []);
        setLinkedEvidence(detailRes.evidence || []);
      }

      // Load task dependencies
      try {
        const depsRes = await tasksApi.getDependencies(task._id || task.id);
        if (requestId !== detailRequestIdRef.current) return;
        if (depsRes) {
          setDependencies(depsRes);
        }
      } catch (error) {
        console.error("Error loading dependencies:", error);
      }

      // Also try the regular timeline/comments endpoints as fallback
      if (!detailRes || (!detailRes.comments?.length && !detailRes.timeline?.length)) {
        const [commentsRes, timelineRes] = await Promise.all([
          tasksApi.getComments(task._id || task.id).catch(() => []),
          tasksApi.getTimeline(task._id || task.id).catch(() => [])
        ]);
        if (requestId !== detailRequestIdRef.current) return;
        if (!detailRes?.comments?.length) setComments(commentsRes || []);
        if (!detailRes?.timeline?.length) setTimeline(timelineRes || []);
      }
    } catch (error) {
      if (requestId !== detailRequestIdRef.current) return;
      // Feature #194: Detect deleted/not-found task
      if (error.response?.status === 404) {
        setTaskNotFound(true);
        return;
      }
      console.error("Error loading task details:", error);
      // Fallback to individual endpoints
      try {
        const [commentsRes, timelineRes] = await Promise.all([
          tasksApi.getComments(task._id || task.id).catch(() => []),
          tasksApi.getTimeline(task._id || task.id).catch(() => [])
        ]);
        if (requestId !== detailRequestIdRef.current) return;
        setComments(commentsRes || []);
        setTimeline(timelineRes || []);
      } catch (e) {
        console.error("Fallback also failed:", e);
      }
    } finally {
      if (requestId === detailRequestIdRef.current) {
        setLoading(false);
      }
    }
  };

  const handleNavigateToClause = (clause) => {
    onClose();
    if (clause.source_type === "policy" && clause.source_id) {
      navigate(`/policies/${clause.source_id}`);
    } else if (clause.source_type === "regulation" && clause.source_id) {
      navigate(`/regulations/${clause.source_id}`);
    }
  };

  const handleNavigateToEvidence = (ev) => {
    onClose();
    navigate(`/evidence`);
  };
  
  const handleStatusChange = async (newStatus) => {
    setSubmitting(true);
    try {
      await tasksApi.updateStatus(task._id || task.id, newStatus);
      toast.success('Task status updated successfully!');
      onUpdate();
    } catch (error) {
      console.error("Error updating status:", error);
      toast.error('Failed to update task status');
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleStartTimer = async () => {
    setSubmitting(true);
    try {
      await tasksApi.startTimer(task._id || task.id);
      toast.success('Timer started');
      onUpdate();
    } catch (error) {
      console.error("Error starting timer:", error);
      toast.error('Failed to start timer');
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleStopTimer = async () => {
    setSubmitting(true);
    try {
      await tasksApi.stopTimer(task._id || task.id);
      toast.success('Timer stopped');
      onUpdate();
    } catch (error) {
      console.error("Error stopping timer:", error);
      toast.error('Failed to stop timer');
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleSubmitForReview = async () => {
    setSubmitting(true);
    try {
      await tasksApi.submitForReview(task._id || task.id, "Submitting for compliance review");
      toast.success('Task submitted for review');
      onUpdate();
    } catch (error) {
      console.error("Error submitting for review:", error);
      toast.error('Failed to submit for review');
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleApprove = async () => {
    setSubmitting(true);
    try {
      await tasksApi.approve(task._id || task.id, true, "Approved - compliance verified");
      toast.success('Task approved successfully!');
      onUpdate();
    } catch (error) {
      console.error("Error approving task:", error);
      toast.error('Failed to approve task');
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleReject = async () => {
    if (!rejectionReason.trim()) {
      toast.error("Please provide a rejection reason");
      return;
    }
    setSubmitting(true);
    try {
      await tasksApi.approve(task._id || task.id, false, rejectionReason);
      toast.success('Task rejected');
      setRejectionReason("");
      onUpdate();
    } catch (error) {
      console.error("Error rejecting task:", error);
      toast.error('Failed to reject task');
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleAddComment = async () => {
    if (!comment.trim()) return;
    setSubmitting(true);
    try {
      await tasksApi.addComment(task._id || task.id, comment);
      toast.success('Comment added');
      setComment("");
      loadTaskDetails();
    } catch (error) {
      console.error("Error adding comment:", error);
      toast.error('Failed to add comment');
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleEvidenceUpload = async () => {
    if (!selectedFile) return;
    setSubmitting(true);
    try {
      // First upload the evidence file
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("description", evidenceDescription);
      formData.append("task_id", task._id || task.id);

      const evidenceRes = await evidenceApi.upload(formData);

      // Then link it to the task
      if (evidenceRes && evidenceRes.id) {
        await tasksApi.addEvidence(task._id || task.id, evidenceRes.id);
      }

      toast.success('Evidence uploaded successfully!');
      setSelectedFile(null);
      setEvidenceDescription("");
      onUpdate();
    } catch (error) {
      console.error("Error uploading evidence:", error);
      toast.error('Failed to upload evidence');
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleAssign = async (memberId) => {
    setSubmitting(true);
    try {
      await tasksApi.assign(task._id || task.id, memberId);
      toast.success('Task assigned successfully!');
      onUpdate();
    } catch (error) {
      console.error("Error assigning task:", error);
      toast.error('Failed to assign task');
    } finally {
      setSubmitting(false);
    }
  };
  
  const handleSaveEdit = async () => {
    setSubmitting(true);
    try {
      const updateData = {
        title: editTitle,
        description: editDescription,
        priority: task.priority,
        assigned_to: task.assigned_to,
        assigned_member_id: task.assigned_member_id,
        department: task.department,
        department_id: task.department_id,
        due_date: task.due_date,
        estimated_hours: task.estimated_hours,
        reminder_days: task.reminder_days || [1, 0],
        tags: task.tags || [],
        is_recurring: task.is_recurring || false,
        recurrence_type: task.recurrence_type || null,
        recurrence_config: task.recurrence_config || null,
        gap_id: task.gap_id || null,
        policy_id: task.policy_id || null,
        regulation_id: task.regulation_id || null,
        circular_id: task.circular_id || null,
        clause_id: task.clause_id || null
      };

      await tasksApi.update(task._id || task.id, updateData);
      toast.success('Task updated successfully');
      setIsEditing(false);
      onUpdate();
    } catch (error) {
      console.error("Error updating task:", error);
      toast.error(error.response?.data?.detail || 'Failed to update task');
    } finally {
      setSubmitting(false);
    }
  };

  if (!task) return null;

  const statusConfig = STATUS_CONFIG[task.status] || STATUS_CONFIG.open;
  const priorityConfig = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
  const StatusIcon = statusConfig.icon;
  
  // Determine available actions based on current status
  const canStart = task.status === "open";
  const canSubmitEvidence = task.status === "in_progress";
  const canSubmitForReview = task.status === "pending_evidence" && (task.evidence_ids?.length > 0);
  const canApprove = task.status === "manual_review";
  
  // Feature #194: Handle delete task
  const handleDeleteTask = async () => {
    if (!task) return;
    const confirmed = window.confirm('Are you sure you want to delete this task? This action cannot be undone.');
    if (!confirmed) return;
    try {
      await tasksApi.delete(task._id || task.id);
      toast.success('Task deleted successfully');
      onClose();
      if (onUpdate) onUpdate();
    } catch (error) {
      console.error('Error deleting task:', error);
      toast.error(error.userMessage || 'Failed to delete task');
    }
  };

  // Feature #194: Show not-found UI for deleted/missing tasks
  if (taskNotFound) {
    return (
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent className="max-w-md" data-testid="task-detail-modal">
          <div className="flex flex-col items-center justify-center py-12 text-center" data-testid="task-not-found">
            <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mb-4">
              <AlertTriangle className="h-8 w-8 text-red-500" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Task Not Found</h3>
            <p className="text-sm text-muted-foreground mb-6">
              This task has been deleted or is no longer available. It may have been removed by another user.
            </p>
            <Button onClick={onClose} data-testid="task-not-found-close">
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col" data-testid="task-detail-modal">
        <DialogHeader>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              {isEditing ? (
                <div className="space-y-2">
                  <Input
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    placeholder="Task title"
                    className="text-lg font-semibold"
                    data-testid="edit-task-title-input"
                  />
                  <Textarea
                    value={editDescription}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val.length <= 10000) {
                        setEditDescription(val);
                      }
                    }}
                    placeholder="Task description"
                    rows={4}
                    maxLength={10000}
                    data-testid="edit-task-description-input"
                  />
                  <div className="flex justify-end">
                    <span className={`text-xs ${editDescription.length > 9000 ? 'text-amber-500' : 'text-muted-foreground'}`} data-testid="edit-description-char-count">
                      {editDescription.length}/10000
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleSaveEdit} disabled={submitting || !editTitle.trim()} data-testid="save-edit-button">
                      Save
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => {
                      setIsEditing(false);
                      setEditTitle(task.title);
                      setEditDescription(task.description);
                    }} disabled={submitting} data-testid="cancel-edit-button">
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <DialogTitle className="text-xl">{task.title}</DialogTitle>
                  <DialogDescription className="mt-1">
                    <div className="flex flex-wrap gap-2 mt-2">
                      <Badge className={`${statusConfig.color} border`}>
                        <StatusIcon className="h-3 w-3 mr-1" />
                        {statusConfig.label}
                      </Badge>
                      <Badge className={priorityConfig.color}>
                        {priorityConfig.label} Priority
                      </Badge>
                      {task.is_timer_running && (
                        <Badge variant="outline" className="text-green-600 border-green-600">
                          <Timer className="h-3 w-3 mr-1 animate-pulse" />
                          Timer Running
                        </Badge>
                      )}
                    </div>
                  </DialogDescription>
                </>
              )}
            </div>
            {!isEditing && (
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setIsEditing(true)} data-testid="edit-task-button">
                  Edit
                </Button>
                <Button size="sm" variant="outline" className="text-red-500 hover:text-red-700 hover:bg-red-50" onClick={handleDeleteTask} data-testid="delete-task-button">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        </DialogHeader>

        {/* --- SUMMARY CARD --- */}
        <Card className="mb-4">
          <CardContent className="p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2">
              <div><span className="font-semibold">Department:</span> {task.department_name || '—'}</div>
              <div><span className="font-semibold">Assignee:</span> {task.assigned_to_name || 'Unassigned'}</div>
              <div><span className="font-semibold">Due Date:</span> {task.due_date ? format(new Date(task.due_date), "MMM d, yyyy") : 'Not set'}</div>
              <div><span className="font-semibold">Status:</span> {statusConfig.label}</div>
              <div><span className="font-semibold">Priority:</span> {priorityConfig.label}</div>
              <div><span className="font-semibold">Time Spent:</span> {task.time_spent_minutes ? `${Math.round(task.time_spent_minutes / 60)}h ${task.time_spent_minutes % 60}m` : '0m'}</div>
              <div><span className="font-semibold">Estimated Time:</span> {task.estimated_hours ? `${task.estimated_hours}h` : 'Not set'}</div>
              <div><span className="font-semibold">Created:</span> {task.created_at ? formatDistanceToNow(new Date(task.created_at), { addSuffix: true }) : '—'}</div>
            </div>
          </CardContent>
        </Card>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 overflow-hidden flex flex-col">
          <TabsList className="w-full justify-start">
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="clauses">
              <Link2 className="h-3 w-3 mr-1" />
              Clauses ({linkedClauses.length})
            </TabsTrigger>
            <TabsTrigger value="evidence">
              <FileText className="h-3 w-3 mr-1" />
              Evidence ({linkedEvidence.length || task?.evidence_ids?.length || 0})
            </TabsTrigger>
            <TabsTrigger value="timeline">
              <History className="h-3 w-3 mr-1" />
              Timeline
            </TabsTrigger>
            <TabsTrigger value="comments">Comments ({comments.length})</TabsTrigger>
            <TabsTrigger value="dependencies">
              Dependencies ({(dependencies.blocks?.length || 0) + (dependencies.blocked_by?.length || 0) + (dependencies.related?.length || 0)})
            </TabsTrigger>
          </TabsList>
          
          <ScrollArea className="flex-1 mt-4">
            <TabsContent value="details" className="mt-0 space-y-4">
              {/* Task Description */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Description</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm whitespace-pre-wrap break-words overflow-hidden" data-testid="task-detail-description">{task.description || "No description provided"}</p>
                </CardContent>
              </Card>
              
              {/* Task Metadata */}
              <div className="grid grid-cols-2 gap-4">
                <Card>
                  <CardContent className="p-4 space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Assigned To</span>
                      <Select 
                        value={task.assigned_to || ""} 
                        onValueChange={handleAssign}
                        disabled={submitting}
                      >
                        <SelectTrigger className="w-40">
                          <SelectValue placeholder="Unassigned" />
                        </SelectTrigger>
                        <SelectContent>
                          {(members || []).map(m => (
                            <SelectItem key={m._id || m.id} value={m._id || m.id}>
                              {m.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Due Date</span>
                      <span className="text-sm font-medium">
                        {task.due_date ? format(new Date(task.due_date), "MMM d, yyyy") : "Not set"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Department</span>
                      <span className="text-sm font-medium">{task.department_name || "—"}</span>
                    </div>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardContent className="p-4 space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Time Spent</span>
                      <span className="text-sm font-medium">
                        {task.time_spent_minutes ? `${Math.round(task.time_spent_minutes / 60)}h ${task.time_spent_minutes % 60}m` : "0m"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Estimated Time</span>
                      <span className="text-sm font-medium">
                        {task.estimated_hours ? `${task.estimated_hours}h` : "Not set"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Created</span>
                      <span className="text-sm font-medium">
                        {task.created_at ? formatDistanceToNow(new Date(task.created_at), { addSuffix: true }) : "—"}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </div>
              
              {/* AI Review Result */}
              {task.ai_review_result && (
                <Card className={task.ai_review_result.is_compliant ? "border-green-200" : "border-amber-200"}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Bot className="h-4 w-4" />
                      AI Review Result
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        {task.ai_review_result.is_compliant ? (
                          <CheckCircle className="h-5 w-5 text-emerald-600" />
                        ) : (
                          <AlertTriangle className="h-5 w-5 text-amber-600" />
                        )}
                        <span className={`font-medium ${task.ai_review_result.is_compliant ? "text-emerald-600" : "text-amber-600"}`}>
                          {task.ai_review_result.is_compliant ? "Evidence appears compliant" : "Review recommended"}
                        </span>
                      </div>
                      {task.ai_review_result.summary && (
                        <p className="text-sm text-muted-foreground">{task.ai_review_result.summary}</p>
                      )}
                      {task.ai_review_result.confidence_score && (
                        <p className="text-xs text-muted-foreground">
                          Confidence: {Math.round(task.ai_review_result.confidence_score * 100)}%
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* Compliance Indicators */}
              {(task.compliance_indicators?.length > 0 || task.unfulfilled_indicators?.length > 0) && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Compliance Indicators</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {task.compliance_indicators?.length > 0 && (
                        <div>
                          <h5 className="text-xs font-medium text-emerald-600 mb-1">Fulfilled</h5>
                          <div className="flex flex-wrap gap-1">
                            {task.compliance_indicators.map((ind, i) => (
                              <Badge key={i} variant="outline" className="text-xs text-emerald-600 border-emerald-300">
                                <CheckCircle className="h-3 w-3 mr-1" />
                                {ind}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                      {task.unfulfilled_indicators?.length > 0 && (
                        <div>
                          <h5 className="text-xs font-medium text-amber-600 mb-1">Pending</h5>
                          <div className="flex flex-wrap gap-1">
                            {task.unfulfilled_indicators.map((ind, i) => (
                              <Badge key={i} variant="outline" className="text-xs text-amber-600 border-amber-300">
                                <AlertTriangle className="h-3 w-3 mr-1" />
                                {ind}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* Action Buttons */}
              <Card>
                <CardContent className="p-4">
                  <div className="flex flex-wrap gap-2">
                    {/* Timer Controls */}
                    {!task.is_timer_running && ["in_progress", "pending_evidence"].includes(task.status) && (
                      <Button size="sm" variant="outline" onClick={handleStartTimer} disabled={submitting} data-testid="start-timer-button">
                        <Play className="h-4 w-4 mr-1" />
                        Start Timer
                      </Button>
                    )}
                    {task.is_timer_running && (
                      <Button size="sm" variant="outline" onClick={handleStopTimer} disabled={submitting} data-testid="stop-timer-button">
                        <Pause className="h-4 w-4 mr-1" />
                        Stop Timer
                      </Button>
                    )}
                    
                    {/* Status Transitions */}
                    {canStart && (
                      <Button size="sm" onClick={() => handleStatusChange("in_progress")} disabled={submitting} data-testid="start-task-button">
                        <Play className="h-4 w-4 mr-1" />
                        Start Working
                      </Button>
                    )}
                    
                    {canSubmitEvidence && (
                      <Button size="sm" onClick={() => handleStatusChange("pending_evidence")} disabled={submitting}>
                        <Upload className="h-4 w-4 mr-1" />
                        Add Evidence
                      </Button>
                    )}
                    
                    {canSubmitForReview && (
                      <Button size="sm" onClick={handleSubmitForReview} disabled={submitting}>
                        <Bot className="h-4 w-4 mr-1" />
                        Submit for AI Review
                      </Button>
                    )}
                    
                    {canApprove && (
                      <>
                        <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={handleApprove} disabled={submitting}>
                          <CheckCircle className="h-4 w-4 mr-1" />
                          Approve
                        </Button>
                        <div className="flex items-center gap-2">
                          <Input 
                            placeholder="Rejection reason..."
                            value={rejectionReason}
                            onChange={(e) => setRejectionReason(e.target.value)}
                            className="w-48"
                          />
                          <Button size="sm" variant="destructive" onClick={handleReject} disabled={submitting || !rejectionReason.trim()}>
                            <XCircle className="h-4 w-4 mr-1" />
                            Reject
                          </Button>
                        </div>
                      </>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* Linked Clauses Tab */}
            <TabsContent value="clauses" className="mt-0 space-y-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Link2 className="h-4 w-4 text-teal-600" />
                    Linked Clauses
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Regulation and policy clauses linked to this task
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-center py-8 text-muted-foreground">Loading...</div>
                  ) : linkedClauses.length > 0 ? (
                    <div className="space-y-3">
                      {linkedClauses.map((clause, i) => (
                        <div
                          key={clause.clause_id || i}
                          className="p-3 border rounded-lg hover:border-teal-400 transition-all cursor-pointer group"
                          onClick={() => handleNavigateToClause(clause)}
                        >
                          <div className="flex items-start justify-between gap-2 mb-2">
                            <div className="flex items-center gap-2">
                              {clause.source_type === "regulation" ? (
                                <Scale className="h-4 w-4 text-purple-600 shrink-0" />
                              ) : (
                                <BookOpen className="h-4 w-4 text-blue-600 shrink-0" />
                              )}
                              <Badge variant="outline" className={
                                clause.source_type === "regulation"
                                  ? "text-purple-600 border-purple-300 text-xs"
                                  : "text-blue-600 border-blue-300 text-xs"
                              }>
                                {clause.source_type === "regulation" ? "Regulation" : "Policy"}
                              </Badge>
                              {clause.section && (
                                <span className="text-xs text-muted-foreground">§ {clause.section}</span>
                              )}
                            </div>
                            <ExternalLink className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                          </div>
                          <p className="text-sm line-clamp-3 mb-2">{clause.text || "No clause text available"}</p>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs text-muted-foreground">
                              From: {clause.source_title}
                            </span>
                            {clause.gap_status && (
                              <Badge variant="outline" className={
                                clause.gap_status === "compliant" || clause.gap_status === "Compliant"
                                  ? "text-emerald-600 border-emerald-300 text-xs"
                                  : "text-amber-600 border-amber-300 text-xs"
                              }>
                                {clause.gap_status}
                              </Badge>
                            )}
                            {clause.similarity_score != null && (
                              <Badge variant="outline" className="text-xs text-muted-foreground">
                                Match: {Math.round(clause.similarity_score * 100)}%
                              </Badge>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <Link2 className="h-8 w-8 text-muted-foreground mx-auto mb-2 opacity-50" />
                      <p className="text-sm text-muted-foreground">
                        No linked clauses found
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Clauses are automatically linked when tasks are created from gap analysis
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="evidence" className="mt-0 space-y-4">
              {/* Upload Evidence */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Upload Evidence</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Input
                    type="file"
                    onChange={(e) => setSelectedFile(e.target.files[0])}
                  />
                  <Textarea
                    placeholder="Description of this evidence..."
                    value={evidenceDescription}
                    onChange={(e) => setEvidenceDescription(e.target.value)}
                  />
                  <Button
                    onClick={handleEvidenceUpload}
                    disabled={!selectedFile || submitting}
                  >
                    <Upload className="h-4 w-4 mr-2" />
                    Upload Evidence
                  </Button>
                </CardContent>
              </Card>

              {/* Evidence List - Enhanced with details */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Shield className="h-4 w-4 text-emerald-600" />
                    Linked Evidence ({linkedEvidence.length || task?.evidence_ids?.length || 0})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {linkedEvidence.length > 0 ? (
                    <div className="space-y-3">
                      {linkedEvidence.map((ev, i) => (
                        <div
                          key={ev.id || i}
                          className="p-3 border rounded-lg hover:border-emerald-400 transition-all cursor-pointer group"
                          onClick={() => handleNavigateToEvidence(ev)}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <FileText className="h-4 w-4 text-emerald-600" />
                                <span className="text-sm font-medium">
                                  {ev.title || ev.filename || `Evidence #${i + 1}`}
                                </span>
                                <ExternalLink className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                              </div>
                              {ev.description && (
                                <p className="text-xs text-muted-foreground line-clamp-2 ml-6">{ev.description}</p>
                              )}
                              <div className="flex items-center gap-3 mt-2 ml-6">
                                {ev.validation_status && (
                                  <Badge variant="outline" className={
                                    ev.validation_status === "Approved"
                                      ? "text-emerald-600 border-emerald-300 text-xs"
                                      : ev.validation_status === "Rejected"
                                        ? "text-red-600 border-red-300 text-xs"
                                        : "text-amber-600 border-amber-300 text-xs"
                                  }>
                                    {ev.validation_status}
                                  </Badge>
                                )}
                                {ev.file_type && (
                                  <span className="text-xs text-muted-foreground uppercase">{ev.file_type}</span>
                                )}
                                {ev.created_at && (
                                  <span className="text-xs text-muted-foreground">
                                    {formatDistanceToNow(new Date(ev.created_at), { addSuffix: true })}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : task?.evidence_ids?.length > 0 ? (
                    <div className="space-y-2">
                      {task.evidence_ids.map((evId, i) => (
                        <div key={evId} className="flex items-center gap-2 p-2 bg-muted rounded cursor-pointer hover:bg-muted/80" onClick={() => navigate('/evidence')}>
                          <FileText className="h-4 w-4" />
                          <span className="text-sm">Evidence #{i + 1}</span>
                          <ExternalLink className="h-3 w-3 ml-auto text-muted-foreground" />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <Upload className="h-8 w-8 text-muted-foreground mx-auto mb-2 opacity-50" />
                      <p className="text-sm text-muted-foreground">
                        No evidence attached yet
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Upload evidence above to link it to this task
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            <TabsContent value="timeline" className="mt-0">
              <Card>
                <CardContent className="p-4">
                  {loading ? (
                    <div className="text-center py-8 text-muted-foreground">Loading...</div>
                  ) : timeline.length > 0 ? (
                    <div className="space-y-4">
                      {timeline.map((activity, i) => (
                        <div key={i} className="flex gap-3">
                          <div className="flex flex-col items-center">
                            <div className="w-2 h-2 rounded-full bg-primary mt-2" />
                            {i < timeline.length - 1 && <div className="w-0.5 flex-1 bg-muted" />}
                          </div>
                          <div className="flex-1 pb-4">
                            <p className="text-sm">{activity.description}</p>
                            <p className="text-xs text-muted-foreground">
                              {activity.performed_by_name && `${activity.performed_by_name} • `}
                              {activity.performed_at ? formatDistanceToNow(new Date(activity.performed_at), { addSuffix: true }) : ""}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No activity yet
                    </p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            <TabsContent value="comments" className="mt-0 space-y-4">
              {/* Add Comment */}
              <Card>
                <CardContent className="p-4">
                  <div className="flex gap-2">
                    <Textarea 
                      placeholder="Add a comment..."
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      className="flex-1"
                    />
                    <Button onClick={handleAddComment} disabled={!comment.trim() || submitting}>
                      <MessageSquare className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
              
              {/* Comments List */}
              <Card>
                <CardContent className="p-4">
                  {loading ? (
                    <div className="text-center py-8 text-muted-foreground">Loading...</div>
                  ) : comments.length > 0 ? (
                    <div className="space-y-4">
                      {comments.map((c, i) => (
                        <div key={i} className="border-b last:border-0 pb-3 last:pb-0">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium">{c.author_name || "Unknown"}</span>
                            <span className="text-xs text-muted-foreground">
                              {c.created_at ? formatDistanceToNow(new Date(c.created_at), { addSuffix: true }) : ""}
                            </span>
                          </div>
                          <p className="text-sm">{c.content}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No comments yet
                    </p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Dependencies Tab */}
            <TabsContent value="dependencies" className="mt-0 space-y-4">
              {/* Blocked By */}
              {dependencies.blocked_by && dependencies.blocked_by.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-red-600">🚫 Blocked By ({dependencies.blocked_by.length})</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {dependencies.blocked_by.map((dep) => (
                      <div key={dep.dependency_id} className="flex items-center justify-between p-2 bg-red-50 rounded border border-red-200">
                        <div className="flex-1">
                          <div className="text-sm font-medium">{dep.task.title}</div>
                          <div className="text-xs text-muted-foreground">
                            Status: <span className={dep.task.status === 'Completed' ? 'text-green-600' : 'text-orange-600'}>{dep.task.status}</span>
                            {' • '}Priority: {dep.task.priority}
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={async () => {
                            try {
                              await tasksApi.removeDependency(task._id || task.id, dep.dependency_id);
                              toast.success('Dependency removed');
                              loadTaskDetails();
                            } catch (error) {
                              toast.error('Failed to remove dependency');
                            }
                          }}
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {/* Blocks */}
              {dependencies.blocks && dependencies.blocks.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-orange-600">⏸️ Blocks ({dependencies.blocks.length})</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {dependencies.blocks.map((dep) => (
                      <div key={dep.dependency_id} className="flex items-center justify-between p-2 bg-orange-50 rounded border border-orange-200">
                        <div className="flex-1">
                          <div className="text-sm font-medium">{dep.task.title}</div>
                          <div className="text-xs text-muted-foreground">
                            Status: {dep.task.status} • Priority: {dep.task.priority}
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={async () => {
                            try {
                              await tasksApi.removeDependency(task._id || task.id, dep.dependency_id);
                              toast.success('Dependency removed');
                              loadTaskDetails();
                            } catch (error) {
                              toast.error('Failed to remove dependency');
                            }
                          }}
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {/* Related Tasks */}
              {dependencies.related && dependencies.related.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm text-blue-600">🔗 Related Tasks ({dependencies.related.length})</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {dependencies.related.map((dep) => (
                      <div key={dep.dependency_id} className="flex items-center justify-between p-2 bg-blue-50 rounded border border-blue-200">
                        <div className="flex-1">
                          <div className="text-sm font-medium">{dep.task.title}</div>
                          <div className="text-xs text-muted-foreground">
                            Status: {dep.task.status} • Priority: {dep.task.priority}
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={async () => {
                            try {
                              await tasksApi.removeDependency(task._id || task.id, dep.dependency_id);
                              toast.success('Dependency removed');
                              loadTaskDetails();
                            } catch (error) {
                              toast.error('Failed to remove dependency');
                            }
                          }}
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {/* No Dependencies */}
              {(!dependencies.blocked_by || dependencies.blocked_by.length === 0) &&
               (!dependencies.blocks || dependencies.blocks.length === 0) &&
               (!dependencies.related || dependencies.related.length === 0) && (
                <Card>
                  <CardContent className="p-8 text-center text-muted-foreground">
                    <div className="text-sm">No dependencies configured</div>
                    <div className="text-xs mt-1">Add blocking, related, or parent/child relationships</div>
                  </CardContent>
                </Card>
              )}

              {/* Add Dependency Section */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">➕ Add Dependency</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-xs text-muted-foreground mb-2">
                    Configure task dependencies to manage workflow and track relationships
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      toast.info('Dependency creation dialog would open here - Feature #50 implementation in progress');
                    }}
                  >
                    Add Dependency
                  </Button>
                </CardContent>
              </Card>
            </TabsContent>
          </ScrollArea>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
};

// Create Task Dialog
const CreateTaskDialog = ({ open, onClose, onCreate, departments, members }) => {
  const defaultFormData = {
    title: "",
    description: "",
    priority: "medium",
    department_id: "",
    assigned_to: "",
    due_date: "",
    estimated_hours: ""
  };

  const [formData, setFormData] = useState(defaultFormData);
  const [submitting, setSubmitting] = useState(false);
  const [showUnsavedWarning, setShowUnsavedWarning] = useState(false);
  const [pendingClose, setPendingClose] = useState(false);

  // Track if form has unsaved changes
  const { isDirty, markClean } = useFormDirtyTracking(defaultFormData, formData);

  const handleReset = () => {
    setFormData(defaultFormData);
    setDateWarning('');
    toast.success('Form reset to defaults');
  };

  const handleClose = () => {
    // If form has unsaved changes, show warning dialog
    if (isDirty && !submitting) {
      setShowUnsavedWarning(true);
      setPendingClose(true);
    } else {
      // No unsaved changes, close immediately
      setFormData(defaultFormData);
      onClose();
    }
  };

  const handleConfirmClose = () => {
    // User confirmed they want to discard changes
    setShowUnsavedWarning(false);
    setPendingClose(false);
    setFormData(defaultFormData);
    onClose();
  };

  const handleCancelClose = () => {
    // User wants to stay and continue editing
    setShowUnsavedWarning(false);
    setPendingClose(false);
  };

  const [dateWarning, setDateWarning] = useState('');

  // Date validation: warn if due date is in the past
  const validateDueDate = (dateStr) => {
    if (!dateStr) {
      setDateWarning('');
      return true;
    }
    const selectedDate = new Date(dateStr + 'T23:59:59');
    const now = new Date();
    if (selectedDate < now) {
      setDateWarning('Warning: Due date is in the past. Task will be immediately overdue.');
      return true; // Allow but warn
    }
    setDateWarning('');
    return true;
  };

  const handleDueDateChange = (e) => {
    const val = e.target.value;
    validateDueDate(val);
    setFormData(prev => ({ ...prev, due_date: val }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.title.trim()) return;

    setSubmitting(true);
    try {
      await tasksApi.create({
        ...formData,
        priority: formData.priority.charAt(0).toUpperCase() + formData.priority.slice(1),
        estimated_hours: formData.estimated_hours ? parseFloat(formData.estimated_hours) : null,
        due_date: formData.due_date || null
      });
      toast.success('Task created successfully!');
      markClean(); // Mark form as clean after successful submission
      setFormData(defaultFormData);
      setDateWarning('');
      onCreate();
      onClose();
    } catch (error) {
      console.error("Error creating task:", error);
      toast.error('Failed to create task: ' + (error.response?.data?.detail || 'Unknown error'));
    } finally {
      setSubmitting(false);
    }
  };
  
  return (
    <>
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent data-testid="create-task-dialog">
        <DialogHeader>
          <DialogTitle>Create New Task</DialogTitle>
          <DialogDescription>Add a new compliance task to track</DialogDescription>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4" data-testid="create-task-form">
          <div>
            <label className="text-sm font-medium">Title *</label>
            <Input 
              value={formData.title}
              onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
              placeholder="Task title"
              required
              data-testid="task-title-input"
            />
          </div>
          
          <div>
            <label className="text-sm font-medium">Description</label>
            <Textarea
              value={formData.description}
              onChange={(e) => {
                const val = e.target.value;
                if (val.length <= 10000) {
                  setFormData(prev => ({ ...prev, description: val }));
                }
              }}
              placeholder="Task description"
              maxLength={10000}
              rows={4}
              data-testid="task-description-input"
            />
            <div className="flex justify-end mt-1">
              <span className={`text-xs ${formData.description.length > 9000 ? 'text-amber-500' : formData.description.length > 9500 ? 'text-red-500' : 'text-muted-foreground'}`} data-testid="description-char-count">
                {formData.description.length}/10000
              </span>
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium">Priority</label>
              <Select 
                value={formData.priority}
                onValueChange={(v) => setFormData(prev => ({ ...prev, priority: v }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <label className="text-sm font-medium">Department</label>
              <Select 
                value={formData.department_id}
                onValueChange={(v) => setFormData(prev => ({ ...prev, department_id: v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select department" />
                </SelectTrigger>
                <SelectContent>
                  {(departments || []).map(d => (
                    <SelectItem key={d._id || d.id} value={d._id || d.id}>{d.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium">Assign To</label>
              <Select 
                value={formData.assigned_to}
                onValueChange={(v) => setFormData(prev => ({ ...prev, assigned_to: v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select member" />
                </SelectTrigger>
                <SelectContent>
                  {(members || []).map(m => (
                    <SelectItem key={m._id || m.id} value={m._id || m.id}>{m.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <label className="text-sm font-medium">Due Date</label>
              <Input
                type="date"
                value={formData.due_date}
                onChange={handleDueDateChange}
                data-testid="task-due-date-input"
              />
              {dateWarning && (
                <p className="text-xs text-amber-500 mt-1 flex items-center gap-1" data-testid="date-past-warning">
                  <AlertTriangle className="w-3 h-3" /> {dateWarning}
                </p>
              )}
            </div>
          </div>
          
          <div>
            <label className="text-sm font-medium">Estimated Hours</label>
            <Input 
              type="number"
              step="0.5"
              value={formData.estimated_hours}
              onChange={(e) => setFormData(prev => ({ ...prev, estimated_hours: e.target.value }))}
              placeholder="e.g., 4"
            />
          </div>
          
          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose} data-testid="cancel-create-task">Cancel</Button>
            <Button type="button" variant="outline" onClick={handleReset} data-testid="reset-task-form">
              Reset
            </Button>
            <Button type="submit" disabled={submitting || !formData.title.trim()} data-testid="submit-create-task">
              {submitting ? "Creating..." : "Create Task"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    {/* Unsaved Changes Warning Dialog */}
    <AlertDialog open={showUnsavedWarning} onOpenChange={setShowUnsavedWarning}>
      <AlertDialogContent data-testid="unsaved-changes-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>Unsaved Changes</AlertDialogTitle>
          <AlertDialogDescription>
            You have unsaved changes. Are you sure you want to leave? Your changes will be lost.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={handleCancelClose} data-testid="stay-on-form">
            Stay
          </AlertDialogCancel>
          <AlertDialogAction onClick={handleConfirmClose} data-testid="leave-form">
            Leave
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  );
};

// Bulk Create Tasks Dialog - Feature #170
const BulkCreateTaskDialog = ({ open, onClose, onCreate, departments, members }) => {
  const [bulkTasks, setBulkTasks] = useState([
    { title: "", description: "", priority: "medium" },
    { title: "", description: "", priority: "medium" },
    { title: "", description: "", priority: "medium" }
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [assignToAll, setAssignToAll] = useState("");

  const addRow = () => {
    setBulkTasks(prev => [...prev, { title: "", description: "", priority: "medium" }]);
  };

  const removeRow = (index) => {
    if (bulkTasks.length <= 1) return;
    setBulkTasks(prev => prev.filter((_, i) => i !== index));
  };

  const updateRow = (index, field, value) => {
    setBulkTasks(prev => prev.map((t, i) => i === index ? { ...t, [field]: value } : t));
  };

  const validTasks = bulkTasks.filter(t => t.title.trim());

  const handleSubmit = async () => {
    if (validTasks.length === 0) return;
    setSubmitting(true);
    try {
      const tasksToCreate = validTasks.map(t => ({
        title: t.title.trim(),
        description: t.description.trim() || t.title.trim(),
        priority: t.priority.charAt(0).toUpperCase() + t.priority.slice(1),
        assigned_member_id: assignToAll || null,
        assigned_to: assignToAll ? (members || []).find(m => (m._id || m.id) === assignToAll)?.name : null,
      }));
      const result = await tasksApi.bulkCreate(tasksToCreate);
      toast.success(`${result.created} tasks created successfully!`);
      setBulkTasks([
        { title: "", description: "", priority: "medium" },
        { title: "", description: "", priority: "medium" },
        { title: "", description: "", priority: "medium" }
      ]);
      setAssignToAll("");
      onCreate();
      onClose();
    } catch (error) {
      console.error("Bulk create error:", error);
      toast.error("Failed to create tasks: " + (error.response?.data?.detail || "Unknown error"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto" data-testid="bulk-create-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Copy className="h-5 w-5" />
            Bulk Create Tasks
          </DialogTitle>
          <DialogDescription>Create multiple tasks at once. Fill in title for each task.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Assign all to one member */}
          <div className="flex items-center gap-4 p-3 bg-muted/50 rounded-lg">
            <label className="text-sm font-medium whitespace-nowrap">Assign all to:</label>
            <Select value={assignToAll} onValueChange={setAssignToAll}>
              <SelectTrigger className="w-[200px]" data-testid="bulk-assign-all-select">
                <SelectValue placeholder="Select member (optional)" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">None</SelectItem>
                {(members || []).map(m => (
                  <SelectItem key={m._id || m.id} value={m._id || m.id}>{m.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Task rows */}
          <div className="space-y-3">
            {bulkTasks.map((task, index) => (
              <div key={index} className="flex items-start gap-3 p-3 border rounded-lg" data-testid={`bulk-task-row-${index}`}>
                <span className="text-sm font-mono text-muted-foreground mt-2 w-6">{index + 1}.</span>
                <div className="flex-1 space-y-2">
                  <Input
                    placeholder="Task title *"
                    value={task.title}
                    onChange={(e) => updateRow(index, "title", e.target.value)}
                    data-testid={`bulk-task-title-${index}`}
                  />
                  <div className="flex gap-2">
                    <Input
                      placeholder="Description (optional)"
                      value={task.description}
                      onChange={(e) => updateRow(index, "description", e.target.value)}
                      className="flex-1"
                      data-testid={`bulk-task-desc-${index}`}
                    />
                    <Select value={task.priority} onValueChange={(v) => updateRow(index, "priority", v)}>
                      <SelectTrigger className="w-[120px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="low">Low</SelectItem>
                        <SelectItem value="medium">Medium</SelectItem>
                        <SelectItem value="high">High</SelectItem>
                        <SelectItem value="critical">Critical</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removeRow(index)}
                  disabled={bulkTasks.length <= 1}
                  data-testid={`bulk-task-remove-${index}`}
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground" />
                </Button>
              </div>
            ))}
          </div>

          <Button variant="outline" size="sm" onClick={addRow} data-testid="bulk-add-row">
            <Plus className="h-4 w-4 mr-1" /> Add Another Task
          </Button>
        </div>

        <DialogFooter>
          <div className="flex items-center justify-between w-full">
            <span className="text-sm text-muted-foreground">
              {validTasks.length} task{validTasks.length !== 1 ? "s" : ""} ready to create
            </span>
            <div className="flex gap-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button
                onClick={handleSubmit}
                disabled={submitting || validTasks.length === 0}
                className="btn-shiny text-white"
                data-testid="bulk-create-submit"
              >
                {submitting ? "Creating..." : `Create ${validTasks.length} Tasks`}
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// Bulk Assign Dialog - Feature #170
const BulkAssignDialog = ({ open, onClose, selectedTaskIds, members, onAssign }) => {
  const [memberId, setMemberId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!memberId) return;
    const member = (members || []).find(m => (m._id || m.id) === memberId);
    if (!member) return;

    setSubmitting(true);
    try {
      const result = await tasksApi.bulkAssign(
        selectedTaskIds,
        memberId,
        member.name,
        member.department_id,
        member.department_name
      );
      toast.success(`${result.updated} tasks assigned to ${member.name}`);
      setMemberId("");
      onAssign();
      onClose();
    } catch (error) {
      console.error("Bulk assign error:", error);
      toast.error("Failed to assign tasks: " + (error.response?.data?.detail || "Unknown error"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent data-testid="bulk-assign-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Bulk Assign Tasks
          </DialogTitle>
          <DialogDescription>
            Assign {selectedTaskIds.length} selected task{selectedTaskIds.length !== 1 ? "s" : ""} to a team member.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium">Assign to *</label>
            <Select value={memberId} onValueChange={setMemberId}>
              <SelectTrigger data-testid="bulk-assign-member-select">
                <SelectValue placeholder="Select team member" />
              </SelectTrigger>
              <SelectContent>
                {(members || []).map(m => (
                  <SelectItem key={m._id || m.id} value={m._id || m.id}>{m.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting || !memberId}
            className="btn-shiny text-white"
            data-testid="bulk-assign-submit"
          >
            {submitting ? "Assigning..." : `Assign ${selectedTaskIds.length} Tasks`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// Main Tasks Page Component
export default function Tasks() {
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState({});
  const [departments, setDepartments] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showBulkCreateDialog, setShowBulkCreateDialog] = useState(false);
  const [showBulkAssignDialog, setShowBulkAssignDialog] = useState(false);
  const [selectedTaskIds, setSelectedTaskIds] = useState([]);
  const [viewMode, setViewMode] = useState("kanban"); // kanban or list
  const [exportFormat, setExportFormat] = useState("excel");
  const [exporting, setExporting] = useState(false);
  const [sortField, setSortField] = useState(""); // Field to sort by
  const [sortOrder, setSortOrder] = useState("asc"); // asc or desc
  const [currentPage, setCurrentPage] = useState(1); // Pagination state
  const pageSize = 10; // Items per page
  const [searchParams, setSearchParams] = useSearchParams();
  const [filters, setFilters] = useState(() => {
    const urlPriority = searchParams.get('priority');
    const urlStatus = searchParams.get('status');
    return {
      department_id: "all",
      priority: urlPriority || "all",
      assigned_to: "all",
      status: urlStatus || "all",
      overdue_only: false,
      search: ""
    };
  });
  
  const { user } = useAuth();

  // Check if user is auditor (read-only access)
  const isAuditor = user?.role === 'auditor';
  const canModify = !isAuditor;

  // Feature #193: Prevent stale API responses from overwriting fresh data
  const loadRequestIdRef = useRef(0);

  const loadData = useCallback(async () => {
    const requestId = ++loadRequestIdRef.current;
    setLoading(true);
    try {
      // Build query params from filters
      const params = {};
      if (filters.department_id && filters.department_id !== "all") params.department_id = filters.department_id;
      if (filters.priority && filters.priority !== "all") params.priority = filters.priority;
      if (filters.assigned_to && filters.assigned_to !== "all") params.assigned_to = filters.assigned_to;
      if (filters.status && filters.status !== "all") params.status = filters.status;
      if (filters.overdue_only) params.overdue_only = true;

      const [tasksRes, statsRes, membersRes] = await Promise.all([
        tasksApi.getAll(params),
        tasksApi.getStats(),
        departmentsApi.getAllMembers()
      ]);

      // Feature #193: Only update state if this is still the latest request
      if (requestId !== loadRequestIdRef.current) return;

      setTasks(tasksRes || []);
      setStats(statsRes || {});
      setMembers(membersRes || []);

      // Extract unique departments from tasks or fetch separately
      const depts = {};
      (tasksRes || []).forEach(t => {
        if (t.department_id && t.department_name) {
          depts[t.department_id] = { _id: t.department_id, name: t.department_name };
        }
      });
      setDepartments(Object.values(depts));

    } catch (error) {
      if (requestId !== loadRequestIdRef.current) return;
      console.error("Error loading tasks:", error);
    } finally {
      if (requestId === loadRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, [filters]);
  
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Reset filters when navigating away from the page
  useEffect(() => {
    return () => {
      // Reset filters on unmount (when navigating away)
      setFilters({
        department_id: "",
        priority: "",
        assigned_to: "",
        status: "",
        overdue_only: false,
        search: ""
      });
    };
  }, []);

  // Filter and sort tasks
  const filteredTasks = useMemo(() => {
    let result = [...tasks];

    // Apply search filter - trim whitespace, ignore whitespace-only input
    const trimmedSearch = (filters.search || '').trim();
    if (trimmedSearch) {
      const search = trimmedSearch.toLowerCase();
      result = result.filter(t =>
        t.title?.toLowerCase().includes(search) ||
        t.description?.toLowerCase().includes(search) ||
        t.assigned_to_name?.toLowerCase().includes(search)
      );
    }

    // Apply sorting
    if (sortField) {
      result.sort((a, b) => {
        let aVal, bVal;

        if (sortField === "due_date") {
          aVal = a.due_date ? new Date(a.due_date).getTime() : 0;
          bVal = b.due_date ? new Date(b.due_date).getTime() : 0;
        } else if (sortField === "priority") {
          const priorityOrder = { critical: 4, high: 3, medium: 2, low: 1 };
          aVal = priorityOrder[a.priority?.toLowerCase()] || 0;
          bVal = priorityOrder[b.priority?.toLowerCase()] || 0;
        } else if (sortField === "title") {
          aVal = a.title?.toLowerCase() || "";
          bVal = b.title?.toLowerCase() || "";
        } else if (sortField === "status") {
          aVal = a.status || "";
          bVal = b.status || "";
        }

        if (sortOrder === "asc") {
          return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
        } else {
          return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
        }
      });
    }

    return result;
  }, [tasks, filters.search, sortField, sortOrder]);

  // Pagination logic
  const totalPages = Math.max(1, Math.ceil(filteredTasks.length / pageSize));
  const paginatedTasks = viewMode === "list"
    ? filteredTasks.slice((currentPage - 1) * pageSize, currentPage * pageSize)
    : filteredTasks; // Kanban shows all tasks

  // Reset to page 1 when filters, search, sort, or view mode change
  useEffect(() => {
    setCurrentPage(1);
  }, [filters.search, filters.department_id, filters.priority, filters.assigned_to, filters.status, filters.overdue_only, sortField, sortOrder, viewMode]);

  // Handle sort by clicking table headers
  const handleSort = (field) => {
    if (sortField === field) {
      // Toggle order if clicking same field
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      // Set new field with ascending order
      setSortField(field);
      setSortOrder("asc");
    }
  };
  
  const handleTaskClick = (task) => {
    setSelectedTask(task);
  };

  const toggleTaskSelection = (taskId) => {
    setSelectedTaskIds(prev =>
      prev.includes(taskId) ? prev.filter(id => id !== taskId) : [...prev, taskId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedTaskIds.length === filteredTasks.length) {
      setSelectedTaskIds([]);
    } else {
      setSelectedTaskIds(filteredTasks.map(t => t._id || t.id));
    }
  };

  const handleTaskUpdate = () => {
    loadData();
    if (selectedTask) {
      // Refresh selected task
      tasksApi.getById(selectedTask._id || selectedTask.id).then(updated => {
        setSelectedTask(updated);
      });
    }
  };
  
  // Pending tasks: open, in_progress, pending_evidence, ai_review, manual_review
  // Use filteredTasks instead of tasks to respect filters and sorting
  const pendingStatuses = ["open", "in_progress", "pending_evidence", "ai_review", "manual_review"];
  const pendingTasks = filteredTasks.filter(t => pendingStatuses.includes(t.status));

  // Feature #53: Export tasks to Excel/PDF
  const handleExport = async (format) => {
    setExporting(true);
    try {
      const params = new URLSearchParams({ format });

      // Add active filters to export
      if (filters.status && filters.status !== "all") params.append('status', filters.status);
      if (filters.priority && filters.priority !== "all") params.append('priority', filters.priority);
      if (filters.department_id && filters.department_id !== "all") params.append('department', filters.department_id);

      const token = localStorage.getItem('token');
      const response = await fetch(`/api/tasks/export?${params.toString()}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Export failed');
      }

      // Get filename from headers or use default
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `tasks_export_${new Date().toISOString().split('T')[0]}.${format === 'pdf' ? 'html' : 'csv'}`;
      if (contentDisposition) {
        const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(contentDisposition);
        if (matches != null && matches[1]) {
          filename = matches[1].replace(/['"]/g, '');
        }
      }

      // Download file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

    } catch (error) {
      console.error('Export error:', error);
      alert('Failed to export tasks. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  // ...existing code...

  return (
    <div className="space-y-6 max-w-full overflow-hidden" data-testid="tasks-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-gradient" data-testid="tasks-title">Task Management</h1>
          <p className="text-muted-foreground mt-1">Track compliance tasks and their lifecycle</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadData} className="btn-silver">
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="btn-silver" disabled={exporting} data-testid="export-tasks-button">
                <Download className="h-4 w-4 mr-1" />
                {exporting ? 'Exporting...' : 'Export'}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleExport('excel')} data-testid="export-excel">
                <FileText className="h-4 w-4 mr-2" />
                Export to Excel/CSV
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport('pdf')} data-testid="export-pdf">
                <FileText className="h-4 w-4 mr-2" />
                Export to PDF
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {canModify && (
            <>
              <Button onClick={() => setShowBulkCreateDialog(true)} variant="outline" className="btn-silver" data-testid="bulk-create-button">
                <Copy className="h-4 w-4 mr-2" />
                Bulk Create
              </Button>
              <Button onClick={() => setShowCreateDialog(true)} className="btn-shiny text-white" data-testid="create-task-button">
                <Plus className="h-4 w-4 mr-2" />
                Create Task
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Stats Cards */}
      <StatsCards stats={stats} />

      {/* Pending Tasks Summary Bar */}
      {pendingTasks.length > 0 && (
        <div className="flex items-center gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg" data-testid="pending-tasks-bar">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
          <span className="text-sm font-medium text-amber-800">
            {pendingTasks.length} pending task{pendingTasks.length !== 1 ? 's' : ''} require attention
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto text-amber-700 hover:text-amber-900 hover:bg-amber-100"
            onClick={() => setFilters(prev => ({ ...prev, status: 'all' }))}
          >
            View All
          </Button>
        </div>
      )}

      {/* Bulk Selection Actions Bar */}
      {selectedTaskIds.length > 0 && canModify && (
        <div className="flex items-center justify-between px-4 py-3 bg-blue-50 border border-blue-200 rounded-lg" data-testid="bulk-actions-bar">
          <span className="text-sm font-medium flex items-center gap-2 text-blue-800">
            <CheckSquare className="h-4 w-4 text-blue-600" />
            {selectedTaskIds.length} task{selectedTaskIds.length !== 1 ? "s" : ""} selected
          </span>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowBulkAssignDialog(true)}
              data-testid="bulk-assign-button"
            >
              <Users className="h-4 w-4 mr-1" />
              Bulk Assign
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setSelectedTaskIds([])}
            >
              Clear
            </Button>
          </div>
        </div>
      )}

      {/* Filters & View Toggle */}
      <Card className="card-elevated">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search tasks..."
                  value={filters.search}
                  onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                  className="pl-9"
                  data-testid="tasks-search-input"
                />
              </div>
            </div>

            {/* Priority Filter */}
            <Select
              value={filters.priority}
              onValueChange={(v) => setFilters(prev => ({ ...prev, priority: v }))}
            >
              <SelectTrigger className="w-[140px]" data-testid="priority-filter">
                <SelectValue placeholder="All Priorities" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Priorities</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>

            {/* Status Filter */}
            <Select
              value={filters.status}
              onValueChange={(v) => setFilters(prev => ({ ...prev, status: v }))}
            >
              <SelectTrigger className="w-[140px]" data-testid="status-filter">
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="open">Open</SelectItem>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="pending_evidence">Pending Evidence</SelectItem>
                <SelectItem value="ai_review">AI Review</SelectItem>
                <SelectItem value="manual_review">Manual Review</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>

            {/* Department Filter */}
            {departments.length > 0 && (
              <Select
                value={filters.department_id}
                onValueChange={(v) => setFilters(prev => ({ ...prev, department_id: v }))}
              >
                <SelectTrigger className="w-[140px]" data-testid="department-filter">
                  <SelectValue placeholder="All Depts" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Departments</SelectItem>
                  {(departments || []).map((d, index) => (
                    <SelectItem key={d._id || d.id || `dept-${index}`} value={d._id || d.id || `dept-${index}`}>{d.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {/* View Mode Toggle */}
            <div className="flex items-center gap-1 border rounded-lg bg-gray-50 p-0.5">
              <Button
                variant={viewMode === "kanban" ? "default" : "ghost"}
                size="sm"
                onClick={() => setViewMode("kanban")}
                className={`rounded-md h-8 px-3 ${viewMode === "kanban" ? "bg-white shadow-sm border" : ""}`}
              >
                <LayoutGrid className="h-4 w-4 mr-1" />
                <span className="hidden sm:inline text-xs">Board</span>
              </Button>
              <Button
                variant={viewMode === "list" ? "default" : "ghost"}
                size="sm"
                onClick={() => setViewMode("list")}
                className={`rounded-md h-8 px-3 ${viewMode === "list" ? "bg-white shadow-sm border" : ""}`}
              >
                <List className="h-4 w-4 mr-1" />
                <span className="hidden sm:inline text-xs">List</span>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : viewMode === "kanban" ? (
        <div className="kanban-container">
          {KANBAN_COLUMNS.map(column => (
            <KanbanColumn 
              key={column.id}
              column={column}
              tasks={filteredTasks}
              onTaskClick={handleTaskClick}
            />
          ))}
        </div>
      ) : (
        <Card className="card-elevated overflow-hidden">
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    {canModify && (
                      <th className="w-10">
                        <input
                          type="checkbox"
                          checked={selectedTaskIds.length === filteredTasks.length && filteredTasks.length > 0}
                          onChange={toggleSelectAll}
                          className="rounded"
                          data-testid="select-all-checkbox"
                        />
                      </th>
                    )}
                    <th
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort("title")}
                      data-testid="sort-title-main"
                    >
                      Task {sortField === "title" && (sortOrder === "asc" ? "↑" : "↓")}
                    </th>
                    <th
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort("status")}
                      data-testid="sort-status-main"
                    >
                      Status {sortField === "status" && (sortOrder === "asc" ? "↑" : "↓")}
                    </th>
                    <th
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort("priority")}
                      data-testid="sort-priority"
                    >
                      Priority {sortField === "priority" && (sortOrder === "asc" ? "↑" : "↓")}
                    </th>
                    <th>Assignee</th>
                    <th
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort("due_date")}
                      data-testid="sort-due-date-main"
                    >
                      Due Date {sortField === "due_date" && (sortOrder === "asc" ? "↑" : "↓")}
                    </th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedTasks.map(task => {
                    const statusConfig = STATUS_CONFIG[task.status] || STATUS_CONFIG.open;
                    const priorityConfig = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
                    const isOverdue = task.due_date && isPast(new Date(task.due_date)) && !["completed", "closed"].includes(task.status);
                    
                    return (
                      <tr
                        key={task._id || task.id}
                        className={`cursor-pointer ${selectedTaskIds.includes(task._id || task.id) ? 'bg-blue-500/10' : ''}`}
                        onClick={() => handleTaskClick(task)}
                      >
                        {canModify && (
                          <td onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={selectedTaskIds.includes(task._id || task.id)}
                              onChange={() => toggleTaskSelection(task._id || task.id)}
                              className="rounded"
                              data-testid={`task-checkbox-${task._id || task.id}`}
                            />
                          </td>
                        )}
                        <td>
                          <div>
                            <p className="font-medium">{task.title}</p>
                            {task.description && (
                              <p className="text-sm text-muted-foreground line-clamp-1">{task.description}</p>
                            )}
                          </div>
                        </td>
                        <td>
                          <Badge className={`${statusConfig.color} border`}>{statusConfig.label}</Badge>
                        </td>
                        <td>
                          <Badge className={priorityConfig.color}>{priorityConfig.label}</Badge>
                        </td>
                        <td>{task.assigned_to_name || "Unassigned"}</td>
                        <td className={isOverdue ? 'text-red-600 font-medium' : ''}>
                          {task.due_date ? format(new Date(task.due_date), "MMM d, yyyy") : "—"}
                        </td>
                        <td>
                          {task.time_spent_minutes > 0 ? `${Math.round(task.time_spent_minutes / 60)}h` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                  {filteredTasks.length === 0 && (
                    <tr>
                      <td colSpan={canModify ? 8 : 7} className="text-center py-8 text-muted-foreground">
                        No tasks found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t bg-gray-50/50" data-testid="tasks-pagination">
                <span className="text-sm text-muted-foreground">
                  Showing {(currentPage - 1) * pageSize + 1}-{Math.min(currentPage * pageSize, filteredTasks.length)} of {filteredTasks.length}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage(prev => prev - 1)}
                    data-testid="prev-page"
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage === totalPages}
                    onClick={() => setCurrentPage(prev => prev + 1)}
                    data-testid="next-page"
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Task Detail Modal */}
      <TaskDetailModal 
        task={selectedTask}
        open={!!selectedTask}
        onClose={() => setSelectedTask(null)}
        onUpdate={handleTaskUpdate}
        members={members}
      />
      
      {/* Create Task Dialog */}
      <CreateTaskDialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        onCreate={loadData}
        departments={departments}
        members={members}
      />

      {/* Bulk Create Tasks Dialog - Feature #170 */}
      <BulkCreateTaskDialog
        open={showBulkCreateDialog}
        onClose={() => setShowBulkCreateDialog(false)}
        onCreate={loadData}
        departments={departments}
        members={members}
      />

      {/* Bulk Assign Dialog - Feature #170 */}
      <BulkAssignDialog
        open={showBulkAssignDialog}
        onClose={() => setShowBulkAssignDialog(false)}
        selectedTaskIds={selectedTaskIds}
        members={members}
        onAssign={() => { loadData(); setSelectedTaskIds([]); }}
      />
    </div>
  );
}
