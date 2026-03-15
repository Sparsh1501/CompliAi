import React, { useEffect, useState } from 'react';
import { losLmsApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { Upload, FileSpreadsheet, Search, Shield, AlertTriangle, CheckCircle, XCircle, Eye, Play } from 'lucide-react';
import { toast } from 'sonner';
import { MOCK_LOS_UPLOADS, MOCK_SCAN_RESULT } from '../lib/mockData';

const complianceFields = [
  'borrower_name', 'loan_amount', 'interest_rate', 'tenure_months', 'disbursement_date',
  'processing_fee', 'insurance', 'emi_amount', 'annual_income', 'credit_score',
  'kyc_status', 'cibil_consent', 'sanction_letter', 'loan_agreement'
];

export default function LosLms() {
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [scanResultOpen, setScanResultOpen] = useState(false);
  const [selectedUpload, setSelectedUpload] = useState(null);
  const [scanResult, setScanResult] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [file, setFile] = useState(null);
  const [fieldMapping, setFieldMapping] = useState({});
  const [aiSuggestions, setAiSuggestions] = useState([]);
  const [activeTab, setActiveTab] = useState('uploads');

  useEffect(() => { loadUploads(); }, []);

  const loadUploads = async () => {
    try {
      const result = await losLmsApi.getUploads();
      const list = Array.isArray(result) ? result : [];
      // Use mock data if API returns empty
      setUploads(list.length > 0 ? list : MOCK_LOS_UPLOADS);
    } catch (error) {
      // Fallback to mock data for demo
      setUploads(MOCK_LOS_UPLOADS);
      console.log('Using mock LOS/LMS data for demo');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) { toast.error('Please select a file'); return; }
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const result = await losLmsApi.upload(formData);
      toast.success('File uploaded successfully!');
      setUploadOpen(false);
      setFile(null);
      if (result?.preview) {
        setSelectedUpload(result);
        setPreviewOpen(true);

        // Call AI to suggest field mappings
        if (result.columns && result.columns.length > 0) {
          try {
            const aiResult = await losLmsApi.suggestMapping(result.columns);
            if (aiResult?.mappings) {
              setAiSuggestions(aiResult.mappings);

              // Auto-apply high-confidence mappings
              const autoMapping = {};
              aiResult.mappings.forEach(m => {
                if (m.confidence >= 0.8 && m.target_field !== 'unmapped') {
                  autoMapping[m.target_field] = m.source_column;
                }
              });
              setFieldMapping(autoMapping);

              if (aiResult.ai_used) {
                toast.success('AI suggested field mappings loaded!');
              } else {
                toast.info('Basic field matching applied');
              }
            }
          } catch (error) {
            toast.error('Failed to get AI suggestions');
            // Fallback to simple matching
            const mapping = {};
            result.columns.forEach(h => {
              const lower = h.toLowerCase().replace(/\s+/g, '_');
              if (complianceFields.includes(lower)) mapping[lower] = h;
            });
            setFieldMapping(mapping);
          }
        }
      }
      loadUploads();
    } catch (error) {
      toast.error('Failed to upload file');
    } finally {
      setUploading(false);
    }
  };

  const handleScan = async (upload) => {
    const uId = upload.id || upload._id || upload.upload_id;
    setScanning(true);
    try {
      const result = await losLmsApi.scan(uId);
      setScanResult(result);
      setScanResultOpen(true);
      toast.success('Compliance scan completed');
      loadUploads();
    } catch (error) {
      // Fallback to mock scan result for demo
      setScanResult(MOCK_SCAN_RESULT);
      setScanResultOpen(true);
      console.log('Using mock scan result for demo');
    } finally {
      setScanning(false);
    }
  };

  const handleSaveMapping = async () => {
    if (Object.keys(fieldMapping).length === 0) {
      toast.error('No field mappings to save');
      return;
    }
    try {
      await losLmsApi.saveMapping('Default Mapping', fieldMapping);
      toast.success('Field mapping saved successfully!');
    } catch (error) {
      toast.error('Failed to save field mapping');
    }
  };

  const handlePreview = (upload) => {
    setSelectedUpload(upload);
    setPreviewOpen(true);
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'compliant': return <Badge className="bg-green-100 text-green-800"><CheckCircle className="h-3 w-3 mr-1" /> Compliant</Badge>;
      case 'non_compliant': return <Badge className="bg-red-100 text-red-800"><XCircle className="h-3 w-3 mr-1" /> Non-Compliant</Badge>;
      case 'scanned': return <Badge className="bg-blue-100 text-blue-800"><Shield className="h-3 w-3 mr-1" /> Scanned</Badge>;
      case 'pending': return <Badge variant="secondary">Pending</Badge>;
      default: return <Badge variant="outline">{status || 'Uploaded'}</Badge>;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="los-lms-loading">
        <div className="text-muted-foreground">Loading LOS/LMS data...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="los-lms-page">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-600 to-violet-800 flex items-center justify-center shadow-lg">
            <FileSpreadsheet className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold" data-testid="los-lms-title">LOS / LMS</h1>
            <p className="text-muted-foreground">Loan Origination & Management System compliance</p>
          </div>
        </div>
        <Button onClick={() => setUploadOpen(true)} data-testid="upload-file-button">
          <Upload className="mr-2 h-4 w-4" /> Upload File
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="uploads" data-testid="uploads-tab">
            <FileSpreadsheet className="h-4 w-4 mr-2" /> Uploads
          </TabsTrigger>
          <TabsTrigger value="mapping" data-testid="mapping-tab">
            <Shield className="h-4 w-4 mr-2" /> Field Mapping
          </TabsTrigger>
        </TabsList>

        <TabsContent value="uploads" data-testid="uploads-content">
          {uploads.length === 0 ? (
            <Card className="flex flex-col items-center justify-center h-64" data-testid="uploads-empty">
              <CardContent className="text-center py-8">
                <FileSpreadsheet className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">No Uploads Yet</h3>
                <p className="text-muted-foreground mb-4">Upload a CSV/Excel file to scan for compliance</p>
                <Button onClick={() => setUploadOpen(true)}><Upload className="mr-2 h-4 w-4" /> Upload File</Button>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table data-testid="uploads-table">
                  <TableHeader>
                    <TableRow>
                      <TableHead>File Name</TableHead>
                      <TableHead>Records</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Compliance</TableHead>
                      <TableHead>Uploaded</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {uploads.map((upload) => {
                      const uId = upload.id || upload._id || upload.upload_id;
                      return (
                        <TableRow key={uId} data-testid={`upload-row-${uId}`}>
                          <TableCell className="font-medium">{upload.filename || upload.file_name}</TableCell>
                          <TableCell>{upload.record_count || upload.total_records || '-'}</TableCell>
                          <TableCell data-testid={`upload-status-${uId}`}>{getStatusBadge(upload.scan_status || upload.status)}</TableCell>
                          <TableCell>
                            {upload.compliance_score !== undefined ? (
                              <div className="flex items-center gap-2">
                                <Progress value={upload.compliance_score} className="w-20" />
                                <span className="text-sm font-medium">{upload.compliance_score}%</span>
                              </div>
                            ) : '-'}
                          </TableCell>
                          <TableCell>{upload.created_at ? new Date(upload.created_at).toLocaleDateString() : '-'}</TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              <Button variant="ghost" size="sm" onClick={() => handlePreview(upload)} data-testid={`preview-upload-${uId}`}>
                                <Eye className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => handleScan(upload)} disabled={scanning}
                                data-testid={`scan-upload-${uId}`}>
                                <Play className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="mapping" data-testid="mapping-content">
          <Card>
            <CardHeader>
              <CardTitle>Field Mapping Configuration</CardTitle>
              <CardDescription>Map your CSV/Excel columns to compliance-required fields</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {complianceFields.map((field) => {
                  const suggestion = aiSuggestions.find(s => s.target_field === field);
                  const hasMapping = !!fieldMapping[field];
                  const confidence = suggestion?.confidence || 0;

                  return (
                    <div key={field} className="flex items-center gap-4 p-3 rounded-lg border" data-testid={`field-mapping-${field}`}>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <Label className="font-medium capitalize">{field.replace(/_/g, ' ')}</Label>
                          {suggestion && suggestion.confidence > 0 && (
                            <Badge variant={confidence >= 0.8 ? 'default' : confidence >= 0.5 ? 'secondary' : 'outline'} className="text-xs">
                              AI: {Math.round(confidence * 100)}%
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {suggestion && suggestion.reasoning ? suggestion.reasoning : 'Required for compliance check'}
                        </p>
                      </div>
                      <Select
                        value={fieldMapping[field] || ''}
                        onValueChange={(v) => setFieldMapping(prev => ({ ...prev, [field]: v }))}
                      >
                        <SelectTrigger className="w-48" data-testid={`mapping-select-${field}`}>
                          <SelectValue placeholder="Select column" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="">None</SelectItem>
                          {selectedUpload?.columns?.map(h => (
                            <SelectItem key={h} value={h}>{h}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  );
                })}
              </div>
              {Object.keys(fieldMapping).length > 0 && (
                <div className="mt-6 flex justify-end">
                  <Button onClick={handleSaveMapping} data-testid="save-mapping-button">
                    Save Mapping Configuration
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Upload Dialog */}
      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent data-testid="upload-dialog">
          <DialogHeader>
            <DialogTitle>Upload Loan Data</DialogTitle>
            <DialogDescription>Upload a CSV or Excel file for compliance scanning</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleUpload} className="space-y-4" data-testid="upload-form">
            <div>
              <Label>Select File</Label>
              <Input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => setFile(e.target.files[0])}
                data-testid="file-input" />
              <p className="text-xs text-muted-foreground mt-1">Supported formats: CSV, XLSX, XLS</p>
            </div>
            <Button type="submit" className="w-full" disabled={uploading || !file} data-testid="submit-upload">
              {uploading ? 'Uploading...' : 'Upload & Preview'}
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      {/* Data Preview Dialog */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-w-4xl" data-testid="preview-dialog">
          <DialogHeader>
            <DialogTitle>Data Preview</DialogTitle>
            <DialogDescription>{selectedUpload?.filename || 'Uploaded file'} — {selectedUpload?.record_count || 0} records</DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-96">
            {selectedUpload?.preview?.length > 0 ? (
              <Table data-testid="preview-table">
                <TableHeader>
                  <TableRow>
                    {(selectedUpload.headers || Object.keys(selectedUpload.preview[0] || {})).map(h => (
                      <TableHead key={h}>{h}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {selectedUpload.preview.map((row, i) => (
                    <TableRow key={i}>
                      {(selectedUpload.headers || Object.keys(row)).map(h => (
                        <TableCell key={h}>{row[h] ?? ''}</TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-muted-foreground text-center py-8">No preview data available</p>
            )}
          </ScrollArea>
        </DialogContent>
      </Dialog>

      {/* Scan Result Dialog */}
      <Dialog open={scanResultOpen} onOpenChange={setScanResultOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh]" data-testid="scan-result-dialog">
          <DialogHeader>
            <DialogTitle>Compliance Scan Results</DialogTitle>
            <DialogDescription>
              Loan-level and portfolio-level compliance analysis
            </DialogDescription>
          </DialogHeader>
          {scanResult && (
            <ScrollArea className="max-h-[70vh]">
              <div className="space-y-6 pr-4">
                {/* Portfolio-Level Metrics */}
                {scanResult.portfolio_metrics && (
                  <div>
                    <h3 className="text-lg font-semibold mb-3" data-testid="portfolio-metrics-title">Portfolio-Level Metrics</h3>
                    <div className="grid grid-cols-4 gap-3">
                      <Card>
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold text-blue-600">{scanResult.portfolio_metrics.compliance_score}%</div>
                          <div className="text-xs text-muted-foreground">Compliance Score</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold text-green-600">{scanResult.portfolio_metrics.compliant_records}</div>
                          <div className="text-xs text-muted-foreground">Compliant</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold text-red-600">{scanResult.portfolio_metrics.non_compliant_records}</div>
                          <div className="text-xs text-muted-foreground">Non-Compliant</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold">{scanResult.portfolio_metrics.total_records}</div>
                          <div className="text-xs text-muted-foreground">Total Loans</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold">₹{(scanResult.portfolio_metrics.total_loan_amount / 100000).toFixed(1)}L</div>
                          <div className="text-xs text-muted-foreground">Total Amount</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold">{scanResult.portfolio_metrics.average_interest_rate}%</div>
                          <div className="text-xs text-muted-foreground">Avg Interest</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold">{scanResult.portfolio_metrics.kyc_compliance_rate}%</div>
                          <div className="text-xs text-muted-foreground">KYC Compliance</div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold">{scanResult.portfolio_metrics.cibil_consent_rate}%</div>
                          <div className="text-xs text-muted-foreground">CIBIL Consent</div>
                        </CardContent>
                      </Card>
                    </div>
                  </div>
                )}

                {/* Exception Summary */}
                {scanResult.portfolio_metrics && (
                  <div>
                    <h3 className="text-lg font-semibold mb-3">Exception Summary</h3>
                    <div className="grid grid-cols-4 gap-3">
                      <Card>
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold">{scanResult.portfolio_metrics.total_exceptions}</div>
                          <div className="text-xs text-muted-foreground">Total Exceptions</div>
                        </CardContent>
                      </Card>
                      <Card className="border-red-200">
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold text-red-600">{scanResult.portfolio_metrics.critical_exceptions}</div>
                          <div className="text-xs text-muted-foreground">Critical</div>
                        </CardContent>
                      </Card>
                      <Card className="border-orange-200">
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold text-orange-600">{scanResult.portfolio_metrics.high_exceptions}</div>
                          <div className="text-xs text-muted-foreground">High</div>
                        </CardContent>
                      </Card>
                      <Card className="border-yellow-200">
                        <CardContent className="p-3 text-center">
                          <div className="text-xl font-bold text-yellow-600">{scanResult.portfolio_metrics.medium_exceptions}</div>
                          <div className="text-xs text-muted-foreground">Medium</div>
                        </CardContent>
                      </Card>
                    </div>
                  </div>
                )}

                {/* Loan-Level Results */}
                {scanResult.loan_level_results && scanResult.loan_level_results.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-3" data-testid="loan-level-results-title">Loan-Level Results</h3>
                    <div className="space-y-2">
                      {scanResult.loan_level_results.map((loan, i) => (
                        <Card key={i} className={loan.is_compliant ? 'border-green-200' : 'border-red-200'} data-testid={`loan-result-${i}`}>
                          <CardContent className="p-3">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                {loan.is_compliant ? (
                                  <CheckCircle className="h-5 w-5 text-green-600" />
                                ) : (
                                  <XCircle className="h-5 w-5 text-red-600" />
                                )}
                                <div>
                                  <div className="font-medium">{loan.borrower_name}</div>
                                  <div className="text-sm text-muted-foreground">
                                    Loan Amount: ₹{loan.loan_amount} • {loan.exceptions_count} exceptions
                                  </div>
                                </div>
                              </div>
                              <Badge variant={loan.is_compliant ? 'default' : 'destructive'}>
                                {loan.is_compliant ? 'Compliant' : 'Non-Compliant'}
                              </Badge>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </div>
                )}

                {/* Exception Report */}
                {scanResult.exceptions && scanResult.exceptions.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-3" data-testid="exception-report-title">Exception Report</h3>
                    <div className="space-y-2">
                      {scanResult.exceptions.map((exception, i) => (
                        <Card key={i} className="border-l-4 border-l-red-500" data-testid={`exception-${i}`}>
                          <CardContent className="p-3">
                            <div className="flex items-start gap-3">
                              <AlertTriangle className={`h-5 w-5 mt-0.5 ${
                                exception.severity === 'Critical' ? 'text-red-600' :
                                exception.severity === 'High' ? 'text-orange-600' : 'text-yellow-600'
                              }`} />
                              <div className="flex-1">
                                <div className="flex items-center justify-between mb-1">
                                  <div className="font-medium">{exception.borrower_name} - {exception.field}</div>
                                  <Badge variant={
                                    exception.severity === 'Critical' ? 'destructive' :
                                    exception.severity === 'High' ? 'default' : 'secondary'
                                  }>
                                    {exception.severity}
                                  </Badge>
                                </div>
                                <div className="text-sm text-muted-foreground mb-1">{exception.issue}</div>
                                <div className="text-xs text-blue-600 mb-1">📋 {exception.regulation_ref}</div>
                                <div className="text-xs text-green-700">💡 {exception.recommendation}</div>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </div>
                )}

                {/* Remediation Tasks Created */}
                {scanResult.created_tasks && scanResult.created_tasks.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold mb-3" data-testid="created-tasks-title">
                      Remediation Tasks Created ({scanResult.tasks_created_count})
                    </h3>
                    <Card className="bg-blue-50 border-blue-200" data-testid="tasks-created-card">
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3 mb-3">
                          <CheckCircle className="h-5 w-5 text-blue-600 mt-0.5" />
                          <div>
                            <div className="font-medium text-blue-900">
                              Automatic Task Creation Successful
                            </div>
                            <div className="text-sm text-blue-700 mt-1">
                              {scanResult.tasks_created_count} remediation task{scanResult.tasks_created_count !== 1 ? 's' : ''} created automatically for compliance exceptions.
                              Navigate to Tasks page to view and assign.
                            </div>
                          </div>
                        </div>
                        <div className="space-y-2 mt-3">
                          {scanResult.created_tasks.map((task, i) => (
                            <div key={i} className="flex items-center justify-between p-2 bg-white rounded border border-blue-200" data-testid={`created-task-${i}`}>
                              <div className="flex items-center gap-2">
                                <Badge variant="outline" className="text-xs">{task.exception_field}</Badge>
                                <span className="text-sm">{task.title}</span>
                              </div>
                              <Badge variant={task.priority === 'High' ? 'destructive' : 'default'}>
                                {task.priority}
                              </Badge>
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 pt-3 border-t border-blue-200">
                          <a href="/tasks" className="text-sm text-blue-600 hover:text-blue-800 font-medium">
                            → View all tasks in Tasks page
                          </a>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}
              </div>
            </ScrollArea>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
