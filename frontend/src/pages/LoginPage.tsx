import { type FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  Copy,
  Eye,
  EyeOff,
  Layers,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Zap,
} from "lucide-react";

import { Button } from "../components/ui/Button";
import { Checkbox } from "../components/ui/Checkbox";
import { Input } from "../components/ui/Input";
import { Modal } from "../components/ui/Modal";
import { DEMO_CREDENTIALS, isAuthenticated, signIn } from "../lib/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [copiedDemo, setCopiedDemo] = useState(false);
  const [copiedAdminEmail, setCopiedAdminEmail] = useState(false);

  if (isAuthenticated()) {
    return <Navigate to="/" replace />;
  }

  function handleFillDemo() {
    setEmail(DEMO_CREDENTIALS.email);
    setPassword(DEMO_CREDENTIALS.password);
    setError(null);
    setCopiedDemo(true);
    setTimeout(() => setCopiedDemo(false), 2000);
  }

  function handleCopyAdminEmail() {
    navigator.clipboard.writeText(DEMO_CREDENTIALS.email);
    setCopiedAdminEmail(true);
    setTimeout(() => setCopiedAdminEmail(false), 2000);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    // Brief smooth transition for responsive tactile feedback
    setTimeout(() => {
      const success = signIn(email, password);
      if (success) {
        navigate("/", { replace: true });
      } else {
        setError("Invalid email or password. Please verify your workspace credentials.");
        setIsSubmitting(false);
      }
    }, 280);
  }

  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[1.1fr_1fr] xl:grid-cols-[1.15fr_1fr]">
      {/* Left Showcase Banner (Desktop) */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-ink p-10 text-white lg:flex xl:p-14">
        {/* Ambient subtle glow and grid */}
        <div
          className="pointer-events-none absolute -top-40 -left-40 size-[540px] rounded-full bg-primary-600/20 blur-[120px]"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -bottom-32 -right-32 size-[460px] rounded-full bg-primary-500/10 blur-[100px]"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,#ffffff06_1px,transparent_1px),linear-gradient(to_bottom,#ffffff06_1px,transparent_1px)] bg-[size:3.5rem_3.5rem] [mask-image:radial-gradient(ellipse_70%_60%_at_50%_40%,#000_60%,transparent_100%)]"
          aria-hidden="true"
        />

        {/* Top Header / Branding */}
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary-600 to-primary-700 text-white shadow-xs ring-1 ring-white/20">
              <Layers className="size-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-body font-bold tracking-tight text-white">
                Client Acquisition
              </p>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-white/50">Growth Workspace</p>
            </div>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-caption font-medium text-white/80 backdrop-blur-xs">
            <span className="size-2 rounded-full bg-emerald-400 animate-pulse" />
            Operational
          </div>
        </div>

        {/* Hero Copy & Live Feature Preview Card */}
        <div className="relative z-10 my-auto py-8">
          <div className="max-w-lg">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary-400/30 bg-primary-500/15 px-3 py-1 text-caption font-medium text-primary-200 backdrop-blur-xs">
              <Sparkles size={13} className="text-primary-300" />
              Intelligent Pipeline Management
            </div>

            <h1 className="mt-4 text-display-lg font-bold tracking-tight text-white">
              Precision workspace for high-value client acquisition.
            </h1>
            <p className="mt-3 text-body-lg text-white/70">
              Automate prospect discovery, conduct website design audits, orchestrate outreach, and
              track deal progress with actionable clarity.
            </p>
          </div>

          {/* Interactive Metric Preview Card */}
          <div className="mt-8 rounded-panel border border-white/10 bg-white/[0.04] p-5 shadow-2xl backdrop-blur-md">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div className="flex items-center gap-2">
                <TrendingUp size={16} className="text-emerald-400" />
                <span className="text-small font-medium text-white/90">Pipeline Momentum</span>
              </div>
              <span className="text-caption text-white/50">Active sprint</span>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="rounded-control border border-white/5 bg-white/[0.03] p-3">
                <p className="text-caption text-white/60">Active Leads</p>
                <div className="mt-1 flex items-baseline gap-1.5">
                  <span className="text-h2 font-bold text-white">148</span>
                  <span className="text-[11px] font-semibold text-emerald-400">+18%</span>
                </div>
              </div>
              <div className="rounded-control border border-white/5 bg-white/[0.03] p-3">
                <p className="text-caption text-white/60">Delivery Rate</p>
                <div className="mt-1 flex items-baseline gap-1.5">
                  <span className="text-h2 font-bold text-white">99.2%</span>
                </div>
              </div>
              <div className="rounded-control border border-white/5 bg-white/[0.03] p-3">
                <p className="text-caption text-white/60">Design Audits</p>
                <div className="mt-1 flex items-baseline gap-1.5">
                  <span className="text-h2 font-bold text-white">36</span>
                  <span className="text-[11px] font-semibold text-primary-300">Ready</span>
                </div>
              </div>
            </div>

            <div className="mt-3.5 flex items-center justify-between rounded-control border border-white/5 bg-white/[0.02] px-3 py-2 text-caption text-white/70">
              <span className="flex items-center gap-2">
                <CheckCircle2 size={13} className="text-emerald-400" />
                Automated discovery run completed
              </span>
              <span className="text-white/40">2m ago</span>
            </div>
          </div>
        </div>

        {/* Bottom Trust & Security Footnote */}
        <div className="relative z-10 border-t border-white/10 pt-6">
          <div className="grid grid-cols-3 gap-4 text-caption text-white/60">
            <div className="flex items-center gap-2">
              <ShieldCheck size={15} className="shrink-0 text-emerald-400" />
              <span>256-bit encryption</span>
            </div>
            <div className="flex items-center gap-2">
              <Zap size={15} className="shrink-0 text-amber-400" />
              <span>Sub-second queries</span>
            </div>
            <div className="flex items-center gap-2">
              <Lock size={15} className="shrink-0 text-primary-300" />
              <span>Role-gated security</span>
            </div>
          </div>
          <p className="mt-4 text-caption text-white/40">
            © 2026 Client Acquisition System · Private Internal Suite
          </p>
        </div>
      </aside>

      {/* Right Column: Clean Authentication Form */}
      <main className="flex items-center justify-center px-4 py-12 sm:px-6 lg:px-10">
        <div className="w-full max-w-[420px]">
          {/* Mobile Top Brand Header */}
          <div className="mb-8 flex items-center justify-center gap-3 lg:hidden">
            <span className="inline-flex size-9 items-center justify-center rounded-control bg-primary text-small font-bold text-white shadow-sm">
              CA
            </span>
            <div className="text-left">
              <p className="text-h4 font-bold tracking-tight text-ink">Client Acquisition</p>
              <p className="text-caption text-gray-500">Internal Workspace</p>
            </div>
          </div>

          {/* Form Card Container */}
          <div className="rounded-2xl border border-gray-200/80 bg-white p-7 shadow-sm sm:p-9">
            <div className="mb-6">
              <h2 className="text-h2 font-bold tracking-tight text-ink">Sign in</h2>
              <p className="mt-1 text-body text-gray-500">
                Enter your workspace credentials to access the portal.
              </p>
            </div>

            {/* Quick Demo Fill Helper Banner */}
            <div className="mb-6 flex items-center justify-between rounded-control border border-primary-200/70 bg-primary-50/60 px-3.5 py-2.5">
              <div className="flex items-center gap-2">
                <Sparkles size={15} className="text-primary-600" />
                <span className="text-small font-medium text-primary-900">Demo workspace</span>
              </div>
              <button
                type="button"
                onClick={handleFillDemo}
                className="inline-flex items-center gap-1.5 rounded-md bg-white px-2.5 py-1 text-caption font-semibold text-primary-700 shadow-2xs hover:bg-primary-50 hover:text-primary-800 transition-colors"
                title="Fill demo email and password"
              >
                {copiedDemo ? (
                  <>
                    <Check size={12} className="text-emerald-600" />
                    <span>Applied</span>
                  </>
                ) : (
                  <>
                    <Copy size={12} />
                    <span>Quick Fill</span>
                  </>
                )}
              </button>
            </div>

            {/* Error Message Box */}
            {error ? (
              <div
                className="mb-6 flex items-start gap-3 rounded-control border border-danger/20 bg-danger/5 p-3.5 text-small text-danger"
                role="alert"
              >
                <AlertCircle size={18} className="mt-0.5 shrink-0 text-danger" />
                <div className="flex-1">
                  <p className="font-semibold text-danger">Sign in failed</p>
                  <p className="mt-0.5 text-danger/90">{error}</p>
                </div>
              </div>
            ) : null}

            {/* Login Form */}
            <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
              <Input
                label="Workspace Email"
                type="email"
                name="email"
                placeholder="name@company.com"
                autoComplete="username"
                autoFocus
                required
                leftIcon={<Mail size={16} />}
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setError(null);
                }}
              />

              <Input
                label="Password"
                type={showPassword ? "text" : "password"}
                name="password"
                placeholder="••••••••••••"
                autoComplete="current-password"
                required
                leftIcon={<Lock size={16} />}
                rightElement={
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="cursor-pointer text-gray-400 hover:text-gray-600 focus:outline-hidden"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                }
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  setError(null);
                }}
              />

              <div className="flex items-center justify-between pt-1">
                <Checkbox
                  label="Remember for 30 days"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                />
                <button
                  type="button"
                  onClick={() => setShowForgotModal(true)}
                  className="text-small font-medium text-primary-600 hover:text-primary-700 hover:underline"
                >
                  Forgot password?
                </button>
              </div>

              <Button
                type="submit"
                isLoading={isSubmitting}
                className="mt-2 w-full font-semibold shadow-xs"
              >
                <span>Sign in to Workspace</span>
                {!isSubmitting && <ArrowRight size={16} />}
              </Button>
            </form>

            <div className="mt-6 border-t border-gray-100 pt-4 text-center">
              <p className="flex items-center justify-center gap-1.5 text-caption text-gray-400">
                <ShieldCheck size={14} className="text-gray-400" />
                Protected internal operator environment
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Forgot Password Information Modal */}
      <Modal
        open={showForgotModal}
        title="Workspace Credentials"
        description="Password reset & recovery guidance for internal workspace operators."
        onClose={() => setShowForgotModal(false)}
      >
        <div className="space-y-4">
          <p className="text-body text-gray-600">
            Client Acquisition is a restricted internal workspace. Passwords are managed directly by
            your workspace administrator.
          </p>

          <div className="rounded-control border border-gray-200 bg-gray-50 p-4">
            <p className="text-caption font-semibold uppercase tracking-wider text-gray-500">
              Workspace Administrator
            </p>
            <div className="mt-2 flex items-center justify-between">
              <span className="font-mono text-small text-ink">{DEMO_CREDENTIALS.email}</span>
              <Button
                variant="secondary"
                size="default"
                className="h-8 px-2.5 text-caption"
                onClick={handleCopyAdminEmail}
              >
                {copiedAdminEmail ? (
                  <>
                    <Check size={14} className="text-emerald-600" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy size={14} />
                    Copy Email
                  </>
                )}
              </Button>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <Button variant="primary" onClick={() => setShowForgotModal(false)}>
              Got it
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
