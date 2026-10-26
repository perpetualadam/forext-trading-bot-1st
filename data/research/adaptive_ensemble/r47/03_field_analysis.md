# R.47 ticket field analysis

Each value is `USER_REPORTED_TICKET_DISPLAY` unless a row says otherwise. None is `ACCOUNT_VERIFIED`.

## Quantity 1

The ticket presents a quantity field on a units-labelled interface. The displayed quantity is 1. The heading associated with the quantity area reads "Units Available".

This shows that the UI can display a quantity of 1 beside a units label on an unsubmitted EUR/USD ticket. It does not define the API order-size contract. It does not establish that 1 is the minimum. It does not establish that the increment is 1. The Submit control was visible and was not used. The broker did not accept or reject the quantity.

The displayed one-pip value is 0.00 GBP, not 1.00 GBP, and the displayed trade value is 0.84 GBP, not 1.00 GBP. Those two displays are incompatible with reading the quantity "1" as "£1 per pip" at the ticket's two-decimal precision. They do not prove that the API size field is base-currency units.

## Units available 3,476

This is a point-in-time platform estimate on the same unsubmitted ticket. It is not a maximum safe trade size. It is not approval of a risk budget. It is not a stable margin rate. It can change when price, margin, or the ticket's own estimate changes. The bot must not adopt 3,476 as `MAX_POSITION_UNITS` or as an order quantity.

An illustrative relationship is examined in the rounding note. It is not a verified formula, and it does not turn 3,476 into a cap.

## Trade value 0.84 GBP

The ticket displayed 0.84 GBP for quantity 1. The text is rounded to two decimals. It is the displayed trade value, not a published definition of GBP stake per point. One rounded number cannot be inverted into an exact EUR/GBP or GBP/USD rate. The magnitude is what a conventional one-euro sterling value can look like at two decimals. That magnitude check is illustrative. It is not the spread-betting contract.

## One pip 0.00 GBP

The ticket printed 0.00 GBP for one pip at quantity 1. Two-decimal rounding makes any amount smaller than one displayed penny look the same. Exact zero is one point that could sit inside that display. The display does not select it. Monetary exposure is not classified as zero.

The missing fact is the unrounded GBP value of one pip at quantity 1, with the broker's definition of one pip.

## Margin required 0.03 GBP

The ticket displayed 0.03 GBP of margin for quantity 1. It is an estimate for that quantity on that ticket. Two-decimal rounding means the unrounded estimate is not the printed 0.03. The figure is not a universal EUR/USD margin rate and not a rate for the other five pairs.

## Margin available 97.15 GBP

The ticket displayed 97.15 GBP of margin available. R.46 recorded a historical balance of £97.15 and a historical NAV of £97.15 as separate screen fields. This ticket adds a third displayed field, margin available, with the same figures. The three labels stay separate. Equal displayed numbers do not collapse balance, NAV, and margin available into one field, and they do not show that the account is flat. The amount is not a risk budget and is not assumed to remain available.

## Stop loss

The stop type displayed is Normal. The inputs displayed are Price and Pips. A normal stop was described in R.45 as able to slip. This ticket does not show a minimum distance, a guaranteed-stop control, a premium, or a guarantee of execution. Guaranteed-stop availability remains the R.45 scope clash and is `UNKNOWN` on this ticket.
