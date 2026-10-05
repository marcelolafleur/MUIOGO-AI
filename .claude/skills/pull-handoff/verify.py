#!/usr/bin/env python3
# GENERATED FILE - do not edit here.
# Source: skills/push-handoff/verify.py
# Regenerate: python scripts/sync_shared.py
# This local copy keeps the installed skill self-contained in Claude and Codex.
"""Verify a MUIO case handoff before it is committed and pushed.

Companion to SKILL.md (push-handoff). Answers the one question Git cannot: is
the RIGHT thing inside the archive? Git tracks the ZIP as a single opaque blob
and transfers it flawlessly whether it holds the case you meant or the control
run standing next to it. The live case itself is gitignored, so nothing in the
normal push path ever looks inside.

Every check here is a predicate with a yes/no answer. It reports and never
fixes: a verifier that repairs things hides the fact that something was wrong.
It fails closed — a state it cannot establish is a FAIL, not a pass.

Usage:
    python verify.py --repo ../CLEWs-PHL --case Philippines_v16
    python verify.py --repo ../CLEWs-PHL --case Philippines_v16 --archive path/to.zip
    python verify.py --repo ... --case ... --staged        # also gate the commit
    python verify.py --repo ... --case ... --allow docs/HISTORY.md
    python verify.py --repo ... --case ... --max-fetch-age 0   # offline, refs stale
    python verify.py --repo ... --case ... --json report.json

Exit status:
    0   every check passed; safe to commit and push
    1   at least one check FAILED; stop and read it
    2   the request was unusable (bad path, no archive, ambiguous archive)

This does not fetch: a verifier that mutates the repository it is judging
cannot be run safely at any moment. Upstream comparison therefore uses the refs
already in the repo, and the run fails if they are older than --max-fetch-age
(default 15 minutes, 0 to disable) rather than quietly comparing against a
week-old picture of the remote. Run `git fetch` first.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys, time, zipfile, zlib

# Content that must never travel in a handoff archive. Solver output is the one
# that matters most: it looks valid to whoever unzips it, and it came from a
# different model version than the inputs beside it.
EXCLUDED = [
    ("solver results (res/)", lambda p: "/res/" in p or p.endswith("/res")),
    ("generated data.txt", lambda p: os.path.basename(p) in (
        "data.txt", "data_processed.txt",
        "upstream_data.txt", "upstream_data_preprocessed.txt")),
    ("LP/MPS solver input", lambda p: p.lower().endswith((".lp", ".mps"))),
    ("solver log", lambda p: p.lower().endswith(".log")),
    ("python cache", lambda p: "__pycache__" in p or p.endswith(".pyc")),
    ("macOS metadata", lambda p: os.path.basename(p) == ".DS_Store"),
]

# Files a recipient needs for the case to open and for pull-handoff to rebuild
# the empty res/ tree the exclusion above removes.
REQUIRED_IN_ZIP = ["genData.json", "view/resData.json"]


class Report:
    """Accumulates findings so every check runs before anything is reported.

    Stopping at the first failure would hide the second one, and the second is
    often what explains the first.
    """

    def __init__(self):
        self.rows = []

    def add(self, ok, name, detail=""):
        self.rows.append({"check": name, "ok": bool(ok), "detail": detail})
        return ok

    def ok(self, name, detail=""):
        return self.add(True, name, detail)

    def fail(self, name, detail=""):
        return self.add(False, name, detail)

    @property
    def failed(self):
        return [r for r in self.rows if not r["ok"]]

    def render(self, stream=sys.stdout):
        width = max((len(r["check"]) for r in self.rows), default=0)
        for r in self.rows:
            mark = "PASS" if r["ok"] else "FAIL"
            line = "  {}  {}".format(mark, r["check"].ljust(width))
            if r["detail"]:
                line += "  " + r["detail"]
            print(line.rstrip(), file=stream)
        print(file=stream)
        if self.failed:
            print("  {} of {} checks FAILED — do not push.".format(
                len(self.failed), len(self.rows)), file=stream)
        else:
            print("  all {} checks passed.".format(len(self.rows)), file=stream)


def git(repo, *args):
    """Run a git command, returning (returncode, stdout). Never raises."""
    try:
        proc = subprocess.run(
            ["git", "-C", repo] + list(args),
            capture_output=True, text=True)
    except OSError as exc:                                       # git missing
        return 127, str(exc)
    return proc.returncode, proc.stdout.strip()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_archive(repo, case):
    """Locate the one archive for this case, or explain why we cannot.

    Returns (path, error). Ambiguity is an error, not a choice to make on the
    caller's behalf — picking the newest is how the wrong version ships.
    """
    hits = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in (".git", "case", "node_modules")]
        if os.path.basename(root) != "muio":
            continue
        for name in files:
            if name.endswith(".zip") and name.startswith(case + "_"):
                hits.append(os.path.join(root, name))
    if not hits:
        return None, ("no archive matching {}_*.zip under any muio/ folder in {}"
                      .format(case, repo))
    if len(hits) > 1:
        listing = "\n    ".join(sorted(os.path.relpath(h, repo) for h in hits))
        return None, ("{} archives match {}_*.zip — name the one you mean with "
                      "--archive:\n    {}".format(len(hits), case, listing))
    return hits[0], None


# ── the checks ────────────────────────────────────────────────────────────────

def _seconds_since_upstream_update(repo):
    """How stale the remote-tracking ref is. None if it has never been synced.

    Two sources, because neither alone is right. The ref's own reflog records
    every time it moved — including by push, which updates origin/main without
    going near FETCH_HEAD, so a repository that has just pushed is current
    even though its last fetch was yesterday. FETCH_HEAD's mtime covers the
    opposite case: a fetch that found nothing new writes FETCH_HEAD but leaves
    no reflog entry, and that repository is current too.

    Taking the more recent of the two is the only answer that is right in both
    directions. Reading them costs nothing and, unlike fetching, does not
    change the repository being judged.
    """
    stamps = []

    code, ref = git(repo, "rev-parse", "--symbolic-full-name", "@{u}")
    if code == 0 and ref:
        code, out = git(repo, "reflog", "show", "--format=%ct", "-1", ref)
        if code == 0 and out:
            try:
                stamps.append(int(out.splitlines()[0]))
            except (ValueError, IndexError):
                pass

    code, gitdir = git(repo, "rev-parse", "--git-dir")
    if code == 0 and gitdir:
        if not os.path.isabs(gitdir):
            gitdir = os.path.join(repo, gitdir)
        try:
            stamps.append(os.path.getmtime(os.path.join(gitdir, "FETCH_HEAD")))
        except OSError:
            pass

    if not stamps:
        return None
    return max(0.0, time.time() - max(stamps))


def _describe_age(seconds):
    if seconds < 90:
        return "{:.0f} seconds ago".format(seconds)
    if seconds < 5400:
        return "{:.0f} minutes ago".format(seconds / 60.0)
    if seconds < 172800:
        return "{:.1f} hours ago".format(seconds / 3600.0)
    return "{:.1f} days ago".format(seconds / 86400.0)


def check_fetch_freshness(rep, repo, max_age):
    """The upstream comparison is only as good as the refs behind it.

    This script never fetches — a verifier that mutates the repository it is
    judging can no longer be run safely at any moment. So it reports how stale
    the comparison is instead, and fails when the answer is old enough that
    'not behind upstream' has stopped meaning anything.
    """
    label = "upstream refs are fresh"
    if max_age <= 0:
        return
    age = _seconds_since_upstream_update(repo)
    if age is None:
        rep.fail(label, "no fetch or push recorded in this clone — "
                        "the upstream comparison is against nothing; run git fetch")
        return
    if age > max_age:
        rep.fail(label, "upstream last synced {} — run git fetch, "
                        "or pass --max-fetch-age 0 if you mean to skip this"
                 .format(_describe_age(age)))
    else:
        rep.ok(label, "upstream synced " + _describe_age(age))


def check_repo_state(rep, repo):
    code, _ = git(repo, "rev-parse", "--git-dir")
    if code != 0:
        return rep.fail("git repository", "{} is not a git checkout".format(repo))
    rep.ok("git repository", os.path.abspath(repo))

    if os.path.exists(os.path.join(repo, ".git", "MERGE_HEAD")):
        rep.fail("no merge in progress", "finish or abort the merge first")
    else:
        rep.ok("no merge in progress")

    code, upstream = git(repo, "rev-parse", "--abbrev-ref", "@{u}")
    if code != 0:
        rep.fail("branch tracks upstream",
                 "no upstream set — a push would not know where to land")
        return
    code, counts = git(repo, "rev-list", "--left-right", "--count", "@{u}...HEAD")
    if code != 0 or not counts:
        rep.fail("branch not behind upstream", "could not compare against " + upstream)
        return
    behind, ahead = (counts.split() + ["?", "?"])[:2]
    if behind != "0":
        rep.fail("branch not behind upstream",
                 "{} commit(s) behind {} — pull before packaging".format(behind, upstream))
    else:
        rep.ok("branch not behind upstream",
               "{} ahead of {} (refs as of last fetch)".format(ahead, upstream))


def check_case_ignored(rep, repo):
    # Ask about "case/", with the slash. The usual rule is "/case/", which is
    # directory-only, and git can only match it against a query that says it is
    # a directory or against a path that already exists on disk. Asking for
    # bare "case" reports "not ignored" in a fresh clone, where the answer
    # matters most.
    code, _ = git(repo, "check-ignore", "-q", "case/")
    if code == 0:
        rep.ok("case/ is gitignored", "the live case stays out of history")
    else:
        rep.fail("case/ is gitignored",
                 "case/ is TRACKABLE — a commit could pull in the whole working tree")


def check_case_and_link(rep, repo, case, datastorage):
    live = os.path.join(repo, "case", case)
    if not os.path.isdir(live):
        rep.fail("live case exists", "no directory at " + live)
        return None
    rep.ok("live case exists", os.path.relpath(live, repo))

    if not datastorage:
        rep.fail("DataStorage link resolves to the live case",
                 "--datastorage not given and could not be located")
        return live

    entry = os.path.join(datastorage, case)
    if not os.path.exists(entry) and not os.path.islink(entry):
        rep.fail("DataStorage link resolves to the live case",
                 "nothing at " + entry)
    elif not os.path.islink(entry):
        rep.fail("DataStorage link resolves to the live case",
                 "{} is a real directory, not a symlink — two candidate sources "
                 "of truth, and no way to tell which you meant".format(entry))
    elif os.path.realpath(entry) != os.path.realpath(live):
        rep.fail("DataStorage link resolves to the live case",
                 "points at {}, expected {}".format(
                     os.path.realpath(entry), os.path.realpath(live)))
    else:
        rep.ok("DataStorage link resolves to the live case",
               "{} -> {}".format(case, os.readlink(entry)))
    return live


def check_case_identity(rep, live, case):
    """The name inside the model must match the folder it lives in.

    A mismatch survives every downstream check, because the archive opens
    perfectly well — under the wrong identity.
    """
    if live is None:
        return
    gen = os.path.join(live, "genData.json")
    if not os.path.isfile(gen):
        rep.fail("osy-casename matches folder", "no genData.json in " + live)
        return
    try:
        with open(gen, encoding="utf-8") as fh:
            declared = json.load(fh).get("osy-casename")
    except (OSError, ValueError) as exc:
        rep.fail("osy-casename matches folder", "unreadable genData.json: {}".format(exc))
        return
    if declared != case:
        rep.fail("osy-casename matches folder",
                 "model calls itself {!r}, folder is {!r}".format(declared, case))
    else:
        rep.ok("osy-casename matches folder", declared)


def check_archive(rep, archive, case):
    if not os.path.isfile(archive):
        rep.fail("archive exists", "no file at " + archive)
        return
    size = os.path.getsize(archive)
    rep.ok("archive exists", "{} ({:.1f} MB)".format(
        os.path.basename(archive), size / 1048576.0))

    try:
        zf = zipfile.ZipFile(archive)
    except (zipfile.BadZipFile, OSError) as exc:
        rep.fail("archive is a readable ZIP", str(exc))
        return
    with zf:
        names = zf.namelist()
        if not names:
            rep.fail("archive is not empty", "no entries")
            return

        tops = sorted({n.split("/")[0] for n in names if n.strip("/")})
        if tops == [case]:
            rep.ok("one top-level folder, named for the case", case)
        else:
            rep.fail("one top-level folder, named for the case",
                     "found {} — expected exactly [{!r}]".format(tops, case))

        for label, matches in EXCLUDED:
            hits = [n for n in names if matches(n)]
            if hits:
                rep.fail("no " + label,
                         "{} entr{} — e.g. {}".format(
                             len(hits), "y" if len(hits) == 1 else "ies", hits[0]))
            else:
                rep.ok("no " + label)

        present = set(names)
        for rel in REQUIRED_IN_ZIP:
            want = "{}/{}".format(case, rel)
            if want in present:
                rep.ok("contains " + rel)
            else:
                rep.fail("contains " + rel, "missing " + want)

        # Read the identity out of the ZIP, not just the live directory. The
        # two agree whenever the archive was built from the case standing next
        # to it — which is exactly the assumption a stale or mis-built archive
        # breaks, and the only situation where this check earns its keep.
        gen = "{}/genData.json".format(case)
        label = "archive's own osy-casename matches the case"
        if gen not in present:
            rep.fail(label, "no " + gen + " to read")
        else:
            try:
                declared = json.loads(zf.read(gen).decode("utf-8")).get("osy-casename")
            except (KeyError, ValueError, UnicodeDecodeError) as exc:
                rep.fail(label, "unreadable {}: {}".format(gen, exc))
            else:
                if declared != case:
                    rep.fail(label, "archive's model calls itself {!r}, case is {!r}".format(
                        declared, case))
                else:
                    rep.ok(label, declared)

        # testzip() names the first entry whose CRC is wrong, but only for
        # damage mild enough that the entry still decompresses. Heavier
        # corruption raises out of zlib instead, and an uncaught exception here
        # would end the run in a stack trace rather than a failed check.
        try:
            bad = zf.testzip()
        except (zipfile.BadZipFile, zlib.error, EOFError, OSError) as exc:
            rep.fail("archive integrity (CRC of every entry)",
                     "{}: {}".format(type(exc).__name__, exc))
        else:
            if bad is None:
                rep.ok("archive integrity (CRC of every entry)",
                       "{} entries".format(len(names)))
            else:
                rep.fail("archive integrity (CRC of every entry)", "corrupt entry: " + bad)


SHA256_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")

# Walking the whole repository, minus the places a hash record cannot live and
# the ones that are expensive to descend.
SKIP_DIRS = {".git", "case", "res", "__pycache__", ".venv", "node_modules"}
MAX_TEXT_BYTES = 2_000_000


def _is_sums_file(name):
    low = name.lower()
    return low.startswith("sha256sums") or low.endswith(".sha256")


def _hash_record_files(repo):
    """Every file that could state an archive's SHA-256: sums files and prose."""
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not (_is_sums_file(name) or name.lower().endswith((".md", ".txt"))):
                continue
            path = os.path.join(dirpath, name)
            try:
                if os.path.getsize(path) > MAX_TEXT_BYTES:
                    continue
            except OSError:
                continue
            yield path


def check_hash_records(rep, repo, archive):
    """EVERY recorded copy of the hash must describe THIS archive.

    One archive's hash is routinely written down in several places — a sums
    file beside it, another at the package root with repo-relative paths, and
    the README a recipient actually reads. They are not redundant: a sums
    file's paths only resolve from one directory, so verifying from two places
    needs two files. But nothing keeps them in step, and an update that
    refreshes two of three leaves the third quietly describing the previous
    archive. Checking only the nearest one passes whenever the stale copy is
    the far one.

    Sums files are parsed structurally: a line whose last field names this
    archive must carry its hash. Prose is judged more loosely, because a hash
    in Markdown is rarely on the same line as the filename it belongs to — a
    file that names this archive and quotes hashes must quote the right one
    somewhere. That is sound in the direction that matters: it cannot be
    satisfied by a stale hash alone.

    Returns the repo-relative paths of every file found to record the hash, so
    the staged-files check knows they are legitimate to commit.
    """
    base = os.path.basename(archive)
    actual = sha256(archive).lower()

    sums_hits, sums_bad, prose_ok, prose_bad = [], [], [], []
    for path in _hash_record_files(repo):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        if base not in text:
            continue
        rel = os.path.relpath(path, repo)
        if _is_sums_file(os.path.basename(path)):
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2 and os.path.basename(parts[-1].lstrip("*")) == base:
                    sums_hits.append(rel)
                    if parts[0].lower() != actual:
                        sums_bad.append((rel, parts[0]))
                    break
        else:
            quoted = {h.lower() for h in SHA256_RE.findall(text)}
            if not quoted:
                continue
            (prose_ok if actual in quoted else prose_bad).append(rel)

    if not sums_hits:
        rep.fail("a checksum file records the archive",
                 "no SHA256SUMS line anywhere names " + base)
    else:
        rep.ok("a checksum file records the archive",
               "{} file(s): {}".format(len(sums_hits), ", ".join(sorted(sums_hits))))

    if sums_bad:
        rep.fail("every checksum record matches the archive",
                 "actual {}… but {}".format(actual[:16], "; ".join(
                     "{} says {}…".format(p, h[:16]) for p, h in sorted(sums_bad))))
    elif sums_hits:
        rep.ok("every checksum record matches the archive", actual[:16] + "…")

    if prose_bad:
        rep.fail("prose references quote the current hash",
                 "{} name{} {} but never quote {}…: {}".format(
                     len(prose_bad), "s" if len(prose_bad) == 1 else "",
                     base, actual[:16], ", ".join(sorted(prose_bad))))
    elif prose_ok:
        rep.ok("prose references quote the current hash",
               "{} file(s): {}".format(len(prose_ok), ", ".join(sorted(prose_ok))))

    return set(sums_hits) | set(prose_ok) | set(prose_bad)


def check_staged(rep, repo, archive, allow, records=()):
    """Only the handoff files may be in the commit.

    Unrelated local work swept into a handoff commit is invisible to the
    recipient and hard to unpick later.
    """
    code, out = git(repo, "diff", "--cached", "--name-only")
    if code != 0:
        rep.fail("staged files are handoff files only", "could not read the index")
        return
    staged = [p for p in out.splitlines() if p.strip()]
    if not staged:
        rep.fail("staged files are handoff files only", "nothing staged")
        return

    adir = os.path.relpath(os.path.dirname(archive), repo)
    permitted = {
        os.path.relpath(archive, repo),
        os.path.join(adir, "SHA256SUMS"),
        os.path.join(adir, "README.md"),
    }
    # Every file that records this archive's hash has to be updatable in the
    # same commit, wherever it sits — that is the whole point of finding them.
    permitted.update(records)
    permitted.update(allow or [])
    extra = [p for p in staged if p not in permitted]
    if extra:
        rep.fail("staged files are handoff files only",
                 "{} unexpected: {}".format(len(extra), ", ".join(sorted(extra)[:5])))
    else:
        rep.ok("staged files are handoff files only",
               "{} file(s)".format(len(staged)))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="country repository (CLEWs-FJI, CLEWs-PHL)")
    ap.add_argument("--case", required=True, help="case name, e.g. Philippines_v16")
    ap.add_argument("--archive", help="the ZIP to publish (default: the one match under muio/)")
    ap.add_argument("--datastorage", help="MUIOGO WebAPP/DataStorage (default: sibling MUIOGO)")
    ap.add_argument("--staged", action="store_true", help="also gate what is staged for commit")
    ap.add_argument("--allow", action="append", metavar="PATH",
                    help="additional repo-relative path allowed in the commit (repeatable)")
    ap.add_argument("--max-fetch-age", type=int, default=900, metavar="SECONDS",
                    dest="max_fetch_age",
                    help="fail if the refs are older than this (default 900; 0 disables)")
    ap.add_argument("--json", metavar="PATH", dest="json_path", help="write the report here too")
    args = ap.parse_args(argv)

    repo = os.path.abspath(os.path.expanduser(args.repo))
    if not os.path.isdir(repo):
        print("error: no directory at " + repo, file=sys.stderr)
        return 2

    archive = args.archive
    if archive:
        archive = os.path.abspath(os.path.expanduser(archive))
    else:
        archive, err = find_archive(repo, args.case)
        if err:
            print("error: " + err, file=sys.stderr)
            return 2

    datastorage = args.datastorage
    if not datastorage:
        guess = os.path.join(os.path.dirname(repo), "MUIOGO", "WebAPP", "DataStorage")
        datastorage = guess if os.path.isdir(guess) else None
    if datastorage:
        datastorage = os.path.abspath(os.path.expanduser(datastorage))

    print("\n  push-handoff verification")
    print("  repo {}\n  case {}\n  zip  {}\n".format(repo, args.case, archive))

    rep = Report()
    check_repo_state(rep, repo)
    check_fetch_freshness(rep, repo, args.max_fetch_age)
    check_case_ignored(rep, repo)
    live = check_case_and_link(rep, repo, args.case, datastorage)
    check_case_identity(rep, live, args.case)
    check_archive(rep, archive, args.case)
    records = check_hash_records(rep, repo, archive)
    if args.staged:
        check_staged(rep, repo, archive, args.allow, records)

    rep.render()

    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as fh:
            json.dump({"repo": repo, "case": args.case, "archive": archive,
                       "checks": rep.rows}, fh, indent=2)

    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
