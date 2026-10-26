# G.14.10 findings preserved

Classification remains `G14_10_FEASIBILITY_REVIEW_COMPLETE_NO_BOUNDARY_VERIFIED`. G.14.11 does not treat that result as isolation.

Recorded and not refreshed here:

- Baseline and staging passed in that stage.
- No Docker, WSL, or VM command. No network. No download. No production change. No dynamic isolation test.
- No candidate architecture. No receiving principal. No protected receiving directory. No export or import channel.
- Host metadata from that stage, level 2 then: Windows Professional, AMD64, medium integrity `S-1-16-8192`, process not elevated, Administrators group present as deny-only, firmware virtualization enabled, hypervisor present, `vmms` running, `WslService` running.
- Docker Desktop 4.57.0 and Engine 29.1.3 remain historical G.14.2 observations.

Those service facts do not prove a guest, a mount policy, or a receiving ACL.

Critical findings carried forward:

1. No verified acquisition boundary.
2. No verified receiving boundary.
3. No trusted receiving principal.
4. No protected receiving directory.
5. No verified export mechanism.
6. No verified import mechanism.
7. No demonstrated resistance to same-user substitution beyond the post-open handle binding in G.14.8.
8. Target profile incomplete.
9. Base-image registry digest unverified.
10. Package source not approved.
