import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { regulationsApi } from '../lib/api';
import { useUpload } from '../context/UploadContext';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Shield, Plus, Upload, Eye, ChevronRight, Search, ArrowUpDown, ArrowUp, ArrowDown, RefreshCw, Globe, CheckCircle, Loader2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

const regulators = ['ALL', 'RBI', 'SEBI', 'NSE', 'BSE', 'IRDAI', 'FIU_IND', 'NPCI'];

export default function Regulations() {
  const navigate = useNavigate();
  const { setShowPanel } = useUpload();
  const { user } = useAuth();
  const [regulations, setRegulations] = useState([]);
  const [activeTab, setActiveTab] = useState('ALL');
  const [loading, setLoading] = useState(true);

  // Check if user is auditor (read-only access)
  const isAuditor = user?.role === 'auditor';
  const canModify = !isAuditor;
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState(null);
  const [autofilling, setAutofilling] = useState(false);
  const [autofilled, setAutofilled] = useState(false);
  const [regData, setRegData] = useState({
    title: '',
    regulatory_body: 'RBI',
    circular_number: ''
  });

  // Crawl state - Feature #176
  const [crawlStatus, setCrawlStatus] = useState(null);
  const [crawling, setCrawling] = useState(false);

  // Search and sorting
  const [searchQuery, setSearchQuery] = useState('');
  const [sortColumn, setSortColumn] = useState('title');
  const [sortDirection, setSortDirection] = useState('asc');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  useEffect(() => {
    loadRegulations();
    loadCrawlStatus();
  }, []);

  // Feature #176: Load latest crawl status
  const loadCrawlStatus = async () => {
    try {
      const status = await regulationsApi.getCrawlStatus();
      setCrawlStatus(status);
    } catch (error) {
      // No crawl status yet, that's OK
    }
  };

  // Feature #176: Trigger regulation crawl
  const handleTriggerCrawl = async () => {
    setCrawling(true);
    try {
      const result = await regulationsApi.triggerCrawl();
      setCrawlStatus(result);
      toast.success('Regulation crawl triggered! Checking sources...');

      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const status = await regulationsApi.getCrawlStatus();
          setCrawlStatus(status);
          if (status.status === 'completed') {
            clearInterval(pollInterval);
            setCrawling(false);
            const newCount = status.results?.new_circulars || 0;
            if (newCount > 0) {
              toast.success(`Crawl complete! Found ${newCount} result(s).`);
            } else {
              toast.info('Crawl complete. No new findings.');
            }
            loadRegulations();
          } else if (status.status === 'error') {
            clearInterval(pollInterval);
            setCrawling(false);
            toast.error('Crawl failed: ' + (status.error || 'Unknown error'));
          }
        } catch (e) {
          clearInterval(pollInterval);
          setCrawling(false);
        }
      }, 2000);

      // Safety timeout after 30s
      setTimeout(() => {
        clearInterval(pollInterval);
        setCrawling(false);
      }, 30000);
    } catch (error) {
      setCrawling(false);
      toast.error('Failed to trigger crawl: ' + (error.response?.data?.detail || 'Unknown error'));
    }
  };

  const loadRegulations = async () => {
    try {
      const response = await regulationsApi.getAll(undefined, true);
      setRegulations(response);
    } catch (error) {
      toast.error('Failed to load regulations');
    } finally {
      setLoading(false);
    }
  };

  // Filtered, searched, and sorted regulations
  const filteredRegulations = useMemo(() => {
    let result = [...regulations];

    // Tab filter
    if (activeTab !== 'ALL') {
      result = result.filter(r => r.regulatory_body === activeTab);
    }

    // Search - trim whitespace, ignore whitespace-only input
    const trimmedSearch = searchQuery.trim();
    if (trimmedSearch) {
      const q = trimmedSearch.toLowerCase();
      result = result.filter(r =>
        r.title?.toLowerCase().includes(q) ||
        r.circular_number?.toLowerCase().includes(q) ||
        r.regulatory_body?.toLowerCase().includes(q)
      );
    }

    // Sort
    result.sort((a, b) => {
      let aVal = a[sortColumn] || '';
      let bVal = b[sortColumn] || '';
      if (sortColumn === 'effective_date' || sortColumn === 'created_at') {
        aVal = new Date(aVal || 0).getTime();
        bVal = new Date(bVal || 0).getTime();
      } else if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = (bVal || '').toLowerCase();
      }
      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return result;
  }, [regulations, activeTab, searchQuery, sortColumn, sortDirection]);

  const totalPages = Math.max(1, Math.ceil(filteredRegulations.length / pageSize));
  const paginatedRegulations = filteredRegulations.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  useEffect(() => { setCurrentPage(1); }, [searchQuery, activeTab]);

  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  const SortIcon = ({ column }) => {
    if (sortColumn !== column) return <ArrowUpDown className="h-3 w-3 ml-1 opacity-50" />;
    return sortDirection === 'asc' ? <ArrowUp className="h-3 w-3 ml-1" /> : <ArrowDown className="h-3 w-3 ml-1" />;
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) {
      toast.error('Please select a file');
      return;
    }

    setUploading(true);
    try {
      await regulationsApi.upload(file, regData);
      setUploadOpen(false);
      setFile(null);
      setRegData({ title: '', regulatory_body: 'RBI', circular_number: '' });
      setAutofilled(false);
      setShowPanel(true);
      toast.info(`Upload started! Processing "${regData.title}" in background...`, { duration: 3000 });
    } catch (error) {
      toast.error('Upload failed: ' + (error.response?.data?.detail || 'Unknown error'));
    } finally {
      setUploading(false);
    }
  };

  const getRegulatorCount = (regulator) => {
    if (regulator === 'ALL') return regulations.length;
    return regulations.filter(r => r.regulatory_body === regulator).length;
  };

  return (
    <div className="space-y-8" data-testid="regulations-page">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold mb-2 text-gradient" data-testid="regulations-title">Regulation Repository</h1>
          <p className="text-muted-foreground">Multi-regulator compliance tracking</p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={handleTriggerCrawl}
            disabled={crawling}
            variant="outline"
            data-testid="trigger-crawl-button"
            className="btn-silver"
          >
            {crawling ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Crawling...</>
            ) : (
              <><Globe className="mr-2 h-4 w-4" /> Trigger Crawl</>
            )}
          </Button>
          <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
            <DialogTrigger asChild>
              <Button data-testid="upload-regulation-button" className="btn-shiny text-white">
                <Plus className="mr-2 h-4 w-4" /> Upload Regulation
              </Button>
            </DialogTrigger>
          <DialogContent data-testid="upload-regulation-dialog">
            <DialogHeader>
              <DialogTitle>Upload Regulation Document</DialogTitle>
              <DialogDescription>Upload a PDF of regulatory circular or guideline</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleUpload} className="space-y-4" data-testid="upload-regulation-form">
              <div>
                <Label htmlFor="reg-title">Regulation Title</Label>
                <Input
                  id="reg-title"
                  data-testid="regulation-title-input"
                  value={regData.title}
                  onChange={(e) => setRegData({ ...regData, title: e.target.value })}
                  placeholder="e.g., RBI KYC Master Directions 2025"
                  required
                />
              </div>
              <div>
                <Label htmlFor="reg-body">Regulatory Body</Label>
                <select
                  id="reg-body"
                  data-testid="regulation-body-input"
                  value={regData.regulatory_body}
                  onChange={(e) => setRegData({ ...regData, regulatory_body: e.target.value })}
                  className="w-full bg-white border border-gray-200 text-gray-900 rounded-md px-3 py-2 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 outline-none"
                  required
                >
                  {regulators.filter(r => r !== 'ALL').map(reg => (
                    <option key={reg} value={reg}>{reg}</option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="reg-circular">Circular Number</Label>
                <Input
                  id="reg-circular"
                  data-testid="regulation-circular-input"
                  value={regData.circular_number}
                  onChange={(e) => setRegData({ ...regData, circular_number: e.target.value })}
                  placeholder="e.g., RBI/2025-26/01"
                />
              </div>
              <div>
                <Label htmlFor="reg-file">Document File (PDF, DOCX, or TXT)</Label>
                <Input
                  id="reg-file"
                  data-testid="regulation-file-input"
                  type="file"
                  accept=".pdf,.docx,.doc,.txt"
                  onChange={async (e) => {
                    const selectedFile = e.target.files[0];
                    setFile(selectedFile);
                    if (selectedFile) {
                      setAutofilling(true);
                      setAutofilled(false);
                      try {
                        const parsed = await regulationsApi.parseFilename(selectedFile.name);
                        const updates = {};
                        if (parsed.title && !regData.title) updates.title = parsed.title;
                        if (parsed.regulatory_body) updates.regulatory_body = parsed.regulatory_body;
                        if (parsed.circular_number && !regData.circular_number) updates.circular_number = parsed.circular_number;
                        if (Object.keys(updates).length > 0) {
                          setRegData(prev => ({ ...prev, ...updates }));
                          setAutofilled(true);
                          toast.success('Fields auto-filled from filename', { duration: 2000 });
                        }
                      } catch (err) {
                        console.warn('Could not parse filename:', err);
                      } finally {
                        setAutofilling(false);
                      }
                    }
                  }}
                  required
                />
                {autofilling && (
                  <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                    <Loader2 className="h-3 w-3 animate-spin" /> Analyzing filename...
                  </p>
                )}
                {autofilled && (
                  <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1">
                    <CheckCircle className="h-3 w-3" /> Fields auto-filled from filename
                  </p>
                )}
              </div>
              <Button type="submit" className="w-full btn-shiny text-white" disabled={uploading} data-testid="upload-regulation-submit">
                {uploading ? 'Uploading...' : 'Upload & Extract Clauses'}
              </Button>
            </form>
          </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Crawl Status Indicator - Feature #176 */}
      {crawlStatus && crawlStatus.status !== 'no_crawls' && (
        <Card className="border border-blue-200 bg-blue-50/50" data-testid="crawl-status-card">
          <CardContent className="flex items-center gap-4 py-3 px-4">
            {crawlStatus.status === 'running' ? (
              <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />
            ) : crawlStatus.status === 'completed' ? (
              <CheckCircle className="h-5 w-5 text-green-600" />
            ) : (
              <AlertCircle className="h-5 w-5 text-red-600" />
            )}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm" data-testid="crawl-status-text">
                  {crawlStatus.status === 'running' ? 'Crawl in progress...' :
                   crawlStatus.status === 'completed' ? 'Last crawl completed' :
                   crawlStatus.status === 'failed' ? 'Crawl failed' : 'Crawl status unknown'}
                </span>
                <Badge variant={crawlStatus.status === 'completed' ? 'default' : crawlStatus.status === 'running' ? 'secondary' : 'destructive'} data-testid="crawl-status-badge">
                  {crawlStatus.status}
                </Badge>
              </div>
              {crawlStatus.status === 'completed' && crawlStatus.results && (
                <p className="text-xs text-muted-foreground mt-1" data-testid="crawl-results-text">
                  Found {crawlStatus.results.new_circulars || 0} new circular(s) from {(crawlStatus.results.sources_checked || []).join(', ')}
                  {crawlStatus.completed_at && ` — ${new Date(crawlStatus.completed_at).toLocaleString()}`}
                </p>
              )}
              {crawlStatus.status === 'completed' && crawlStatus.results?.findings?.length > 0 && (
                <div className="mt-2 space-y-1" data-testid="crawl-findings">
                  {crawlStatus.results.findings.slice(0, 3).map((finding, idx) => (
                    <div key={idx} className="text-xs flex items-center gap-2 text-muted-foreground">
                      <Badge variant="outline" className="text-xs">{finding.source}</Badge>
                      <span>{finding.title}</span>
                    </div>
                  ))}
                </div>
              )}
              {crawlStatus.error && (
                <p className="text-xs text-red-600 mt-1" data-testid="crawl-error-text">{crawlStatus.error}</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Search Bar */}
      <div className="flex gap-3" data-testid="regulations-filter-bar">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by title, circular number..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
            data-testid="regulations-search-input"
          />
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="flex-wrap h-auto bg-muted/50" data-testid="regulator-tabs">
          {regulators.map(reg => (
            <TabsTrigger key={reg} value={reg} data-testid={`regulator-tab-${reg}`} className="min-w-[100px] data-[state=active]:bg-white data-[state=active]:text-emerald-600 data-[state=active]:shadow-sm">
              {reg} ({getRegulatorCount(reg)})
            </TabsTrigger>
          ))}
        </TabsList>

        {regulators.map(reg => (
          <TabsContent key={reg} value={reg} className="mt-6">
            {loading ? (
              <div className="flex items-center justify-center h-64" data-testid="regulations-loading">
                <div className="text-muted-foreground">Loading regulations...</div>
              </div>
            ) : filteredRegulations.length === 0 ? (
              <Card className="flex flex-col items-center justify-center h-64 card-elevated" data-testid="regulations-empty">
                <CardContent className="text-center">
                  <Shield className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No {reg !== 'ALL' ? reg : ''} Regulations Yet</h3>
                  <p className="text-muted-foreground mb-4">Upload your first regulation document</p>
                  <Button onClick={() => setUploadOpen(true)} data-testid="upload-first-regulation" className="btn-shiny text-white">
                    <Upload className="mr-2 h-4 w-4" /> Upload Regulation
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4" data-testid="regulations-list-section">
                <Card>
                  <Table data-testid="regulations-table">
                    <TableHeader>
                      <TableRow>
                        <TableHead>
                          <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('title')} data-testid="sort-reg-title">
                            Title <SortIcon column="title" />
                          </button>
                        </TableHead>
                        <TableHead>
                          <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('regulatory_body')} data-testid="sort-reg-body">
                            Regulatory Body <SortIcon column="regulatory_body" />
                          </button>
                        </TableHead>
                        <TableHead>
                          <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('circular_number')} data-testid="sort-reg-circular">
                            Circular Number <SortIcon column="circular_number" />
                          </button>
                        </TableHead>
                        <TableHead>
                          <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('effective_date')} data-testid="sort-reg-date">
                            Effective Date <SortIcon column="effective_date" />
                          </button>
                        </TableHead>
                        <TableHead>Clauses</TableHead>
                        <TableHead className="w-20">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {paginatedRegulations.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={6} className="text-center py-8 text-muted-foreground" data-testid="no-reg-results">
                            No regulations match your search criteria
                          </TableCell>
                        </TableRow>
                      ) : (
                        paginatedRegulations.map((regulation) => (
                          <TableRow
                            key={regulation.id}
                            className="cursor-pointer hover:bg-muted/50"
                            data-testid={`regulation-row-${regulation.id}`}
                            onClick={() => navigate(`/regulations/${regulation.id}`)}
                          >
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Shield className="h-4 w-4 text-emerald-600 flex-shrink-0" />
                                <span className="font-medium" data-testid="reg-title-cell">
                                  {regulation.title}
                                </span>
                              </div>
                            </TableCell>
                            <TableCell data-testid="reg-body-cell">
                              <Badge variant="outline">{regulation.regulatory_body}</Badge>
                              {regulation.source === 'npci_circular' && (
                                <Badge variant="secondary" className="ml-1 text-[10px] px-1.5">Auto</Badge>
                              )}
                            </TableCell>
                            <TableCell data-testid="reg-circular-cell">
                              <span className="truncate block max-w-[120px]">
                                {regulation.circular_number || '—'}
                              </span>
                            </TableCell>
                            <TableCell data-testid="reg-date-cell">
                              {regulation.effective_date ? new Date(regulation.effective_date).toLocaleDateString() : '—'}
                            </TableCell>
                            <TableCell data-testid="reg-clauses-cell">{regulation.clauses?.length || 0}</TableCell>
                            <TableCell onClick={(e) => e.stopPropagation()}>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => navigate(`/regulations/${regulation.id}`)}
                                data-testid={`view-regulation-${regulation.id}`}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </Card>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between" data-testid="regulations-pagination">
                    <span className="text-sm text-muted-foreground">
                      Showing {(currentPage - 1) * pageSize + 1}-{Math.min(currentPage * pageSize, filteredRegulations.length)} of {filteredRegulations.length}
                    </span>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" disabled={currentPage === 1} onClick={() => setCurrentPage(prev => prev - 1)} data-testid="reg-prev-page">
                        Previous
                      </Button>
                      <Button variant="outline" size="sm" disabled={currentPage === totalPages} onClick={() => setCurrentPage(prev => prev + 1)} data-testid="reg-next-page">
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
