5. How are claims verified?
"Each claim is compared against the retrieved evidence to determine whether the evidence actually supports it. Depending on the implementation, this can be done using an LLM-based verifier, similarity-based checks, deterministic rules, or a combination of them. Claims that are unsupported or contradicted are marked as failures."
The important thing is:
Claim
  ↓
Retrieved evidence
  ↓
Does evidence support claim?
  ↓
Yes → supported
No  → unsupported
A strong system should ideally also distinguish:
Supported
Unsupported
Contradicted
rather than treating everything as simply true/false.

12. How do you know that the second retrieval is actually better?
"I don't assume that the second retrieval is better simply because it's a second attempt. I evaluate it using the same retrieval and verification criteria. The new context should provide better evidence for the previously unsupported claims. If verification still fails, I continue healing or eventually fall back."
Conceptually:
First retrieval
      ↓
Claim verification
      ↓
Unsupported claim
      ↓
Query rewrite
      ↓
Second retrieval
      ↓
Claim verification
      ↓
Supported?
   ↙       ↘
 Yes        No
 ↓           ↓
Answer    Heal again
A more advanced implementation could also compare retrieval metrics such as:
similarity/relevance scores
ranking quality
evidence coverage
claim support rate
But don't claim you calculate these unless your implementation actually does.