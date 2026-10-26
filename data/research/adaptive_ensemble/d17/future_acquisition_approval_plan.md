# Future acquisition approval

Acquisition is separate from resolution and is not approved now.

It starts only from a reviewed lock. Each download has an expected file name, an expected SHA-256, an approved origin, and a maximum size. The network allow-list is the approved origin only. A hash mismatch quarantines the file. Downloaded files are not executed and not installed in that stage.

The stage must not write into the production tree, build an image, or contact the broker, Telegram, or the production database.
