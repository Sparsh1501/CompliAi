import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Badge } from './ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Plus, Mail, RefreshCw, X, UserPlus } from 'lucide-react';
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

const invitesApi = {
    getAll: (status) => api.get('/invites', { params: { status } }).then(r => r.data),
    create: (data) => api.post('/invites', data).then(r => r.data),
    resend: (id) => api.post(`/invites/${id}/resend`).then(r => r.data),
    revoke: (id) => api.delete(`/invites/${id}`).then(r => r.data),
};

export default function InviteManagement() {
    const [invites, setInvites] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
    const [inviteToRevoke, setInviteToRevoke] = useState(null);
    const [formData, setFormData] = useState({
        email: '',
        role: 'user'
    });

    useEffect(() => {
        loadInvites();
    }, []);

    const loadInvites = async () => {
        try {
            const data = await invitesApi.getAll();
            setInvites(data);
        } catch (error) {
            toast.error('Failed to load invites');
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        try {
            await invitesApi.create(formData);
            toast.success('Invite sent successfully');
            setIsDialogOpen(false);
            resetForm();
            loadInvites();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to send invite');
        }
    };

    const handleResend = async (inviteId) => {
        try {
            await invitesApi.resend(inviteId);
            toast.success('Invite resent successfully');
            loadInvites();
        } catch (error) {
            toast.error('Failed to resend invite');
        }
    };

    const handleRevoke = async (e, inviteId) => {
        e.preventDefault();
        e.stopPropagation();
        setInviteToRevoke(inviteId);
        setConfirmDialogOpen(true);
    };

    const confirmRevoke = async () => {
        if (!inviteToRevoke) return;

        try {
            await invitesApi.revoke(inviteToRevoke);
            toast.success('Invite revoked successfully');
            loadInvites();
        } catch (error) {
            toast.error('Failed to revoke invite');
        } finally {
            setConfirmDialogOpen(false);
            setInviteToRevoke(null);
        }
    };

    const cancelRevoke = () => {
        setConfirmDialogOpen(false);
        setInviteToRevoke(null);
    };

    const resetForm = () => {
        setFormData({ email: '', role: 'user' });
    };

    const handleDialogClose = (open) => {
        setIsDialogOpen(open);
        if (!open) resetForm();
    };

    const getStatusBadge = (status) => {
        const variants = {
            pending: 'default',
            accepted: 'success',
            expired: 'secondary',
            revoked: 'destructive'
        };
        // Capitalize first letter for display (Sentence case)
        const displayStatus = status.charAt(0).toUpperCase() + status.slice(1);
        return <Badge variant={variants[status] || 'secondary'}>{displayStatus}</Badge>;
    };

    const formatDate = (dateStr) => {
        return new Date(dateStr).toLocaleDateString();
    };

    if (loading) {
        return <div className="text-center py-8">Loading invites...</div>;
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Organization Invites</h2>
                    <p className="text-muted-foreground">Invite users to join your organization</p>
                </div>

                <Dialog open={isDialogOpen} onOpenChange={handleDialogClose}>
                    <DialogTrigger asChild>
                        <Button>
                            <Plus className="mr-2 h-4 w-4" />
                            Send Invite
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="sm:max-w-[425px]">
                        <DialogHeader>
                            <DialogTitle>Send Invitation</DialogTitle>
                            <DialogDescription>
                                Invite a user to join your organization. They'll receive an email with a link to create their account.
                            </DialogDescription>
                        </DialogHeader>
                        <form onSubmit={handleSubmit}>
                            <div className="grid gap-4 py-4">
                                <div className="grid gap-2">
                                    <Label htmlFor="email">Email Address *</Label>
                                    <Input
                                        id="email"
                                        type="email"
                                        placeholder="user@example.com"
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
                                            <SelectItem value="user">User</SelectItem>
                                            <SelectItem value="compliance_head">Compliance Head</SelectItem>
                                            <SelectItem value="admin">Admin</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button type="button" variant="outline" onClick={() => handleDialogClose(false)}>
                                    Cancel
                                </Button>
                                <Button type="submit">
                                    <Mail className="mr-2 h-4 w-4" />
                                    Send Invite
                                </Button>
                            </DialogFooter>
                        </form>
                    </DialogContent>
                </Dialog>
            </div>

            {invites.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12">
                        <UserPlus className="h-12 w-12 text-muted-foreground mb-4" />
                        <p className="text-muted-foreground text-center">
                            No invites yet. Send an invite to add users to your organization.
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Email</TableHead>
                                    <TableHead>Role</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Invited By</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead>Expires</TableHead>
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {invites.map((invite) => (
                                    <TableRow key={invite.id}>
                                        <TableCell className="font-medium">{invite.email}</TableCell>
                                        <TableCell>
                                            <Badge variant="outline">{invite.role}</Badge>
                                        </TableCell>
                                        <TableCell>{getStatusBadge(invite.status)}</TableCell>
                                        <TableCell>{invite.invited_by_name}</TableCell>
                                        <TableCell>{formatDate(invite.created_at)}</TableCell>
                                        <TableCell>{formatDate(invite.expires_at)}</TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex gap-2 justify-end">
                                                {invite.status === 'pending' && (
                                                    <>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => handleResend(invite.id)}
                                                            title="Resend invite"
                                                        >
                                                            <RefreshCw className="h-4 w-4" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={(e) => handleRevoke(e, invite.id)}
                                                            title="Revoke invite"
                                                        >
                                                            <X className="h-4 w-4 text-destructive" />
                                                        </Button>
                                                    </>
                                                )}
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            )}

            {/* Revoke Confirmation Dialog */}
            <Dialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
                <DialogContent className="sm:max-w-[425px]">
                    <DialogHeader>
                        <DialogTitle>Confirm Revoke</DialogTitle>
                        <DialogDescription>
                            Are you sure you want to revoke this invite? This action cannot be undone.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={cancelRevoke}>
                            Cancel
                        </Button>
                        <Button type="button" variant="destructive" onClick={confirmRevoke}>
                            Revoke Invite
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
