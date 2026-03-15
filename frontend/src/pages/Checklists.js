import React, { useState, useEffect } from 'react';
import { checklistApi, gapAnalysisApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Checkbox } from '../components/ui/checkbox';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { CheckSquare, Plus, Trash2, Clock, CheckCircle2, Circle } from 'lucide-react';
import { toast } from 'sonner';

export default function Checklists() {
  const [checklists, setChecklists] = useState([]);
  const [selectedChecklist, setSelectedChecklist] = useState(null);
  const [gapAnalyses, setGapAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);

  // Create form state
  const [selectedGapAnalysis, setSelectedGapAnalysis] = useState('');
  const [checklistTitle, setChecklistTitle] = useState('');
  const [checklistDescription, setChecklistDescription] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [checklistsData, gapAnalysesData] = await Promise.all([
        checklistApi.getAll().catch(() => []),
        gapAnalysisApi.getAll().catch(() => [])
      ]);
      setChecklists(checklistsData);
      setGapAnalyses(gapAnalysesData);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateChecklist = async () => {
    if (!selectedGapAnalysis) {
      toast.error('Please select a gap analysis');
      return;
    }

    try {
      await checklistApi.generate({
        gap_analysis_id: selectedGapAnalysis,
        title: checklistTitle || undefined,
        description: checklistDescription || undefined
      });

      toast.success('Checklist created successfully');
      setCreateDialogOpen(false);
      setSelectedGapAnalysis('');
      setChecklistTitle('');
      setChecklistDescription('');
      loadData();
    } catch (error) {
      toast.error('Failed to create checklist');
    }
  };

  const handleToggleItem = async (checklistId, item) => {
    try {
      const updated = await checklistApi.updateItem(
        checklistId,
        item.id,
        { completed: !item.completed }
      );

      // Update local state
      if (selectedChecklist && selectedChecklist.id === checklistId) {
        setSelectedChecklist(updated);
      }

      setChecklists(checklists.map(c =>
        c.id === checklistId ? updated : c
      ));

      toast.success(item.completed ? 'Item marked incomplete' : 'Item marked complete');
    } catch (error) {
      toast.error('Failed to update item');
    }
  };

  const handleDeleteChecklist = async (checklistId) => {
    if (!window.confirm('Are you sure you want to delete this checklist?')) {
      return;
    }

    try {
      await checklistApi.delete(checklistId);
      toast.success('Checklist deleted');
      setChecklists(checklists.filter(c => c.id !== checklistId));
      if (selectedChecklist && selectedChecklist.id === checklistId) {
        setDetailDialogOpen(false);
        setSelectedChecklist(null);
      }
    } catch (error) {
      toast.error('Failed to delete checklist');
    }
  };

  const handleViewDetails = async (checklist) => {
    try {
      const fullChecklist = await checklistApi.getById(checklist.id);
      setSelectedChecklist(fullChecklist);
      setDetailDialogOpen(true);
    } catch (error) {
      toast.error('Failed to load checklist details');
    }
  };

  const calculateProgress = (checklist) => {
    const total = checklist.items?.length || 0;
    const completed = checklist.items?.filter(i => i.completed).length || 0;
    return total > 0 ? Math.round((completed / total) * 100) : 0;
  };

  const getSeverityColor = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'destructive';
      case 'high': return 'destructive';
      case 'medium': return 'secondary';
      case 'low': return 'outline';
      default: return 'secondary';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="checklists-loading">
        <div className="text-muted-foreground">Loading checklists...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="checklists-page">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-blue-800 flex items-center justify-center shadow-lg">
            <CheckSquare className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold" data-testid="checklists-title">Compliance Checklists</h1>
            <p className="text-muted-foreground">Track gap remediation progress</p>
          </div>
        </div>

        <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="create-checklist-button">
              <Plus className="mr-2 h-4 w-4" /> Generate Checklist
            </Button>
          </DialogTrigger>
          <DialogContent data-testid="create-checklist-dialog">
            <DialogHeader>
              <DialogTitle>Generate Compliance Checklist</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="gap-analysis">Gap Analysis *</Label>
                <Select value={selectedGapAnalysis} onValueChange={setSelectedGapAnalysis}>
                  <SelectTrigger id="gap-analysis">
                    <SelectValue placeholder="Select gap analysis" />
                  </SelectTrigger>
                  <SelectContent>
                    {gapAnalyses.map(ga => (
                      <SelectItem key={ga.id} value={ga.id}>
                        {ga.policy_name} vs {ga.regulation_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="title">Checklist Title (Optional)</Label>
                <Input
                  id="title"
                  value={checklistTitle}
                  onChange={(e) => setChecklistTitle(e.target.value)}
                  placeholder="Leave blank for auto-generated title"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description (Optional)</Label>
                <Textarea
                  id="description"
                  value={checklistDescription}
                  onChange={(e) => setChecklistDescription(e.target.value)}
                  placeholder="Additional notes or context"
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateChecklist} data-testid="confirm-create-checklist">
                Generate Checklist
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Checklists Grid */}
      {checklists.length === 0 ? (
        <Card className="flex flex-col items-center justify-center h-64" data-testid="checklists-empty">
          <CardContent className="text-center py-8">
            <CheckSquare className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Checklists Yet</h3>
            <p className="text-muted-foreground mb-4">Generate a checklist from a gap analysis to get started</p>
            <Button onClick={() => setCreateDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" /> Generate First Checklist
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {checklists.map(checklist => {
            const progress = calculateProgress(checklist);
            const totalItems = checklist.items?.length || 0;
            const completedItems = checklist.items?.filter(i => i.completed).length || 0;

            return (
              <Card
                key={checklist.id}
                className="cursor-pointer hover:shadow-lg transition-shadow"
                onClick={() => handleViewDetails(checklist)}
                data-testid={`checklist-card-${checklist.id}`}
              >
                <CardHeader>
                  <CardTitle className="text-lg flex items-start justify-between">
                    <span className="flex-1">{checklist.title}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteChecklist(checklist.id);
                      }}
                      data-testid={`delete-checklist-${checklist.id}`}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </CardTitle>
                  {checklist.description && (
                    <p className="text-sm text-muted-foreground">{checklist.description}</p>
                  )}
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Progress Bar */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Progress</span>
                      <span className="font-medium">{progress}%</span>
                    </div>
                    <Progress value={progress} />
                  </div>

                  {/* Stats */}
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                      <span>{completedItems} completed</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Circle className="h-4 w-4 text-gray-400" />
                      <span>{totalItems - completedItems} remaining</span>
                    </div>
                  </div>

                  {/* Created Date */}
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    <span>Created {new Date(checklist.created_at).toLocaleDateString()}</span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Checklist Detail Dialog */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto" data-testid="checklist-detail-dialog">
          {selectedChecklist && (
            <>
              <DialogHeader>
                <DialogTitle>{selectedChecklist.title}</DialogTitle>
                {selectedChecklist.description && (
                  <p className="text-sm text-muted-foreground">{selectedChecklist.description}</p>
                )}
              </DialogHeader>

              <div className="space-y-4 py-4">
                {/* Progress Summary */}
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">Overall Progress</span>
                      <span className="text-2xl font-bold">{calculateProgress(selectedChecklist)}%</span>
                    </div>
                    <Progress value={calculateProgress(selectedChecklist)} className="h-3" />
                  </CardContent>
                </Card>

                {/* Checklist Items */}
                <div className="space-y-3">
                  <h3 className="font-semibold text-lg">Checklist Items</h3>
                  {selectedChecklist.items?.map((item, index) => (
                    <Card
                      key={item.id}
                      className={item.completed ? 'bg-green-50' : ''}
                      data-testid={`checklist-item-${index}`}
                    >
                      <CardContent className="pt-6">
                        <div className="flex items-start gap-4">
                          <Checkbox
                            checked={item.completed}
                            onCheckedChange={() => handleToggleItem(selectedChecklist.id, item)}
                            className="mt-1"
                            data-testid={`checkbox-item-${index}`}
                          />
                          <div className="flex-1 space-y-2">
                            <div className="flex items-start justify-between">
                              <p className={`font-medium ${item.completed ? 'line-through text-muted-foreground' : ''}`}>
                                {item.text}
                              </p>
                              <Badge variant={getSeverityColor(item.severity)}>
                                {item.severity || 'MEDIUM'}
                              </Badge>
                            </div>

                            {item.description && (
                              <p className="text-sm text-muted-foreground">{item.description}</p>
                            )}

                            {item.notes && (
                              <div className="text-sm">
                                <span className="font-medium">Notes: </span>
                                <span className="text-muted-foreground">{item.notes}</span>
                              </div>
                            )}

                            {item.completed && item.completed_at && (
                              <div className="text-xs text-green-600 flex items-center gap-2">
                                <CheckCircle2 className="h-3 w-3" />
                                Completed on {new Date(item.completed_at).toLocaleString()}
                              </div>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setDetailDialogOpen(false)}>
                  Close
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
