import React, { useEffect, useState } from 'react';
import { departmentsApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Building2, Plus, Users, CheckCircle, AlertTriangle, Clock, Edit, Trash2, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

export default function Departments() {
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [membersOpen, setMembersOpen] = useState(false);
  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [selectedDept, setSelectedDept] = useState(null);
  const [members, setMembers] = useState([]);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deptData, setDeptData] = useState({
    name: '',
    head_of_department: ''
  });
  const [memberData, setMemberData] = useState({
    name: '',
    email: '',
    title: '',
    role: 'analyst'
  });

  useEffect(() => {
    loadDepartments();
  }, []);

  const loadDepartments = async () => {
    try {
      const response = await departmentsApi.getAll();
      setDepartments(response);
    } catch (error) {
      toast.error('Failed to load departments');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await departmentsApi.create(deptData);
      toast.success('Department created successfully!');
      setCreateOpen(false);
      setDeptData({ name: '', head_of_department: '' });
      loadDepartments();
    } catch (error) {
      toast.error('Failed to create department');
    } finally {
      setCreating(false);
    }
  };

  const handleEdit = (dept) => {
    setSelectedDept(dept);
    setDeptData({
      name: dept.name || '',
      head_of_department: dept.head_of_department || ''
    });
    setEditOpen(true);
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    const deptId = selectedDept?.id || selectedDept?._id;
    if (!deptId) return;
    setSaving(true);
    try {
      await departmentsApi.update(deptId, deptData);
      toast.success('Department updated successfully!');
      setEditOpen(false);
      setSelectedDept(null);
      loadDepartments();
    } catch (error) {
      toast.error('Failed to update department');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteConfirm = (dept) => {
    setSelectedDept(dept);
    setDeleteConfirmOpen(true);
  };

  const handleDelete = async () => {
    const deptId = selectedDept?.id || selectedDept?._id;
    if (!deptId) return;
    try {
      await departmentsApi.delete(deptId);
      toast.success('Department deleted');
      setDeleteConfirmOpen(false);
      setSelectedDept(null);
      loadDepartments();
    } catch (error) {
      toast.error('Failed to delete department');
    }
  };

  const handleViewMembers = async (dept) => {
    setSelectedDept(dept);
    const deptId = dept.id || dept._id;
    try {
      const response = await departmentsApi.getMembers(deptId);
      setMembers(Array.isArray(response) ? response : []);
      setMembersOpen(true);
    } catch (error) {
      toast.error('Failed to load members');
    }
  };

  const handleAddMember = async (e) => {
    e.preventDefault();
    const deptId = selectedDept?.id || selectedDept?._id;
    if (!deptId) return;
    setSaving(true);
    try {
      await departmentsApi.addMember(deptId, memberData);
      toast.success('Member added successfully!');
      setAddMemberOpen(false);
      setMemberData({ name: '', email: '', title: '', role: 'analyst' });
      handleViewMembers(selectedDept); // Refresh members list
    } catch (error) {
      toast.error('Failed to add member');
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveMember = async (memberId) => {
    const deptId = selectedDept?.id || selectedDept?._id;
    if (!deptId) return;
    try {
      await departmentsApi.removeMember(deptId, memberId);
      toast.success('Member removed');
      handleViewMembers(selectedDept); // Refresh members list
    } catch (error) {
      toast.error('Failed to remove member');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'Compliant':
        return 'bg-[#34D399]/20 text-[#34D399] border-[#34D399]/30';
      case 'Partially Compliant':
        return 'bg-[#FBAD41]/20 text-[#FBAD41] border-[#FBAD41]/30';
      case 'Non-Compliant':
        return 'bg-[#F87171]/20 text-[#F87171] border-[#F87171]/30';
      default:
        return 'bg-[#808089]/20 text-[#808089] border-[#808089]/30';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'Compliant':
        return <CheckCircle className="h-5 w-5 text-[#34D399]" />;
      case 'Partially Compliant':
        return <Clock className="h-5 w-5 text-[#FBAD41]" />;
      case 'Non-Compliant':
        return <AlertTriangle className="h-5 w-5 text-[#F87171]" />;
      default:
        return <Building2 className="h-5 w-5 text-[#808089]" />;
    }
  };

  return (
    <div className="space-y-8" data-testid="departments-page">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#80FFF9] to-[#34D399] flex items-center justify-center shadow-lg">
            <Building2 className="h-6 w-6 text-[#111113]" />
          </div>
          <div>
            <h1 className="text-4xl font-bold text-gradient mb-1">Department Management</h1>
            <p className="text-muted-foreground">Organize compliance by department</p>
          </div>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button className="btn-shiny text-white" data-testid="create-department-button">
              <Plus className="mr-2 h-4 w-4" /> Add Department
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Department</DialogTitle>
              <DialogDescription>Add a new department to your organization</DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <Label htmlFor="dept-name">Department Name</Label>
                <Input
                  id="dept-name"
                  value={deptData.name}
                  onChange={(e) => setDeptData({ ...deptData, name: e.target.value })}
                  placeholder="e.g., Legal & Compliance"
                  required
                />
              </div>
              <div>
                <Label htmlFor="dept-head">Head of Department</Label>
                <Input
                  id="dept-head"
                  value={deptData.head_of_department}
                  onChange={(e) => setDeptData({ ...deptData, head_of_department: e.target.value })}
                  placeholder="e.g., John Doe"
                />
              </div>
              <Button type="submit" className="w-full btn-shiny text-white" disabled={creating}>
                {creating ? 'Creating...' : 'Create Department'}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading departments...</div>
        </div>
      ) : departments.length === 0 ? (
        <Card className="flex flex-col items-center justify-center h-64 shiny-card">
          <CardContent className="text-center">
            <Building2 className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Departments Yet</h3>
            <p className="text-muted-foreground mb-4">Create your first department</p>
            <Button className="btn-shiny text-white" onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" /> Add Department
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {departments.map((dept) => (
            <Card key={dept.id} className="shiny-card">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(dept.compliance_status)}
                    <CardTitle>{dept.name}</CardTitle>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={getStatusColor(dept.compliance_status)}>
                      {dept.compliance_status}
                    </Badge>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleEdit(dept)} data-testid={`edit-dept-${dept.id}`}>
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleDeleteConfirm(dept)} data-testid={`delete-dept-${dept.id}`}>
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                </div>
                {dept.head_of_department && (
                  <CardDescription className="flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    Head: {dept.head_of_department}
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex justify-between items-center p-3 bg-[#1C1C1E] rounded-lg border border-[#2A2A2E]">
                    <span className="text-sm font-medium text-[#E6E6E9]">Total Tasks</span>
                    <span className="text-xl font-bold text-[#80FFF9]">{dept.total_tasks || 0}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-[#1C1C1E] rounded-lg border border-[#2A2A2E]">
                    <span className="text-sm font-medium text-[#E6E6E9]">Overdue Tasks</span>
                    <span className="text-xl font-bold text-[#F87171]">{dept.overdue_tasks || 0}</span>
                  </div>
                  {dept.members && dept.members.length > 0 && (
                    <div className="text-sm text-muted-foreground">
                      {dept.members.length} team members
                    </div>
                  )}
                  <Button variant="outline" className="w-full" onClick={() => handleViewMembers(dept)} data-testid={`view-members-${dept.id}`}>
                    <Users className="mr-2 h-4 w-4" /> Manage Members
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Edit Department Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent data-testid="edit-department-dialog">
          <DialogHeader>
            <DialogTitle>Edit Department</DialogTitle>
            <DialogDescription>Update department details</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleUpdate} className="space-y-4">
            <div>
              <Label htmlFor="edit-dept-name">Department Name</Label>
              <Input
                id="edit-dept-name"
                value={deptData.name}
                onChange={(e) => setDeptData({ ...deptData, name: e.target.value })}
                placeholder="e.g., Legal & Compliance"
                required
                data-testid="edit-dept-name-input"
              />
            </div>
            <div>
              <Label htmlFor="edit-dept-head">Head of Department</Label>
              <Input
                id="edit-dept-head"
                value={deptData.head_of_department}
                onChange={(e) => setDeptData({ ...deptData, head_of_department: e.target.value })}
                placeholder="e.g., John Doe"
                data-testid="edit-dept-head-input"
              />
            </div>
            <Button type="submit" className="w-full btn-shiny text-white" disabled={saving} data-testid="update-dept-button">
              {saving ? 'Updating...' : 'Update Department'}
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent data-testid="delete-dept-confirm">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Department</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedDept?.name}"? This will also remove all members. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-dept">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700" data-testid="confirm-delete-dept">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Members Management Dialog */}
      <Dialog open={membersOpen} onOpenChange={setMembersOpen}>
        <DialogContent className="max-w-2xl" data-testid="members-dialog">
          <DialogHeader>
            <DialogTitle>Manage Members - {selectedDept?.name}</DialogTitle>
            <DialogDescription>Add or remove members from this department</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Button className="w-full btn-shiny text-white" onClick={() => setAddMemberOpen(true)} data-testid="add-member-button">
              <UserPlus className="mr-2 h-4 w-4" /> Add Member
            </Button>
            {members.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No members yet. Add your first team member.
              </div>
            ) : (
              <div className="space-y-2" data-testid="members-list">
                {members.map((member) => (
                  <Card key={member.id || member._id}>
                    <CardContent className="flex items-center justify-between p-4">
                      <div>
                        <div className="font-medium">{member.name}</div>
                        <div className="text-sm text-muted-foreground">{member.email}</div>
                        {member.title && <div className="text-sm text-muted-foreground">{member.title}</div>}
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => handleRemoveMember(member.id || member._id)}
                        data-testid={`remove-member-${member.id || member._id}`}>
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Member Dialog */}
      <Dialog open={addMemberOpen} onOpenChange={setAddMemberOpen}>
        <DialogContent data-testid="add-member-dialog">
          <DialogHeader>
            <DialogTitle>Add Team Member</DialogTitle>
            <DialogDescription>Add a new member to {selectedDept?.name}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleAddMember} className="space-y-4">
            <div>
              <Label htmlFor="member-name">Name</Label>
              <Input
                id="member-name"
                value={memberData.name}
                onChange={(e) => setMemberData({ ...memberData, name: e.target.value })}
                placeholder="e.g., Jane Smith"
                required
                data-testid="member-name-input"
              />
            </div>
            <div>
              <Label htmlFor="member-email">Email</Label>
              <Input
                id="member-email"
                type="email"
                value={memberData.email}
                onChange={(e) => setMemberData({ ...memberData, email: e.target.value })}
                placeholder="e.g., jane@example.com"
                required
                data-testid="member-email-input"
              />
            </div>
            <div>
              <Label htmlFor="member-title">Title</Label>
              <Input
                id="member-title"
                value={memberData.title}
                onChange={(e) => setMemberData({ ...memberData, title: e.target.value })}
                placeholder="e.g., Compliance Officer"
                data-testid="member-title-input"
              />
            </div>
            <div>
              <Label htmlFor="member-role">Role</Label>
              <Input
                id="member-role"
                value={memberData.role}
                onChange={(e) => setMemberData({ ...memberData, role: e.target.value })}
                placeholder="e.g., analyst"
                data-testid="member-role-input"
              />
            </div>
            <Button type="submit" className="w-full btn-shiny text-white" disabled={saving} data-testid="submit-member-button">
              {saving ? 'Adding...' : 'Add Member'}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
