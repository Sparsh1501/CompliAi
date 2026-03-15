import React, { useState, useEffect } from 'react';
import { chartersApi } from '../lib/api';
import { Button } from './ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { Badge } from './ui/badge';
import { Plus, Edit, Trash2, Building2 } from 'lucide-react';
import { toast } from 'sonner';

export default function CharterManagement() {
    const [charters, setCharters] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [editingCharter, setEditingCharter] = useState(null);
    const [formData, setFormData] = useState({
        name: '',
        code: '',
        description: '',
        regulatory_bodies: ''
    });

    useEffect(() => {
        loadCharters();
    }, []);

    const loadCharters = async () => {
        try {
            const charters = await chartersApi.getAll();
            setCharters(charters);
        } catch (error) {
            toast.error('Failed to load charters');
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        const charterData = {
            name: formData.name,
            code: formData.code.toUpperCase(),
            description: formData.description,
            regulatory_bodies: formData.regulatory_bodies
                .split(',')
                .map(b => b.trim())
                .filter(b => b)
        };

        try {
            if (editingCharter) {
                await chartersApi.update(editingCharter.id, charterData);
                toast.success('Charter updated successfully');
            } else {
                await chartersApi.create(charterData);
                toast.success('Charter created successfully');
            }

            setIsDialogOpen(false);
            resetForm();
            loadCharters();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Failed to save charter');
        }
    };

    const handleEdit = (charter) => {
        setEditingCharter(charter);
        setFormData({
            name: charter.name,
            code: charter.code,
            description: charter.description || '',
            regulatory_bodies: charter.regulatory_bodies.join(', ')
        });
        setIsDialogOpen(true);
    };

    const handleDelete = async (charterId) => {
        if (!window.confirm('Are you sure you want to delete this charter?')) return;

        try {
            await chartersApi.delete(charterId);
            toast.success('Charter deleted successfully');
            loadCharters();
        } catch (error) {
            toast.error('Failed to delete charter');
        }
    };

    const resetForm = () => {
        setFormData({ name: '', code: '', description: '', regulatory_bodies: '' });
        setEditingCharter(null);
    };

    const handleDialogClose = (open) => {
        setIsDialogOpen(open);
        if (!open) resetForm();
    };

    if (loading) {
        return <div className="text-center py-8">Loading charters...</div>;
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Compliance Charters</h2>
                    <p className="text-muted-foreground">Manage product/compliance area categories</p>
                </div>

                <Dialog open={isDialogOpen} onOpenChange={handleDialogClose}>
                    <DialogTrigger asChild>
                        <Button>
                            <Plus className="mr-2 h-4 w-4" />
                            Add Charter
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="sm:max-w-[525px]">
                        <DialogHeader>
                            <DialogTitle>{editingCharter ? 'Edit Charter' : 'Create New Charter'}</DialogTitle>
                            <DialogDescription>
                                Define a compliance charter/product category for organizing policies and regulations.
                            </DialogDescription>
                        </DialogHeader>
                        <form onSubmit={handleSubmit}>
                            <div className="grid gap-4 py-4">
                                <div className="grid gap-2">
                                    <Label htmlFor="name">Charter Name *</Label>
                                    <Input
                                        id="name"
                                        placeholder="e.g., NBFC Compliance, UPI TPAP"
                                        value={formData.name}
                                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                        required
                                    />
                                </div>
                                <div className="grid gap-2">
                                    <Label htmlFor="code">Charter Code *</Label>
                                    <Input
                                        id="code"
                                        placeholder="e.g., NBFC, UPI_TPAP, OPA"
                                        value={formData.code}
                                        onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                                        required
                                    />
                                    <p className="text-xs text-muted-foreground">Short unique identifier (auto-uppercased)</p>
                                </div>
                                <div className="grid gap-2">
                                    <Label htmlFor="description">Description</Label>
                                    <Textarea
                                        id="description"
                                        placeholder="Brief description of this compliance area"
                                        value={formData.description}
                                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                        rows={3}
                                    />
                                </div>
                                <div className="grid gap-2">
                                    <Label htmlFor="regulatory_bodies">Regulatory Bodies</Label>
                                    <Input
                                        id="regulatory_bodies"
                                        placeholder="e.g., RBI, NPCI, SEBI (comma-separated)"
                                        value={formData.regulatory_bodies}
                                        onChange={(e) => setFormData({ ...formData, regulatory_bodies: e.target.value })}
                                    />
                                    <p className="text-xs text-muted-foreground">Comma-separated list of regulatory bodies</p>
                                </div>
                            </div>
                            <DialogFooter>
                                <Button type="button" variant="outline" onClick={() => handleDialogClose(false)}>
                                    Cancel
                                </Button>
                                <Button type="submit">
                                    {editingCharter ? 'Update' : 'Create'} Charter
                                </Button>
                            </DialogFooter>
                        </form>
                    </DialogContent>
                </Dialog>
            </div>

            {charters.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12">
                        <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
                        <p className="text-muted-foreground text-center">
                            No compliance charters yet. Create one to start organizing your policies and regulations.
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {charters.map((charter) => (
                        <Card key={charter.id} className="hover:shadow-lg transition-shadow">
                            <CardHeader>
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <CardTitle className="text-lg">{charter.name}</CardTitle>
                                        <Badge variant="secondary" className="mt-2">{charter.code}</Badge>
                                    </div>
                                    <div className="flex gap-2">
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => handleEdit(charter)}
                                        >
                                            <Edit className="h-4 w-4" />
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            onClick={() => handleDelete(charter.id)}
                                        >
                                            <Trash2 className="h-4 w-4 text-destructive" />
                                        </Button>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {charter.description && (
                                    <p className="text-sm text-muted-foreground mb-3">{charter.description}</p>
                                )}
                                {charter.regulatory_bodies && charter.regulatory_bodies.length > 0 && (
                                    <div className="flex flex-wrap gap-2">
                                        {charter.regulatory_bodies.map((body, idx) => (
                                            <Badge key={idx} variant="outline">{body}</Badge>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
