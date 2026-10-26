# PARTIAL FILE POLICY

Not implemented in D.29-R1.

A future acquisition acquires one unique blob at a time. Its temporary name is chosen inside a directory named by that future approval, never from a URL path. The file is promoted only after the streamed size and SHA-256 match the manifest descriptor. There is no resume and no reuse of an unverified partial.

On failure, the temporary file in that directory is removed. Failure to remove it stops the stage. A sanitised failure record remains. Files outside the approved acquisition directory are not deleted.
