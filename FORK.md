# Maintaining this fork

Based on upstream main `cc0633a96e01fc95ff1b2857ee236dac524db850`, which includes
changes after v0.18.0. Upstream's rewritten history is the foundation; the old
local history is not merged into this branch.

## Included changes

- Six additional providers: Bright Start, Capital One, Huntington, Schwab,
  STP / BluePrint and U.S. Bank. They use the current core and explicit host
  checks. Fresh supervised pilots of the reconciled versions remain pending.
- Upstream's provider setup, add/remove controls, archive freshness and gap
  detection. The old display-only hiding preferences are intentionally retired.
- A Last panel run column showing successful Run All / Resume exits per
  account. This is not proof that every expected document was downloaded.
  Pilot, Discover and Verify activity is recorded but does not advance that
  column; CLI runs are not observed.
- Optional shared Chrome profile and optional root Python environment.
- Optional manual cache-only cleanup. No automatic pruning, disabled component
  updates, or deletion of security/session databases.

## Shared browser configuration

Set `"browser_profile_mode": "shared"` in a private provider config. Omit
`profile_dir` and `cdp_url` to use the repository's `browser-profile/` on port
9222. Explicit paths and ports take precedence, including secondary accounts.
The default browser mode for a shared profile is `installed-chrome`: Chrome
first, then another installed Chromium browser. Normal upstream browser modes
and launch/port checks remain available. Set `browser` explicitly to override.

Before using a different browser executable with an existing profile, close
that profile's current browser. Each provider uses its own matching tab; if no
matching tab exists it opens one instead of taking over a different provider.
Target also supports CDP attachment and does not close the shared browser.

New provider installations created by upstream's setup keep their separate
profile/port configuration until explicitly changed. Shared mode is opt-in.

## Shared environment

Run `python3 tools/setup_shared.py` (Windows: `python tools/setup_shared.py`)
from the repository. This installs all app requirements, the GUI and the core
into the root `.venv`; it does not download or launch a browser. App and GUI
launchers prefer this environment when present and otherwise retain their
per-app behavior. Upstream's setup scripts remain available.

## Cache cleanup

Close every Chrome, Edge and Chromium process first. Preview with:

```
python tools/prune_profile.py /path/to/browser-profile
```

Add `--apply` to delete the listed page/code/GPU caches. The tool refuses
running browsers, profile locks, and symlinked paths. Cookies, login data,
service-worker storage, Safe Browsing data and component updates are untouched.

## State and updates

Successful panel-run history lives in `.panel-runs.json` inside each provider
installation, is ignored by Git and moves with upstream's remove/restore flow.
Keep all private configs, state, profiles, PDFs and diagnostics out of commits.

Use `origin` for the personal fork and `upstream` for the original repository.
Fetch upstream into a review branch, integrate fixes there, run the core/GUI
suite and each provider's tests separately, and perform affected live pilots
before updating the normal working branch. Do not merge the pre-rewrite history
or push local preservation branches or tags.

Provider contributions should target upstream independently of shared-browser
changes. Completed-run history is a separate proposal. Shared architecture and
cache cleanup remain fork features unless discussed with the maintainer.

## Verification

Automated provider tests use synthetic fixtures. A passing suite establishes
parser, naming, configuration and guard behavior; it does not establish that a
live provider has not changed its site. Keep the live-pilot checklist incomplete
on proposed provider PRs until supervised validation has actually finished.
