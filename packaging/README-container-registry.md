## Quay

The images are automatically rebuilt on new GIT tags or pushes to any branch:

Configuration (here for `fedora-nmstate-dev`, the other build just specifies
a different container spec (Dockerfile location):

Container spec: /packaging/Dockerfile.fedora-nmstate-dev

Build context: /packaging

The tags are named after the branch/tag that triggered the build.
