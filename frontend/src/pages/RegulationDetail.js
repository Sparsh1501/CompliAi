import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { regulationsApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import ClauseViewer from '../components/ClauseViewer';
import { 
  ArrowLeft, 
  Shield, 
  Calendar, 
  Building, 
  Download,
  Share2,
  AlertTriangle,
  FileText,
  Clock,
  ExternalLink,
  Info
} from 'lucide-react';
import { toast } from 'sonner';

const regulatorConfig = {
  RBI: { color: 'bg-blue-100 text-blue-700', name: 'Reserve Bank of India' },
  SEBI: { color: 'bg-emerald-100 text-emerald-700', name: 'Securities and Exchange Board of India' },
  IRDAI: { color: 'bg-purple-100 text-purple-700', name: 'Insurance Regulatory Authority' },
  NPCI: { color: 'bg-amber-100 text-amber-700', name: 'National Payments Corporation of India' },
  FIU_IND: { color: 'bg-red-100 text-red-700', name: 'Financial Intelligence Unit' },
  NSE: { color: 'bg-yellow-100 text-yellow-700', name: 'National Stock Exchange' },
  BSE: { color: 'bg-pink-100 text-pink-700', name: 'Bombay Stock Exchange' }
};

export default function RegulationDetail() {
  const { regulationId } = useParams();
  const navigate = useNavigate();
  const [regulation, setRegulation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('clauses');
  const [versions, setVersions] = useState([]);
  const [selectedVersionId, setSelectedVersionId] = useState(null);
  const [diff, setDiff] = useState(null);
  const [diffMode, setDiffMode] = useState('side-by-side'); // 'side-by-side' or 'inline'
  const [loadingDiff, setLoadingDiff] = useState(false);

  useEffect(() => {
    loadRegulation();
  }, [regulationId]);

  const loadRegulation = async () => {
    try {
      const response = await regulationsApi.getById(regulationId);
      setRegulation(response);

      // Load versions
      try {
        const versionsData = await regulationsApi.getVersions(regulationId);
        setVersions(versionsData.versions || []);
      } catch (err) {
        console.error('Failed to load versions:', err);
      }
    } catch (error) {
      toast.error('Failed to load regulation');
      navigate('/regulations');
    } finally {
      setLoading(false);
    }
  };

  const loadDiff = async (compareVersionId) => {
    setLoadingDiff(true);
    try {
      const diffData = await regulationsApi.compareVersions(regulationId, compareVersionId);
      setDiff(diffData);
      setSelectedVersionId(compareVersionId);
      toast.success('Version comparison loaded');
    } catch (error) {
      console.error('Failed to load diff:', error);
      toast.error('Failed to compare versions');
    } finally {
      setLoadingDiff(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading regulation...</div>
      </div>
    );
  }

  if (!regulation) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <AlertTriangle className="w-12 h-12 text-yellow-500 mb-4" />
        <h3 className="text-lg font-semibold mb-2">Regulation Not Found</h3>
        <Button onClick={() => navigate('/regulations')}>
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Regulations
        </Button>
      </div>
    );
  }

  const regulator = regulatorConfig[regulation.regulatory_body] || { 
    color: 'bg-gray-100 text-gray-500',
    name: regulation.regulatory_body
  };
  const clauses = regulation.clauses || [];
  
  // Calculate clause statistics
  const clauseStats = {
    total: clauses.length,
    mandatory: clauses.filter(c => c.requirement_type === 'mandatory').length,
    prohibitions: clauses.filter(c => c.requirement_type === 'prohibition').length,
    highPriority: clauses.filter(c => c.criticality === 'high').length,
    categories: [...new Set(clauses.map(c => c.subject_category).filter(Boolean))].length
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Button 
            variant="ghost" 
            size="icon"
            onClick={() => navigate('/regulations')}
            className="hover:bg-gray-100"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center shadow-lg">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-3xl font-bold text-gradient">{regulation.title}</h1>
            </div>
            <div className="flex items-center gap-3 text-muted-foreground flex-wrap">
              <Badge className={regulator.color}>{regulation.regulatory_body}</Badge>
              {regulation.circular_number && (
                <>
                  <span>•</span>
                  <span className="font-mono text-sm">{regulation.circular_number}</span>
                </>
              )}
              {regulation.is_master_circular && (
                <>
                  <span>•</span>
                  <Badge variant="outline" className="border-primary text-primary">
                    Master Circular
                  </Badge>
                </>
              )}
            </div>
          </div>
        </div>
        
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="btn-silver">
            <Download className="w-4 h-4 mr-2" /> Download
          </Button>
          <Button variant="outline" size="sm" className="btn-silver">
            <Share2 className="w-4 h-4 mr-2" /> Share
          </Button>
          <Button size="sm" className="btn-shiny text-white" onClick={() => navigate('/gap-analysis')}>
            Run Gap Analysis
          </Button>
        </div>
      </div>

      {/* Key Dates */}
      {(regulation.issued_date || regulation.effective_date || regulation.due_date) && (
        <div className="flex gap-4 flex-wrap">
          {regulation.issued_date && (
            <div className="flex items-center gap-2 text-sm">
              <Calendar className="w-4 h-4 text-muted-foreground" />
              <span className="text-muted-foreground">Issued:</span>
              <span className="font-medium">
                {new Date(regulation.issued_date).toLocaleDateString()}
              </span>
            </div>
          )}
          {regulation.effective_date && (
            <div className="flex items-center gap-2 text-sm">
              <Clock className="w-4 h-4 text-muted-foreground" />
              <span className="text-muted-foreground">Effective:</span>
              <span className="font-medium">
                {new Date(regulation.effective_date).toLocaleDateString()}
              </span>
            </div>
          )}
          {regulation.due_date && (
            <div className="flex items-center gap-2 text-sm">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              <span className="text-muted-foreground">Due:</span>
              <span className="font-medium text-amber-500">
                {new Date(regulation.due_date).toLocaleDateString()}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="stats-card">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold">{clauseStats.total}</div>
                <div className="text-sm text-muted-foreground">Total Clauses</div>
              </div>
              <FileText className="w-8 h-8 text-muted-foreground/30" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="stats-card">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-red-500">{clauseStats.mandatory}</div>
                <div className="text-sm text-muted-foreground">Mandatory</div>
              </div>
              <AlertTriangle className="w-8 h-8 text-red-500/30" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="stats-card">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-amber-500">{clauseStats.prohibitions}</div>
                <div className="text-sm text-muted-foreground">Prohibitions</div>
              </div>
              <Shield className="w-8 h-8 text-amber-500/30" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="stats-card">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-red-500">{clauseStats.highPriority}</div>
                <div className="text-sm text-muted-foreground">High Priority</div>
              </div>
              <AlertTriangle className="w-8 h-8 text-red-500/30" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="stats-card">
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-blue-600">{clauseStats.categories}</div>
                <div className="text-sm text-muted-foreground">Categories</div>
              </div>
              <Building className="w-8 h-8 text-blue-200" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Summary Card (if available) */}
      {regulation.summary && (
        <Card className="shiny-card border-emerald-200">
          <CardContent className="pt-4">
            <div className="flex gap-3">
              <Info className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-semibold text-gray-900 mb-2">
                  Executive Summary
                </h3>
                <p className="text-gray-700">
                  {regulation.summary}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Impact Cards */}
      {(regulation.impact_organization || regulation.impact_technical || regulation.impact_operational) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {regulation.impact_organization && (
            <Card className="shiny-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Building className="w-4 h-4" />
                  Organization Impact
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {regulation.impact_organization}
                </p>
              </CardContent>
            </Card>
          )}
          
          {regulation.impact_technical && (
            <Card className="shiny-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  Technical Impact
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {regulation.impact_technical}
                </p>
              </CardContent>
            </Card>
          )}
          
          {regulation.impact_operational && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  Operational Impact
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {regulation.impact_operational}
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList>
          <TabsTrigger value="clauses">
            Clauses ({clauses.length})
          </TabsTrigger>
          <TabsTrigger value="overview">
            Details
          </TabsTrigger>
          <TabsTrigger value="versions">
            Versions ({versions.length})
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="clauses" className="mt-6">
          <ClauseViewer 
            clauses={clauses} 
            documentType="regulation"
            title={regulation.title}
          />
        </TabsContent>
        
        <TabsContent value="overview" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Regulation Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Title</label>
                  <p className="mt-1">{regulation.title}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Regulatory Body</label>
                  <p className="mt-1">
                    <Badge className={regulator.color}>{regulation.regulatory_body}</Badge>
                    <span className="ml-2 text-sm text-muted-foreground">{regulator.name}</span>
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Circular Number</label>
                  <p className="mt-1 font-mono">{regulation.circular_number || 'Not specified'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Type</label>
                  <p className="mt-1">
                    {regulation.is_master_circular ? 'Master Circular' : 'Standard Circular'}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Issued Date</label>
                  <p className="mt-1">
                    {regulation.issued_date 
                      ? new Date(regulation.issued_date).toLocaleDateString() 
                      : 'Not specified'}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Effective Date</label>
                  <p className="mt-1">
                    {regulation.effective_date 
                      ? new Date(regulation.effective_date).toLocaleDateString() 
                      : 'Not specified'}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Compliance Due Date</label>
                  <p className="mt-1">
                    {regulation.due_date 
                      ? new Date(regulation.due_date).toLocaleDateString() 
                      : 'Not specified'}
                  </p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">File</label>
                  <p className="mt-1">{regulation.file_name || 'Not available'}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Versions Tab - Feature #34 & #35 */}
        <TabsContent value="versions" className="mt-6">
          <div className="space-y-6">
            {/* Version Selector */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Version History</CardTitle>
                <CardDescription>
                  Compare different versions of this regulation to see what has changed
                </CardDescription>
              </CardHeader>
              <CardContent>
                {versions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No version history available</p>
                ) : versions.length === 1 ? (
                  <p className="text-sm text-muted-foreground">This is the only version</p>
                ) : (
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Select version to compare with current:</label>
                    <select
                      className="w-full border rounded-md p-2"
                      value={selectedVersionId || ''}
                      onChange={(e) => {
                        if (e.target.value) {
                          loadDiff(e.target.value);
                        }
                      }}
                    >
                      <option value="">-- Select a version --</option>
                      {versions
                        .filter(v => v.id !== regulationId)
                        .map(v => (
                          <option key={v.id} value={v.id}>
                            Version {v.version} - {v.title} ({new Date(v.created_at).toLocaleDateString()})
                          </option>
                        ))}
                    </select>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Diff View Mode Toggle */}
            {diff && (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">Comparison View</CardTitle>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant={diffMode === 'side-by-side' ? 'default' : 'outline'}
                        onClick={() => setDiffMode('side-by-side')}
                      >
                        Side-by-Side
                      </Button>
                      <Button
                        size="sm"
                        variant={diffMode === 'inline' ? 'default' : 'outline'}
                        onClick={() => setDiffMode('inline')}
                      >
                        Inline
                      </Button>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            )}

            {/* Loading State */}
            {loadingDiff && (
              <Card>
                <CardContent className="p-8 text-center text-muted-foreground">
                  Loading comparison...
                </CardContent>
              </Card>
            )}

            {/* AI Summary */}
            {diff && !loadingDiff && (
              <Card className="border-blue-200 bg-blue-50/50">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Info className="h-5 w-5 text-blue-600" />
                    AI-Generated Changes Summary
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm">{diff.changes_summary}</p>
                  <div className="mt-3 flex gap-4 text-sm">
                    <span className="text-green-600">
                      ✓ {diff.diff.additions.length} Added
                    </span>
                    <span className="text-red-600">
                      ✗ {diff.diff.deletions.length} Removed
                    </span>
                    <span className="text-orange-600">
                      ⟳ {diff.diff.modifications.length} Modified
                    </span>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Side-by-Side Diff */}
            {diff && !loadingDiff && diffMode === 'side-by-side' && (
              <div className="grid grid-cols-2 gap-4">
                {/* Current Version */}
                <Card>
                  <CardHeader className="bg-green-50">
                    <CardTitle className="text-sm text-green-700">
                      Current Version ({diff.current_version.version})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4 p-4 max-h-[600px] overflow-y-auto">
                    {diff.diff.additions.map((addition, idx) => (
                      <div key={idx} className="p-3 bg-green-50 border border-green-200 rounded">
                        <div className="text-xs font-medium text-green-700 mb-1">
                          ✓ Added: Clause {addition.clause_number}
                        </div>
                        <p className="text-sm">{addition.text}</p>
                      </div>
                    ))}
                    {diff.diff.modifications.map((mod, idx) => (
                      <div key={idx} className="p-3 bg-orange-50 border border-orange-200 rounded">
                        <div className="text-xs font-medium text-orange-700 mb-1">
                          ⟳ Modified: Clause {mod.clause_number}
                        </div>
                        <p className="text-sm">{mod.new_text}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                {/* Previous Version */}
                <Card>
                  <CardHeader className="bg-red-50">
                    <CardTitle className="text-sm text-red-700">
                      Previous Version ({diff.compare_version.version})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4 p-4 max-h-[600px] overflow-y-auto">
                    {diff.diff.deletions.map((deletion, idx) => (
                      <div key={idx} className="p-3 bg-red-50 border border-red-200 rounded">
                        <div className="text-xs font-medium text-red-700 mb-1">
                          ✗ Removed: Clause {deletion.clause_number}
                        </div>
                        <p className="text-sm line-through">{deletion.text}</p>
                      </div>
                    ))}
                    {diff.diff.modifications.map((mod, idx) => (
                      <div key={idx} className="p-3 bg-orange-50 border border-orange-200 rounded">
                        <div className="text-xs font-medium text-orange-700 mb-1">
                          ⟳ Original: Clause {mod.clause_number}
                        </div>
                        <p className="text-sm line-through">{mod.old_text}</p>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Inline Diff */}
            {diff && !loadingDiff && diffMode === 'inline' && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Changes</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 max-h-[600px] overflow-y-auto">
                  {diff.diff.additions.map((addition, idx) => (
                    <div key={`add-${idx}`} className="p-3 bg-green-50 border-l-4 border-green-500 rounded">
                      <div className="text-xs font-medium text-green-700 mb-1 flex items-center gap-2">
                        <span className="bg-green-600 text-white px-2 py-0.5 rounded text-xs">+</span>
                        Added: Clause {addition.clause_number}
                      </div>
                      <p className="text-sm text-green-900">{addition.text}</p>
                    </div>
                  ))}
                  {diff.diff.deletions.map((deletion, idx) => (
                    <div key={`del-${idx}`} className="p-3 bg-red-50 border-l-4 border-red-500 rounded">
                      <div className="text-xs font-medium text-red-700 mb-1 flex items-center gap-2">
                        <span className="bg-red-600 text-white px-2 py-0.5 rounded text-xs">-</span>
                        Removed: Clause {deletion.clause_number}
                      </div>
                      <p className="text-sm text-red-900 line-through">{deletion.text}</p>
                    </div>
                  ))}
                  {diff.diff.modifications.map((mod, idx) => (
                    <div key={`mod-${idx}`} className="p-3 bg-orange-50 border-l-4 border-orange-500 rounded">
                      <div className="text-xs font-medium text-orange-700 mb-2 flex items-center gap-2">
                        <span className="bg-orange-600 text-white px-2 py-0.5 rounded text-xs">~</span>
                        Modified: Clause {mod.clause_number}
                      </div>
                      <div className="space-y-2">
                        <div>
                          <div className="text-xs text-red-600 mb-1">- Old:</div>
                          <p className="text-sm text-red-900 line-through bg-red-100 p-2 rounded">{mod.old_text}</p>
                        </div>
                        <div>
                          <div className="text-xs text-green-600 mb-1">+ New:</div>
                          <p className="text-sm text-green-900 bg-green-100 p-2 rounded">{mod.new_text}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                  {diff.diff.total_changes === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      No changes detected between these versions
                    </p>
                  )}
                </CardContent>
              </Card>
            )}

            {/* No Version Selected */}
            {!diff && !loadingDiff && versions.length > 1 && (
              <Card>
                <CardContent className="p-8 text-center text-muted-foreground">
                  Select a version above to view comparison
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
