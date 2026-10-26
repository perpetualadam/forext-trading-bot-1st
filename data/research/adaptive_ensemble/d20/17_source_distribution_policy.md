# Source distribution policy

Native source distributions need a compiler, headers, and a recorded libc. The Dockerfile installs no compiler. A build on one architecture does not produce the other architecture's wheel. Build scripts execute upstream code.

The future policy for a first reproducible milestone remains wheel-only: source distributions prohibited, local compilation prohibited, and every wheel hashed. A missing wheel fails that platform. It does not fall through to a compile.

No build, compilation, download, install, or lock occurred in this stage.
