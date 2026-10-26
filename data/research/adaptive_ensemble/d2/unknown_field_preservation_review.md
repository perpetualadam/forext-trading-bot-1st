# Unknown-field preservation

TESTED on synthetic version-1 documents.

Top-level keys that are not part of the known safety set are copied through a supported load and save. A nested object under an unknown top-level key survives. T03 and T04.

Each known strategy row keeps keys that are not in the fixed safety set. Both a scalar and a nested object survive. T05 and T06. A strategy name that is not one of the six known names is left in the `strategies` object. T07.

Known fields are written after the unknown copy, so an unknown key cannot replace `active`, `authorised_for_live`, or `live_order_authorisation.state`. T08 keeps authorisation BLOCKED and every known strategy inactive.

Supported saves use `sort_keys=True`. Field values survive. Byte-for-byte identity of a version-1 file is not claimed, because key order and runtime sample fields are rewritten. Future-schema files are not rewritten at all.
