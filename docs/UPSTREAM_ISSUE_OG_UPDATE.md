# Draft upstream issue for EAPD-DRB/MUIOGO

Status: opened 2026-09-03 as EAPD-DRB/MUIOGO#543 (https://github.com/EAPD-DRB/MUIOGO/issues/543);
fix proposed the same day as EAPD-DRB/MUIOGO#544 (https://github.com/EAPD-DRB/MUIOGO/pull/544). Background in `docs/API_ENDPOINTS.md`,
"Updating a locally-registered model".

---

**Title:** OG-Core page: no way to update a model installed by the installer

**Body:**

"Check for updates" on a model card says a newer version exists, but the card
only offers "Update the local folder to get this version" and no Update button.
The button is reserved for models installed from a Git URL; models registered
from a local folder are never pulled, to protect development copies. The
MUIOGO-AI installer registers every model from a local folder, so in an
installed world no model can be updated from the UI.

Also, after the user pulls by hand, "Check again" resets the state to
"installed" but keeps the old commit hash in the registry.

Proposed:

1. Show the Update button for a local folder whose tree is clean and whose
   branch tracks a remote (or let the register call flag the folder as
   installer-managed).
2. When a check finds the folder already at the latest version, store that
   commit in the registry.

Workaround for now: `./scripts/install.sh --update` in MUIOGO-AI. Happy to
open a PR for either change.
