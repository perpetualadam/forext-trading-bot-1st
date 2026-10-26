# Multi-platform lock strategies

No lock was created and no resolver ran.

Strategy A uses one version resolution and then picks platform-specific artifacts. A version can satisfy AMD64 and fail ARM64. Marker mistakes are easy to miss.

Strategy B uses a separate fully resolved lock for each architecture. Each lock has its own closure, hashes, and failure. The maintenance cost is two reviews. The audit trail is clearer.

Strategy C uses one multi-platform lock that records markers, wheel filenames, and hashes per platform. It is auditable only if a later-verified tool actually emits those fields. No such tool was executed or assumed to be installed.

If the user later approves dual support, the audit preference is Strategy B unless a demonstrated Strategy C record contains per-platform hashes. Convenience is not the reason. Neither strategy is approved now. An AMD64-only lock would still need its own approval and would not cover ARM64.
