---
name: generate-scene-bg
description: "Generate ADV / Visual Novel style scene background illustrations. Use when creating narrative game backdrops, dialogue scene backgrounds, VN/ADV location art, or scene illustrations in anime, semi-realistic, painted, or cel-shaded styles. Supports optional time-of-day variants (day/night/sunset/rain) with visual reference handoff for consistency. NOT for character or sprite assets (use generate-tachie)."
---

# Generate Scene BG

Generate scene background illustrations for ADV / Visual Novel style games (Persona, Ace Attorney, etc.). Output is a finished single-image backdrop, not a layered game map.

## Parameters

Infer from the user request. Only `prompt` is required.

- `art_style`: `anime_illustration` | `semi_realistic` | `painted_scene` | `cel_shaded` | `project-native`
- `prompt`: the user's scene description
- `aspect_ratio`: `16:9` (default) | `4:3` | custom WxH
- `time_variant`: optional — `day` | `sunset` | `night` | `rain` | `overcast` | custom

When unspecified:
- Default `art_style` to `anime_illustration`.
- Default `aspect_ratio` to `16:9` (1920x1080).
- Omit `time_variant` unless the user asks for a specific time or weather.

## Workflow

### Step 1 — Scene Plan

From the user's description, infer:
- What location this is (classroom, courtroom, café, rooftop, etc.)
- Art style and aspect ratio
- Whether a time variant is requested
- Output file naming: `assets/bg/<scene-name>.png`

State the plan briefly and confirm before generating.

### Step 2 — Generate Background

1. Write the image prompt manually. The prompt must describe:
   - The scene composition, perspective, and depth
   - Art style cues matching the chosen `art_style`
   - Lighting and atmosphere matching `time_variant` if set
   - "No characters, no text, no UI elements" — backgrounds must be empty of actors
2. Call `image_gen` with the prompt.
3. Save the prompt as `assets/bg/<scene-name>.prompt.txt`.
4. Validate: correct dimensions/aspect ratio, no baked-in characters or text.

### Generating Variants (same scene, different time/angle)

When the user asks for a variant of an existing background (e.g., "same classroom but at night"):

1. Make the original background visible in conversation context. If it is a local file, call `view_image` immediately before writing the variant prompt.
2. In the variant prompt, explicitly say: use the visible image above as the visual reference — preserve the room layout, furniture positions, perspective, and composition. Change only the lighting/atmosphere/weather to match the new variant.
3. Generate the variant and save as `assets/bg/<scene-name>-<variant>.png` with its own `.prompt.txt`.
4. Save the base prompt alongside the variant prompt so the lineage is traceable.

This is best-effort consistency — image generation does not guarantee identical composition across variants. The visual reference handoff improves consistency but does not make it pixel-perfect.

## Prompt Guidelines

### Art Style Cues

| Style | Prompt cues |
|-------|------------|
| `anime_illustration` | anime-style background illustration, detailed anime scenery, soft lighting, clean lines |
| `semi_realistic` | semi-realistic digital painting, detailed environment art, cinematic lighting |
| `painted_scene` | hand-painted background, watercolor-inspired, painterly atmosphere |
| `cel_shaded` | cel-shaded background, flat color with clean outlines, stylized shading |

### What to Include

- Perspective and camera angle (eye-level, slightly elevated, wide shot, etc.)
- Key architectural/environmental features
- Lighting direction and quality
- Atmosphere and mood through visual description (not a separate mood parameter — describe it in the prompt)
- Time of day through lighting and sky cues when `time_variant` is set

### What to Exclude

- Characters, people, silhouettes, or figures
- Text, signs with readable text, UI elements
- Game HUD or overlay elements

## File Structure

```
assets/bg/
  classroom.png
  classroom.prompt.txt
  classroom-night.png
  classroom-night.prompt.txt
  courtroom.png
  courtroom.prompt.txt
```

## Validation

- Output image matches requested `aspect_ratio`
- No characters or text baked into the background
- Prompt file saved alongside every generated image
- Variant filenames follow `<scene-name>-<variant>.png` convention

## Boundaries

- Character sprites, standing illustrations → `generate-tachie`
- This skill produces scene illustrations only — no runtime metadata, no engine wiring
