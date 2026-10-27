# V2.6B Downloader Compatibility

Inspected the existing V26 code; it remains unchanged. Instrument names,
M5, unsmoothed MBA, RFC3339, includeFirst=true and from/to are consistent with
legacy definitions. Source schemas and current related docs:
https://developer.oanda.com/rest-live-v20/instrument-df/
https://developer.oanda.com/rest-live-v20/primitives-df/
https://developer.oanda.com/rest-live-v20/pricing-ep/

The current account-specific route advertises5000; that cap is not established
for the required non-account route. V26 conservatively limits windows to5000 and
defaults1000. It omits count with both time bounds. Completion is explicit; malformed
or out-of-range/duplicate candles fail, gaps remain gaps, fractional nanoseconds
are not silently truncated, and observed decimal lexemes are retained.

Half-open model: from=a, to=b-1 second on an M5 grid, followed by from=b. Both
synthetic inclusive/exclusive START-time end models retain every boundary start exactly once.
This is conditional mathematical/model evidence, not a verified broker contract.
A completion-filtered end model is a counterexample: to=end-1 returns nine
candles and leaves the final five-minute slot missing. Current wording does not
resolve this model versus start-time filtering. This is not an observed broker
defect; no downloader change is justified. No universal no-skip guarantee has
been established. Exact to semantics require provider confirmation.

Serial pacing, bounded retries and429 handling remain unchanged. Socket timeout
is15s; body-loop deadline30s. DNS and trickled response headers lack a proven
strict total deadline. A stricter one-shot timeout needs review. External archive
support is also gated: V26 Store deliberately refuses the newly prepared root.
That is a design boundary, not a reproduced defect; no root-policy bypass was made.
A reviewed external-root adapter and one-shot driver are proposed before B.

No authenticated requests. Production remains NO-GO.
