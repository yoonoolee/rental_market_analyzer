"""
LLM-as-judge evaluators using Claude.
Each judge returns a dict with `score` (0-10 int) and `rationale` (str).
"""
import json
from anthropic import Anthropic
from evals.config import JUDGE_MODEL


class LLMJudge:
    """Reusable LLM judge backed by Claude."""

    def __init__(self, api_key: str | None = None):
        self.client = Anthropic(api_key=api_key) if api_key else Anthropic()

    def _call(self, system: str, user: str) -> dict:
        resp = self.client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        raw = resp.content[0].text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON block
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(raw[start:end])
            return {"score": -1, "rationale": raw}

    # ── Search judges ─────────────────────────────────────────────────────────

    def is_valid_listing_url(self, url: str, city: str, snippet: str = "") -> dict:
        """
        Returns {score: 0|1, rationale: str}.
        1 = URL is a valid, active rental listing for the given city.
        0 = Not a listing (homepage, search results page, ad, wrong city, etc.)
        """
        system = (
            "You are a strict evaluator. Respond ONLY with a JSON object: "
            '{"score": 0 or 1, "rationale": "one sentence"}. '
            "score=1 means the URL is a direct link to a single, real rental listing in the target city. "
            "score=0 for any other page (search results, homepages, wrong city, etc.)."
        )
        user = f"city: {city}\nurl: {url}\nsnippet: {snippet}"
        return self._call(system, user)

    def query_relevance(self, query: str, results_text: str) -> dict:
        """
        Returns {score: 1-10, rationale: str}.
        How relevant are the search results to the query?
        """
        system = (
            "You are a search quality evaluator. Respond ONLY with JSON: "
            '{"score": <1-10>, "rationale": "one sentence"}. '
            "10 = all results are highly relevant rental listings directly matching the query. "
            "1 = results are irrelevant or not rental listings."
        )
        user = f"query: {query}\n\nresults:\n{results_text}"
        return self._call(system, user)

    # ── Image analysis judges ─────────────────────────────────────────────────

    def photo_analysis_quality(
        self, analysis: dict, image_urls: list[str], preferences: dict
    ) -> dict:
        """
        Returns {score: 1-10, rationale: str}.
        How accurate and useful is this photo analysis given the user's preferences?
        """
        system = (
            "You are a real estate photo analysis evaluator. Respond ONLY with JSON: "
            '{"score": <1-10>, "rationale": "2-3 sentences"}. '
            "Score the analysis on: accuracy of boolean fields, usefulness of description, "
            "alignment with the user's stated preferences, and absence of hallucination."
        )
        user = (
            f"user_preferences: {json.dumps(preferences)}\n\n"
            f"image_urls: {json.dumps(image_urls)}\n\n"
            f"analysis_output: {json.dumps(analysis)}"
        )
        return self._call(system, user)

    def photo_analysis_consistency(self, run1: dict, run2: dict) -> dict:
        """
        Returns {score: 1-10, rationale: str}.
        How consistent are two independent analyses of the same images?
        """
        system = (
            "You are evaluating the consistency of two AI photo analyses of the same apartment images. "
            "Respond ONLY with JSON: "
            '{"score": <1-10>, "rationale": "one sentence"}. '
            "10 = analyses are nearly identical. 1 = contradictory outputs."
        )
        user = f"analysis_1: {json.dumps(run1)}\n\nanalysis_2: {json.dumps(run2)}"
        return self._call(system, user)

    # ── Elicitation judges ────────────────────────────────────────────────────

    def question_quality(self, question: str, conversation_so_far: list[dict]) -> dict:
        """
        Returns {score: 1-10, rationale: str}.
        Is this a good follow-up question for apartment preference gathering?
        """
        system = (
            "You are evaluating conversational quality for an apartment-hunting assistant. "
            "Respond ONLY with JSON: "
            '{"score": <1-10>, "rationale": "one sentence"}. '
            "Score on: naturalness, relevance to gathering key missing info (commute, trade-offs), "
            "avoiding redundancy with previous messages, and warmth of tone. "
            "10 = perfect follow-up. 1 = irrelevant, robotic, or redundant."
        )
        convo_str = "\n".join(f"{m['role']}: {m['content']}" for m in conversation_so_far)
        user = f"conversation so far:\n{convo_str}\n\nnew question to evaluate:\n{question}"
        return self._call(system, user)

    # ── Planner judges ────────────────────────────────────────────────────────

    def query_format_validity(self, query: str, preferences: dict) -> dict:
        """
        Returns {score: 0|1, rationale: str}.
        1 = query contains site: operator, location, bedroom count, and price range.
        """
        system = (
            "Evaluate whether this SerpAPI search query follows best practices for finding rental listings. "
            "Respond ONLY with JSON: "
            '{"score": 0 or 1, "rationale": "one sentence"}. '
            "score=1 requires: site: operator targeting a listing site, city/location, "
            "bedroom count, and price range. score=0 if any required element is missing."
        )
        user = f"preferences: {json.dumps(preferences)}\nquery: {query}"
        return self._call(system, user)

    # ── Listing agent judges ──────────────────────────────────────────────────

    def listing_profile_quality(self, profile: dict, preferences: dict) -> dict:
        """
        Returns {score: 1-10, rationale: str}.
        How complete and accurate is the extracted listing profile relative to user preferences?
        """
        system = (
            "You are evaluating a structured apartment listing profile extracted by an AI agent. "
            "Respond ONLY with JSON: "
            '{"score": <1-10>, "rationale": "2-3 sentences"}. '
            "Score on: completeness of key fields (price, address, bedrooms), "
            "correct disqualification decisions, relevance to user preferences, "
            "and absence of hallucinated data."
        )
        user = f"user_preferences: {json.dumps(preferences)}\n\nprofile: {json.dumps(profile)}"
        return self._call(system, user)

    def disqualification_accuracy(
        self, profile: dict, preferences: dict, ground_truth_disqualified: bool
    ) -> dict:
        """
        Returns {correct: bool, rationale: str}.
        Did the agent make the right disqualification decision?
        """
        system = (
            "You are evaluating whether an AI agent correctly decided to disqualify a rental listing. "
            "Respond ONLY with JSON: "
            '{"correct": true or false, "rationale": "one sentence"}.'
        )
        user = (
            f"user_preferences: {json.dumps(preferences)}\n"
            f"agent_profile: {json.dumps(profile)}\n"
            f"ground_truth_disqualified: {ground_truth_disqualified}"
        )
        return self._call(system, user)

    # ── Reducer judges ────────────────────────────────────────────────────────

    def recommendation_quality(
        self, response: str, preferences: dict, listing_profiles: list[dict]
    ) -> dict:
        """
        Returns {score: 1-10, rationale: str}.
        Does the final recommendation honor user preferences and rank correctly?
        """
        system = (
            "You are evaluating the quality of rental apartment recommendations produced by an AI. "
            "Respond ONLY with JSON: "
            '{"score": <1-10>, "rationale": "3-5 sentences"}. '
            "Score on: preference alignment (does the #1 pick best match stated needs?), "
            "trade-off rule application, clarity and actionability, "
            "honesty about missing data, and conversational tone."
        )
        user = (
            f"user_preferences: {json.dumps(preferences)}\n\n"
            f"listing_profiles_used: {json.dumps(listing_profiles[:5])}\n\n"
            f"final_response:\n{response}"
        )
        return self._call(system, user)

    def trade_off_adherence(
        self, response: str, trade_off_rules: list[str], listing_profiles: list[dict]
    ) -> dict:
        """
        Returns {score: 1-10, rationale: str}.
        Are the user's explicit trade-off rules correctly applied in the response?
        """
        system = (
            "You are checking whether an AI recommendation correctly applied the user's stated "
            "trade-off rules (e.g., 'willing to pay +$300/mo if commute < 10 min'). "
            "Respond ONLY with JSON: "
            '{"score": <1-10>, "rationale": "2-3 sentences"}. '
            "10 = every trade-off rule is explicitly and correctly honored in the ranking. "
            "1 = trade-off rules are ignored or misapplied."
        )
        user = (
            f"trade_off_rules: {json.dumps(trade_off_rules)}\n\n"
            f"listing_data_available: {json.dumps(listing_profiles[:5])}\n\n"
            f"recommendation:\n{response}"
        )
        return self._call(system, user)
