# Git for Long-Form Work

**Audience:** students who have never or barely used Git.

This document explains why long-form projects benefit from Git and gives you the three commands you actually need. It is not a complete Git tutorial — for that, see the official [Pro Git book](https://git-scm.com/book) (free).

---

## Why Git for a thesis?

A thesis is months of work. During that time you will:
- Reorganize chapters and lose track of what changed when
- Want to revert a change you made yesterday but no longer like
- Wonder which version of the bibliography is current
- Need a backup that isn't "thesis_v37_FINAL_really_final_v2.docx"

Git solves all four. It tracks every change, lets you go back to any state, and acts as a backup history.

The setup script initializes a Git repository for you automatically. You don't need to install anything beyond Git itself.

---

## One-time setup: tell Git who you are

Git records an author name and email with every commit. If you have never used Git on this machine, set them once:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

They only appear in your local commit history (and on remotes you push to later). Without this, your very first `git commit` stops with "Author identity unknown / Please tell me who you are" — run the two commands above, then commit again.

---

## The three commands

### 1. `git status`

Shows what has changed since the last commit.

```bash
git status
```

Run this whenever you want to see "where am I right now?". It's safe and harmless.

### 2. `git add .`

Stages all changes for the next commit.

```bash
git add .
```

The `.` means "everything in the current directory and below". This is the simple variant.

**Word of caution:** `git add .` also stages files you might not want in version control — for example `.env` files (containing secrets), or drafts you copied from elsewhere by mistake. Two safer habits:

- Run `git status` before every `git add .` and look at the list. If something unexpected is there, stage specific files instead: `git add 03_Theory_chapters/chapter_2.md`.
- Keep a thorough `.gitignore`. The setup script creates a reasonable default, but add anything project-specific you know you never want committed.

For a thesis project where everything in the project is meant to be versioned anyway, `git add .` is usually fine. For projects with mixed confidential data, be more deliberate.

### 3. `git commit -m "message"`

Records the staged changes as a checkpoint, with a short description.

```bash
git commit -m "theory: chapter 3 first draft complete"
```

The orchestrator suggests commit messages for you at the end of each chat. Use those.

---

## When to commit

A reasonable rhythm:

- **At the end of every chat** (mandatory in long-form workflows)
- **After resolving a `❓` item in styleguide.md**
- **After receiving and integrating supervisor feedback**
- **Before any potentially destructive operation** (e.g., reorganizing chapters)

Don't commit in the middle of a half-finished thought. Commit when something is at least a coherent unit, even if not perfect.

---

## Commit message conventions

cephalo workflows use a `phase: description` format:

```
theory: chapter 3.1 complete, sources A-C verified
methods: design refined to qualitative content analysis
introduction: first complete draft
formal: bibliography minus-test passed
meta: styleguide updated to guideline version 2.1
```

Multi-project setups add a sub-project prefix:

```
proposal/research: literature gap identified
main/theory: chapter 3 complete
defense/slides: structure draft, 14 slides
```

Why bother with conventions? When you scroll back through 200 commits in 6 months, structured messages let you find anything in seconds.

---

## When things go wrong

### "I committed something I shouldn't have"

```bash
git reset --soft HEAD~1
```

This undoes the last commit but keeps your file changes. You can then fix and re-commit.

**Warning:** `git reset --hard` deletes your changes too. Don't use it unless you're sure.

### "I want to see what was in the file last week"

```bash
git log -- path/to/file.md
```

Shows all commits that touched that file. Pick a commit hash, then:

```bash
git show <hash>:path/to/file.md
```

This prints the file as it was in that commit. You can copy what you need.

### "I want to actually revert to last week's state"

Don't do this carelessly. First, make a fresh commit of your current state so you don't lose it. Then:

```bash
git restore --source=<hash> path/to/file.md
```

This restores that file to the state in the given commit. (Older Git tutorials use `git checkout <hash> -- path/to/file.md`, which still works but is considered legacy — `git restore` has been the recommended form since Git 2.23.)

If you want to revert the entire project (rare), make sure you understand what you're doing first or ask for help.

---

## Tags for milestones

For named milestones (proposal accepted, thesis submitted, defense passed), use tags:

```bash
git tag -a proposal_accepted_2026-03-15 -m "Proposal accepted by supervisor"
git tag -a work_submitted_2026-09-01 -m "Bachelor thesis officially submitted"
git tag -a defense_passed_2026-10-12 -m "Defense passed, grade pending"
```

Tags appear in `git log --tags` and let you jump to specific milestones easily.

The submission tag matters beyond bookkeeping: in multi-project setups, the defense workflow's first step verifies that the main work carries a submission tag (`v_final_<date>` or `work_submitted_<date>`) before any defense preparation begins.

---

## What about Git LFS?

Word documents, PDFs, and PowerPoint files are binary. Git stores them inefficiently — every save adds a full copy to history, and the repository balloons.

Git LFS (Large File Storage) handles binary files differently: it stores them outside the main repository and substitutes lightweight pointers. The setup script enables LFS for `.docx`, `.pptx`, `.pdf`, and similar extensions automatically (see `.gitattributes`).

You don't need to do anything special. Just commit normally; LFS handles the rest.

If LFS isn't installed on your system, install it:
- **Windows:** download from [git-lfs.com](https://git-lfs.com)
- **macOS:** `brew install git-lfs`
- **Linux:** `apt install git-lfs` (Debian/Ubuntu) or distribution equivalent

After installation, run once: `git lfs install`

---

## Backing up your repository

Local Git keeps everything on your machine. If your laptop dies, your thesis dies with it.

Two practical backup options:

### Option 1: Cloud sync of the project directory

Tools like OneDrive, iCloud Drive, Dropbox, or Google Drive can sync the project directory to the cloud. Git inside that synced directory works fine. This is the simplest option if you already use one of these services.

**Caveat:** Real-time sync of binary files can occasionally cause conflicts. Resolve them by keeping the local version and letting the sync service re-upload it.

### Option 2: Remote Git repository

Push your repository to a remote Git host (GitHub, GitLab, your institution's Git server). This is more robust but requires creating an account and learning a few more Git commands.

```bash
git remote add origin <repository-url>
git push -u origin main
```

After that, `git push` after each commit (or batch of commits) sends your work to the remote.

For a private thesis project, use a private repository — never public.

If you set the project up in place (without `--target` / `-Target`), it still contains cephalo's own `.github/` folder. Delete it before the first push, otherwise GitHub runs cephalo's CI workflow on every push to your thesis repository.

---

## What you don't need to learn (yet)

Git has many features you can ignore for a thesis:

- Branches and merging
- Rebasing
- Pull requests
- Stashing

You may want them later. For now, `status`, `add`, `commit` (plus tags) cover everything.

---

## A practical first day

After running cephalo's setup script:

```bash
git status                                    # see what was created
git add .
git commit -m "meta: initial setup"           # baseline commit
```

That's it. From here on, follow the chat closure ritual: at the end of each chat, the orchestrator gives you a `git add .` + `git commit -m "..."` to run.

Over months, you'll build a complete history of your project. You'll be glad you did.
