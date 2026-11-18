---
name: remove-tachie-bg
description: "Remove the background from an EXISTING anime character standing illustration (tachie), producing a clean transparent PNG plus dual-background check previews. Use when the user brings their own tachie image (hand-drawn, externally generated, green-screen, or fake-transparent) and only wants de-backgrounding — no image generation. NOT for generating tachie (use generate-tachie) or scene backgrounds (use generate-scene-bg)."
---

# Remove Tachie Background (帶圖去背)

Take one **existing** anime character standing illustration and produce a clean transparent-background RGBA PNG. Input is an image the user already has — hand-drawn, externally generated, green-screen, or fake-transparent. This skill **only removes background**; it does not generate.

This is the "bring-your-own-image" de-background path — the counterpart to `generate-tachie` (which generates and de-backgrounds in one flow). It exists because you often have a finished image from elsewhere that just needs cutting out.

## When to use / not

- **Use when**: the user already has a tachie image and only wants it de-backgrounded.
- **Not for**: generating tachie (→ `generate-tachie`), scene backgrounds (→ `generate-scene-bg`).
- **Style limit**: anime-style illustrations only. `isnet-anime` is trained on anime art; semi-realistic / 3D-render / photographic inputs will degrade. Say so upfront rather than silently producing a poor cut.

## Prerequisites

`rembg[cpu]` (with `isnet-anime` model), Pillow, numpy — already in `requirements.txt`.

## Workflow

### Step 0 — Confirm input and background type

Ask the user two things (do **not** auto-detect — one question is more reliable):

1. **Is this an anime-style illustration?** (if not, warn about degraded quality)
2. **What is the original background?** — `green` (chroma green) / `solid` (other flat color) / `transparent` (fake checkered) / `native` (real alpha channel straight from the generator) / `other`

Background type decides the decontamination strategy in Step 1.

### Step 1 — De-background + post-process

Run the script:

```bash
python3 scripts/remove_bg.py <input> -o <output> --bg-type <green|solid|transparent|native|other>
```

It does: downscale to long-edge 1536 → `rembg -m isnet-anime` → alpha clamp (α≥120→255, α≤30→0) → **if green: two-stage de-greening** → save transparent PNG + dark/white check previews.

The green path is two-stage because green residue comes in two physically different forms (verified 2026-07-11, hongliu regeneration):

1. **Feathered-edge spill** (30<α<255 rim band): green light reflected onto hair edges → green-channel suppression.
2. **Solid green gap-blocks** (α=255): rembg misjudges green background trapped in hair slits as *foreground* — edge decontamination can't touch these because they aren't edges. Fixed by color-gate dig-out (`(g>r+40)&(g>b+40)&(g>120)` → alpha 0) followed by ≤64px isolated-speck cleanup for the fragments the dig-out leaves behind.

**Native path** (`--bg-type native`): for images that already carry a real alpha channel (e.g. `generate-tachie` base images and Step 3 variants). Skips rembg entirely — re-segmenting real alpha only loses edge detail — and instead: verifies the alpha is real (exits **3** with `[not-native]` if there is no alpha channel or under 10% fully transparent pixels, i.e. fake/checkered transparency) → snaps alpha ≥250 to 255 (`image_gen` returns the body at 250–254, slightly see-through) → drops alpha ≤30 to 0 (clears the green RGB `image_gen` leaves at alpha ≈ 2–3) → bleeds the nearest visible colour into fully transparent pixels so engine filtering can't pull in green or black at the edge. Verified 2026-11-18 on hongliu: visible greenish px 0, edges unchanged at 3× zoom.

**Matching another image's size** (`--match-size <image>`, any `--bg-type`): resizes the input to that reference image's pixel size at load time, in place of the long-edge downscale. `generate-tachie` Step 3 uses it so every expression of a character lands on the base image's canvas — `image_gen` does not guarantee the size it is asked for. The resize runs before the alpha work on purpose: resizing a finished RGBA image zeroes the RGB under fully transparent pixels and undoes the edge-colour bleed. It refuses (exit 1, no output) when the aspect ratios differ by more than 1% rather than distort the character. Verified 2026-11-18 on hongliu smile, 1254×1254 → 1024×1024 on the native path: opaque-area colours identical to a plain resize of the source, edge bleed intact on every transparent pixel, both checks clean at 3× zoom; without the flag the output is pixel-identical to before. On the green path the known thin green fringe stays about the same (surprised: 0.14% → 0.16% of pixels above the green threshold) — matching the size neither fixes nor hides it.

**Escape hatch**: the dig-out assumes the character's own palette contains no saturated green. For a green-eyed / green-haired / green-outfit character it would eat the character — pass `--no-green-dig` to skip stage 2 (stage 1 spill suppression still runs).

### Step 2 — Dual-background eye check (the core)

The script emits `<output>_darkcheck.png` (dark 30,30,38) and `<output>_whitecheck.png` (white). **Show BOTH to the user for eye inspection** — they catch different defects:

- **Dark background** exposes **bright** artifacts (white rim, bright stray strands, **gray gap-residue**)
- **White background** exposes **dark / green** artifacts (residual green spill)

Looking at only one will miss half the defects. This is eyes-first — the previews are for a human to judge, not for a score.

When the dark check shows light patches, tell apart the two causes by comparing against the **pre-rembg original**: if the patch sits in a slit between hair strands and carries the source background's color/texture (e.g. checker pattern), it is **trapped background residue** (see Step 3); if the light stroke already exists in the original artwork, it is a painted-in highlight.

### Step 3 — Honestly flag the unsolvable

If the dual check shows either of these, **say plainly "de-background can't fix this"** — do not pretend it's clean:

- **Closed silhouette, including its MICRO version** — background trapped inside enclosed regions. Macro: twin-tails curling back against the torso. Micro: **thin slits between hair strands, hair-vs-neck gaps in dynamic poses** — each slit is a tiny semi-enclosed region rembg can't reach. On checkered/fake-transparent sources the trapped background survives as light-gray patches (sometimes with visible checker texture) that only the dark check reveals. Verified 2026-07-03: `assets/tachie/hongliu/debg-comparison/report_assets/verify_gap_residue.png`
- **Painted-in light strokes** (flyaway strands, outline highlights drawn into the artwork) → `rembg` correctly keeps them as foreground; alpha/erosion post-processing is useless

These are design/drawing-stage problems, unsolvable at the de-background stage. The honest move is to name them and point at where they are.

## Principles

- **Eyes-first**: the dual preview is judged by a human. Quantification (green-spill %, edge stats) is only for batch triage when you can't eyeball each one.
- **Honest about the unsolvable**: what can't be fixed, say so and mark where — don't fake it.
- **Background color decides strategy**: green needs de-greening, other solid colors need matching decontamination, neutral / fake-transparent is cleanest.

## Known Limitations

- `isnet-anime` is anime-trained; non-anime styles degrade.
- **"Perfect de-background" does not exist** — closed silhouettes (macro or micro) and painted-in strokes are physically unsolvable. This skill's goal is "as clean as possible + honestly flag the unsolvable", not perfection.
- **The main variable is silhouette openness, not background color.** An open, non-enclosed pose/hairstyle de-backgrounds cleanly on any background; a gap-heavy one leaves residue on every background. Background color only decides **what color the failure is** when gaps exist.
- **Each background type carries its own debt — background choice is a fuse, not a ranking**:
  - *Green screen* → edge spill (measured 82.4% green edge), but the residue is green → **recoverable** by de-greening (82.4%→5% verified).
  - *Fake-transparent / checkered* → zero edge spill, but gap-trapped gray/checker residue has **no decontamination** — gray is too close to hair highlights and skin to target.
  - Practical call: gap-heavy designs (twin-tails, flyaway dynamic poses) → a green-screen source + de-green is the safer bet because its failure mode has an antidote; clean open silhouettes → fake-transparent stays zero-debt and skips a processing step.
  - Verified by same-prompt same-tool A/B (2026-07-11, hongliu surprised): green does **not** make rembg cut micro-gaps cleaner at the source — solid green gap-blocks survive anyway (778–2216 px per image). Its entire advantage is that the residue is *color-identifiable and therefore recoverable*: the two-stage de-greening passed the dual check, while the fake-transparent takes failed twice on gray gap residue with no antidote. The fuse model is measured fact, not hypothesis.

## Web UI (optional)

`webapp/` wraps this same pipeline in a local drag-drop browser UI (dual-preview side by side, download button) for manual use — double-click `webapp/start.command`, see `webapp/README.md`. It calls `scripts/remove_bg.py` as a subprocess, so behavior is identical to the CLI path.

## Boundaries

- Generate tachie → `generate-tachie`
- Scene backgrounds → `generate-scene-bg`
- Batch processing, background auto-detection, alpha-matting refinement, perfect cutout on complex backgrounds → deliberately **not** in this MVP (v2 scope)
