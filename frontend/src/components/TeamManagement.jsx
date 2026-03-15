import React, { useState, useEffect, useRef } from 'react';
import { Button } from './ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Badge } from './ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Plus, Edit, Trash2, Upload, Download, Users } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

const api = axios.create({
    baseURL: `${API_URL}/api`,
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

const teamMembersApi = {
    getAll: (team) => api.get('/team-members', { params: { team } }).then(r => r.data),
    getById: (id) => api.get(`/team-members/${id}`).then(r => r.data),
    create: (data) => api.post('/team-members', data).then(r => r.data),
    update: (id, data) => api.put(`/team-members/${id}`, data).then(r => r.data),
    delete: (id) => api.delete(`/team-members/${id}`).then(r => r.data),
    uploadCsv: (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return api.post('/team-members/upload-csv', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        }).then(r => r.data);
    },
    downloadSample: () => api.get('/team-members/download/sample-csv', { responseType: 'blob' })
};

export default function TeamManagement() {
    const [members, setMembers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [editingMember, setEditingMember] = useState(null);
    const [filterTeam, setFilterTeam] = useState('all');
    const [formData, setFormData] = useState({
        name: '',
        team: '',
        email: '',
        role: 'Member'
    });
    const fileInputRef = useRef(null);

    useEffect(() => {
        loadMembers();
    }, [filterTeam]);

    const loadMembers = async () => {
        try {
            const teamFilter = filterTeam === 'all' ? undefined : filterTeam;
            const data = await teamMembersApi.getAll(teamFilter);
            setMembers(data);
        } catch (error) {
            toast.error('Failed to load team members');
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        try {
            if (editingMember) {
                await teamMembersApi.update(editingMember.id, formData);
                toast.success('Team member updated successfully');
            } else {
                await teamMembersApi.create(formData);
                toast.success('Team member created successfully');
            }

            setIsDialogOpen(false);
            resetForm();
            loadMembers();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to save team member');
        }
    };

    const handleEdit = (member) => {
        setEditingMember(member);
        setFormData({
            name: member.name,
            team: member.team,
            email: member.email,
            role: member.role
        });
        setIsDialogOpen(true);
    };

    const handleDelete = async (memberId) => {
        if (!window.confirm('Are you sure you want to delete this team member?')) return;

        try {
            await teamMembersApi.delete(memberId);
            toast.success('Team member deleted successfully');
            loadMembers();
        } catch (error) {
            toast.error('Failed to delete team member');
        }
    };

    const handleCsvUpload = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        try {
            const result = await teamMembersApi.uploadCsv(file);
            toast.success(`CSV uploaded: ${result.created} created, ${result.updated} updated`);
            if (result.errors.length > 0) {
                console.error('CSV errors:', result.errors);
                toast.warning(`${result.errors.length} rows had errors. Check console for details.`);
            }
            loadMembers();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to upload CSV');
        }

        // Reset file input
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const handleDownloadSample = async () => {
        try {
            const response = await teamMembersApi.downloadSample();
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'team_members_sample.csv');
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (error) {
            toast.error('Failed to download sample CSV');
        }
    };

    const resetForm = () => {
        setFormData({ name: '', team: '', email: '', role: 'Member' });
        setEditingMember(null);
    };

    const handleDialogClose = (open) => {
        setIsDialogOpen(open);
        if (!open) resetForm();
    };

    const teams = [...new Set(members.map(m => m.team))];

    if (loading) {
        return <div className="text-center py-8">Loading team members...</div>;
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Team Management</h2>
                    <p className="text-muted-foreground">Manage team members for task assignment</p>
                </div>

                <div className="flex gap-2">
                    <Button variant="outline" onClick={handleDownloadSample}>
                        <Download className="mr-2 h-4 w-4" />
                        Sample CSV
                    </Button>
                    <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
                        <Upload className="mr-2 h-4 w-4" />
                        Upload CSV
                    </Button>
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".csv"
                        className="hidden"
                        onChange={handleCsvUpload}
                    />

                    <Dialog open={isDialogOpen} onOpenChange={handleDialogClose}>
                        <DialogTrigger asChild>
                            <Button>
                                <Plus className="mr-2 h-4 w-4" />
                                Add Member
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-[525px]">
                            <DialogHeader>
                                <DialogTitle>{editingMember ? 'Edit Member' : 'Add New Member'}</DialogTitle>
                                <DialogDescription>
                                    Add team members for task assignment and notifications.
                                </DialogDescription>
                            </DialogHeader>
                            <form onSubmit={handleSubmit}>
                                <div className="grid gap-4 py-4">
                                    <div className="grid gap-2">
                                        <Label htmlFor="name">Name *</Label>
                                        <Input
                                            id="name"
                                            value={formData.name}
                                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                            required
                                        />
                                    </div>
                                    <div className="grid gap-2">
                                        <Label htmlFor="team">Team *</Label>
                                        <Input
                                            id="team"
                                            placeholder="e.g., Tech, Product, Infosec"
                                            value={formData.team}
                                            onChange={(e) => setFormData({ ...formData, team: e.target.value })}
                                            required
                                        />
                                    </div>
                                    <div className="grid gap-2">
                                        <Label htmlFor="email">Email *</Label>
                                        <Input
                                            id="email"
                                            type="email"
                                            value={formData.email}
                                            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                            required
                                        />
                                    </div>
                                    <div className="grid gap-2">
                                        <Label htmlFor="role">Role *</Label>
                                        <Select value={formData.role} onValueChange={(v) => setFormData({ ...formData, role: v })}>
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select role" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="SPOC">SPOC</SelectItem>
                                                <SelectItem value="Lead">Lead</SelectItem>
                                                <SelectItem value="Member">Member</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button type="button" variant="outline" onClick={() => handleDialogClose(false)}>
                                        Cancel
                                    </Button>
                                    <Button type="submit">
                                        {editingMember ? 'Update' : 'Create'} Member
                                    </Button>
                                </DialogFooter>
                            </form>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>

            <div className="flex gap-4">
                <Select value={filterTeam} onValueChange={setFilterTeam}>
                    <SelectTrigger className="w-[200px]">
                        <SelectValue placeholder="All Teams" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Teams</SelectItem>
                        {teams.map(team => (
                            <SelectItem key={team} value={team}>{team}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {members.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12">
                        <Users className="h-12 w-12 text-muted-foreground mb-4" />
                        <p className="text-muted-foreground text-center">
                            No team members yet. Add members manually or upload a CSV file.
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Team</TableHead>
                                    <TableHead>Email</TableHead>
                                    <TableHead>Role</TableHead>
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {members.map((member) => (
                                    <TableRow key={member.id}>
                                        <TableCell className="font-medium">{member.name}</TableCell>
                                        <TableCell>
                                            <Badge variant="outline">{member.team}</Badge>
                                        </TableCell>
                                        <TableCell>{member.email}</TableCell>
                                        <TableCell>
                                            <Badge variant={member.role === 'SPOC' ? 'default' : 'secondary'}>
                                                {member.role}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex gap-2 justify-end">
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => handleEdit(member)}
                                                >
                                                    <Edit className="h-4 w-4" />
                                                </Button>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => handleDelete(member.id)}
                                                >
                                                    <Trash2 className="h-4 w-4 text-destructive" />
                                                </Button>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
