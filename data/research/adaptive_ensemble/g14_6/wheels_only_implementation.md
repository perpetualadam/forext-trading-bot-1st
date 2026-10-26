# Wheels-only policy

`assess_wheel_candidate` rejects source archives, non-wheel names, unsupported tags, yanked releases, prereleases, and partial candidates. `--prefer-binary` is rejected. The required argument recorded on a plan is `--only-binary=:all:`. Plans are not executed.

Native manylinux tags are not treated as verified for this target because the glibc version is unknown. Pure `py3-none-any` candidates can pass the filename policy. No package was downloaded, built, or installed.
