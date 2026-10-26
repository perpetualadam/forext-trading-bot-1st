# R.45 stake and sizing evidence

The public pages that were retrieved describe forex size as units, not as GBP per point.

- Margin examples buy "1 million units" and "1000 units".
- The financing example is a long position of 200,000 EURUSD. The illustrative financing table says FX charges in that table are based on 100,000 units.
- The hours page, under the heading Forex CFDs, says one standard lot equivalent is 100,000 units for all FX products except TRY pairs. A later note says MT4 lot size applies to CFD trades on an MT4 account. The FX row itself is inside the CFD section.
- The spread-betting page uses the words pips and points. It says spreads on EUR/USD from 0.6 pips. It does not define a pip in price decimals, a point in GBP, or a conversion from a v20 unit to a stake.
- The GSLO example uses "one unit" of an index CFD and a GBP loss formula `(order size x stop distance) + (order size x premium)`. That example is an index CFD, not one of the six forex pairs.
- The pip help URL did not return the article.

No retrieved page states that a v20 forex spread bet is entered as a GBP-per-point stake, or that one unit equals one pound per pip. Conventional FX units are not treated as equivalent to a spread-bet stake.

Classification: `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` for the stake-to-units mapping, the minimum size, and the size increment. The unit language and the 100,000-unit CFD lot are `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS`.

The local code's unit sizing is consistent with the unit language on these pages and is still not a verified spread-bet stake. No sizing code was changed.
