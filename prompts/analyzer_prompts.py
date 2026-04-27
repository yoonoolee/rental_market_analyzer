ANALYZER_PROMPT = """Look at the full set of listings (qualifying + disqualified) and surface 3–4 patterns the user can act on. They've already seen the recommendations — don't restate them.

Write in plain markdown:
- A single small header: "## Market snapshot"
- 3–4 tight bullets. Each must include a real number (price, count, minutes). No bullet without data.
- One closing line: a concrete search adjustment if they want more options (e.g. "Bumping budget to $X would unlock N more listings.")

What to look for:
- Where does their budget sit vs actual market prices? Near-miss disqualifications ($50–200 over) vs far misses ($500+ over) tell different stories.
- What's the main thing cutting listings? Count it.
- Commute range across listings, if data exists.
- Any pattern linking price to a feature they care about (pet-friendly, modern, commute).

Skip any category if you don't have the data. If total listings < 3, say the sample is too small.
Tone: direct, no filler, numbers only."""
