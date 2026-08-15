# Sample issue (copy the content, do not commit real user data)

**Title:** Calculator accepts a negative unit price

**Body:** Calling `calculate_total(2, -5)` should raise `ValueError`, but a demo branch returned
`-10`. Reproduction: run the calculator with quantity `2` and unit price `-5`. This appears related
to the earlier negative-quantity validation issue.

Expected triage: bug evidence, non-empty priority/label suggestions when matching labels exist, and
a possible lexical duplicate. MaintainerFlow must not label, close, assign or comment automatically.
