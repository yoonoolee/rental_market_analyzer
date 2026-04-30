export function ThinkingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <div className="w-7 h-7 rounded-full bg-teal-700 text-cream-50 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
        <span className="font-display text-xs font-semibold">R</span>
      </div>
      <div className="flex items-center gap-1.5 pt-2.5">
        <span className="w-1.5 h-1.5 bg-teal-700 rounded-full animate-bounce [animation-delay:0ms]" />
        <span className="w-1.5 h-1.5 bg-teal-700 rounded-full animate-bounce [animation-delay:150ms]" />
        <span className="w-1.5 h-1.5 bg-teal-700 rounded-full animate-bounce [animation-delay:300ms]" />
      </div>
    </div>
  )
}
