import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { 
  Collapsible, 
  CollapsibleContent, 
  CollapsibleTrigger 
} from './ui/collapsible';
import { ScrollArea } from './ui/scroll-area';
import { Separator } from './ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { 
  ChevronDown, 
  ChevronRight, 
  AlertCircle, 
  CheckCircle, 
  Info, 
  Shield, 
  Target, 
  Users, 
  Tag, 
  FileCheck,
  Lightbulb,
  Filter,
  Search,
  List,
  LayoutGrid,
  Edit,
  Trash2,
  ClipboardCheck,
  BookOpen,
  Link2
} from 'lucide-react';
import { Input } from './ui/input';

// Color mappings for requirement types
const requirementTypeConfig = {
  mandatory: { 
    color: 'bg-[#F87171]/20 text-[#F87171] border-[#F87171]/30', 
    icon: AlertCircle,
    label: 'Mandatory',
    description: 'Must comply'
  },
  recommended: { 
    color: 'bg-[#60A5FA]/20 text-[#60A5FA] border-[#60A5FA]/30', 
    icon: Lightbulb,
    label: 'Recommended',
    description: 'Should comply'
  },
  prohibition: { 
    color: 'bg-[#FBAD41]/20 text-[#FBAD41] border-[#FBAD41]/30', 
    icon: Shield,
    label: 'Prohibition',
    description: 'Must not do'
  },
  informational: { 
    color: 'bg-[#808089]/20 text-[#808089] border-[#808089]/30', 
    icon: Info,
    label: 'Informational',
    description: 'For reference'
  },
  conditional: { 
    color: 'bg-[#A78BFA]/20 text-[#A78BFA] border-[#A78BFA]/30', 
    icon: Target,
    label: 'Conditional',
    description: 'If-then rule'
  }
};

// Color mappings for criticality
const criticalityConfig = {
  high: { color: 'bg-[#F87171] text-white', label: 'High Priority' },
  medium: { color: 'bg-[#FBAD41] text-[#111113]', label: 'Medium Priority' },
  low: { color: 'bg-[#34D399] text-[#111113]', label: 'Low Priority' }
};

// Subject category display names
const categoryLabels = {
  data_protection: 'Data Protection',
  customer_due_diligence: 'Customer Due Diligence (KYC)',
  reporting_requirements: 'Reporting Requirements',
  risk_management: 'Risk Management',
  internal_controls: 'Internal Controls',
  governance: 'Governance',
  audit_compliance: 'Audit & Compliance',
  record_keeping: 'Record Keeping',
  disclosure: 'Disclosure',
  licensing_authorization: 'Licensing & Authorization',
  operational_procedures: 'Operational Procedures',
  training_awareness: 'Training & Awareness',
  third_party_management: 'Third Party Management',
  incident_management: 'Incident Management',
  technology_security: 'Technology & Security',
  financial_limits: 'Financial Limits',
  customer_rights: 'Customer Rights',
  anti_money_laundering: 'Anti-Money Laundering',
  fraud_prevention: 'Fraud Prevention',
  business_continuity: 'Business Continuity',
  general: 'General'
};

// Single Clause Card Component
const ClauseCard = ({ clause, index, isExpanded, onToggle, onEdit, onDelete, documentType }) => {
  const reqType = requirementTypeConfig[clause.requirement_type] || requirementTypeConfig.informational;
  const criticality = criticalityConfig[clause.criticality] || criticalityConfig.medium;
  const ReqIcon = reqType.icon;
  
  // Get the title - use new title field, fallback to section
  const displayTitle = clause.title || clause.section || `Clause ${index + 1}`;
  
  // Get the content - use new content field, fallback to text
  const displayContent = clause.content || clause.text || clause.original_text || '';
  
  // Get tags - use new tags field, fallback to keywords
  const displayTags = clause.tags && clause.tags.length > 0 ? clause.tags : clause.keywords || [];
  
  return (
    <Card className={`mb-3 border-l-4 ${clause.criticality === 'high' ? 'border-l-red-500' : clause.criticality === 'medium' ? 'border-l-yellow-500' : 'border-l-green-500'} hover:shadow-md transition-shadow`}>
      <Collapsible open={isExpanded} onOpenChange={onToggle}>
        <CollapsibleTrigger className="w-full">
          <CardHeader className="pb-2">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3 flex-1">
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-sm font-semibold">
                  {index + 1}
                </div>
                <div className="flex-1 text-left">
                  {/* NEW: Prominent Title Display */}
                  <h3 className="text-base font-semibold text-foreground mb-2 uppercase tracking-wide">
                    {displayTitle}
                  </h3>
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <Badge className={`${reqType.color} border`}>
                      <ReqIcon className="w-3 h-3 mr-1" />
                      {reqType.label}
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      {categoryLabels[clause.subject_category] || clause.subject_category}
                    </Badge>
                    <Badge className={`${criticality.color} text-xs`}>
                      {criticality.label}
                    </Badge>
                  </div>
                  {/* NEW: Tags Display */}
                  {displayTags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {displayTags.slice(0, 5).map((tag, i) => (
                        <Badge key={i} variant="secondary" className="text-xs bg-gray-100 text-gray-700">
                          #{tag}
                        </Badge>
                      ))}
                      {displayTags.length > 5 && (
                        <Badge variant="secondary" className="text-xs">+{displayTags.length - 5} more</Badge>
                      )}
                    </div>
                  )}
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {clause.semantic_summary || displayContent?.substring(0, 150) + '...'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1 text-muted-foreground">
                {(onEdit || onDelete) && (
                  <div className="flex gap-0.5" onClick={(e) => e.stopPropagation()}>
                    {onEdit && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0"
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); onEdit(clause); }}
                        data-testid={`edit-clause-${clause.clause_id || index}`}
                      >
                        <Edit className="w-3.5 h-3.5" />
                      </Button>
                    )}
                    {onDelete && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0 text-red-600 hover:text-red-700"
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDelete(clause); }}
                        data-testid={`delete-clause-${clause.clause_id || index}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    )}
                  </div>
                )}
                {isExpanded ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
              </div>
            </div>
          </CardHeader>
        </CollapsibleTrigger>
        
        <CollapsibleContent>
          <CardContent className="pt-0">
            <Separator className="my-3" />
            
            {/* NEW: Content Section */}
            {displayContent && (
              <div className="mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
                <h4 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                  <FileCheck className="w-4 h-4" />
                  Clause Content
                </h4>
                <p className="text-sm text-gray-700 whitespace-pre-wrap">
                  {displayContent}
                </p>
              </div>
            )}
            
            {/* Semantic Summary (LLM Understanding) */}
            {clause.semantic_summary && (
              <div className="mb-4 p-3 bg-emerald-50 rounded-lg border border-emerald-200">
                <div className="flex items-start gap-2">
                  <Lightbulb className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900 mb-1">
                      AI Understanding (Anthropic Claude)
                    </h4>
                    <p className="text-sm text-gray-700">
                      {clause.semantic_summary}
                    </p>
                  </div>
                </div>
              </div>
            )}
            
            {/* All Tags */}
            {displayTags.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <Tag className="w-4 h-4 text-primary" />
                  Tags
                </h4>
                <div className="flex flex-wrap gap-1">
                  {displayTags.map((tag, i) => (
                    <Badge key={i} variant="outline" className="text-xs bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                      #{tag}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            
            {/* Key Obligations */}
            {clause.key_obligations && clause.key_obligations.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <Target className="w-4 h-4 text-primary" />
                  Key Obligations
                </h4>
                <ul className="space-y-1">
                  {clause.key_obligations.map((obligation, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <CheckCircle className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                      <span>{obligation}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Entities Involved */}
            {clause.entities_involved && clause.entities_involved.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <Users className="w-4 h-4 text-primary" />
                  Responsible Parties
                </h4>
                <div className="flex flex-wrap gap-2">
                  {clause.entities_involved.map((entity, i) => (
                    <Badge key={i} variant="secondary">{entity}</Badge>
                  ))}
                </div>
              </div>
            )}
            
            {/* Compliance Indicators */}
            {clause.compliance_indicators && clause.compliance_indicators.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <FileCheck className="w-4 h-4 text-primary" />
                  Compliance Evidence
                </h4>
                <ul className="space-y-1">
                  {clause.compliance_indicators.map((indicator, i) => (
                    <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                      <span className="text-green-600">✓</span>
                      {indicator}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Keywords (only show if different from tags) */}
            {clause.keywords && clause.keywords.length > 0 && (!clause.tags || clause.tags.length === 0) && (
              <div className="mb-4">
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <Tag className="w-4 h-4 text-primary" />
                  Keywords
                </h4>
                <div className="flex flex-wrap gap-1">
                  {clause.keywords.map((keyword, i) => (
                    <Badge key={i} variant="outline" className="text-xs bg-muted">
                      {keyword}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            
            {/* === POLICY-SPECIFIC SECTIONS === */}
            {/* Implementation Evidence (policy only) */}
            {documentType === 'policy' && clause.implementation_evidence && clause.implementation_evidence.length > 0 && (
              <div className="mb-4 p-3 bg-green-50 rounded-lg border border-green-200">
                <h4 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                  <ClipboardCheck className="w-4 h-4 text-green-600" />
                  Implementation Evidence
                </h4>
                <ul className="space-y-1">
                  {clause.implementation_evidence.map((evidence, i) => (
                    <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                      <CheckCircle className="w-3.5 h-3.5 text-green-600 mt-0.5 flex-shrink-0" />
                      <span>{evidence}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Processes Described (policy only) */}
            {documentType === 'policy' && clause.processes_described && clause.processes_described.length > 0 && (
              <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                <h4 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-blue-600" />
                  Processes Described
                </h4>
                <ul className="space-y-1">
                  {clause.processes_described.map((process, i) => (
                    <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                      <span className="text-blue-600 font-bold mt-0.5">›</span>
                      <span>{process}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Regulatory References (policy only) */}
            {documentType === 'policy' && clause.regulatory_references && clause.regulatory_references.length > 0 && (
              <div className="mb-4 p-3 bg-purple-50 rounded-lg border border-purple-200">
                <h4 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                  <Link2 className="w-4 h-4 text-purple-600" />
                  Regulatory References
                </h4>
                <div className="flex flex-wrap gap-2">
                  {clause.regulatory_references.map((ref, i) => (
                    <Badge key={i} variant="outline" className="text-xs border-purple-300 text-purple-700">
                      {ref}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            
            {/* === REGULATION-SPECIFIC SECTIONS === */}
            {/* Compliance Checklist (regulation only) */}
            {documentType === 'regulation' && clause.compliance_checklist && clause.compliance_checklist.length > 0 && (
              <div className="mb-4 p-3 bg-amber-50 rounded-lg border border-amber-200">
                <h4 className="text-sm font-semibold text-gray-900 mb-2 flex items-center gap-2">
                  <ClipboardCheck className="w-4 h-4 text-amber-600" />
                  Compliance Checklist
                </h4>
                <ul className="space-y-2">
                  {clause.compliance_checklist.map((item, i) => (
                    <li key={i} className="text-sm flex items-start gap-2 p-2 rounded bg-white border border-gray-200">
                      <div className="flex-shrink-0 mt-0.5">
                        {item.mandatory ? (
                          <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                        ) : (
                          <Info className="w-3.5 h-3.5 text-blue-500" />
                        )}
                      </div>
                      <div className="flex-1">
                        <span className="text-gray-800">{item.item || item}</span>
                        {item.evidence_type && (
                          <Badge variant="outline" className="ml-2 text-[10px] py-0">
                            {item.evidence_type}
                          </Badge>
                        )}
                        {item.verification_method && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Verify: {item.verification_method}
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Original Text (collapsed, for reference) */}
            {clause.original_text && clause.original_text !== displayContent && (
              <div className="mt-4 p-3 bg-muted/50 rounded-lg">
                <h4 className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
                  Original Extracted Text
                </h4>
                <p className="text-sm whitespace-pre-wrap text-muted-foreground">
                  {clause.original_text}
                </p>
              </div>
            )}
            
            {/* Section & Page Info */}
            {(clause.section || clause.page_number) && (
              <p className="text-xs text-muted-foreground mt-3">
                {clause.section && `Section: ${clause.section}`}
                {clause.section && clause.page_number && ' • '}
                {clause.page_number && `Page ${clause.page_number}`}
              </p>
            )}
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
};

// Summary Statistics Component
const ClauseSummary = ({ clauses }) => {
  const stats = {
    total: clauses.length,
    byType: {},
    byCriticality: {},
    byCategory: {}
  };
  
  clauses.forEach(clause => {
    // Count by requirement type
    const type = clause.requirement_type || 'informational';
    stats.byType[type] = (stats.byType[type] || 0) + 1;
    
    // Count by criticality
    const crit = clause.criticality || 'medium';
    stats.byCriticality[crit] = (stats.byCriticality[crit] || 0) + 1;
    
    // Count by category
    const cat = clause.subject_category || 'general';
    stats.byCategory[cat] = (stats.byCategory[cat] || 0) + 1;
  });
  
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <Card>
        <CardContent className="pt-4">
          <div className="text-3xl font-bold text-primary">{stats.total}</div>
          <div className="text-sm text-muted-foreground">Total Clauses</div>
        </CardContent>
      </Card>
      
      <Card>
        <CardContent className="pt-4">
          <div className="text-3xl font-bold text-[#F87171]">{stats.byType.mandatory || 0}</div>
          <div className="text-sm text-muted-foreground">Mandatory</div>
        </CardContent>
      </Card>
      
      <Card>
        <CardContent className="pt-4">
          <div className="text-3xl font-bold text-[#FBAD41]">{stats.byType.prohibition || 0}</div>
          <div className="text-sm text-muted-foreground">Prohibitions</div>
        </CardContent>
      </Card>
      
      <Card>
        <CardContent className="pt-4">
          <div className="text-3xl font-bold text-[#F87171]">{stats.byCriticality.high || 0}</div>
          <div className="text-sm text-muted-foreground">High Priority</div>
        </CardContent>
      </Card>
    </div>
  );
};

// Main ClauseViewer Component
export default function ClauseViewer({ clauses = [], documentType = 'policy', title = '', onEditClause, onDeleteClause }) {
  const [expandedClauses, setExpandedClauses] = useState(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterCriticality, setFilterCriticality] = useState('all');
  const [viewMode, setViewMode] = useState('list'); // 'list' or 'grouped'
  
  // Toggle clause expansion
  const toggleClause = (index) => {
    const newExpanded = new Set(expandedClauses);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedClauses(newExpanded);
  };
  
  // Expand/Collapse all
  const expandAll = () => {
    setExpandedClauses(new Set(clauses.map((_, i) => i)));
  };
  
  const collapseAll = () => {
    setExpandedClauses(new Set());
  };
  
  // Filter clauses
  const filteredClauses = clauses.filter(clause => {
    // Search filter
    if (searchTerm) {
      const searchLower = searchTerm.toLowerCase();
      const matchesSearch = 
        (clause.text || '').toLowerCase().includes(searchLower) ||
        (clause.original_text || '').toLowerCase().includes(searchLower) ||
        (clause.semantic_summary || '').toLowerCase().includes(searchLower) ||
        (clause.keywords || []).some(k => k.toLowerCase().includes(searchLower));
      if (!matchesSearch) return false;
    }
    
    // Type filter
    if (filterType !== 'all' && clause.requirement_type !== filterType) {
      return false;
    }
    
    // Category filter
    if (filterCategory !== 'all' && clause.subject_category !== filterCategory) {
      return false;
    }
    
    // Criticality filter
    if (filterCriticality !== 'all' && clause.criticality !== filterCriticality) {
      return false;
    }
    
    return true;
  });
  
  // Group clauses by category
  const groupedClauses = filteredClauses.reduce((acc, clause, index) => {
    const category = clause.subject_category || 'general';
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push({ ...clause, originalIndex: index });
    return acc;
  }, {});
  
  // Get unique categories from clauses
  const uniqueCategories = [...new Set(clauses.map(c => c.subject_category || 'general'))];
  
  if (!clauses || clauses.length === 0) {
    return (
      <Card className="p-8 text-center">
        <div className="text-muted-foreground">
          <Info className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <h3 className="text-lg font-semibold mb-2">No Clauses Found</h3>
          <p>This document has no extracted clauses yet.</p>
        </div>
      </Card>
    );
  }
  
  return (
    <div className="space-y-4">
      {/* Summary Statistics */}
      <ClauseSummary clauses={clauses} />
      
      {/* Filters and Controls */}
      <Card className="p-4">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search clauses..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>
          
          {/* Filters */}
          <div className="flex gap-2 flex-wrap">
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="border rounded-md px-3 py-2 text-sm"
            >
              <option value="all">All Types</option>
              <option value="mandatory">Mandatory</option>
              <option value="recommended">Recommended</option>
              <option value="prohibition">Prohibition</option>
              <option value="informational">Informational</option>
              <option value="conditional">Conditional</option>
            </select>
            
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="border rounded-md px-3 py-2 text-sm"
            >
              <option value="all">All Categories</option>
              {uniqueCategories.map(cat => (
                <option key={cat} value={cat}>
                  {categoryLabels[cat] || cat}
                </option>
              ))}
            </select>
            
            <select
              value={filterCriticality}
              onChange={(e) => setFilterCriticality(e.target.value)}
              className="border rounded-md px-3 py-2 text-sm"
            >
              <option value="all">All Priorities</option>
              <option value="high">High Priority</option>
              <option value="medium">Medium Priority</option>
              <option value="low">Low Priority</option>
            </select>
          </div>
          
          {/* View Mode Toggle */}
          <div className="flex gap-1 border rounded-md p-1">
            <Button
              variant={viewMode === 'list' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('list')}
            >
              <List className="w-4 h-4" />
            </Button>
            <Button
              variant={viewMode === 'grouped' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('grouped')}
            >
              <LayoutGrid className="w-4 h-4" />
            </Button>
          </div>
        </div>
        
        {/* Expand/Collapse All */}
        <div className="flex justify-between items-center mt-4 pt-4 border-t">
          <span className="text-sm text-muted-foreground">
            Showing {filteredClauses.length} of {clauses.length} clauses
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={expandAll}>
              Expand All
            </Button>
            <Button variant="outline" size="sm" onClick={collapseAll}>
              Collapse All
            </Button>
          </div>
        </div>
      </Card>
      
      {/* Clauses Display */}
      <ScrollArea className="h-[calc(100vh-400px)] pr-4">
        {viewMode === 'list' ? (
          // List View
          <div className="space-y-3">
            {filteredClauses.map((clause, index) => (
              <ClauseCard
                key={clause.clause_id || index}
                clause={clause}
                index={index}
                isExpanded={expandedClauses.has(index)}
                onToggle={() => toggleClause(index)}
                onEdit={onEditClause}
                onDelete={onDeleteClause}
                documentType={documentType}
              />
            ))}
          </div>
        ) : (
          // Grouped View
          <Tabs defaultValue={Object.keys(groupedClauses)[0]} className="w-full">
            <TabsList className="flex flex-wrap h-auto gap-1 mb-4">
              {Object.entries(groupedClauses).map(([category, items]) => (
                <TabsTrigger key={category} value={category} className="text-xs">
                  {categoryLabels[category] || category} ({items.length})
                </TabsTrigger>
              ))}
            </TabsList>
            
            {Object.entries(groupedClauses).map(([category, items]) => (
              <TabsContent key={category} value={category}>
                <div className="space-y-3">
                  {items.map((clause, idx) => (
                    <ClauseCard
                      key={clause.clause_id || idx}
                      clause={clause}
                      index={clause.originalIndex}
                      isExpanded={expandedClauses.has(clause.originalIndex)}
                      onToggle={() => toggleClause(clause.originalIndex)}
                      onEdit={onEditClause}
                      onDelete={onDeleteClause}
                      documentType={documentType}
                    />
                  ))}
                </div>
              </TabsContent>
            ))}
          </Tabs>
        )}
      </ScrollArea>
    </div>
  );
}

// Export the ClauseCard for use in other components
export { ClauseCard, ClauseSummary };
