import React, { useEffect, useState } from 'react';
import { organizationApi } from '../lib/api';
import { Button } from './ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { Progress } from './ui/progress';
import { Save, Building2, Shield, Banknote, Users, Plus, Trash2, FileText } from 'lucide-react';
import { toast } from 'sonner';

const ENTITY_TYPES = [
  { value: 'bank_pa', label: 'Bank Payment Aggregator' },
  { value: 'non_bank_pa', label: 'Non-bank Payment Aggregator' },
  { value: 'pa_p', label: 'PA-P (Physical POS)' },
  { value: 'pg_only', label: 'Payment Gateway Only' },
  { value: 'nbfc', label: 'NBFC' },
  { value: 'digital_lender', label: 'Digital Lender' },
  { value: 'fintech', label: 'FinTech' },
  { value: 'unknown', label: 'Not Classified' },
];

const BANK_TYPES = [
  { value: 'scheduled_commercial', label: 'Scheduled Commercial Bank' },
  { value: 'cooperative', label: 'Cooperative Bank' },
  { value: 'small_finance', label: 'Small Finance Bank' },
  { value: 'payments_bank', label: 'Payments Bank' },
];

const LICENSE_STATUSES = [
  { value: 'not_applied', label: 'Not Applied' },
  { value: 'application_submitted', label: 'Application Submitted' },
  { value: 'in_principle', label: 'In-Principle Authorization' },
  { value: 'authorized', label: 'Authorized' },
  { value: 'conditional', label: 'Conditional Authorization' },
  { value: 'renewal_pending', label: 'Renewal Pending' },
];

const PERSONNEL_ROLES = ['md', 'cco', 'cto', 'ciso', 'cfo', 'cs', 'nodal_officer'];

export default function OrganizationProfileForm() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({});
  const [newPersonnel, setNewPersonnel] = useState({ role: '', name: '', email: '' });

  useEffect(() => { loadProfile(); }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const data = await organizationApi.getProfile();
      setProfile(data);
      setFormData(data);
    } catch (err) {
      toast.error('Failed to load organization profile');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updateData = {};
      const fields = [
        'entity_type', 'bank_type', 'authorized_activities', 'license_status',
        'rbi_registration_number', 'authorization_date', 'authorization_validity',
        'pravaah_application_id', 'net_worth_crore', 'net_worth_as_of',
        'escrow_bank_name', 'escrow_account_number', 'nodal_account_bank',
        'nodal_account_number', 'business_commencement_date', 'registered_address',
        'cin_number', 'website', 'merchant_count', 'annual_transaction_volume',
        'business_categories', 'key_personnel',
      ];
      for (const f of fields) {
        if (formData[f] !== undefined && formData[f] !== profile[f]) {
          updateData[f] = formData[f];
        }
      }
      if (Object.keys(updateData).length === 0) {
        toast.info('No changes to save');
        setSaving(false);
        return;
      }
      const updated = await organizationApi.updateProfile(updateData);
      setProfile(updated);
      setFormData(updated);
      toast.success('Organization profile updated');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const addPersonnel = () => {
    if (!newPersonnel.role || !newPersonnel.name) return;
    const personnel = [...(formData.key_personnel || []), { ...newPersonnel, is_fit_and_proper: true }];
    setFormData({ ...formData, key_personnel: personnel });
    setNewPersonnel({ role: '', name: '', email: '' });
  };

  const removePersonnel = (idx) => {
    const personnel = (formData.key_personnel || []).filter((_, i) => i !== idx);
    setFormData({ ...formData, key_personnel: personnel });
  };

  const updateField = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return <div className="text-muted-foreground text-sm p-4">Loading organization profile...</div>;
  }

  const completeness = formData.setup_completion_pct || 0;

  return (
    <div className="space-y-6">
      {/* Profile Completeness */}
      <div className="flex items-center gap-4 mb-2">
        <span className="text-sm text-muted-foreground">Profile Completeness</span>
        <Progress value={completeness} className="flex-1 h-2" />
        <span className="text-sm font-medium">{completeness}%</span>
      </div>

      {/* Entity Classification */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2"><Building2 className="h-4 w-4" /> Entity Classification</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Entity Type</Label>
              <Select value={formData.entity_type || 'unknown'} onValueChange={v => updateField('entity_type', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ENTITY_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {formData.entity_type === 'bank_pa' && (
              <div>
                <Label>Bank Type</Label>
                <Select value={formData.bank_type || ''} onValueChange={v => updateField('bank_type', v)}>
                  <SelectTrigger><SelectValue placeholder="Select bank type" /></SelectTrigger>
                  <SelectContent>
                    {BANK_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <div>
            <Label>Business Categories</Label>
            <Input
              placeholder="e.g. e-commerce, utilities, education (comma-separated)"
              value={(formData.business_categories || []).join(', ')}
              onChange={e => updateField('business_categories', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
            />
          </div>
        </CardContent>
      </Card>

      {/* License & Authorization */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2"><Shield className="h-4 w-4" /> License & Authorization</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>License Status</Label>
              <Select value={formData.license_status || 'not_applied'} onValueChange={v => updateField('license_status', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {LICENSE_STATUSES.map(s => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>RBI Registration Number</Label>
              <Input value={formData.rbi_registration_number || ''} onChange={e => updateField('rbi_registration_number', e.target.value)} placeholder="PA-XYZ-2024-001" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label>Authorization Date</Label>
              <Input type="date" value={formData.authorization_date || ''} onChange={e => updateField('authorization_date', e.target.value)} />
            </div>
            <div>
              <Label>Validity Until</Label>
              <Input type="date" value={formData.authorization_validity || ''} onChange={e => updateField('authorization_validity', e.target.value)} />
            </div>
            <div>
              <Label>PRAVAAH Application ID</Label>
              <Input value={formData.pravaah_application_id || ''} onChange={e => updateField('pravaah_application_id', e.target.value)} placeholder="PRV-2024-00123" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Financial */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2"><Banknote className="h-4 w-4" /> Financial Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label>Net Worth (₹ Crore)</Label>
              <Input type="number" step="0.01" value={formData.net_worth_crore ?? ''} onChange={e => updateField('net_worth_crore', e.target.value ? parseFloat(e.target.value) : null)} />
            </div>
            <div>
              <Label>Net Worth As Of</Label>
              <Input type="date" value={formData.net_worth_as_of || ''} onChange={e => updateField('net_worth_as_of', e.target.value)} />
            </div>
            <div>
              <Label>Annual Volume (₹ Crore)</Label>
              <Input type="number" step="0.01" value={formData.annual_transaction_volume ?? ''} onChange={e => updateField('annual_transaction_volume', e.target.value ? parseFloat(e.target.value) : null)} />
            </div>
          </div>
          <Separator />
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Escrow Bank</Label>
              <Input value={formData.escrow_bank_name || ''} onChange={e => updateField('escrow_bank_name', e.target.value)} />
            </div>
            <div>
              <Label>Nodal Account Bank</Label>
              <Input value={formData.nodal_account_bank || ''} onChange={e => updateField('nodal_account_bank', e.target.value)} />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Key Personnel */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2"><Users className="h-4 w-4" /> Key Personnel</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {(formData.key_personnel || []).length > 0 && (
            <div className="space-y-2">
              {(formData.key_personnel || []).map((p, idx) => (
                <div key={idx} className="flex items-center gap-3 p-2 rounded-md border">
                  <Badge variant="outline" className="uppercase">{p.role}</Badge>
                  <span className="flex-1 text-sm">{p.name}</span>
                  <span className="text-sm text-muted-foreground">{p.email}</span>
                  {p.is_fit_and_proper && <Badge variant="secondary" className="text-xs">F&P</Badge>}
                  <Button variant="ghost" size="sm" onClick={() => removePersonnel(idx)}><Trash2 className="h-3 w-3" /></Button>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2 items-end">
            <div>
              <Label>Role</Label>
              <Select value={newPersonnel.role} onValueChange={v => setNewPersonnel({ ...newPersonnel, role: v })}>
                <SelectTrigger className="w-40"><SelectValue placeholder="Select role" /></SelectTrigger>
                <SelectContent>
                  {PERSONNEL_ROLES.map(r => <SelectItem key={r} value={r}>{r.toUpperCase()}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="flex-1">
              <Label>Name</Label>
              <Input value={newPersonnel.name} onChange={e => setNewPersonnel({ ...newPersonnel, name: e.target.value })} placeholder="Full name" />
            </div>
            <div className="flex-1">
              <Label>Email</Label>
              <Input value={newPersonnel.email} onChange={e => setNewPersonnel({ ...newPersonnel, email: e.target.value })} placeholder="email@org.com" />
            </div>
            <Button variant="outline" size="sm" onClick={addPersonnel}><Plus className="h-4 w-4 mr-1" /> Add</Button>
          </div>
        </CardContent>
      </Card>

      {/* Business Info */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2"><FileText className="h-4 w-4" /> Business Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>CIN Number</Label>
              <Input value={formData.cin_number || ''} onChange={e => updateField('cin_number', e.target.value)} placeholder="U74999MH2020PTC345678" />
            </div>
            <div>
              <Label>Business Commencement Date</Label>
              <Input type="date" value={formData.business_commencement_date || ''} onChange={e => updateField('business_commencement_date', e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Website</Label>
              <Input value={formData.website || ''} onChange={e => updateField('website', e.target.value)} placeholder="https://example.com" />
            </div>
            <div>
              <Label>Approximate Merchant Count</Label>
              <Input type="number" value={formData.merchant_count ?? ''} onChange={e => updateField('merchant_count', e.target.value ? parseInt(e.target.value) : null)} />
            </div>
          </div>
          <div>
            <Label>Registered Address</Label>
            <Input value={formData.registered_address || ''} onChange={e => updateField('registered_address', e.target.value)} placeholder="Full registered address" />
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          <Save className="h-4 w-4 mr-2" />
          {saving ? 'Saving...' : 'Save Organization Profile'}
        </Button>
      </div>
    </div>
  );
}
