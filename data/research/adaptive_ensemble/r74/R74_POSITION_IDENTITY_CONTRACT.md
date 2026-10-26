# R.74 Position Identity Contract

`Position` now carries `position_instance_id` and `position_generation` (`forex_bot/positions.py` lines 44–46). `open_position` (lines 87–107) assigns a UUID when the id is blank and starts the generation at 1. The id is not `id(position)`.

`ensure_position_identity` (lines 78–84) does the same assignment under `_book_lock` before a live close is reserved.

`adjust_position_units_to_broker` (lines 220–256) increments `position_generation` under the same lock when it changes units or direction.

The close journal stores the instance id, generation, account binding, instrument, trade id, direction, original units, and requested units. The account binding is `sha256` of the account id (`close_journal.account_binding`, lines 77–82). The raw account id is not written.

A later row is a different position when any of these differ: instance id, generation, trade id, direction, units, instrument, or account binding. Confirmation for the earlier row does not match.
