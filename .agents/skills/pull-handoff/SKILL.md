---
name: pull-handoff
description: Bootstrap or pull the official Fiji and Philippines model repositories, safely unzip their current MUIO cases into ignored repository-local working trees, and maintain relative MUIOGO DataStorage symlinks. Use for a pristine MUIOGO setup or an existing two-laptop handoff.
---

# Pull Handoff

Pull and unzip. Do not solve, validate, or change model inputs as part of this
skill.

## Scope

Resolve MUIOGO by its Git remote and use its parent directory as the local
workspace. Operate only on the countries the user requests; use both when the
request says to update the full handoff. The official public remotes are:

- `https://github.com/EAPD-DRB/CLEWs-FJI.git`
- `https://github.com/EAPD-DRB/CLEWs-PHL.git`

Read applicable `AGENTS.md` files after locating or cloning each repository.

## Workflow

One step needs judgment: naming the case. Everything after it — pull, verify,
unzip, link, restore run directories — is `install.py`, which prints what it
will do before it does anything.

1. **Clone, if the repository is missing.** Locate each requested country
   repository among MUIOGO's siblings by its `origin` remote, not by folder
   name. Clone the official remote into the unused sibling path `CLEWs-FJI` or
   `CLEWs-PHL` only if that path does not exist — never over a file,
   directory, symlink, or partial checkout. Then confirm the canonical
   `origin`, the default branch, and a clean status.
2. **Judgment — name the case.** Read the country repository's current-model
   documentation, unless the user names it. Never infer the current case or
   archive from filename sorting: the newest-looking name is routinely a
   control run or a predecessor kept for reference. If two archives could
   plausibly be the one, ask.
3. **Plan.** Run this for each country repository, and read the output:

   ```bash
   python .claude/skills/pull-handoff/install.py --repo <country-repository> --case <case-name> --pull
   ```

   It changes nothing without `--apply`. It reports what it would pull, which
   archive it resolved, which live case it would overwrite and how large it is,
   what it would do to the MUIOGO link, and any reason it refuses to start.
   Add `--archive` when the archive path is ambiguous, `--datastorage` when
   MUIOGO is not a sibling, and drop `--pull` to install from what is already
   checked out. **Exit 1 or 2 stops the handoff.** Report what failed; do not
   work around it.
4. **Apply.** Re-run the same command with `--apply`.

   ```bash
   python .claude/skills/pull-handoff/install.py --repo <country-repository> --case <case-name> --pull --apply
   ```

   It fast-forwards with `git pull --ff-only` on a clean branch and stops on
   local changes or divergence; refuses to install unless `/case/` is
   gitignored; verifies the archive before anything moves — one correctly-named
   top-level folder, no excluded solver results, intact CRC, `osy-casename`
   agreeing with the folder name, and every recorded SHA-256 in the repository
   describing this archive; extracts to a temporary directory beside the target
   and moves it into place only once complete; maintains
   `MUIOGO/WebAPP/DataStorage/<case-name>` as a relative symlink and checks
   that it resolves; and recreates the empty `res/<run>/csv` directories named
   in `view/resData.json`.

   **It overwrites the live case.** That is deliberate — the case is gitignored
   working state, everything that matters travels in the tracked archive, and
   solver results are excluded from the archive because they are re-created by
   solving. Nothing is backed up. A failure at any point leaves the previous
   case exactly where it was.

Never reset, clean, rebase, or force-update a country repository.

Do not solve, run validation, reconstruct provenance, or edit the model.

Report repositories cloned and pulled, repository-local case paths, relative
symlink targets, archive hashes, and any repository skipped because of local
changes or an occupied clone destination.
