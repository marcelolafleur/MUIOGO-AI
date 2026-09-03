# MUIOGO-AI

Run [MUIOGO](https://github.com/EAPD-DRB/MUIOGO) — the UN DESA modelling
interface for CLEWs and OG-Core — without the GUI, driven by AI skills:
install it, run scenarios, couple it with OG country models, and get
analytical outputs on demand.

Works on macOS and Linux. Windows is not supported yet.

## Requirements

Git. If you don't have it:

macOS:

```bash
xcode-select --install
```

Linux (Debian/Ubuntu):

```bash
sudo apt install git
```

## Install (about 15 minutes)

Open a terminal (macOS: press Cmd+Space, type `Terminal`, press Enter) and
run:

```bash
git clone https://github.com/EAPD-DRB/MUIOGO-AI.git
```

If that says **"destination path 'MUIOGO-AI' already exists"**, you already have
a copy here — skip the clone and bring it up to date instead:

```bash
cd MUIOGO-AI && git pull
```

Otherwise:

```bash
cd MUIOGO-AI
```

```bash
./scripts/install.sh --country PHL
```

This installs MUIOGO, the Philippines example country, and the OG-CLEWS
link, and checks that everything works before finishing.

It first asks where everything should live — press Enter to accept the
default (`~/muiogoai`) or type another folder. The location is permanent, so
pick one outside any git checkout and with a few gigabytes to spare.
(Scripted runs pass `--dest` instead.)

There is one installation per machine. Running the installer again repairs
or completes the existing one; to start over, run `scripts/uninstall.sh`
first. The installation is fully self-contained — it never touches, and is
never affected by, any MUIOGO or OG model checkouts you keep for your own
work.

At the end it offers to install the modelling skills for use outside this
repository. You can say no and do it later — see below.

## The AI skills

The skills teach an AI assistant how to build, calibrate, run, and review these
models. **Inside this repository there is nothing to install** — open it in
Claude Code or Codex (`cd MUIOGO-AI`, then `claude` or `codex`) and the skills
are already active. Ask for what you want in plain language, for example
*"assess the calibration of this CLEWs model"* or *"run the preflight checks
before I start this solve"*.

New to this? [docs/USING_THE_SKILLS.md](docs/USING_THE_SKILLS.md) walks through
three worked examples with the exact prompts to type.

To use them in your own model repositories too:

```bash
./scripts/install-skills.sh
```

It asks which assistant you use (Claude Code, Codex, both, or a folder you
name) and copies the skills there; restart your assistant afterwards.

See [SKILLS.md](SKILLS.md) for the full list and what each one does.

## Start MUIOGO

```bash
muiogo-ai serve --detach
```

Leave that window open. For the web interface, open
[http://127.0.0.1:5102](http://127.0.0.1:5102) in your browser. Press
Ctrl+C in the terminal to stop.

## Update a country model

Country models (OG-PHL and the others) keep improving upstream. To see whether
a newer version exists, open MUIOGO's **OG-Core** page and click the refresh
icon on the model's card ("Check for updates"). If it says a newer version is
available, stop MUIOGO and run the installer in update mode from the
`MUIOGO-AI` folder:

```bash
muiogo-ai stop
```

```bash
./scripts/install.sh --update
```

It pulls the latest version of every model installed here, rebuilds each one's
environment (a few minutes per model), and refreshes MUIOGO's registry. Models
with local changes are left alone and reported. Then start MUIOGO again.

The card's own "Update" button is not offered for these models yet: MUIOGO will
not pull over a folder it did not clone itself, to protect people's development
copies. The installer knows these folders are its own, so it can.

## If something goes wrong

- **"destination path 'MUIOGO-AI' already exists and is not an empty
  directory"** — the folder is already there, usually because the clone was run
  twice. Nothing is wrong. Check what it is:

  ```bash
  git -C MUIOGO-AI remote -v
  ```

  If that prints `EAPD-DRB/MUIOGO-AI`, it is the right thing — carry on with
  `cd MUIOGO-AI && git pull` and then the installer. If it prints something
  else, or nothing at all, move it out of the way (don't delete it — it may be
  someone's work) and clone again:

  ```bash
  mv MUIOGO-AI MUIOGO-AI.old
  ```
- **"port … is already in use"** — add `--port 5103` to the command. (The installed runtime uses 5102; 5002 is left for a MUIOGO you run yourself.)
- **A message about conda** — run `conda deactivate` and try again.
- Still stuck? The installer writes logs into the install directory
  (`~/muiogoai` unless you chose another) — share the newest `.log` file when
  asking for help.

## Uninstall

```bash
./scripts/uninstall.sh
```

It stops the server and **moves** the installation aside
(`~/muiogoai` becomes `~/muiogoai.removed-<timestamp>`, with the launcher and
world record tucked inside) — nothing is deleted. Check the moved folder,
then delete it yourself when you are sure. Your own model checkouts, the
shared registry, and any `muiogo` command you installed yourself are never
touched.

## Manual installation

The installer above just runs each project's own installer for you. To do it
by hand instead:

1. **MUIOGO** — follow the install instructions in the
   [MUIOGO README](https://github.com/EAPD-DRB/MUIOGO#installation).
2. **An OG country model** — use the OG-Core universal installer:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/PSLmodels/OG-Core/master/scripts/install.sh -o og-install.sh
   bash og-install.sh --repo og-phl --dest ~/.muiogo/og-models --yes
   ```

3. **ogclews-link** — clone it and run its setup:

   ```bash
   git clone https://github.com/marcelolafleur/ogclews-link.git
   cd ogclews-link && ./scripts/setup.sh --og-path ~/.muiogo/og-models/OG-PHL
   ```

## For contributors

- Layout: `docs/` (scope and design), `.agents/skills/` (the skills;
  `.claude/skills/` holds one symlink each), [SKILLS.md](SKILLS.md) (the
  catalogue), `client/` (Python client + `muiogo` CLI), `clews/` (country
  catalog), `experiments/` (studies).
- Start with [docs/SCOPE.md](docs/SCOPE.md); install details are in
  [docs/INSTALL_DESIGN.md](docs/INSTALL_DESIGN.md).
- One hard rule: talk to MUIOGO over HTTP only — never import its backend
  code. Process is light: push to `main`, branch when you want review.

## License

Apache License 2.0 (`LICENSE`), same as MUIOGO.
