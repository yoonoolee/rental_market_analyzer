export function ThinkingIndicator() {
  return (
    <div className="flex items-start">
      <div className="flex items-center gap-1.5">
        <span className="w-2 h-2 bg-[#1a3f6f] rounded-full animate-bounce [animation-delay:0ms]" />
        <span className="w-2 h-2 bg-[#1a3f6f] rounded-full animate-bounce [animation-delay:150ms]" />
        <span className="w-2 h-2 bg-[#1a3f6f] rounded-full animate-bounce [animation-delay:300ms]" />
      </div>
    </div>
  )
}
