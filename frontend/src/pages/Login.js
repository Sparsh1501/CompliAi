import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Shield } from 'lucide-react';
import { toast } from 'sonner';

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/dashboard';
  const [loading, setLoading] = useState(false);

  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [registerData, setRegisterData] = useState({
    email: '',
    password: '',
    full_name: '',
    organization: ''
  });
  const [registerErrors, setRegisterErrors] = useState({});

  const validateEmail = (email) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  const validateRegisterForm = () => {
    const errors = {};
    if (!registerData.full_name.trim()) {
      errors.full_name = 'Full name is required';
    }
    if (!registerData.email.trim()) {
      errors.email = 'Email is required';
    } else if (!validateEmail(registerData.email)) {
      errors.email = 'Please enter a valid email address';
    }
    if (!registerData.organization.trim()) {
      errors.organization = 'Organization is required';
    }
    if (!registerData.password) {
      errors.password = 'Password is required';
    } else if (registerData.password.length < 6) {
      errors.password = 'Password must be at least 6 characters';
    }
    setRegisterErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    const result = await login(loginData.email, loginData.password);
    setLoading(false);

    if (result.success) {
      toast.success('Login successful!');
      navigate(from, { replace: true });
    } else {
      toast.error(result.error || 'Login failed');
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    if (!validateRegisterForm()) return;
    setLoading(true);
    const result = await register(
      registerData.email,
      registerData.password,
      registerData.full_name,
      registerData.organization
    );
    setLoading(false);

    if (result.success) {
      toast.success('Registration successful!');
      navigate(from, { replace: true });
    } else {
      toast.error(result.error || 'Registration failed');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4" data-testid="login-page">
      {/* Background effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-emerald-100/50 rounded-full blur-3xl"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-100/50 rounded-full blur-3xl"></div>
      </div>

      <div className="w-full max-w-md relative z-10">
        <div className="flex items-center justify-center mb-8" data-testid="logo-section">
          <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 flex items-center justify-center shadow-lg shadow-emerald-500/20 mr-4">
            <Shield className="h-8 w-8 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">CompliAI</h1>
            <p className="text-sm text-gray-500">Enterprise Compliance Platform</p>
          </div>
        </div>

        <Card data-testid="auth-card" className="bg-white border-gray-200 shadow-xl">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl text-gray-900">Welcome Back</CardTitle>
            <CardDescription className="text-gray-500">AI-powered compliance management for regulated entities</CardDescription>
          </CardHeader>

          <CardContent>
            <Tabs defaultValue="login" className="w-full">
              <TabsList className="grid w-full grid-cols-2 bg-gray-100 border border-gray-200">
                <TabsTrigger value="login" data-testid="login-tab" className="data-[state=active]:bg-white data-[state=active]:text-emerald-700 data-[state=active]:shadow-sm text-gray-500">Login</TabsTrigger>
                <TabsTrigger value="register" data-testid="register-tab" className="data-[state=active]:bg-white data-[state=active]:text-emerald-700 data-[state=active]:shadow-sm text-gray-500">Register</TabsTrigger>
              </TabsList>

              <TabsContent value="login" data-testid="login-form">
                <form onSubmit={handleLogin} className="space-y-4 mt-4">
                  <div>
                    <Label htmlFor="login-email" className="text-gray-700">Email</Label>
                    <Input
                      id="login-email"
                      data-testid="login-email-input"
                      type="email"
                      placeholder="your@email.com"
                      value={loginData.email}
                      onChange={(e) => setLoginData({ ...loginData, email: e.target.value })}
                      required
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="login-password" className="text-gray-700">Password</Label>
                    <Input
                      id="login-password"
                      data-testid="login-password-input"
                      type="password"
                      placeholder="••••••••"
                      value={loginData.password}
                      onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                      required
                      className="mt-1"
                    />
                  </div>
                  <Button type="submit" className="w-full btn-shiny text-white h-11" disabled={loading} data-testid="login-submit-button">
                    {loading ? 'Logging in...' : 'Login'}
                  </Button>
                </form>
              </TabsContent>

              <TabsContent value="register" data-testid="register-form">
                <form onSubmit={handleRegister} className="space-y-4 mt-4" noValidate>
                  <div>
                    <Label htmlFor="register-name" className="text-gray-700">Full Name</Label>
                    <Input
                      id="register-name"
                      data-testid="register-name-input"
                      type="text"
                      placeholder="John Doe"
                      value={registerData.full_name}
                      onChange={(e) => { setRegisterData({ ...registerData, full_name: e.target.value }); setRegisterErrors(prev => ({ ...prev, full_name: undefined })); }}
                      className={registerErrors.full_name ? 'border-red-500' : ''}
                    />
                    {registerErrors.full_name && <p className="text-sm text-red-500 mt-1" data-testid="register-name-error">{registerErrors.full_name}</p>}
                  </div>
                  <div>
                    <Label htmlFor="register-email" className="text-gray-700">Email</Label>
                    <Input
                      id="register-email"
                      data-testid="register-email-input"
                      type="email"
                      placeholder="your@email.com"
                      value={registerData.email}
                      onChange={(e) => { setRegisterData({ ...registerData, email: e.target.value }); setRegisterErrors(prev => ({ ...prev, email: undefined })); }}
                      className={registerErrors.email ? 'border-red-500' : ''}
                    />
                    {registerErrors.email && <p className="text-sm text-red-500 mt-1" data-testid="register-email-error">{registerErrors.email}</p>}
                  </div>
                  <div>
                    <Label htmlFor="register-organization" className="text-gray-700">Organization</Label>
                    <Input
                      id="register-organization"
                      data-testid="register-organization-input"
                      type="text"
                      placeholder="Your NBFC/FinTech"
                      value={registerData.organization}
                      onChange={(e) => { setRegisterData({ ...registerData, organization: e.target.value }); setRegisterErrors(prev => ({ ...prev, organization: undefined })); }}
                      className={registerErrors.organization ? 'border-red-500' : ''}
                    />
                    {registerErrors.organization && <p className="text-sm text-red-500 mt-1" data-testid="register-organization-error">{registerErrors.organization}</p>}
                  </div>
                  <div>
                    <Label htmlFor="register-password" className="text-gray-700">Password</Label>
                    <Input
                      id="register-password"
                      data-testid="register-password-input"
                      type="password"
                      placeholder="••••••••"
                      value={registerData.password}
                      onChange={(e) => { setRegisterData({ ...registerData, password: e.target.value }); setRegisterErrors(prev => ({ ...prev, password: undefined })); }}
                      className={registerErrors.password ? 'border-red-500' : ''}
                    />
                    {registerErrors.password && <p className="text-sm text-red-500 mt-1" data-testid="register-password-error">{registerErrors.password}</p>}
                  </div>
                  <Button type="submit" className="w-full btn-shiny text-white h-11" disabled={loading} data-testid="register-submit-button">
                    {loading ? 'Creating account...' : 'Register'}
                  </Button>
                </form>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <p className="text-center text-sm text-gray-500 mt-6">
          AI-powered compliance management for regulated entities
        </p>
      </div>
    </div>
  );
}
