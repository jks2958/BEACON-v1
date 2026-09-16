# Phase 6 Memory feature reproduction

## Reference search

No paired raw/structured Volatility output and corresponding prepared Memory
CSV exists in this repository. The original feature-generation implementation
is also absent. No comparison data was fabricated.

## Result

- Exact empirical matches: **0 / 94**
- Matches within justified tolerance: **0 / 94**
- Unresolved feature semantics: **94 / 94**
- Structural names/order recovered from the preprocessing artifact: **94 / 94**

A structured JSON record may contain names matching the contract, but matching
labels alone does not prove that its plugin versions, filters, aggregation,
sample unit, or calculations reproduce training semantics. The shipped
contract therefore marks all entries `unverified`; the compatibility gate
fails closed and prevents these diagnostic records from reaching the Memory
controller.

## Raw-memory investigation

No Volatility executable, memory image, or controlled reference pair is
available in the implementation environment. Raw `.raw`, `.mem`, and `.dmp`
uploads remain rejected by ingestion. BEACON does not invoke subprocesses,
accept plugin arguments, persist dumps, or expose raw-memory analysis.
