from ..state import RentalState


# how many good (non-disqualified) listing profiles we want before proceeding to reducer
MIN_GOOD_RESULTS = 10

# cap on how many search + listing cycles we'll run before giving up and going to reducer
# with whatever we have. prevents infinite loops when the market is thin.
MAX_SEARCH_ATTEMPTS = 3


async def supervisor_node(state: RentalState) -> dict:
    """
    Extracts new listing URLs from search results and queues them for listing agents.

    On each call (initial or retry), supervisor looks at all accumulated search_results,
    filters out URLs already sent to a listing agent (tracked in searched_urls), and
    queues the remaining ones in pending_urls for this round.

    The fan_out_to_listing_agents routing function in builder.py reads pending_urls
    to create the parallel Send calls - same pattern as fan_out_to_searches for search nodes.
    """
    all_search_results = state.get("search_results", [])
    already_searched = set(state.get("searched_urls", []))

    # extract all URLs from accumulated search results across all rounds
    all_urls = []
    for result_batch in all_search_results:
        for r in result_batch.get("results", []):
            link = r.get("link", "")
            if link:
                all_urls.append(link)

    # only queue URLs we haven't processed yet
    new_urls = [url for url in all_urls if url not in already_searched]

    return {
        # pending_urls is a plain list (replaced each round) - fan_out reads from this
        "pending_urls": new_urls,
        # searched_urls uses operator.add, so returning new_urls appends them
        # to the running history. subsequent supervisor calls won't re-queue these.
        "searched_urls": new_urls,
    }


async def results_check_node(state: RentalState) -> dict:
    """
    Runs after all listing agents complete. Counts good results and increments
    the attempt counter.

    The routing decision (reducer vs retry) lives in route_after_results_check
    in builder.py - this node just updates the attempt count so the router
    can make that decision.
    """
    return {"search_attempts": state.get("search_attempts", 0) + 1}


def route_after_results_check(state: RentalState) -> str:
    """
    Decide whether we have enough good listings or need to retry.

    Proceeds to reducer if:
    - We have MIN_GOOD_RESULTS or more non-disqualified profiles, OR
    - We've hit MAX_SEARCH_ATTEMPTS (go with what we have, don't loop forever)

    Otherwise routes back to planner to generate new queries and try again.
    """
    good_profiles = [
        p for p in state.get("listing_profiles", [])
        if not p.get("disqualified")
    ]
    attempts = state.get("search_attempts", 0)

    if len(good_profiles) >= MIN_GOOD_RESULTS or attempts >= MAX_SEARCH_ATTEMPTS:
        if attempts >= MAX_SEARCH_ATTEMPTS and len(good_profiles) < MIN_GOOD_RESULTS:
            # hit the cap with fewer results than ideal - reducer will note this
            pass
        return "reducer"

    return "planner"
