from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.posting_api import TwitterAPI

@TwitterAPI.register_patch("search_tweets", "scenario_1")
def search_tweets(self, keyword):
    if self._patch_call_count < 3:
        # change behavior for the first 3 calls
        results = self._original_function(keyword)
        keyword_lower = keyword.lower()
        seen_ids = {t["id"] for t in results}
        for tweet in self.tweets.values():
            if tweet["id"] not in seen_ids:
                if keyword_lower in [m.lower() for m in tweet.get("mentions", [])]:
                    results.append(tweet)
        return results
    else:
        return self._original_function(keyword)
