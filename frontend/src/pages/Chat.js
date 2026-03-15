import React, { useState, useRef, useEffect } from 'react';
import { chatApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { MessageCircle, Send, Sparkles, User, Search, Plus, History, X, Menu, Link as LinkIcon } from 'lucide-react';
import { toast } from 'sonner';
import { v4 as uuidv4 } from 'uuid';
import { useNavigate } from 'react-router-dom';

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => uuidv4());
  const [threads, setThreads] = useState([]);
  const [threadsOpen, setThreadsOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [proactiveInsight, setProactiveInsight] = useState(null);
  const [insightData, setInsightData] = useState(null);
  const messagesEndRef = useRef(null);
  const navigate = useNavigate();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);
  useEffect(() => { loadThreads(); loadInsights(); }, []);

  const loadInsights = async () => {
    try {
      const result = await chatApi.getInsights();
      if (result && result.insight) {
        setProactiveInsight(result.insight);
        setInsightData(result.data || {});
      }
    } catch (error) {
      // Insights are optional, fail silently
    }
  };

  const loadThreads = async () => {
    try {
      const result = await chatApi.getThreads();
      setThreads(Array.isArray(result) ? result : []);
    } catch (error) {
      // Threads may not exist yet
    }
  };

  const loadThread = async (threadSessionId) => {
    try {
      const result = await chatApi.getThread(threadSessionId);
      const threadMessages = (Array.isArray(result) ? result : result?.messages || []).map(m => ({
        role: m.role,
        content: m.content || m.response || m.message,
        timestamp: new Date(m.timestamp || m.created_at || Date.now()),
      }));
      setMessages(threadMessages);
      setSessionId(threadSessionId);
      toast.success('Thread loaded');
    } catch (error) {
      toast.error('Failed to load thread');
    }
  };

  const handleNewThread = () => {
    setSessionId(uuidv4());
    setMessages([]);
    toast.success('New conversation started');
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const result = await chatApi.search(searchQuery);
      setSearchResults(Array.isArray(result) ? result : result?.results || []);
    } catch (error) {
      toast.error('Search failed');
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = { role: 'user', content: input, timestamp: new Date() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await chatApi.sendMessage(sessionId, input);
      const assistantMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, assistantMessage]);
      loadThreads(); // Refresh thread list
    } catch (error) {
      toast.error('Failed to get response');
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'I apologize, but I encountered an error. Please try again.', timestamp: new Date() }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Render bold markdown (**text**) as <strong>
  const renderBold = (text) => {
    if (!text) return text;
    const boldRegex = /\*\*([^*]+)\*\*/g;
    const parts = [];
    let lastIndex = 0;
    let match;
    while ((match = boldRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }
      parts.push(<strong key={match.index}>{match[1]}</strong>);
      lastIndex = match.index + match[0].length;
    }
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }
    return parts.length > 0 ? parts : text;
  };

  return (
    <div className="h-[calc(100vh-12rem)] flex" data-testid="chat-page">
      {/* Thread Sidebar */}
      {sidebarOpen && (
        <div className="w-64 border-r flex flex-col mr-4" data-testid="chat-sidebar">
          <div className="p-3 border-b flex items-center justify-between">
            <span className="font-semibold text-sm">Threads</span>
            <div className="flex gap-1">
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setSearchOpen(true)} data-testid="chat-search-button">
                <Search className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleNewThread} data-testid="new-thread-button">
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <ScrollArea className="flex-1">
            <div className="p-2 space-y-1">
              <div
                className={`p-2 rounded cursor-pointer text-sm hover:bg-muted ${!threads.find(t => (t.session_id || t._id) === sessionId) ? 'bg-muted' : ''}`}
                onClick={handleNewThread}
                data-testid="current-thread"
              >
                <div className="flex items-center gap-2">
                  <MessageCircle className="h-3.5 w-3.5" />
                  <span className="truncate">Current Conversation</span>
                </div>
              </div>
              {threads.map((thread) => {
                const tId = thread.session_id || thread._id;
                return (
                  <div
                    key={tId}
                    className={`p-2 rounded cursor-pointer text-sm hover:bg-muted ${sessionId === tId ? 'bg-muted' : ''}`}
                    onClick={() => loadThread(tId)}
                    data-testid={`thread-${tId}`}
                  >
                    <div className="flex items-center gap-2">
                      <History className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="truncate">{thread.first_message || thread.title || `Thread ${tId.slice(0, 8)}`}</span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {thread.message_count || 0} messages
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <div className="mb-4 flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(!sidebarOpen)} data-testid="toggle-sidebar">
            <Menu className="h-5 w-5" />
          </Button>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center shadow-lg">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold" data-testid="chat-title">NeoGPT</h1>
            <p className="text-sm text-muted-foreground">BFSI-focused compliance AI assistant</p>
          </div>
        </div>

        <Card className="flex-1 flex flex-col">
          <CardContent className="flex-1 flex flex-col p-0">
            <div className="flex-1 overflow-y-auto p-6 space-y-4" data-testid="chat-messages">
              {messages.length === 0 ? (
                <div className="flex flex-col h-full" data-testid="chat-empty">
                  {/* Proactive AI Insights */}
                  {proactiveInsight && (
                    <div className="flex gap-3 justify-start mb-6" data-testid="proactive-insight">
                      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                        <Sparkles className="h-5 w-5 text-primary" />
                      </div>
                      <div className="max-w-[85%] rounded-lg p-4 bg-muted">
                        <div className="text-sm whitespace-pre-wrap" data-testid="insight-content">
                          {proactiveInsight.split('\n').map((line, i) => {
                            // Parse markdown links like [text](/path)
                            const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
                            const parts = [];
                            let lastIndex = 0;
                            let match;
                            while ((match = linkRegex.exec(line)) !== null) {
                              if (match.index > lastIndex) {
                                parts.push(<span key={`t-${i}-${lastIndex}`}>{renderBold(line.slice(lastIndex, match.index))}</span>);
                              }
                              const linkPath = match[2];
                              parts.push(
                                <button
                                  key={`l-${i}-${match.index}`}
                                  className="text-primary hover:underline font-medium inline-flex items-center gap-1"
                                  onClick={() => navigate(linkPath)}
                                  data-testid={`insight-link-${linkPath.replace(/\//g, '-')}`}
                                >
                                  {match[1]}
                                  <LinkIcon className="h-3 w-3 inline" />
                                </button>
                              );
                              lastIndex = match.index + match[0].length;
                            }
                            if (lastIndex < line.length) {
                              parts.push(<span key={`t-${i}-${lastIndex}`}>{renderBold(line.slice(lastIndex))}</span>);
                            }
                            if (parts.length === 0) {
                              parts.push(<span key={`t-${i}-0`}>{renderBold(line)}</span>);
                            }
                            return <div key={i} className={line === '' ? 'h-2' : ''}>{parts}</div>;
                          })}
                        </div>
                        <div className="text-xs opacity-70 mt-2">
                          {new Date().toLocaleTimeString()} · Proactive Insight
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Empty state with suggestions */}
                  <div className="flex flex-col items-center justify-center flex-1 text-center">
                    {!proactiveInsight && (
                      <>
                        <MessageCircle className="h-16 w-16 text-muted-foreground mb-4" />
                        <h3 className="text-lg font-semibold mb-2">Start a Conversation</h3>
                        <p className="text-muted-foreground max-w-md">
                          Ask me anything about compliance, regulations, policies, or get guidance on RBI/SEBI requirements.
                        </p>
                      </>
                    )}
                    <div className={`${proactiveInsight ? 'mt-2' : 'mt-6'} grid grid-cols-1 gap-2 max-w-lg`}>
                      {['What are the key KYC requirements for NBFCs?', 'Explain RBI fair practices code', 'What are AML compliance requirements?'].map(q => (
                        <Button key={q} variant="outline" className="text-left justify-start" onClick={() => setInput(q)}
                          data-testid="suggested-question">
                          {q}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                messages.map((message, index) => (
                  <div key={index} className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    data-testid={`chat-message-${index}`}>
                    {message.role === 'assistant' && (
                      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                        <Sparkles className="h-5 w-5 text-primary" />
                      </div>
                    )}
                    <div className={`max-w-[80%] rounded-lg p-4 ${message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
                      <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                      <div className="text-xs opacity-70 mt-2">
                        {message.timestamp instanceof Date ? message.timestamp.toLocaleTimeString() : new Date(message.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                    {message.role === 'user' && (
                      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                        <User className="h-5 w-5 text-primary-foreground" />
                      </div>
                    )}
                  </div>
                ))
              )}
              {loading && (
                <div className="flex gap-3 justify-start" data-testid="chat-loading">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                    <Sparkles className="h-5 w-5 text-primary animate-pulse" />
                  </div>
                  <div className="bg-muted rounded-lg p-4">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="border-t p-4" data-testid="chat-input-area">
              <div className="flex gap-2">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask about compliance, regulations, policies..."
                  className="min-h-[60px] max-h-[120px]"
                  disabled={loading}
                  data-testid="chat-input"
                />
                <Button onClick={handleSend} disabled={!input.trim() || loading} size="icon" className="h-[60px] w-[60px]" data-testid="chat-send-button">
                  <Send className="h-5 w-5" />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                NeoGPT is powered by AI. Verify critical compliance information with official sources.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search Dialog */}
      <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
        <DialogContent className="max-w-lg" data-testid="chat-search-dialog">
          <DialogHeader>
            <DialogTitle>Search Messages</DialogTitle>
          </DialogHeader>
          <div className="flex gap-2">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search across all conversations..."
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              data-testid="chat-search-input"
            />
            <Button onClick={handleSearch} disabled={searching} data-testid="chat-search-submit">
              <Search className="h-4 w-4" />
            </Button>
          </div>
          <ScrollArea className="max-h-64 mt-2">
            {searchResults.length > 0 ? (
              <div className="space-y-2" data-testid="chat-search-results">
                {searchResults.map((result, i) => (
                  <Card key={i} className="cursor-pointer hover:bg-muted" onClick={() => {
                    if (result.session_id) loadThread(result.session_id);
                    setSearchOpen(false);
                  }} data-testid={`search-result-${i}`}>
                    <CardContent className="p-3">
                      <div className="text-sm font-medium">{result.content || result.message}</div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {result.role} · {result.created_at ? new Date(result.created_at).toLocaleString() : ''}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : searchQuery && !searching ? (
              <p className="text-sm text-muted-foreground text-center py-4" data-testid="search-no-results">No results found</p>
            ) : null}
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </div>
  );
}
