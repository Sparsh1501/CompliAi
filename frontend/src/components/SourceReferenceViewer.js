import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import { Separator } from './ui/separator';
import {
  FileText, Scale, Eye, Loader2, X, BookOpen,
  ChevronLeft, ChevronRight, AlertTriangle, Maximize2, Minimize2
} from 'lucide-react';
import { gapAnalysisApi } from '../lib/api';
import { toast } from 'sonner';

/**
 * SourceReferenceViewer - Displays PDF page images with highlighted sections
 * for gap analysis source references. Shows the exact page and section where
 * a policy or regulation clause was found.
 */
export default function SourceReferenceViewer({ analysisId, gapIndex, gap, onClose }) {
  const [loading, setLoading] = useState(true);
  const [sourceData, setSourceData] = useState(null);
  const [activeTab, setActiveTab] = useState('policy'); // 'policy' or 'regulation'
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (analysisId && gapIndex !== undefined && gapIndex !== null) {
      loadSourceReference();
    }
  }, [analysisId, gapIndex]);

  const loadSourceReference = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await gapAnalysisApi.getSourceReference(analysisId, gapIndex);
      setSourceData(data);
      // Auto-select the tab that has data
      if (data.regulation_source && !data.policy_source) {
        setActiveTab('regulation');
      }
    } catch (err) {
      console.error('Failed to load source reference:', err);
      setError(err.userMessage || 'Failed to load source reference');
      toast.error('Failed to load source reference');
    } finally {
      setLoading(false);
    }
  };

  const currentSource = activeTab === 'policy' ? sourceData?.policy_source : sourceData?.regulation_source;

  return (
    <div
      className={`${isFullscreen ? 'fixed inset-0 z-50 bg-background p-4' : 'relative'}`}
      data-testid="source-reference-viewer"
    >
      <Card className={`overflow-hidden ${isFullscreen ? 'h-full' : ''}`}>
        {/* Header */}
        <CardHeader className="pb-3 bg-gradient-to-r from-slate-800 to-slate-900 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-600/30 flex items-center justify-center">
                <BookOpen className="h-5 w-5 text-emerald-400" />
              </div>
              <div>
                <CardTitle className="text-lg text-white" data-testid="source-viewer-title">
                  Source Reference Viewer
                </CardTitle>
                <p className="text-sm text-slate-300">
                  Gap #{(gapIndex || 0) + 1} — {gap?.gap_type || 'Unknown'} ({gap?.severity || 'Unknown'})
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsFullscreen(!isFullscreen)}
                className="text-white hover:bg-white/10"
              >
                {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              </Button>
              {onClose && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onClose}
                  className="text-white hover:bg-white/10"
                  data-testid="close-source-viewer"
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>

          {/* Document tab selector */}
          {!loading && sourceData && (
            <div className="flex gap-2 mt-3">
              {sourceData.policy_source && (
                <Button
                  variant={activeTab === 'policy' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setActiveTab('policy')}
                  className={`gap-2 ${activeTab === 'policy' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-white/10'}`}
                  data-testid="tab-policy-source"
                >
                  <FileText className="h-4 w-4" />
                  Policy Source
                  {sourceData.policy_source.page_number && (
                    <Badge variant="outline" className="ml-1 text-xs border-current">
                      p.{sourceData.policy_source.page_number}
                    </Badge>
                  )}
                </Button>
              )}
              {sourceData.regulation_source && (
                <Button
                  variant={activeTab === 'regulation' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setActiveTab('regulation')}
                  className={`gap-2 ${activeTab === 'regulation' ? 'bg-purple-600 text-white' : 'text-slate-300 hover:bg-white/10'}`}
                  data-testid="tab-regulation-source"
                >
                  <Scale className="h-4 w-4" />
                  Regulation Source
                  {sourceData.regulation_source.page_number && (
                    <Badge variant="outline" className="ml-1 text-xs border-current">
                      p.{sourceData.regulation_source.page_number}
                    </Badge>
                  )}
                </Button>
              )}
            </div>
          )}
        </CardHeader>

        <CardContent className="p-0">
          {/* Loading state */}
          {loading && (
            <div className="flex flex-col items-center justify-center py-16" data-testid="source-viewer-loading">
              <Loader2 className="h-8 w-8 animate-spin text-emerald-600 mb-4" />
              <p className="text-muted-foreground">Loading source reference...</p>
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <AlertTriangle className="h-8 w-8 mb-4 text-amber-500" />
              <p className="font-medium">{error}</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={loadSourceReference}>
                Try Again
              </Button>
            </div>
          )}

          {/* Source reference content */}
          {!loading && !error && sourceData && currentSource && (
            <div className="flex flex-col" data-testid="source-reference-content">
              {/* Document info bar with Page & Clause numbers */}
              <div className="bg-slate-50 px-4 py-3 border-b">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-sm text-slate-900" data-testid="source-document-title">
                    {currentSource.document_title}
                  </h3>
                </div>
                <div className="flex items-center gap-3 flex-wrap">
                  <Badge
                    className={activeTab === 'policy' ? 'bg-blue-100 text-blue-800 border-blue-300' : 'bg-purple-100 text-purple-800 border-purple-300'}
                    data-testid="source-page-badge"
                  >
                    Page {currentSource.page_number}
                  </Badge>
                  {currentSource.clause_number && (
                    <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300" data-testid="source-clause-number-badge">
                      Clause #{currentSource.clause_number}
                    </Badge>
                  )}
                  {currentSource.clause_id && (
                    <Badge variant="outline" className="text-xs text-gray-600 border-gray-300" data-testid="source-clause-id-badge">
                      ID: {currentSource.clause_id.substring(0, 8)}...
                    </Badge>
                  )}
                  {currentSource.section && (
                    <span className="text-xs text-slate-600 font-medium">
                      Section: {currentSource.section}
                    </span>
                  )}
                </div>
              </div>

              <ScrollArea className={`${isFullscreen ? 'h-[calc(100vh-280px)]' : 'h-[500px]'}`} ref={scrollRef}>
                <div className="p-4 space-y-4">
                  {/* PDF Page Image */}
                  {currentSource.page_image && (
                    <div className="border rounded-lg overflow-hidden shadow-sm" data-testid="pdf-page-image-container">
                      <div className="bg-slate-100 px-3 py-2 border-b flex items-center gap-2">
                        <Eye className="h-4 w-4 text-slate-500" />
                        <span className="text-xs font-medium text-slate-600">
                          PDF Page {currentSource.page_number} Render
                        </span>
                      </div>
                      <div className="bg-white p-2 flex justify-center" data-testid="pdf-page-image-wrapper">
                        <img
                          src={`data:image/png;base64,${currentSource.page_image}`}
                          alt={`Page ${currentSource.page_number} of ${currentSource.document_title}`}
                          className="max-w-full h-auto border border-slate-200 shadow-md"
                          style={{ maxHeight: isFullscreen ? '70vh' : '450px' }}
                          data-testid="pdf-page-image"
                        />
                      </div>
                    </div>
                  )}

                  {/* No image available - show text-only view */}
                  {!currentSource.page_image && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4" data-testid="no-pdf-image-notice">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className="h-4 w-4 text-amber-600" />
                        <span className="text-sm font-medium text-amber-800">PDF page image not available</span>
                      </div>
                      <p className="text-xs text-amber-700">
                        The source document may not be a PDF or the page rendering could not be completed.
                        The clause text is shown below.
                      </p>
                    </div>
                  )}

                  <Separator />

                  {/* Highlighted Clause Text */}
                  <div data-testid="highlighted-clause-section">
                    <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-slate-900">
                      <FileText className="h-4 w-4 text-emerald-600" />
                      Relevant Clause Text
                      {currentSource.clause_number && (
                        <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300 text-xs ml-1">
                          Clause #{currentSource.clause_number}
                        </Badge>
                      )}
                    </h4>
                    {currentSource.clause_title && (
                      <p className="text-sm font-semibold text-emerald-800 mb-2 bg-emerald-50 px-3 py-1.5 rounded border border-emerald-200">
                        {currentSource.clause_title}
                      </p>
                    )}
                    <div
                      className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-lg shadow-sm"
                      data-testid="clause-text-highlight"
                    >
                      <p className="text-sm text-gray-900 leading-relaxed whitespace-pre-line">
                        {currentSource.clause_text || 'No clause text available'}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-xs text-slate-600">
                      <span className="flex items-center gap-1 font-medium">
                        <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">Page {currentSource.page_number}</span>
                      </span>
                      {currentSource.clause_number && (
                        <span className="flex items-center gap-1 font-medium">
                          <span className="bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded">Clause #{currentSource.clause_number}</span>
                        </span>
                      )}
                      {currentSource.section && (
                        <span>Section: {currentSource.section}</span>
                      )}
                    </div>
                  </div>

                  {/* Gap context */}
                  {sourceData.description && (
                    <>
                      <Separator />
                      <div>
                        <h4 className="font-semibold text-sm mb-2 flex items-center gap-2 text-slate-900">
                          <AlertTriangle className="h-4 w-4 text-amber-500" />
                          Gap Context
                        </h4>
                        <p className="text-sm text-slate-700 bg-slate-50 p-3 rounded-lg border">
                          {sourceData.description}
                        </p>
                      </div>
                    </>
                  )}
                </div>
              </ScrollArea>
            </div>
          )}

          {/* No source data available */}
          {!loading && !error && sourceData && !currentSource && (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <FileText className="h-12 w-12 mb-4 opacity-50" />
              <p className="text-lg font-medium">No source reference available</p>
              <p className="text-sm">
                {activeTab === 'policy'
                  ? 'No policy clause data available for this gap'
                  : 'No regulation clause data available for this gap'
                }
              </p>
              {sourceData.regulation_source && activeTab === 'policy' && (
                <Button variant="outline" size="sm" className="mt-4" onClick={() => setActiveTab('regulation')}>
                  View Regulation Source
                </Button>
              )}
              {sourceData.policy_source && activeTab === 'regulation' && (
                <Button variant="outline" size="sm" className="mt-4" onClick={() => setActiveTab('policy')}>
                  View Policy Source
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
