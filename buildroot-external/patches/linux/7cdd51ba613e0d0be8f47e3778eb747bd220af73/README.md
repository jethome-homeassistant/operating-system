# Linux patches for the JetHome vendor kernel (JetHub D3-mini / j310)

This directory is version-scoped for the git-pinned vendor kernel used by
`jethub_j310_defconfig`:

    BR2_LINUX_KERNEL_CUSTOM_GIT=y
    BR2_LINUX_KERNEL_CUSTOM_REPO_URL="https://github.com/jethome-iot/linux-kernel.git"
    BR2_LINUX_KERNEL_CUSTOM_REPO_VERSION="7cdd51ba613e0d0be8f47e3778eb747bd220af73"

## Why the directory exists

`buildroot/package/pkg-utils.mk` computes the patch directory as:

    pkg-patches-dirs = $(foreach dir, $(call pkg-patch-hash-dirs,$(1)),\
            $(wildcard $(if $($(1)_VERSION),\
                    $(or $(wildcard $(dir)/$($(1)_VERSION)),$(dir)),\
                    $(dir))))

i.e. `<patchdir>/<PKG_VERSION>/` wins if it exists, otherwise every patch
directly in `<patchdir>/` is applied. For a git-pinned kernel `LINUX_VERSION`
is the git ref, so without this directory the mainline-targeted
`../0001-ipv6-add-option-to-explicitly-enable-reachability-te.patch` would be
force-applied to the vendor 5.15 tree and fail:

    checking file net/ipv6/Kconfig
    Hunk #1 succeeded at 47 (offset -1 lines).
    checking file net/ipv6/route.c
    Hunk #1 FAILED at 2273.
    1 out of 1 hunk FAILED

The same mechanism is already used in-tree by `patches/uboot/2024.01/`.

Creating this directory does not affect any other board: `pkg-generic.mk`
invokes `support/scripts/apply-patches.sh $(@D) $(dir) \*.patch`, and
`ls -d *.patch` never matches a subdirectory, so `apply-patches.sh` never
recurses into version directories when the unversioned parent is selected.

## Contents

* `0001-ipv6-add-option-to-explicitly-enable-reachability-te.patch` —
  the HAOS `CONFIG_IPV6_REACHABILITY_PROBE` patch, rebased onto vendor 5.15.
  The only delta against the mainline copy in `../` is that 5.15 reads
  `net->ipv6.devconf_all->forwarding` without `READ_ONCE()`. Verified to apply
  with zero offset and zero fuzz against commit
  `7cdd51ba613e0d0be8f47e3778eb747bd220af73`.

Enable the resulting symbol with `CONFIG_IPV6_REACHABILITY_PROBE=y` in the
j310 kernel fragment under `buildroot-external/kernel/v5.15.y/`.
