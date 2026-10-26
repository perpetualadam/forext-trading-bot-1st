# WINDOWS PROCESS-TREE LIMITATIONS

Python subprocess.terminate on Windows calls TerminateProcess for the worker handle. That confirms the supervised process exited when poll returns an exit code.

TerminateProcess does not automatically terminate processes that the worker might have created. D.30-R2 did not spawn a grandchild, because an orphaned grandchild would make cleanup uncertain. Descendant containment is NOT_EVALUATED.

No Job Object or process-tree package was added. Pipes are read on separate threads up to a fixed byte cap so a worker that writes both streams cannot fill a pipe and stall the supervisor.
