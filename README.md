# cloud-ai-pocs

Proof-of-concept projects for AI services on different cloud providers.

| Folder   | Contents                     |
| -------- | ---------------------------- |
| `azure/` | PoCs on Microsoft Azure      |
| `gcp/`   | PoCs on Google Cloud         |
| `aws/`   | PoCs on Amazon Web Services  |

Each PoC lives in `<cloud>/<poc-name>/` and has its own structure and tech stack.

## Setup
Enable the secret-scanning git hooks once per clone:

```sh
brew install betterleaks && git config core.hooksPath .githooks
```
