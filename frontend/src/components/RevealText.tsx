import { motion, type Variants } from "framer-motion"

// Per-word "slide up from behind a mask" reveal, staggered - the effect used on most modern product
// landing pages for a hero headline. Each word sits in its own overflow-hidden span so it looks like it's
// rising out from behind the line, rather than a plain fade.
const container: Variants = {
  hidden: {},
  show: (delay: number) => ({ transition: { staggerChildren: 0.08, delayChildren: delay } }),
}

const word: Variants = {
  hidden: { y: "110%" },
  show: { y: "0%", transition: { duration: 0.65, ease: [0.22, 1, 0.36, 1] } },
}

export function RevealText({ text, delay = 0, className = "" }: { text: string; delay?: number; className?: string }) {
  const words = text.split(" ")
  return (
    <motion.span
      variants={container}
      custom={delay}
      initial="hidden"
      animate="show"
      className={`inline-block ${className}`}
    >
      {words.map((w, i) => (
        <span key={i} className="inline-block overflow-hidden pb-[0.15em] align-bottom">
          <motion.span variants={word} className="inline-block">
            {w}
            {i < words.length - 1 ? " " : ""}
          </motion.span>
        </span>
      ))}
    </motion.span>
  )
}
