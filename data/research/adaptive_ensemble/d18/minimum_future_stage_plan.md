# Minimum future stage

Existing files cannot establish the CPU architecture. Option A, offline selection from existing evidence, cannot resolve that fact. Options B through E need a platform before they have a target to verify. Production inspection is not the next step.

The smallest next stage is an explicit target-selection decision by the user. It names the OCI platform and confirms the registry. It does not query a registry, pull an image, run Docker, resolve dependencies, or read production.

After that decision, the next technical stage is a controlled registry manifest read for the selected platform, without a pull. Python patch and libc version stay in a later metadata inspection if the manifest labels omit them. Wheel verification stays behind the lock and remains unauthorised.
