import React, { useEffect, useState } from 'react';
import { calendarApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Calendar as CalendarIcon, Plus, Clock, Shield, Edit, Trash2, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';
import { MOCK_CALENDAR_EVENTS } from '../lib/mockData';

const regulators = ['RBI', 'SEBI', 'NSE', 'BSE', 'IRDAI', 'FIU_IND', 'NPCI', 'ICCL', 'NSDL'];
const eventTypes = ['Submission', 'Filing', 'Report', 'Review', 'Audit', 'Renewal', 'Other'];
const statuses = ['Pending', 'In Progress', 'Completed', 'Overdue'];

const emptyEvent = {
  title: '', description: '', event_type: 'Submission', regulator: 'RBI',
  due_date: '', responsible_department: '', status: 'Pending'
};

export default function Calendar() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [saving, setSaving] = useState(false);
  const [eventData, setEventData] = useState({ ...emptyEvent });
  const [filterRegulator, setFilterRegulator] = useState('all');

  useEffect(() => { loadEvents(); }, []);

  const loadEvents = async () => {
    try {
      const response = await calendarApi.getEvents();
      const list = Array.isArray(response) ? response : [];
      // Use mock data if API returns empty
      setEvents(list.length > 0 ? list : MOCK_CALENDAR_EVENTS);
    } catch (error) {
      // Fallback to mock data for demo
      setEvents(MOCK_CALENDAR_EVENTS);
      console.log('Using mock calendar data for demo');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await calendarApi.createEvent({ ...eventData, due_date: new Date(eventData.due_date).toISOString() });
      toast.success('Event created successfully!');
      setCreateOpen(false);
      setEventData({ ...emptyEvent });
      loadEvents();
    } catch (error) {
      toast.error('Failed to create event');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (event) => {
    const eId = event.id || event._id;
    setSelectedEvent(event);
    setEventData({
      title: event.title || '',
      description: event.description || '',
      event_type: event.event_type || 'Submission',
      regulator: event.regulator || 'RBI',
      due_date: event.due_date ? new Date(event.due_date).toISOString().slice(0, 16) : '',
      responsible_department: event.responsible_department || '',
      status: event.status || 'Pending',
    });
    setEditOpen(true);
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    const eId = selectedEvent?.id || selectedEvent?._id;
    if (!eId) return;
    setSaving(true);
    try {
      await calendarApi.updateEvent(eId, { ...eventData, due_date: new Date(eventData.due_date).toISOString() });
      toast.success('Event updated successfully!');
      setEditOpen(false);
      setSelectedEvent(null);
      loadEvents();
    } catch (error) {
      toast.error('Failed to update event');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteConfirm = (event) => {
    setSelectedEvent(event);
    setDeleteConfirmOpen(true);
  };

  const handleDelete = async () => {
    const eId = selectedEvent?.id || selectedEvent?._id;
    if (!eId) return;
    try {
      await calendarApi.deleteEvent(eId);
      toast.success('Event deleted');
      setDeleteConfirmOpen(false);
      setSelectedEvent(null);
      loadEvents();
    } catch (error) {
      toast.error('Failed to delete event');
    }
  };

  const handleMarkComplete = async (event) => {
    const eId = event.id || event._id;
    try {
      await calendarApi.updateEvent(eId, { ...event, status: 'Completed' });
      toast.success('Event marked as completed');
      loadEvents();
    } catch (error) {
      toast.error('Failed to update event');
    }
  };

  const getStatusColor = (event) => {
    if (event.status === 'Completed') return 'bg-green-100 text-green-800';
    const dueDate = new Date(event.due_date);
    const today = new Date();
    const daysUntilDue = Math.ceil((dueDate - today) / (1000 * 60 * 60 * 24));
    if (daysUntilDue < 0) return 'bg-red-100 text-red-800';
    if (daysUntilDue <= 7) return 'bg-orange-100 text-orange-800';
    if (daysUntilDue <= 30) return 'bg-yellow-100 text-yellow-800';
    return 'bg-blue-100 text-blue-800';
  };

  const getDaysUntilDue = (event) => {
    if (event.status === 'Completed') return 'Completed';
    const due = new Date(event.due_date);
    const today = new Date();
    const days = Math.ceil((due - today) / (1000 * 60 * 60 * 24));
    if (days < 0) return `${Math.abs(days)} days overdue`;
    if (days === 0) return 'Due today';
    if (days === 1) return 'Due tomorrow';
    return `${days} days remaining`;
  };

  const filteredEvents = events.filter(e => filterRegulator === 'all' || e.regulator === filterRegulator);

  const groupEventsByMonth = () => {
    const grouped = {};
    filteredEvents.forEach(event => {
      const date = new Date(event.due_date);
      const monthYear = date.toLocaleDateString('en-US', { year: 'numeric', month: 'long' });
      if (!grouped[monthYear]) grouped[monthYear] = [];
      grouped[monthYear].push(event);
    });
    return grouped;
  };

  const groupedEvents = groupEventsByMonth();

  const renderEventForm = (onSubmit, buttonText) => (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="event-form">
      <div>
        <Label htmlFor="event-title">Title</Label>
        <Input id="event-title" value={eventData.title} onChange={(e) => setEventData({ ...eventData, title: e.target.value })}
          placeholder="e.g., Quarterly AML Report Submission" required data-testid="event-title-input" />
      </div>
      <div>
        <Label htmlFor="event-description">Description</Label>
        <Textarea id="event-description" value={eventData.description} onChange={(e) => setEventData({ ...eventData, description: e.target.value })}
          placeholder="Details about the compliance obligation..." rows={3} data-testid="event-description-input" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label>Event Type</Label>
          <Select value={eventData.event_type} onValueChange={(v) => setEventData({ ...eventData, event_type: v })}>
            <SelectTrigger data-testid="event-type-select"><SelectValue /></SelectTrigger>
            <SelectContent>{eventTypes.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div>
          <Label>Regulator</Label>
          <Select value={eventData.regulator} onValueChange={(v) => setEventData({ ...eventData, regulator: v })}>
            <SelectTrigger data-testid="event-regulator-select"><SelectValue /></SelectTrigger>
            <SelectContent>{regulators.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label>Due Date</Label>
          <Input type="datetime-local" value={eventData.due_date} onChange={(e) => setEventData({ ...eventData, due_date: e.target.value })}
            required data-testid="event-due-date-input" />
        </div>
        <div>
          <Label>Status</Label>
          <Select value={eventData.status} onValueChange={(v) => setEventData({ ...eventData, status: v })}>
            <SelectTrigger data-testid="event-status-select"><SelectValue /></SelectTrigger>
            <SelectContent>{statuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>
      <div>
        <Label>Responsible Department</Label>
        <Input value={eventData.responsible_department} onChange={(e) => setEventData({ ...eventData, responsible_department: e.target.value })}
          placeholder="e.g., Compliance" data-testid="event-department-input" />
      </div>
      <Button type="submit" className="w-full" disabled={saving} data-testid="submit-event-button">
        {saving ? 'Saving...' : buttonText}
      </Button>
    </form>
  );

  return (
    <div className="space-y-8" data-testid="calendar-page">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center shadow-lg">
            <CalendarIcon className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold" data-testid="calendar-title">Compliance Calendar</h1>
            <p className="text-muted-foreground">Track compliance obligations and deadlines</p>
          </div>
        </div>
        <div className="flex gap-2 items-center">
          <Select value={filterRegulator} onValueChange={setFilterRegulator}>
            <SelectTrigger className="w-36" data-testid="calendar-regulator-filter"><SelectValue placeholder="All Regulators" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Regulators</SelectItem>
              {regulators.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
            </SelectContent>
          </Select>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button data-testid="create-event-button"><Plus className="mr-2 h-4 w-4" /> Add Event</Button>
            </DialogTrigger>
            <DialogContent data-testid="create-event-dialog">
              <DialogHeader>
                <DialogTitle>Create Compliance Event</DialogTitle>
                <DialogDescription>Add a new compliance obligation to the calendar</DialogDescription>
              </DialogHeader>
              {renderEventForm(handleCreate, 'Create Event')}
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64" data-testid="calendar-loading">
          <div className="text-muted-foreground">Loading events...</div>
        </div>
      ) : filteredEvents.length === 0 ? (
        <Card className="flex flex-col items-center justify-center h-64" data-testid="calendar-empty">
          <CardContent className="text-center py-8">
            <CalendarIcon className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Events</h3>
            <p className="text-muted-foreground mb-4">Create your first compliance event</p>
            <Button onClick={() => setCreateOpen(true)}><Plus className="mr-2 h-4 w-4" /> Add Event</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-8">
          {Object.entries(groupedEvents).map(([monthYear, monthEvents]) => (
            <div key={monthYear}>
              <h2 className="text-2xl font-bold mb-4">{monthYear}</h2>
              <div className="space-y-4">
                {monthEvents.map((event) => {
                  const eId = event.id || event._id;
                  return (
                    <Card key={eId} data-testid={`calendar-event-${eId}`}>
                      <CardHeader>
                        <div className="flex items-start justify-between">
                          <div>
                            <CardTitle className="flex items-center gap-2">
                              <Shield className="h-5 w-5" />
                              {event.title}
                            </CardTitle>
                            <CardDescription>{event.description}</CardDescription>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge className={getStatusColor(event)} data-testid={`event-status-${eId}`}>
                              {getDaysUntilDue(event)}
                            </Badge>
                            {event.status !== 'Completed' && (
                              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleMarkComplete(event)}
                                data-testid={`complete-event-${eId}`} title="Mark complete">
                                <CheckCircle className="h-4 w-4 text-green-500" />
                              </Button>
                            )}
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleEdit(event)}
                              data-testid={`edit-event-${eId}`}>
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleDeleteConfirm(event)}
                              data-testid={`delete-event-${eId}`}>
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                          <div>
                            <div className="text-muted-foreground">Type</div>
                            <div className="font-medium">{event.event_type}</div>
                          </div>
                          <div>
                            <div className="text-muted-foreground">Regulator</div>
                            <div className="font-medium">{event.regulator}</div>
                          </div>
                          <div>
                            <div className="text-muted-foreground">Due Date</div>
                            <div className="font-medium flex items-center gap-1">
                              <Clock className="h-4 w-4" />
                              {new Date(event.due_date).toLocaleDateString()}
                            </div>
                          </div>
                          <div>
                            <div className="text-muted-foreground">Status</div>
                            <div className="font-medium">{event.status || 'Pending'}</div>
                          </div>
                          {event.responsible_department && (
                            <div>
                              <div className="text-muted-foreground">Department</div>
                              <div className="font-medium">{event.responsible_department}</div>
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Event Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent data-testid="edit-event-dialog">
          <DialogHeader>
            <DialogTitle>Edit Event</DialogTitle>
            <DialogDescription>Update compliance event details</DialogDescription>
          </DialogHeader>
          {renderEventForm(handleUpdate, 'Update Event')}
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <AlertDialogContent data-testid="delete-event-confirm">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Event</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedEvent?.title}"? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-event">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700" data-testid="confirm-delete-event">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
