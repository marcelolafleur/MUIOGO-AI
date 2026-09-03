# Draft upstream issue for EAPD-DRB/MUIOGO

Status: draft, not yet opened. Written 2026-09-03 after updating OG-PHL by hand
in an installed MUIOGO-AI world (see `docs/API_ENDPOINTS.md`, "Updating a
locally-registered model"). Open it in EAPD-DRB/MUIOGO once approved; keep the
plain-language voice.

---

**Title:** OG-Core page: let users update a country model that the installer set up

**Body:**

When a newer version of a country model exists, the OG-Core page tells the user
so, but gives them no way to get it.

What a user sees today:

1. On the model's card they click the refresh icon ("Check for updates").
2. The card changes to "Update the local folder to get this version" with a
   "Check again" button. There is no Update button.
3. Nothing explains what "update the local folder" means. To do it, the user has
   to know to run a git pull and a `uv sync --extra dev` in the model's folder.
4. If they manage that and click "Check again", the card goes back to
   "installed", but the version MUIOGO records for the model stays at the old
   one. Only removing the model and adding the folder again corrects it.

Why this happens: the Update button is only shown for models installed from a
Git URL through the OG-Core page itself. Models registered from a local folder
are deliberately never pulled over, so that MUIOGO cannot damage someone's own
development copy. That protection is right. But the MUIOGO-AI one-line installer
sets up every country model as a local folder (it clones with the OG-Core
universal installer, then registers the folder), so in an installed world no
model ever gets an Update button.

Two changes would fix it:

1. **Show the Update button for folders that are safe to update.** A folder is
   safe when its working tree is clean and its branch tracks a remote. Either
   check that at refresh time, or let the register call mark the folder as
   managed by an installer (a small `managed: true` flag on the record) so the
   refusal stays for real development copies.
2. **Record the new version after a check.** When "Check for updates" finds the
   local folder already at the latest version, store that commit as the model's
   version instead of leaving the old one in place.

Until then, MUIOGO-AI ships an installer update mode
(`./scripts/install.sh --update`) that pulls, re-syncs and re-registers the
models it installed, and its README points users there. Happy to open a PR for
either change if the approach suits.
