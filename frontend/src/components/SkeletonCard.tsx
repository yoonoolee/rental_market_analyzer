export function SkeletonCard() {
  return (
    <article className="rounded-2xl bg-white border border-ink-200/60 overflow-hidden flex flex-col shadow-[0_2px_10px_-4px_rgba(0,0,0,0.06)]">
      <div className="h-60 bg-gradient-to-br from-ink-100 to-cream-200 shimmer" />
      <div className="p-5 flex flex-col gap-3">
        <div className="flex justify-between items-start gap-3">
          <div className="flex flex-col gap-2 flex-1">
            <div className="h-7 w-32 rounded-md bg-ink-100 shimmer" />
            <div className="h-4 w-48 rounded bg-ink-100 shimmer" />
          </div>
          <div className="h-8 w-16 rounded-full bg-ink-100 shimmer" />
        </div>
        <div className="flex gap-1.5">
          <div className="h-6 w-20 rounded-full bg-ink-100 shimmer" />
          <div className="h-6 w-24 rounded-full bg-ink-100 shimmer" />
        </div>
        <div className="rounded-xl bg-cream-100 px-3.5 py-3 flex flex-col gap-2">
          <div className="h-3 w-20 rounded bg-ink-100/70 shimmer" />
          <div className="h-4 w-40 rounded bg-ink-100/70 shimmer" />
        </div>
      </div>
    </article>
  )
}

export function SkeletonRail() {
  return (
    <div className="flex flex-col gap-5">
      <SkeletonCard />
      <SkeletonCard />
    </div>
  )
}
