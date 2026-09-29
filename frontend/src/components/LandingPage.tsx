import { motion } from "framer-motion"
import {
  ArrowRight,
  AudioLines,
  Bot,
  CheckCircle2,
  MessageSquare,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { useNavigate } from "react-router-dom"
import { RevealText } from "./RevealText"

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0 },
}

const FEATURES = [
  {
    icon: AudioLines,
    title: "Speaks & listens",
    body: "Describe an issue out loud. DeskPilot transcribes it, triages it, and reads the routing decision back to you.",
    accent: "text-violet-300 bg-violet-500/15",
  },
  {
    icon: Search,
    title: "Grounded in real precedent",
    body: "Every decision cites similar past tickets from hybrid keyword + semantic search - never a guess pulled from thin air.",
    accent: "text-sky-300 bg-sky-500/15",
  },
  {
    icon: ShieldCheck,
    title: "Knows when to ask for help",
    body: "A deterministic confidence gate double-checks the agent's own judgment and escalates instead of guessing when evidence is weak.",
    accent: "text-emerald-300 bg-emerald-500/15",
  },
  {
    icon: Bot,
    title: "Watch it think",
    body: "Stream the agent's reasoning live - which tools it called, what it found, and why - not just the final answer.",
    accent: "text-amber-300 bg-amber-500/15",
  },
]

const STEPS = [
  { icon: MessageSquare, title: "Describe the issue", body: "Type it, or just say it - your call." },
  { icon: Search, title: "Agent investigates", body: "Searches ticket history, checks the account, weighs the evidence." },
  { icon: CheckCircle2, title: "Routed with confidence", body: "Auto-resolved, routed to the right queue, or escalated to a human." },
]

export function LandingPage() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen overflow-x-hidden">
      <nav className="flex items-center justify-between px-6 py-5 sm:px-10">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/30">
            <Bot size={16} className="text-white" />
          </div>
          <span className="text-sm font-bold tracking-tight text-gray-100">DeskPilot</span>
        </div>
        <button
          onClick={() => navigate("/app")}
          className="rounded-lg border border-white/10 bg-white/[0.04] px-3.5 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:border-white/20 hover:bg-white/[0.08]"
        >
          Get Started
        </button>
      </nav>

      <header className="mx-auto flex max-w-3xl flex-col items-center px-6 pt-20 pb-24 text-center sm:pt-28">
        <motion.span
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-6 flex items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-[11px] font-medium text-indigo-300"
        >
          <Sparkles size={12} />
          AI support agent · now with voice
        </motion.span>

        <h1 className="text-4xl font-extrabold leading-[1.1] tracking-tight text-gray-50 sm:text-6xl">
          <RevealText text="Tickets triaged in seconds -" />
          <br />
          <RevealText
            text="not guessed. Reasoned."
            delay={0.5}
            className="bg-gradient-to-r from-indigo-400 via-violet-400 to-fuchsia-400 bg-clip-text text-transparent"
          />
        </h1>

        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 1.1 }}
          className="mt-6 max-w-xl text-balance text-base text-gray-400 sm:text-lg"
        >
          DeskPilot listens to your customers, grounds every decision in real precedent, and only
          auto-resolves when it's actually sure - escalating the rest to a human instead of guessing.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 1.3 }}
          className="mt-9 flex flex-col items-center gap-3"
        >
          <button
            onClick={() => navigate("/app")}
            className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-500 px-6 py-3.5 text-sm font-semibold text-white shadow-xl shadow-violet-500/30 transition-all hover:shadow-violet-500/50 hover:brightness-110 active:scale-[0.98]"
          >
            Get Started with DeskPilot
            <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
          </button>
          <span className="text-xs text-gray-600">No signup needed - it's a live demo.</span>
        </motion.div>
      </header>

      <motion.section
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.2 }}
        variants={{ show: { transition: { staggerChildren: 0.1 } } }}
        className="mx-auto grid max-w-5xl grid-cols-1 gap-4 px-6 pb-24 sm:grid-cols-2"
      >
        {FEATURES.map((f) => (
          <motion.div
            key={f.title}
            variants={fadeUp}
            className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm transition-colors hover:border-white/20"
          >
            <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${f.accent}`}>
              <f.icon size={18} />
            </div>
            <h3 className="text-sm font-semibold text-gray-100">{f.title}</h3>
            <p className="text-sm leading-relaxed text-gray-400">{f.body}</p>
          </motion.div>
        ))}
      </motion.section>

      <motion.section
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, amount: 0.3 }}
        variants={{ show: { transition: { staggerChildren: 0.12 } } }}
        className="mx-auto max-w-4xl px-6 pb-28"
      >
        <motion.h2 variants={fadeUp} className="mb-10 text-center text-xl font-bold text-gray-100 sm:text-2xl">
          How it works
        </motion.h2>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-3">
          {STEPS.map((s, i) => (
            <motion.div key={s.title} variants={fadeUp} className="flex flex-col items-center text-center">
              <div className="relative flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/[0.04]">
                <s.icon size={20} className="text-indigo-300" />
                <span className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white">
                  {i + 1}
                </span>
              </div>
              <h3 className="mt-4 text-sm font-semibold text-gray-100">{s.title}</h3>
              <p className="mt-1.5 max-w-[220px] text-sm text-gray-500">{s.body}</p>
            </motion.div>
          ))}
        </div>
      </motion.section>

      <footer className="border-t border-white/5 px-6 py-8 text-center">
        <div className="mb-1.5 flex items-center justify-center gap-2 text-sm font-semibold text-gray-300">
          <Bot size={14} />
          DeskPilot
        </div>
        <p className="text-xs text-gray-600">An agentic AI ticket-routing system - built as a demonstration of applied AI engineering.</p>
      </footer>
    </div>
  )
}
