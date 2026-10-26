# R.47 future verification checklist

No credential is requested. No broker query is performed.

| Priority | Fact | Further redacted ticket | Redacted instrument specification | Public pages already reviewed | Later read-only API, only if separately authorised |
| --- | --- | --- | --- | --- | --- |
| 1 | What one EUR/USD quantity unit means in words | A ticket that names the unit, not only the heading "Units" | Yes, if it defines the size field | Pages use units and do not define GBP per point | An instrument field could name it. Not approved. |
| 2 | Whether the ticket quantity is the v20 API units value | A ticket cannot show the API body | A field dictionary could | Not established | The only direct comparison. Not approved. |
| 3 | Minimum and increment | A ticket that rejects a too-small or off-step quantity, with the rejection text redacted | Yes, if printed | Not found | Not approved |
| 4 | Unrounded GBP pip value at quantity 1 | Only if the UI can show more than two decimals or an extra digit | Yes, if it states the money value of one pip | Examples use 0.0001 as a price pip for EUR pairs. They do not state the GBP amount. | Not approved. A candle download is not this check. |
| 5 | GBP conversion mechanism and markup | A ticket line that shows the rate and any markup | Yes, if the schedule names v20 spread betting | Candidate only: 1.0% on v20 and v20 MT4, and a separate 0.5% financing example | Not approved |
| 6 | GBP stop risk | Needs the unrounded pip value, the stop distance, and slippage terms together | The distance rule, if printed | A normal stop can slip. Distance was "on the ticket" and was not in this redacted view. | Not approved |
| 7 | Margin rate and closeout | This ticket's 0.03 GBP is one rounded estimate | The schedule and the v20 100% rule if the document applies them to this product | Class caps and the v20 candidate. Rate not identified. | Not approved |
| 8 | Stop restrictions and guaranteed stops | A ticket that shows distance, type, and premium | Yes, if the product terms include them | Scope clash remains | Not approved |
| 9 | Financing and conversion charges on a hold | One line can show a currency and a sign. It cannot supply the schedule. | Yes | Formula and Wednesday rule. Rate not retrieved. | Not approved |
| 10 | Fill and transaction P&L currency | A submitted fill is an order. This stage does not ask for one. A redacted field label from an existing confirmation would have to be supplied without identifiers. | A field dictionary | Charges page says realised P&L converts into the home currency. The API field is unconfirmed. | Not approved |

The two-decimal pip line cannot be made precise by photographing it again at the same precision. A later ticket is useful for item 4 only when it shows more precision or a stated formula.
