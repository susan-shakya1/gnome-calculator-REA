# What REA is, and what it actually did here

[github.com/morluto/rea](https://github.com/morluto/rea) · npm `rea-agents` · MIT

This project is named after REA, so it's worth being precise about what REA
is, what it does well, and why it ended up contributing nothing to this
particular build. Everything marked **verified** below I checked on this
machine; everything else is from the project's own documentation.

---

## The one-line version

REA puts **one interface in front of many reverse-engineering tools**, so an
AI agent can inspect compiled software without you wiring up each tool by hand.

Its tagline: *"Reverse engineer anything with agents, from app behavior down to
native binaries."*

## The problem it solves

Reverse engineering is a tool-zoo. Ghidra decompiles native binaries, JADX does
Android, `apktool` does APK resources, Binwalk does firmware, TShark does
packet captures, Rizin does scripted disassembly — each with its own CLI,
output format, and mental model.

An AI agent asked to "explain how this app works" would otherwise need to know
all of them. REA collapses that into a single MCP surface. The agent calls one
consistent set of tools; REA decides which engine can answer and translates.

**The key thing to understand: REA is an orchestration layer, not an analysis
engine.** It does not contain a decompiler. It drives *your* Ghidra, *your*
Hopper, *your* IDA. This is exactly why it did nothing on this machine — more
on that below.

## Architecture

```
  Your agent (Claude Code, Cursor, Codex, Gemini CLI, …)
        │  MCP
        ▼
  ┌─────────────────────────────────────────┐
  │  REA                                     │
  │  • 207 MCP tools / 153 CLI commands      │  ← verified via `rea doctor`
  │  • provider selection                    │
  │  • Evidence envelope + snapshot cache    │
  └─────────────────────────────────────────┘
        │  delegates to
        ▼
  Ghidra · Hopper · IDA · Rizin · objdump · JADX
  apktool · Binwalk · TShark · pwntools · Playwright
```

Two front doors onto the same workflows:

- **MCP server** — `npx rea-agents setup` registers it with your agent and
  installs matching workflow instructions. It knows about Claude Code, Codex,
  Cursor, Gemini CLI, VS Code, Copilot CLI, opencode and antigravity.
- **CLI** — `rea <command>`. Same operations, scriptable. *This is what this
  project used*, because an MCP registration needs an agent restart to take
  effect and the CLI needs nothing.

**Analysis runs locally.** Nothing is uploaded.

## Three concepts worth knowing

### 1. Providers

A *provider* is a backing engine. REA selects one automatically when exactly
one can handle the target, or you pin it with `--provider <id>`.

> "The selected provider remains bound to the session until an explicit switch
> or close."

When none is available you get a `provider_unavailable` error carrying
`details.rejections` — a per-provider list of why each was rejected. That error
is genuinely well designed; it tells you precisely what to install. We saw a
lot of it.

### 2. Evidence

The concept that distinguishes REA from just shelling out to Ghidra. Results
come back in a structured envelope that retains:

> "artifact identity, source locations, observations, inferences and unresolved
> findings."

The point is the **separation of observation from inference**. An LLM reading
raw decompiler output will happily state a guess as fact. By forcing results
into a shape where "what was observed at address X" and "what that probably
means" are different fields — alongside explicitly *unresolved* findings — REA
makes an agent's confident hallucination structurally harder.

Bundles can be exported, re-imported and diffed (`evidence-export`,
`evidence-import`, `compare`), so you can compare two versions of an app.

This is the idea this project borrowed even without using REA. See
[HOW-IT-WAS-BUILT.md](HOW-IT-WAS-BUILT.md) — every claim in the behaviour table
is an observation from the real binary, and the differential test re-checks
them on demand.

### 3. Snapshots

A local result cache, reused only when target bytes, operation, parameters,
provider *and* settings all match exactly. Because a cache hit is read before
the provider process starts, repeat queries skip Ghidra's startup cost
entirely. Opt in with `--snapshot <file>`.

## What it can target

Native binaries (Ghidra/Hopper/IDA) · offline ELF layout · Go and Rust
binaries · WASM · EVM bytecode · JavaScript and Electron apps · .NET
assemblies · Android APKs and live devices · Flutter · firmware · websites and
saved HAR/SAZ captures · packet captures · SQLite databases · process
behaviour on Linux and macOS.

Static JavaScript and .NET inspection need no native engine — those work out of
the box. That is REA at its best: point it at an Electron app and it
reconstructs modules, IPC and routes with zero setup.

---

## What actually happened on this machine

**Verified.** Install was clean: `rea-agents` v6.5.0, repo `morluto/rea`,
maintainer `morluto`, MIT, Node 24.19.0. `rea doctor` reported 153 CLI
commands and 207 MCP tools ready.

Then every analysis path refused:

| Command | Result |
|---|---|
| `analyze /usr/bin/gnome-calculator` | `provider_unavailable` — needs Ghidra, Hopper or IDA |
| `inspect-binary-layout` | needs `REA_PWNTOOLS_PYTHON` with pwntools 4.15.0 + pyelftools 0.33 + Unicorn 2.1.2 |
| `capture-native-ui-scenario` | needs a numeric window ID — Wayland does not expose one |

`rea capabilities` tells the whole story. Of 7 providers, **3 have any usable
operation here**:

```
AVAILABLE    rea-artifact-graph    (safe archive/artifact inventory)
             rea-dotnet-static     (PE/CLI metadata — no .NET on this box to use it on)
             sqlite                (database inspection)

UNAVAILABLE  ghidra, hopper, ida   not installed
             native-macos          unsupported_host
```

None of the three can analyse a stripped GTK4 ELF.

### Was that REA's fault?

No. REA behaved correctly and told us exactly what was missing each time. It is
a broker, and the brokered tools were absent. Installing Ghidra (~500 MB + a
JDK) would have made `analyze` and `decompile` work.

### Would Ghidra have helped?

**Probably not much, and this is the interesting part.**

`gnome-calculator` is written in Vala, which compiles to C and then to a
stripped binary. Decompiling it yields Vala's generated C — `GObject` vtable
boilerplate, `_g_object_ref0` wrappers, reference-counting noise — with the
symbol names gone. Recovering the button grid from *that* would be brutal.

Meanwhile the app ships its complete UI definition inside itself as a GResource
bundle, and `gresource` extracts it in one command:

```sh
gresource extract /usr/bin/gnome-calculator /org/gnome/calculator/buttons-basic.ui
```

That returns the **authoritative source** — the actual XML the developers
wrote — not a reconstruction. All 17 files are in [`../reference/`](../reference/).

And the binary ships `gnome-calculator -s "<expr>"`, a solver mode that turns
the real engine into a queryable oracle. That is better than reading
decompiled arithmetic, because it reports what the program *actually does*
rather than what the decompilation appears to say.

**The lesson generalises:** before reaching for a decompiler, ask what the
target already exposes. Embedded resources, a CLI mode, a debug flag, an
accessibility tree, a plugin API — these give ground truth that a decompiler
can only approximate. REA is the right tool when a binary is genuinely opaque.
This one was not.

## If you do want to use REA here

```sh
npx rea-agents setup                  # register with your agent, restart it after
npx rea-agents doctor                 # what is ready and what is missing
npx rea-agents capabilities           # per-provider operations and side effects
```

To unlock native analysis, install Ghidra 12.1.x and export
`GHIDRA_INSTALL_DIR`. Good first targets on this machine would be an Electron
app (no native engine needed) or an APK.

## Legal

REA's own disclaimer, verbatim — it applies to this project too:

> "REA is for lawful research, education, interoperability, software
> preservation" and "analysis of software you own or are authorized to
> examine."

GNOME Calculator is GPL-3.0 free software, installed locally from the Debian
archive. Analysing it is unambiguously permitted; its source is public in the
first place. This project reverse engineered it as an exercise, deliberately
without reading that source.

One practical warning from the README, worth repeating because fake copies of
this repo have circulated:

> "A similar repository name or copied README does not establish that a
> download is official."

Official sources are `morluto/rea`, `rea.tools`, and the `rea-agents` npm
package. The copy used here was checked against all three before running it.
