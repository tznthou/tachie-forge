---
name: generate-tachie
description: "Generate ADV / Visual Novel character standing illustrations (tachie / 立繪). Use when creating dialogue-scene standing portraits with expression variations (neutral, smile, angry, sad, surprised, confused). Supports consistent character design via design doc + visual reference handoff. NOT for scene backgrounds (use generate-scene-bg)."
---

# Generate Tachie (立繪)

Generate character standing illustrations for ADV / Visual Novel style games (Persona, Ace Attorney, etc.). Output is a set of waist-up transparent-background PNGs with expression variations for one character.

## Parameters

Infer from the user request. Only `character_name` is required.

- `character_name`: identifier for the character (used in filenames and design doc)
- `art_style`: `anime_illustration` | `semi_realistic` | `cel_shaded`
- `expression`: `neutral` | `smile` | `angry` | `sad` | `surprised` | `confused` | custom
- `framing`: `waist-up` (default) | `bust-up` | `full-body`

When unspecified:
- Default `art_style` to `anime_illustration`.
- Default `framing` to `waist-up`.
- Default `expression` to `neutral` for first generation.

## Workflow

**Rejection at any step**: if the user is unsatisfied with a result (design direction, base image, or variant), discuss what's off, update the relevant prompt or design doc, and regenerate. If the Prompt Anchor changes, update design.md and regenerate affected images.

### Step 0 — Ask Character Style Direction

Before any generation, ask the user about the character's visual direction:

1. **Who is this character?** — role in the story, personality, age range
2. **Visual style preference?** — anime_illustration / semi_realistic / cel_shaded, or defer to project default
3. **Key visual traits** — hair color/style, eye color, outfit, distinguishing features
4. **Mood/aura** — cool, warm, energetic, mysterious, etc.

This step builds the Prompt Anchor that keeps all expression variants visually consistent. Without it, the anchor will be vague and variants will drift in appearance. Infer what you can from the user's request — only ask about what's genuinely missing.

When shaping visual traits, steer away from design elements that inherently form closed loops against the body (e.g., twin tails or hair that curls back and touches the torso, hoop earrings, closed necklace chains resting flush on the outfit, tightly crossed arms). These trap background pixels inside a fully enclosed region that `rembg` cannot reach regardless of prompt wording — this is a design-time prevention, not just a prompt-time instruction. Prefer hairstyles and poses with natural gaps to the outside of the silhouette.

### Step 1 — Create or Load Design Doc

Check if `assets/tachie/<character_name>/design.md` exists.

**If it does not exist** (new character):

From the Step 0 answers, create `assets/tachie/<character_name>/design.md` with:

```markdown
# <Character Name> — Design Doc

## Identity
- Role: ...
- Personality: ...
- Age range: ...

## Visual Design
- Art style: ...
- Framing: ...
- Hair: color, length, style
- Eyes: color, shape
- Outfit: description
- Distinguishing features: ...
- Mood/aura: ...

## Prompt Anchor
<A reusable prompt fragment describing the character's appearance.
This exact text is pasted into every generation prompt for consistency.>
```

The **Prompt Anchor** is the key consistency mechanism — a fixed text block describing the character's physical appearance that gets included verbatim in every image prompt.

**If it already exists** (returning character): load the design doc and use the Prompt Anchor.

### Step 2 — Generate Base Tachie (neutral expression)

1. Write the image prompt manually. The prompt must include:
   - The full Prompt Anchor from the design doc (verbatim)
   - Framing: "waist-up portrait" / "bust-up" / "full-body standing"
   - Expression: "neutral expression, calm face"
   - "Single character, clean lines, no text, no UI"
   - Every line from the **Anti-Artifact Prompt Lines** section below, verbatim (apply the non-dark-hair adaptation if the character's hair is not dark)
   - Art style cues matching the chosen `art_style`
   - Request transparent background in the prompt (gpt-image-2 renders a checkered-pattern fake transparency)
2. Call `image_gen` with the prompt. Use `--size 1024x1024` for waist-up/bust-up, `--size 768x1344` for full-body. If the agent has no native `image_gen` tool (e.g. Claude Code), invoke it via Bash instead: `scripts/call-codex-imagegen.sh --size <size> -o <output-path> "<prompt>"` — this bridges to Codex CLI's `image_gen`.
3. Post-process and inspect per the **Post-Process & Artifact Check** section below.
4. Save to `assets/tachie/<character_name>/<character_name>_<expression>.png`
5. Save prompt as `assets/tachie/<character_name>/<character_name>_<expression>.prompt.txt`
6. Show the result (transparent PNG **and** both background checks) to the user for approval before generating variants.

### Step 3 — Generate Expression Variants

For each requested expression (or all 6 MVP expressions: smile, angry, sad, surprised, confused):

1. Make the base (neutral) image visible in conversation context (via `view_image` or any available image reading method).
2. Write the variant prompt including:
   - The full Prompt Anchor from the design doc (verbatim)
   - Same framing as the base
   - "Use the visible image above as the visual reference — preserve the exact character design, outfit, hair, pose, and proportions. Change only the facial expression."
   - The target expression: describe it concretely (e.g., "angry expression: furrowed brows, clenched jaw, sharp eyes" not just "angry")
   - "Single character, no text"
   - Every line from the **Anti-Artifact Prompt Lines** section below, verbatim (apply the non-dark-hair adaptation if the character's hair is not dark)
3. Generate, then post-process and inspect per the **Post-Process & Artifact Check** section below.
4. Save as `<character_name>_<expression>.png` with `.prompt.txt`.

This is best-effort consistency — image generation cannot guarantee identical appearance across variants. The Prompt Anchor + visual reference handoff improves consistency but is not pixel-perfect.

## Anti-Artifact Prompt Lines

Include every line below verbatim in every generation prompt — base (Step 2) and variants (Step 3). This wording was tuned via a 5-round autoresearch loop (2026-07-02): median edge-artifact severity dropped from 4 to 1. Do NOT "sharpen" it with technique names (e.g. "rim lighting") or exact fractions (e.g. "upper quarter") — both were tested and made results worse (see Known Limitation).

- "Hair strands and clothing edges should not form a closed silhouette — leave visible gaps between hair and outfit so the background is clearly separable"
- "No flyaway hair strands, no stray loose hair strands separated from the main hair silhouette"
- "If the hair rendering includes any glossy shine or highlight accents, they must be placed only near the crown/top of the head, well inside the silhouette and away from any edge — the outer silhouette edge and the tapered strand tips must remain a uniform flat dark tone with zero highlight, since any brightness at the very edge or tip directly touches the transparent background boundary"
- "The character silhouette should have a crisp, high-contrast, clean-cut edge against the background — avoid soft blending, gradient fading, or anti-aliased blur at the outline boundary"

**Non-dark hair adaptation**: the validated wording assumes dark hair — the loop's test character was black-haired. For a blonde/silver/pink/white-haired character, "a uniform flat dark tone" contradicts the design and may confuse the model or darken the hair edges. Replace it with "a uniform flat tone of the hair's base color" in the highlight-placement line. This substitution is semantically required but has not been loop-validated.

## Post-Process & Artifact Check

Run this sequence after every generation (base and variants):

1. **Background removal**: `rembg i -m isnet-anime <raw>.png <output>.png`, then alpha-clamp (alpha >= 120 → 255, alpha <= 30 → 0) to get a clean RGBA PNG. Requires `rembg[cpu]` with the `isnet-anime` model.
2. **Dual-background check**: defect visibility is symmetric with backdrop tone — a **dark** backdrop exposes **bright** artifacts (light rim strokes, residual light halo, gray gap-residue), a **white** backdrop exposes **dark** artifacts (dark strokes or halo hugging the silhouette edge). Inspecting only the transparent PNG, or only one backdrop, misses half the defects (verified 2026-07-03). Composite over both and look at the hair silhouette:

   ```bash
   python3 -c "from PIL import Image; fg=Image.open('<output>.png').convert('RGBA'); d=Image.new('RGBA', fg.size, (30,30,38,255)); d.alpha_composite(fg); d.convert('RGB').save('<output>_darkcheck.png'); w=Image.new('RGBA', fg.size, (255,255,255,255)); w.alpha_composite(fg); w.convert('RGB').save('<output>_whitecheck.png')"
   ```

   Show both previews alongside the transparent PNG when asking for approval. The `_darkcheck` / `_whitecheck` files are scratch — delete them after review, never commit them.
3. **Retry discipline**: if either background check shows severe edge artifacts, regenerate once with the exact same prompt before editing any wording. The validated prompt has low median severity but non-zero variance — a same-prompt redraw is cheap and safe, while "improving" the wording has twice been shown to backfire (see Known Limitation).

## Expression Descriptions

Use these concrete descriptions in prompts (not just the emotion word):

| Expression | Prompt description |
|-----------|-------------------|
| `neutral` | neutral expression, relaxed face, calm eyes, slight natural resting expression |
| `smile` | warm smile, soft eyes, gentle happy expression, relaxed brows |
| `angry` | angry expression, furrowed brows, clenched jaw, intense sharp eyes |
| `sad` | sad expression, downcast eyes, slightly lowered brows, melancholic look |
| `surprised` | surprised expression, wide eyes, slightly open mouth, raised eyebrows |
| `confused` | confused expression, one eyebrow raised, slight frown, puzzled look |

## Art Style Cues

| Style | Prompt cues |
|-------|------------|
| `anime_illustration` | anime-style character illustration, detailed anime art, clean linework, cel-shaded coloring |
| `semi_realistic` | semi-realistic digital portrait, detailed rendering, soft lighting on face |
| `cel_shaded` | cel-shaded character art, flat colors with clean outlines, stylized anime shading |

## File Structure

MVP uses one pose per character. Multi-pose support (e.g., `<character>_<pose>_<expression>.png`) is a deliberate v2 scope item — not an oversight.

```
assets/tachie/
  akira/
    design.md
    akira_neutral.png
    akira_neutral.prompt.txt
    akira_smile.png
    akira_smile.prompt.txt
    akira_angry.png
    akira_angry.prompt.txt
    ...
```

## Validation

- All images for one character share the same framing and approximate proportions
- Transparent background (no solid color background baked in)
- Dual-background artifact check (dark + white) performed on every accepted image (bright artifacts only show against dark, dark artifacts only against white)
- Prompt Anchor text appears verbatim in every prompt
- Design doc exists before any generation
- Prompt file saved alongside every generated image

## Known Limitation — Hair Edge Highlight

The image model has a strong tendency to render a thin light-colored rim-light stroke along the hair silhouette edge, especially near strand tips (a common anime rendering convention, baked into the artwork itself). This is not a background-removal artifact — `rembg` correctly keeps these pixels as foreground, so no alpha-clamp or erosion post-processing can remove it.

Directly instructing the model to avoid all hair highlights is unreliable and can backfire — naming specific rendering techniques (e.g. "rim lighting", "specular highlights") or pointing at specific parts (e.g. "tips") sometimes increases their occurrence instead of suppressing it, likely a diffusion model attention artifact. What works better, validated via autoresearch-loop iteration (2026-07-02): instructing the model to confine any highlight near the crown/top of the head, away from the silhouette edge and strand tips, redirects the highlight to a harmless location instead of fighting the model's rendering prior — this is the highlight-placement line of the Anti-Artifact Prompt Lines section, used by both Step 2 and Step 3. This reduced edge-highlight severity from a median rubric score of 4 down to 1 across repeated trials on the Step 2 (text-to-image) path, though it does not fully eliminate the risk on every generation. Step 3 (image-to-image variant generation with visual reference) was not independently tested via autoresearch-loop — the same instruction was applied there for consistency, on the reasoning that the post-processing pipeline and the model's rendering prior are the same regardless of expression. A follow-up attempt to make the boundary even more precise (exact fractions like "upper quarter") backfired the same way as naming specific techniques — the vaguer-but-correctly-aimed instruction outperformed the more precise one.

Workaround for residual cases: first regenerate once with the same prompt (see Post-Process & Artifact Check — the distribution has low median but non-zero variance); if the artifact persists, avoid placing the character's hair silhouette directly over dark areas of the background when compositing (e.g., shift horizontal position, or pick a scene with a light-toned area behind the head). The compositing-time dodge remains a useful safety net, not a replacement for the prompt-level mitigation above.

## Boundaries

- Scene backgrounds → `generate-scene-bg`
- Dialogue UI, text boxes → separate skill (TBD)
- Cross-skill art style consistency (tachie + BG looking cohesive) → project-level style guide (TBD)
- This skill produces standing illustrations only — no engine metadata, no animation frames
