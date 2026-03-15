import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { policiesApi } from '../lib/api';
import { useUpload } from '../context/UploadContext';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Checkbox } from '../components/ui/checkbox';
import { Badge } from '../components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import { FileText, Plus, Upload, Sparkles, X, Eye, ChevronRight, Search, ArrowUpDown, ArrowUp, ArrowDown, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

const policyTypes = [
  { value: 'KYC', label: 'KYC Policy' },
  { value: 'AML', label: 'AML Policy' },
  { value: 'Digital Lending', label: 'Digital Lending Policy' },
  { value: 'InfoSec', label: 'Information Security Policy' },
  { value: 'Outsourcing', label: 'Outsourcing Policy' },
  { value: 'Risk Management', label: 'Risk Management Policy' },
  { value: 'Fraud Management', label: 'Fraud Management Policy' },
  { value: 'UPI/Payments', label: 'UPI/Payments Policy' },
  { value: 'Other', label: 'Other Policy' }
];

const statusConfig = {
  draft: { color: 'bg-amber-100 text-amber-700', label: 'Draft' },
  active: { color: 'bg-emerald-100 text-emerald-700', label: 'Active' },
  archived: { color: 'bg-gray-100 text-gray-500', label: 'Archived' },
  review: { color: 'bg-blue-100 text-blue-700', label: 'Under Review' },
  approved: { color: 'bg-green-100 text-green-700', label: 'Approved' },
  rejected: { color: 'bg-red-100 text-red-700', label: 'Rejected' },
};

export default function Policies() {
  const navigate = useNavigate();
  const { setShowPanel } = useUpload();
  const { user } = useAuth();
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);

  // Check if user is auditor (read-only access)
  const isAuditor = user?.role === 'auditor';
  const canModify = !isAuditor;
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [file, setFile] = useState(null);
  const [fileName, setFileName] = useState('');
  const [policyData, setPolicyData] = useState({
    title: '',
    policy_type: 'OTHER',
    version: '1.0',
    department: ''
  });

  // Search, filter, sort state
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [sortColumn, setSortColumn] = useState('updated_at');
  const [sortDirection, setSortDirection] = useState('desc');
  const searchTimerRef = useRef(null);

  // Debounce search input - waits 300ms after user stops typing
  const handleSearchChange = useCallback((value) => {
    setSearchQuery(value);
    if (searchTimerRef.current) {
      clearTimeout(searchTimerRef.current);
    }
    searchTimerRef.current = setTimeout(() => {
      setDebouncedSearchQuery(value);
    }, 300);
  }, []);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (searchTimerRef.current) {
        clearTimeout(searchTimerRef.current);
      }
    };
  }, []);

  // Bulk selection state
  const [selectedPolicies, setSelectedPolicies] = useState(new Set());
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 10;

  useEffect(() => {
    loadPolicies();
  }, []);

  const loadPolicies = async () => {
    try {
      const response = await policiesApi.getAll();
      setPolicies(response);
    } catch (error) {
      toast.error('Failed to load policies');
    } finally {
      setLoading(false);
    }
  };

  // Filtered and sorted policies (uses debounced search for performance)
  const filteredPolicies = useMemo(() => {
    const startTime = performance.now();
    let result = [...policies];

    // Search filter - uses debounced value to avoid filtering on every keystroke
    const trimmedSearch = debouncedSearchQuery.trim();
    if (trimmedSearch) {
      const q = trimmedSearch.toLowerCase();
      result = result.filter(p =>
        p.title?.toLowerCase().includes(q) ||
        p.department?.toLowerCase().includes(q) ||
        p.policy_type?.toLowerCase().includes(q)
      );
    }

    // Type filter
    if (typeFilter !== 'ALL') {
      result = result.filter(p => p.policy_type === typeFilter);
    }

    // Status filter
    if (statusFilter !== 'ALL') {
      result = result.filter(p => (p.status || 'Draft').toLowerCase() === statusFilter.toLowerCase());
    }

    // Sort
    result.sort((a, b) => {
      let aVal = a[sortColumn] || '';
      let bVal = b[sortColumn] || '';
      if (sortColumn === 'updated_at' || sortColumn === 'created_at') {
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

    const elapsed = performance.now() - startTime;
    if (elapsed > 100) {
      console.warn(`Search filtering took ${elapsed.toFixed(0)}ms`);
    }

    return result;
  }, [policies, debouncedSearchQuery, typeFilter, statusFilter, sortColumn, sortDirection]);

  // Paginated policies
  const totalPages = Math.max(1, Math.ceil(filteredPolicies.length / pageSize));
  const paginatedPolicies = filteredPolicies.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  // Reset page when filters change (uses debounced search to stay in sync)
  useEffect(() => { setCurrentPage(1); }, [debouncedSearchQuery, typeFilter, statusFilter]);

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

  const toggleSelectAll = () => {
    if (selectedPolicies.size === paginatedPolicies.length) {
      setSelectedPolicies(new Set());
    } else {
      setSelectedPolicies(new Set(paginatedPolicies.map(p => p.id)));
    }
  };

  const toggleSelect = (id) => {
    const newSet = new Set(selectedPolicies);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setSelectedPolicies(newSet);
  };

  const handleBulkDelete = async () => {
    setBulkDeleting(true);
    try {
      const ids = Array.from(selectedPolicies);
      await policiesApi.bulkDelete(ids);
      toast.success(`Deleted ${ids.length} policies`);
      setSelectedPolicies(new Set());
      setBulkDeleteOpen(false);
      await loadPolicies();
    } catch (error) {
      toast.error('Failed to delete policies: ' + (error.response?.data?.detail || 'Unknown error'));
    } finally {
      setBulkDeleting(false);
    }
  };

  const resetUploadForm = () => {
    setFile(null);
    setFileName('');
    setUploadProgress(0);
    setPolicyData({
      title: '',
      policy_type: 'OTHER',
      version: '1.0',
      department: ''
    });
  };

  const handleOpenUploadDialog = () => {
    resetUploadForm();
    setUploadDialogOpen(true);
  };

  const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt'];
  const MAX_FILE_SIZE_MB = 50;
  const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

  const validateFileType = (selectedFile) => {
    if (!selectedFile) return null;
    const ext = selectedFile.name.substring(selectedFile.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported file format: "${ext}". Only PDF, DOCX, and TXT files are supported for policy upload.`;
    }
    return null;
  };

  const validateFileSize = (selectedFile) => {
    if (!selectedFile) return null;
    if (selectedFile.size > MAX_FILE_SIZE_BYTES) {
      const fileSizeMB = (selectedFile.size / (1024 * 1024)).toFixed(1);
      return `File too large (${fileSizeMB}MB). Maximum file size is ${MAX_FILE_SIZE_MB}MB. Please reduce the file size and try again.`;
    }
    return null;
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      // Validate file type first
      const typeError = validateFileType(selectedFile);
      if (typeError) {
        toast.error(typeError);
        setFile(null);
        setFileName('');
        // Reset the file input so the same file can be re-selected
        e.target.value = '';
        return;
      }
      // Validate file size
      const sizeError = validateFileSize(selectedFile);
      if (sizeError) {
        toast.error(sizeError);
        setFile(null);
        setFileName('');
        e.target.value = '';
        return;
      }
      setFile(selectedFile);
      setFileName(selectedFile.name);
      if (!policyData.title) {
        // Remove file extension from title (supports .pdf, .docx, .doc, .txt)
        const titleWithoutExt = selectedFile.name.replace(/\.(pdf|docx|doc|txt)$/i, '');
        setPolicyData({ ...policyData, title: titleWithoutExt });
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      toast.error('Please select a file (PDF, DOCX, or TXT)');
      return;
    }

    // Double-check file type before submission
    const validationError = validateFileType(file);
    if (validationError) {
      toast.error(validationError);
      return;
    }

    // Double-check file size before submission
    const sizeError = validateFileSize(file);
    if (sizeError) {
      toast.error(sizeError);
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    try {
      const onUploadProgress = (progressEvent) => {
        if (progressEvent.total) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percentCompleted);
        }
      };
      await policiesApi.upload(file, policyData, onUploadProgress);
      setUploadProgress(100);
      setUploadDialogOpen(false);
      resetUploadForm();
      setShowPanel(true);
      toast.info(`Upload started! Processing "${policyData.title}" in background...`, { duration: 3000 });
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.userMessage || 'Unknown error';
      toast.error('Upload failed: ' + errorMsg);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const getStatusBadge = (status) => {
    const cfg = statusConfig[(status || 'draft').toLowerCase()] || statusConfig.draft;
    return <Badge className={cfg.color} data-testid="policy-status-badge">{cfg.label}</Badge>;
  };

  return (
    <div className="space-y-8" data-testid="policies-page">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold mb-2 text-gradient" data-testid="policies-title">Policy Repository</h1>
          <p className="text-muted-foreground">Manage your internal compliance policies</p>
        </div>
        {canModify && (
          <Button
            onClick={handleOpenUploadDialog}
            data-testid="upload-policy-button"
            className="btn-shiny text-white"
          >
            <Plus className="mr-2 h-4 w-4" /> Upload Policy
          </Button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64" data-testid="policies-loading">
          <div className="text-muted-foreground">Loading policies...</div>
        </div>
      ) : policies.length === 0 ? (
        <Card className="flex flex-col items-center justify-center h-64 card-elevated" data-testid="policies-empty">
          <CardContent className="text-center">
            <FileText className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Policies Yet</h3>
            <p className="text-muted-foreground mb-4">
              {isAuditor ? 'No policies to review' : 'Upload your first policy document to get started'}
            </p>
            {canModify && (
              <Button onClick={handleOpenUploadDialog} data-testid="upload-first-policy" className="btn-shiny text-white">
                <Upload className="mr-2 h-4 w-4" /> Upload Policy
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4" data-testid="policies-list-section">
          {/* Search and Filter Bar */}
          <div className="flex flex-col sm:flex-row gap-3" data-testid="policies-filter-bar">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search policies..."
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="pl-9"
                data-testid="policies-search-input"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-[180px]" data-testid="policies-type-filter">
                <SelectValue placeholder="Filter by type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All Types</SelectItem>
                {policyTypes.map((type) => (
                  <SelectItem key={type.value} value={type.value}>{type.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[160px]" data-testid="policies-status-filter">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All Statuses</SelectItem>
                <SelectItem value="Draft">Draft</SelectItem>
                <SelectItem value="Review">Under Review</SelectItem>
                <SelectItem value="Approved">Approved</SelectItem>
                <SelectItem value="Archived">Archived</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Bulk Action Toolbar */}
          {selectedPolicies.size > 0 && canModify && (
            <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg" data-testid="bulk-action-toolbar">
              <span className="text-sm font-medium">{selectedPolicies.size} selected</span>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setBulkDeleteOpen(true)}
                data-testid="bulk-delete-button"
              >
                <Trash2 className="h-4 w-4 mr-1" /> Delete Selected
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedPolicies(new Set())}
                data-testid="clear-selection-button"
              >
                Clear Selection
              </Button>
            </div>
          )}

          {/* Data Table */}
          <Card>
            <Table data-testid="policies-table">
              <TableHeader>
                <TableRow>
                  {canModify && (
                    <TableHead className="w-12">
                      <Checkbox
                        checked={paginatedPolicies.length > 0 && selectedPolicies.size === paginatedPolicies.length}
                        onCheckedChange={toggleSelectAll}
                        data-testid="select-all-checkbox"
                      />
                    </TableHead>
                  )}
                  <TableHead>
                    <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('title')} data-testid="sort-title">
                      Title <SortIcon column="title" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('policy_type')} data-testid="sort-type">
                      Type <SortIcon column="policy_type" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('status')} data-testid="sort-status">
                      Status <SortIcon column="status" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('department')} data-testid="sort-department">
                      Department <SortIcon column="department" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button className="flex items-center font-medium hover:text-foreground" onClick={() => handleSort('updated_at')} data-testid="sort-updated">
                      Updated <SortIcon column="updated_at" />
                    </button>
                  </TableHead>
                  <TableHead className="w-20">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedPolicies.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={canModify ? 7 : 6} className="text-center py-8 text-muted-foreground" data-testid="no-results">
                      No policies match your search criteria
                    </TableCell>
                  </TableRow>
                ) : (
                  paginatedPolicies.map((policy) => (
                    <TableRow
                      key={policy.id}
                      className="cursor-pointer hover:bg-muted/50"
                      data-testid={`policy-row-${policy.id}`}
                      onClick={() => navigate(`/policies/${policy.id}`)}
                    >
                      {canModify && (
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            checked={selectedPolicies.has(policy.id)}
                            onCheckedChange={() => toggleSelect(policy.id)}
                            data-testid={`select-policy-${policy.id}`}
                          />
                        </TableCell>
                      )}
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-emerald-600 flex-shrink-0" />
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="font-medium truncate max-w-[250px] block" data-testid="policy-title-cell">
                                  {policy.title}
                                </span>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p className="max-w-xs">{policy.title}</p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </div>
                      </TableCell>
                      <TableCell data-testid="policy-type-cell">
                        <span className="truncate block max-w-[150px]">
                          {policy.policy_type?.replace(/_/g, ' ')}
                        </span>
                      </TableCell>
                      <TableCell data-testid="policy-status-cell">{getStatusBadge(policy.status)}</TableCell>
                      <TableCell data-testid="policy-department-cell">
                        <span className="truncate block max-w-[120px]">
                          {policy.department || '—'}
                        </span>
                      </TableCell>
                      <TableCell data-testid="policy-updated-cell">
                        {policy.updated_at ? new Date(policy.updated_at).toLocaleDateString() : '—'}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/policies/${policy.id}`)}
                          data-testid={`view-policy-${policy.id}`}
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
            <div className="flex items-center justify-between" data-testid="policies-pagination">
              <span className="text-sm text-muted-foreground">
                Showing {(currentPage - 1) * pageSize + 1}-{Math.min(currentPage * pageSize, filteredPolicies.length)} of {filteredPolicies.length}
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
        </div>
      )}

      {/* Bulk Delete Confirmation */}
      <AlertDialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}>
        <AlertDialogContent data-testid="bulk-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {selectedPolicies.size} Policies?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the selected policies and all their associated clauses.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="bulk-delete-cancel">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleBulkDelete}
              className="bg-red-600 hover:bg-red-700"
              disabled={bulkDeleting}
              data-testid="bulk-delete-confirm"
            >
              {bulkDeleting ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Upload Policy Dialog */}
      <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Upload Policy Document
            </DialogTitle>
            <DialogDescription>
              Upload a PDF policy document for AI-powered clause extraction and analysis
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit} className="space-y-5" data-testid="upload-policy-form">
            {/* File Upload Section */}
            <div className="border-2 border-dashed border-border rounded-lg p-6 text-center hover:border-primary/50 transition-colors" data-testid="file-drop-zone">
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                  <Upload className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <Label
                    htmlFor="file-upload"
                    className="cursor-pointer text-base font-semibold text-primary hover:text-primary/80"
                  >
                    Click to upload document
                  </Label>
                  <p className="text-xs text-muted-foreground mt-1">
                    Supports PDF, DOCX, TXT • Maximum file size: 50MB
                  </p>
                </div>
                <Input
                  id="file-upload"
                  type="file"
                  accept=".pdf,.docx,.doc,.txt"
                  onChange={handleFileChange}
                  className="hidden"
                  data-testid="file-input"
                />
                {fileName && (
                  <div className="w-full space-y-2" data-testid="upload-progress">
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-primary/10 rounded-md">
                      <FileText className="h-4 w-4 text-primary" />
                      <span className="text-sm font-medium truncate">{fileName}</span>
                      {file && (
                        <span className="text-xs text-muted-foreground whitespace-nowrap" data-testid="file-size-display">
                          ({(file.size / (1024 * 1024)).toFixed(1)} MB)
                        </span>
                      )}
                      {!uploading && (
                        <button
                          type="button"
                          onClick={() => { setFile(null); setFileName(''); }}
                          className="ml-auto text-muted-foreground hover:text-foreground flex-shrink-0"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                    {uploading && (
                      <div className="space-y-1" data-testid="upload-progress-bar">
                        <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                          <div
                            className="bg-blue-500 h-full rounded-full transition-all duration-300 ease-out"
                            style={{ width: `${uploadProgress}%` }}
                            data-testid="upload-progress-fill"
                          />
                        </div>
                        <p className="text-xs text-muted-foreground text-center" data-testid="upload-progress-text">
                          {uploadProgress < 100
                            ? `Uploading... ${uploadProgress}%`
                            : 'Upload complete! Processing document...'}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Policy Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="policy-title">Policy Title *</Label>
                <Input
                  id="policy-title"
                  data-testid="policy-title-input"
                  value={policyData.title}
                  onChange={(e) => setPolicyData({ ...policyData, title: e.target.value })}
                  placeholder="e.g., KYC Policy 2025"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="policy-type">Policy Type *</Label>
                <Select
                  value={policyData.policy_type}
                  onValueChange={(value) => setPolicyData({ ...policyData, policy_type: value })}
                >
                  <SelectTrigger data-testid="policy-type-select">
                    <SelectValue placeholder="Select policy type" />
                  </SelectTrigger>
                  <SelectContent>
                    {policyTypes.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="policy-version">Version</Label>
                <Input
                  id="policy-version"
                  data-testid="policy-version-input"
                  value={policyData.version}
                  onChange={(e) => setPolicyData({ ...policyData, version: e.target.value })}
                  placeholder="e.g., 1.0"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="policy-department">Department (Optional)</Label>
                <Input
                  id="policy-department"
                  data-testid="policy-department-input"
                  value={policyData.department}
                  onChange={(e) => setPolicyData({ ...policyData, department: e.target.value })}
                  placeholder="e.g., Compliance"
                />
              </div>
            </div>

            {/* AI Features Info */}
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <Sparkles className="h-4 w-4 text-emerald-600 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-medium text-gray-900 text-sm">
                    AI-Powered Processing
                  </h3>
                  <p className="text-xs text-gray-500">
                    Your policy will be automatically processed to extract clauses and identify key sections.
                  </p>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setUploadDialogOpen(false)}
                className="flex-1"
                disabled={uploading}
                data-testid="cancel-button"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                className="flex-1"
                disabled={uploading || !file}
                data-testid="upload-submit-button"
              >
                {uploading ? (
                  <>
                    <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    {uploadProgress < 100 ? `Uploading ${uploadProgress}%...` : 'Processing...'}
                  </>
                ) : (
                  <>
                    <Upload className="mr-2 h-4 w-4" />
                    Upload Policy
                  </>
                )}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
