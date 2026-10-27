# V2.5 Statistical Assessment

32 fixed B/C/D/E versus A paired daily portfolio comparisons: two pricing
cases * four entry timeframes * four policies. Reuse existing two-day moving-block
bootstrap,2,000 draws, seed25; fold boundaries retained. Holm family includes all32
even unavailable estimates. All reliable_advantage_established flags remain false.
Machine-readable effect intervals, raw/adjusted values and fold-day counts are
in performance.json; expectancy and portfolio effect sizes in paired_effects.json.

8/24 B/C/D comparisons have higher sample net/trade, 14/24 higher
sample total net. Counting these is descriptive, not a binomial success test:
strategies, pairs, policies and pricing cases overlap. Short nonstationary known
data cannot validate block length, symmetry or IID trade assumptions. Paired
trade outcomes are not used as independent samples. No minimum-count, positive
sample score or adjusted p-value permits promotion or a claim of unseen edge.

Research only. Production remains NO-GO.
