#!/usr/bin/env python3
"""Install a MUIO case handoff: archive -> live working tree -> MUIOGO link.

Companion to SKILL.md (pull-handoff), and the mirror image of push-handoff's
verify.py. That script only judges, because in a push the model does the work.
Here the work IS the job -- unzip, replace, link -- so this one acts.

It overwrites. The live case is gitignored and everything that matters about it
travels in the tracked archive; solver results under res/ are excluded from the
archive on purpose and are re-created by solving. There is nothing to preserve,
so nothing is backed up.

What it will not do is leave a half-installed case behind. The archive is
verified before anything moves, extraction happens beside the target and is
moved into place only once complete, and a failure at any point leaves the
previous case exactly where it was.

Usage:
    python install.py --repo ../CLEWs-PHL --case Philippines_v16           # plan only
    python install.py --repo ../CLEWs-PHL --case Philippines_v16 --apply
    python install.py --repo ... --case ... --archive path/to.zip --apply
    python install.py --repo ... --case ... --pull --apply     # ff-only pull first

Without --apply it changes nothing and prints what it would do. Read that, then
re-run with --apply.

Exit status:
    0   plan printed, or install completed
    1   a precondition failed
    2   the request was unusable (bad path, no archive, ambiguous archive)
"""
from __future__ import annotations
import argparse, json, os, shutil, sys, tempfile, zipfile, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify  # noqa: E402  -- vendored from push-handoff; see scripts/sync_shared.py


class Plan:
    """What will happen, printed before any of it does.

    One block the operator reads in a glance replaces the several turns it
    would otherwise take to assemble the same picture by hand. It is also the
    record of what --apply is about to do, which is the only reason --apply is
    safe to run without asking again.
    """

    def __init__(self):
        self.steps = []
        self.blockers = []

    def step(self, what, detail=""):
        self.steps.append((what, detail))

    def block(self, why):
        self.blockers.append(why)

    def render(self, apply_):
        if self.steps:
            print("\n  {}:\n".format("done" if apply_ else "would do"))
            width = max(len(w) for w, _ in self.steps)
            for what, detail in self.steps:
                line = "    {}".format(what.ljust(width))
                if detail:
                    line += "  " + detail
                print(line.rstrip())
        if self.blockers:
            print("\n  stopped:\n")
            for why in self.blockers:
                print("    - " + why)
        print()


def check_clean(plan, repo):
    code, out = verify.git(repo, "status", "--porcelain")
    if code != 0:
        plan.block("{} is not a git checkout".format(repo))
        return False
    if out.strip():
        n = len(out.splitlines())
        plan.block("{} has {} uncommitted change(s) — commit or stash first"
                   .format(os.path.basename(repo), n))
        return False
    return True


def check_case_ignored(plan, repo):
    """Refuse to install into a tracked tree.

    A live case is hundreds of megabytes of generated working state. If /case/
    is not ignored, installing it leaves the whole thing sitting untracked in
    the status output, and the first `git add -A` publishes it.

    Ask about "case/", with the slash: the usual rule is "/case/", which is
    directory-only, so git only matches it against a query that says directory
    or against a path already on disk. Bare "case" answers "not ignored" in a
    fresh clone — the one place this check has to be right.
    """
    code, _ = verify.git(repo, "check-ignore", "-q", "case/")
    if code != 0:
        plan.block("/case/ is not gitignored in {} — installing there would put "
                   "the live case in front of the next commit"
                   .format(os.path.basename(repo)))
        return False
    return True


def pull(plan, repo, apply_):
    code, upstream = verify.git(repo, "rev-parse", "--abbrev-ref", "@{u}")
    if code != 0:
        plan.block("no upstream branch set on " + os.path.basename(repo))
        return False
    if not apply_:
        plan.step("git pull --ff-only", upstream + " (may change which archive is current)")
        return True
    code, out = verify.git(repo, "pull", "--ff-only")
    if code != 0:
        tail = out.strip().splitlines()
        plan.block("pull --ff-only failed: " + (tail[-1] if tail else "unknown error"))
        return False
    lines = out.strip().splitlines()
    plan.step("pulled", "{} — {}".format(upstream, lines[-1] if lines else "up to date"))
    return True


def verify_archive(plan, repo, archive, case):
    """Reuse push-handoff's checks on receipt.

    Same predicates on both ends, from one file, so sender and receiver cannot
    drift into disagreeing about what a valid handoff is. The hash check is the
    one that matters most here: it is what distinguishes the archive that was
    sent from the bytes that arrived.
    """
    rep = verify.Report()
    verify.check_archive(rep, archive, case)
    verify.check_hash_records(rep, repo, archive)
    if rep.failed:
        for row in rep.failed:
            plan.block("{} — {}".format(row["check"], row["detail"]))
        return False
    plan.step("verified archive", "{} — {} checks".format(
        os.path.basename(archive), len(rep.rows)))
    return True


def install(plan, archive, live, apply_):
    parent = os.path.dirname(live)
    if os.path.isdir(live):
        n = sum(len(f) for _, _, f in os.walk(live))
        plan.step("replace live case", "{} — {} files, overwritten".format(live, n))
    else:
        plan.step("create live case", live)
    if not apply_:
        return True

    os.makedirs(parent, exist_ok=True)
    # Extract beside the target, so moving it into place is a rename on the
    # same filesystem rather than a second copy that can fail halfway. The old
    # case is not touched until the new one is fully on disk.
    staging = tempfile.mkdtemp(prefix=".incoming-", dir=parent)
    try:
        try:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(staging)
        except (zipfile.BadZipFile, zlib.error, EOFError, OSError) as exc:
            plan.block("extraction failed ({}: {}) — live case not touched"
                       .format(type(exc).__name__, exc))
            return False
        extracted = os.path.join(staging, os.path.basename(live))
        if not os.path.isdir(extracted):
            plan.block("archive did not extract a {}/ folder".format(os.path.basename(live)))
            return False
        if os.path.isdir(live):
            shutil.rmtree(live)
        shutil.move(extracted, live)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return True


def link(plan, live, datastorage, case, apply_):
    """Point MUIOGO's DataStorage entry at the case, by a relative symlink.

    Relative so the pair of repositories can be cloned anywhere as long as they
    stay siblings; an absolute link works on the machine that made it and
    nowhere else.
    """
    if not datastorage:
        plan.step("skip MUIOGO link", "no --datastorage and no sibling MUIOGO found")
        return True
    dest = os.path.join(datastorage, case)
    target = os.path.relpath(live, datastorage)

    if os.path.islink(dest) and os.path.realpath(dest) == os.path.realpath(live):
        plan.step("MUIOGO link already correct", dest)
        return True
    if os.path.islink(dest):
        plan.step("repoint MUIOGO link", "{} -> {}".format(dest, target))
    elif os.path.isdir(dest):
        n = sum(len(f) for _, _, f in os.walk(dest))
        plan.step("replace directory with link",
                  "{} — {} files -> {}".format(dest, n, target))
    elif os.path.exists(dest):
        plan.step("replace file with link", "{} -> {}".format(dest, target))
    else:
        plan.step("create MUIOGO link", "{} -> {}".format(dest, target))
    if not apply_:
        return True

    os.makedirs(datastorage, exist_ok=True)
    if os.path.islink(dest) or os.path.isfile(dest):
        os.unlink(dest)
    elif os.path.isdir(dest):
        shutil.rmtree(dest)
    os.symlink(target, dest)
    if os.path.realpath(dest) != os.path.realpath(live):
        plan.block("link {} does not resolve to {}".format(dest, live))
        return False
    return True


def result_dirs(live):
    """The empty res/<Case>/csv folders MUIO writes solver output into.

    The archive excludes res/ on purpose, so these vanish in transit. Their
    names are not guessable from the case name — they come from the run list in
    view/resData.json, which does travel.
    """
    try:
        with open(os.path.join(live, "view", "resData.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    return [os.path.join(live, "res", e["Case"], "csv")
            for e in data.get("osy-cases", []) if e.get("Case")]


def restore_result_dirs(plan, live, apply_):
    if not apply_:
        plan.step("recreate empty res/<run>/csv", "run names from view/resData.json")
        return True
    made = result_dirs(live)
    for path in made:
        os.makedirs(path, exist_ok=True)
    plan.step("recreated empty res/<run>/csv", "{} — {}".format(
        len(made), ", ".join(os.path.basename(os.path.dirname(p)) for p in made) or "none listed"))
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="country repository (CLEWs-FJI, CLEWs-PHL)")
    ap.add_argument("--case", required=True, help="case name, e.g. Philippines_v16")
    ap.add_argument("--archive", help="the ZIP to install (default: the one match under muio/)")
    ap.add_argument("--datastorage", help="MUIOGO WebAPP/DataStorage (default: sibling MUIOGO)")
    ap.add_argument("--pull", action="store_true", help="git pull --ff-only first")
    ap.add_argument("--apply", action="store_true", help="do it (default: plan only)")
    args = ap.parse_args(argv)

    repo = os.path.abspath(os.path.expanduser(args.repo))
    if not os.path.isdir(repo):
        print("error: no directory at " + repo, file=sys.stderr)
        return 2

    datastorage = args.datastorage
    if not datastorage:
        guess = os.path.join(os.path.dirname(repo), "MUIOGO", "WebAPP", "DataStorage")
        datastorage = guess if os.path.isdir(guess) else None
    if datastorage:
        datastorage = os.path.abspath(os.path.expanduser(datastorage))

    live = os.path.join(repo, "case", args.case)
    plan = Plan()

    # Ignore check first. If /case/ is not ignored then an existing live case
    # makes the tree dirty, and reporting "you have uncommitted changes" would
    # name the symptom while the cause sits one line below it.
    ok = check_case_ignored(plan, repo) and check_clean(plan, repo)
    if ok and args.pull:
        ok = pull(plan, repo, args.apply)

    archive = None
    if ok:
        # Resolved after the pull, never before: a pull is exactly the event
        # that can change which archive is the current one.
        if args.archive:
            archive = os.path.abspath(os.path.expanduser(args.archive))
        else:
            archive, err = verify.find_archive(repo, args.case)
            if err:
                plan.render(args.apply)
                print("error: " + err, file=sys.stderr)
                return 2

    print("\n  pull-handoff install")
    print("  repo    {}".format(repo))
    print("  case    {}".format(args.case))
    print("  archive {}".format(archive or "(not resolved)"))

    if ok:
        ok = verify_archive(plan, repo, archive, args.case)
    if ok:
        ok = install(plan, archive, live, args.apply)
    if ok:
        ok = link(plan, live, datastorage, args.case, args.apply)
    if ok:
        ok = restore_result_dirs(plan, live, args.apply)

    plan.render(args.apply)
    if plan.blockers:
        return 1
    if not args.apply:
        print("  nothing changed. re-run with --apply to do it.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
