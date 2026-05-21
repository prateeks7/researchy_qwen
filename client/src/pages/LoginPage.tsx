import { Search, BrainCircuit, MessageSquare, ShieldCheck } from 'lucide-react'
import sidebarBg from '../../utils/backgrounds/sidebar.jpg'
import chatBg from '../../utils/backgrounds/chat.jpg'
import icon from '../../utils/backgrounds/Icon.png'

const API_BASE = 'http://localhost:8000'

const FEATURES = [
  {
    icon: Search,
    title: 'Three databases, one query',
    desc: 'Search arXiv, Semantic Scholar, and PubMed simultaneously — no tab switching.',
  },
  {
    icon: BrainCircuit,
    title: 'AI answers grounded in real papers',
    desc: 'Every claim is backed by a paper your agent downloaded and parsed — never hallucinated.',
  },
  {
    icon: MessageSquare,
    title: 'Multi-turn research conversations',
    desc: 'Ask follow-ups, request comparisons, and dig into methodology — all in context.',
  },
  {
    icon: ShieldCheck,
    title: 'Private history, always accessible',
    desc: 'Every conversation is saved to your account and restored exactly as you left it.',
  },
]

function GoogleIcon() {
  return (
    <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  )
}

function GitHubIcon() {
  return (
    <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
    </svg>
  )
}

export function LoginPage() {
  return (
    <div className="flex h-screen w-screen overflow-hidden">

      {/* ── Left panel 70% ───────────────────────────────────────────────── */}
      <div
        className="relative flex-[7] flex flex-col justify-between p-14 overflow-hidden"
        style={{ backgroundImage: `url(${sidebarBg})`, backgroundSize: 'cover', backgroundPosition: 'center' }}
      >

        {/* Top: Logo + wordmark */}
        <div className="relative z-10 flex items-center gap-3">
          <img src={icon} alt="Berg" className="w-10 h-10 rounded-full object-cover shadow-lg" />
          <div>
            <p className="text-black font-semibold text-base leading-tight tracking-wide">Researchy Berg</p>
            <p className="text-black/45 text-[11px] tracking-wider uppercase">AI Research Assistant</p>
          </div>
        </div>

        {/* Centre: Headline + sub */}
        <div className="relative z-10">
          <p className="text-black/50 text-sm font-medium tracking-[0.2em] uppercase mb-4">
            Research · Discover · Understand
          </p>
          <h1
            className="text-black leading-[1.1] mb-6"
            style={{ fontFamily: "'Playfair Display', Georgia, serif", fontSize: 'clamp(2.8rem, 4.5vw, 4.2rem)', fontWeight: 900 }}
          >
            Explore the World<br />
            <span style={{ fontStyle: 'italic', fontWeight: 700 }}>of Research</span>
          </h1>
          <p className="text-black/65 text-lg leading-relaxed max-w-lg">
            Berg is your AI-powered academic research companion — searching millions of papers,
            extracting real insights, and answering your questions with full citations.
          </p>
        </div>

        {/* Bottom: Feature grid */}
        <div className="relative z-10 grid grid-cols-2 gap-4">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="flex gap-3 p-4 rounded-xl bg-black/8 border border-black/10"
            >
              <div className="flex-shrink-0 mt-0.5">
                <div className="w-7 h-7 rounded-lg bg-black/15 flex items-center justify-center">
                  <Icon className="w-3.5 h-3.5 text-black/80" />
                </div>
              </div>
              <div>
                <p className="text-black text-sm font-semibold leading-snug mb-0.5">{title}</p>
                <p className="text-black/50 text-xs leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right panel 30% ──────────────────────────────────────────────── */}
      <div
        className="relative flex-[3] flex items-center justify-center p-6 overflow-hidden"
        style={{ backgroundImage: `url(${chatBg})`, backgroundSize: 'cover', backgroundPosition: 'center' }}
      >

        {/* Card */}
        <div
          className="relative z-10 w-full max-w-[340px] rounded-2xl shadow-2xl border border-black/10"
          style={{ backgroundImage: `url(${sidebarBg})`, backgroundSize: 'cover', backgroundPosition: 'center' }}
        >
          <div className="relative z-10 p-7">

            {/* Card header */}
            <div className="flex flex-col items-center gap-2 mb-8">
              <img src={icon} alt="Berg" className="w-11 h-11 rounded-full object-cover shadow" />
              <p className="text-black font-semibold text-base">Welcome to Berg</p>
              <p className="text-black/40 text-xs">Sign in to your research account</p>
            </div>

            {/* OAuth buttons */}
            <div className="flex flex-col gap-3">
              <a
                href={`${API_BASE}/api/auth/google`}
                className="flex items-center justify-center gap-2.5 py-2.5 rounded-lg bg-white border border-black/15 hover:bg-black/5 text-black text-sm font-medium transition-all shadow-sm"
              >
                <GoogleIcon /> Continue with Google
              </a>
              <a
                href={`${API_BASE}/api/auth/github`}
                className="flex items-center justify-center gap-2.5 py-2.5 rounded-lg bg-black/85 hover:bg-black border border-black/10 text-white text-sm font-medium transition-all shadow-sm"
              >
                <GitHubIcon /> Continue with GitHub
              </a>
            </div>

            <p className="text-black/25 text-[10px] text-center mt-7">
              Powered by Qwen · Berg Agent
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
