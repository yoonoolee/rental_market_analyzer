ANALYZER_PROMPT = """Look at the full set of listings (qualifying + disqualified) and surface 2–3 patterns the user can act on. They already saw recommendations — don't restate them.

Write in plain markdown:
- A single small header: "## Market snapshot"
- 2–3 tight bullets maximum. Each bullet must include a real number (price, count, minutes), stay <= 18 words, and avoid filler.
- Add one concrete search-adjustment line only if your data supports it.

What to look for:
- Where does their budget sit vs actual market prices? Near-miss disqualifications ($50–200 over) vs far misses ($500+ over) tell different stories.
- What's the main thing cutting listings? Count it.
- Commute range across listings, if data exists.
- Any pattern linking price to a feature they care about (pet-friendly, modern, commute).

Skip any category if you don't have the data. If total listings < 3, say the sample is too small.
No preface or extra sections beyond the required header.
Tone: direct, no filler, numbers only."""
