# G.14.7 wheels-only resolution

Resolution runs only after policy and target validation, and before destination creation and artifact exchange.

## Target

The workflow requires this explicit profile:

- operating system `linux`
- architecture `x86_64`
- implementation `cp`
- Python `3.12`

`python_patch`, `soabi`, `glibc`, `pip_version`, and `native_wheel_tags` must be the string `UNKNOWN`. A profile that claims native compatibility is `VERIFIED` is rejected. The stored target classification remains `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`. Marker evaluation uses the G.14.6 inventory environment (`sys_platform=linux`, `python_version=3.12`, `platform_machine=x86_64`). `python_full_version` stays unknown. The host `sys.platform` value is not consulted.

## Selection

`parse_requirement_document` parses the synthetic requirement text, including extras and environment markers. A marker that evaluates false for the Linux target fails with `incorrect_environment_marker`. A marker the evaluator cannot decide fails with `marker_unverified`.

Each index project must carry provenance `SYNTHETIC_TEST_ONLY`. `assess_wheel_candidate` then rejects source distributions, non-wheels, yanked releases, unapproved prereleases, tags that are not pure `py3`/`py312`/`cp312` with an `any` platform, and URLs outside the proposed artifact policy. Two names that differ only by case fail with `case_collision`. The same filename twice fails with `duplicate_filename`. A requirement with no selected project fails with `missing_wheel`.

The positive path uses one pure `py3-none-any` wheel. Native tags are rejected and are not described as compatible.

## Graph

The lock's `requires` list and the wheel `Requires-Dist` metadata are checked by `verify_member_bytes`, which calls `assert_dependency_graph`. A missing dependency and an unsatisfied constraint fail closed. Requested extras that the wheel does not provide fail with `missing_requested_extra`.

This consistency result is `CONSISTENT_FOR_SYNTHETIC_SET` for the synthetic documents only. `production_dependency_graph` remains `DEPENDENCY_GRAPH_COMPLETENESS_UNVERIFIED`.
