import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Bell, ChevronRight, AlertCircle, CheckCircle, Clock, FileText, TrendingUp, Users, Edit3, History } from 'lucide-react';
import { toast } from 'sonner';
import { MOCK_REGULATORY_UPDATES } from '../lib/mockData';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export default function RegulatoryUpdates() {
  const navigate = useNavigate();
  const [updates, setUpdates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedUpdate, setSelectedUpdate] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [adjustScoreOpen, setAdjustScoreOpen] = useState(false);
  const [newScore, setNewScore] = useState('');
  const [justification, setJustification] = useState('');
  const [adjusting, setAdjusting] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    loadUpdates();
  }, []);

  const loadUpdates = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/regulation-updates`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to load regulatory updates');
      }

      const data = await response.json();
      const updates = data.updates || [];
      // Use mock data if API returns empty
      setUpdates(updates.length > 0 ? updates : MOCK_REGULATORY_UPDATES);
    } catch (error) {
      console.error('Error loading regulatory updates:', error);
      // Fallback to mock data for demo
      setUpdates(MOCK_REGULATORY_UPDATES);
      console.log('Using mock regulatory updates for demo');
    } finally {
      setLoading(false);
    }
  };

  const loadUpdateDetail = async (updateId) => {
    setDetailLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/regulation-updates/${updateId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to load update details');
      }

      const data = await response.json();
      setSelectedUpdate(data);
      setDetailOpen(true);
    } catch (error) {
      console.error('Error loading update detail:', error);
      // Fallback: use the update from mock data
      const mockUpdate = MOCK_REGULATORY_UPDATES.find(u => u._id === updateId);
      if (mockUpdate) {
        setSelectedUpdate(mockUpdate);
        setDetailOpen(true);
      } else {
        toast.error('Failed to load update details');
      }
    } finally {
      setDetailLoading(false);
    }
  };

  const markAsReviewed = async (updateId) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/regulation-updates/${updateId}/review`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error('Failed to mark as reviewed');
      }

      toast.success('Marked as reviewed');
      setDetailOpen(false);
      loadUpdates(); // Reload list
    } catch (error) {
      console.error('Error marking as reviewed:', error);
      toast.error('Failed to mark as reviewed');
    }
  };

  const openAdjustScore = () => {
    setNewScore(selectedUpdate?.impact_score?.toString() || '');
    setJustification('');
    setAdjustScoreOpen(true);
  };

  const handleAdjustScore = async () => {
    if (!newScore || newScore === '') {
      toast.error('Please enter a score');
      return;
    }

    const score = parseFloat(newScore);
    if (isNaN(score) || score < 0 || score > 100) {
      toast.error('Score must be between 0 and 100');
      return;
    }

    if (!justification || justification.length < 10) {
      toast.error('Please provide a justification (at least 10 characters)');
      return;
    }

    setAdjusting(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/api/regulation-updates/${selectedUpdate.id}/adjust-impact-score`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          new_score: score,
          justification: justification
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to adjust impact score');
      }

      const result = await response.json();
      toast.success('Impact score adjusted successfully');
      setAdjustScoreOpen(false);

      // Reload the update detail
      await loadUpdateDetail(selectedUpdate.id);
    } catch (error) {
      console.error('Error adjusting impact score:', error);
      toast.error(error.message || 'Failed to adjust impact score');
    } finally {
      setAdjusting(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-IN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const getChangeTypeBadge = (changeType) => {
    const types = {
      'new': { variant: 'default', label: 'New' },
      'amendment': { variant: 'secondary', label: 'Amendment' },
      'superseded': { variant: 'outline', label: 'Superseded' }
    };
    const config = types[changeType] || types['new'];
    return <Badge variant={config.variant}>{config.label}</Badge>;
  };

  const getStatusBadge = (status) => {
    const statuses = {
      'pending_review': { variant: 'destructive', icon: AlertCircle, label: 'Pending Review' },
      'reviewed': { variant: 'secondary', icon: CheckCircle, label: 'Reviewed' }
    };
    const config = statuses[status] || statuses['pending_review'];
    const Icon = config.icon;
    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <Icon className="h-3 w-3" />
        {config.label}
      </Badge>
    );
  };

  const getPriorityBadge = (priority) => {
    const priorities = {
      'critical': { variant: 'destructive', label: 'Critical' },
      'high': { variant: 'default', label: 'High' },
      'medium': { variant: 'secondary', label: 'Medium' },
      'low': { variant: 'outline', label: 'Low' }
    };
    const config = priorities[priority] || priorities['medium'];
    return <Badge variant={config.variant}>{config.label}</Badge>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-muted-foreground">Loading regulatory updates...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <Bell className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Regulatory Updates</h1>
            <p className="text-sm text-muted-foreground">
              Track new circulars and their impact on your policies
            </p>
          </div>
        </div>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Updates</p>
                <p className="text-2xl font-bold">{updates.length}</p>
              </div>
              <FileText className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Pending Review</p>
                <p className="text-2xl font-bold">
                  {updates.filter(u => u.status === 'pending_review').length}
                </p>
              </div>
              <Clock className="h-8 w-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Reviewed</p>
                <p className="text-2xl font-bold">
                  {updates.filter(u => u.status === 'reviewed').length}
                </p>
              </div>
              <CheckCircle className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Updates</CardTitle>
          <CardDescription>
            Timeline of new regulatory circulars and amendments
          </CardDescription>
        </CardHeader>
        <CardContent>
          {updates.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No regulatory updates found</p>
              <p className="text-sm mt-1">New circulars will appear here</p>
            </div>
          ) : (
            <div className="space-y-4">
              {updates.map((update, index) => (
                <div
                  key={update.id || index}
                  className="border rounded-lg p-4 hover:bg-gray-50 transition-colors cursor-pointer"
                  onClick={() => loadUpdateDetail(update.id)}
                  data-testid={`update-item-${index}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 space-y-2">
                      {/* Date and badges */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium text-muted-foreground">
                          {formatDate(update.crawl_date)}
                        </span>
                        {update.regulation?.regulatory_body && (
                          <Badge variant="outline">{update.regulation.regulatory_body}</Badge>
                        )}
                        {update.change_type && getChangeTypeBadge(update.change_type)}
                        {update.status && getStatusBadge(update.status)}
                      </div>

                      {/* Title */}
                      <h3 className="font-semibold text-lg text-gray-900">
                        {update.regulation?.title || 'Regulatory Update'}
                      </h3>

                      {/* Summary */}
                      {update.ai_summary && (
                        <p className="text-sm text-gray-600 line-clamp-2">
                          {update.ai_summary}
                        </p>
                      )}

                      {/* Impact indicators */}
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        {update.affected_policies && update.affected_policies.length > 0 && (
                          <span className="flex items-center gap-1">
                            <FileText className="h-4 w-4" />
                            {update.affected_policies.length} {update.affected_policies.length === 1 ? 'policy' : 'policies'} affected
                          </span>
                        )}
                        {update.priority_recommendation && (
                          <span className="flex items-center gap-1">
                            <TrendingUp className="h-4 w-4" />
                            Priority: {getPriorityBadge(update.priority_recommendation)}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* View detail arrow */}
                    <ChevronRight className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-2" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail Dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          {detailLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-muted-foreground">Loading details...</div>
            </div>
          ) : selectedUpdate ? (
            <>
              <DialogHeader>
                <DialogTitle className="text-xl">
                  {selectedUpdate.regulation?.title || 'Regulatory Update'}
                </DialogTitle>
                <DialogDescription>
                  Impact Analysis Package
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-6">
                {/* Meta info */}
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm text-muted-foreground">
                    {formatDate(selectedUpdate.crawl_date)}
                  </span>
                  {selectedUpdate.regulation?.regulatory_body && (
                    <Badge variant="outline">{selectedUpdate.regulation.regulatory_body}</Badge>
                  )}
                  {selectedUpdate.change_type && getChangeTypeBadge(selectedUpdate.change_type)}
                  {selectedUpdate.status && getStatusBadge(selectedUpdate.status)}
                </div>

                {/* Summary */}
                {selectedUpdate.ai_summary && (
                  <div>
                    <h3 className="font-semibold mb-2">Summary</h3>
                    <p className="text-sm text-gray-700">{selectedUpdate.ai_summary}</p>
                  </div>
                )}

                {/* Impact Score */}
                <div>
                  <h3 className="font-semibold mb-2 flex items-center gap-2">
                    <TrendingUp className="h-4 w-4" />
                    Impact Score
                  </h3>
                  <div className="space-y-2">
                    {selectedUpdate.impact_score !== null && selectedUpdate.impact_score !== undefined ? (
                      <div className="flex items-center gap-3">
                        <div className="text-3xl font-bold text-primary">
                          {selectedUpdate.impact_score}
                          <span className="text-base text-muted-foreground">/100</span>
                        </div>
                        <Button variant="outline" size="sm" onClick={openAdjustScore}>
                          <Edit3 className="h-3 w-3 mr-1" />
                          Adjust
                        </Button>
                        {selectedUpdate.impact_score_corrections && selectedUpdate.impact_score_corrections.length > 0 && (
                          <Button variant="ghost" size="sm" onClick={() => setShowHistory(!showHistory)}>
                            <History className="h-3 w-3 mr-1" />
                            History ({selectedUpdate.impact_score_corrections.length})
                          </Button>
                        )}
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">No score assigned</span>
                        <Button variant="outline" size="sm" onClick={openAdjustScore}>
                          <Edit3 className="h-3 w-3 mr-1" />
                          Set Score
                        </Button>
                      </div>
                    )}

                    {selectedUpdate.impact_analysis && (
                      <div className="mt-2">
                        <p className="text-sm text-muted-foreground font-medium">Analysis:</p>
                        <p className="text-sm text-gray-700">{selectedUpdate.impact_analysis}</p>
                      </div>
                    )}

                    {showHistory && selectedUpdate.impact_score_corrections && selectedUpdate.impact_score_corrections.length > 0 && (
                      <div className="mt-3 border rounded-lg p-3 bg-gray-50">
                        <h4 className="text-sm font-semibold mb-2">Adjustment History</h4>
                        <div className="space-y-2">
                          {selectedUpdate.impact_score_corrections.map((correction, idx) => (
                            <div key={idx} className="text-xs border-l-2 border-primary pl-2">
                              <div className="flex items-center gap-2 text-muted-foreground">
                                <span>{new Date(correction.timestamp).toLocaleString('en-IN')}</span>
                                <span>•</span>
                                <span>{correction.user_email}</span>
                              </div>
                              <div className="font-medium">
                                {correction.old_score !== null && correction.old_score !== undefined ? correction.old_score : 'N/A'} → {correction.new_score}
                              </div>
                              <div className="text-gray-700 italic">"{correction.justification}"</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Priority */}
                {selectedUpdate.priority_recommendation && (
                  <div>
                    <h3 className="font-semibold mb-2">Priority Recommendation</h3>
                    <div>{getPriorityBadge(selectedUpdate.priority_recommendation)}</div>
                  </div>
                )}

                {/* Remediation Effort */}
                {selectedUpdate.remediation_effort_estimate && (
                  <div>
                    <h3 className="font-semibold mb-2">Remediation Effort Estimate</h3>
                    <p className="text-sm text-gray-700">{selectedUpdate.remediation_effort_estimate}</p>
                  </div>
                )}

                {/* Affected Policies */}
                {selectedUpdate.affected_policies_details && selectedUpdate.affected_policies_details.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      Affected Policies ({selectedUpdate.affected_policies_details.length})
                    </h3>
                    <div className="space-y-2">
                      {selectedUpdate.affected_policies_details.map((policy, i) => (
                        <div
                          key={policy.id || i}
                          className="p-3 border rounded-lg hover:bg-gray-50 cursor-pointer"
                          onClick={() => {
                            setDetailOpen(false);
                            navigate(`/policies/${policy.id}`);
                          }}
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="font-medium text-sm">{policy.title}</p>
                              <p className="text-xs text-muted-foreground">{policy.type}</p>
                            </div>
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Affected Clauses */}
                {selectedUpdate.affected_clauses_details && selectedUpdate.affected_clauses_details.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2">Affected Clauses ({selectedUpdate.affected_clauses_details.length})</h3>
                    <div className="space-y-2 max-h-40 overflow-y-auto">
                      {selectedUpdate.affected_clauses_details.map((clause, i) => (
                        <div key={clause.clause_id || i} className="p-2 bg-gray-50 rounded text-sm">
                          <p className="text-gray-700 line-clamp-2">{clause.clause_text}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Auto-created Tasks */}
                {selectedUpdate.auto_created_tasks_details && selectedUpdate.auto_created_tasks_details.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <Users className="h-4 w-4" />
                      Auto-Created Review Tasks ({selectedUpdate.auto_created_tasks_details.length})
                    </h3>
                    <div className="space-y-2">
                      {selectedUpdate.auto_created_tasks_details.map((task, i) => (
                        <div
                          key={task.id || i}
                          className="p-3 border rounded-lg hover:bg-gray-50 cursor-pointer"
                          onClick={() => {
                            setDetailOpen(false);
                            navigate('/tasks');
                          }}
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="font-medium text-sm">{task.title}</p>
                              <p className="text-xs text-muted-foreground">
                                {task.assignee ? `Assigned to: ${task.assignee}` : 'Unassigned'}
                              </p>
                            </div>
                            <Badge variant="outline">{task.status}</Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex justify-end gap-2 pt-4 border-t">
                  <Button variant="outline" onClick={() => setDetailOpen(false)}>
                    Close
                  </Button>
                  {selectedUpdate.status === 'pending_review' && (
                    <Button onClick={() => markAsReviewed(selectedUpdate.id)}>
                      Mark as Reviewed
                    </Button>
                  )}
                </div>
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* Adjust Impact Score Dialog */}
      <Dialog open={adjustScoreOpen} onOpenChange={setAdjustScoreOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Adjust Impact Score</DialogTitle>
            <DialogDescription>
              Manually adjust the impact score for this regulatory update
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="impact-score">Impact Score (0-100)</Label>
              <Input
                id="impact-score"
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={newScore}
                onChange={(e) => setNewScore(e.target.value)}
                placeholder="Enter score (0-100)"
                className="mt-1"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Current: {selectedUpdate?.impact_score !== null && selectedUpdate?.impact_score !== undefined ? selectedUpdate.impact_score : 'Not set'}
              </p>
            </div>

            <div>
              <Label htmlFor="justification">Justification *</Label>
              <Textarea
                id="justification"
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                placeholder="Explain why you're adjusting the score (minimum 10 characters)"
                rows={4}
                className="mt-1"
              />
              <p className="text-xs text-muted-foreground mt-1">
                {justification.length}/10 minimum characters
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-4 border-t">
              <Button variant="outline" onClick={() => setAdjustScoreOpen(false)} disabled={adjusting}>
                Cancel
              </Button>
              <Button onClick={handleAdjustScore} disabled={adjusting}>
                {adjusting ? 'Saving...' : 'Save Adjustment'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
