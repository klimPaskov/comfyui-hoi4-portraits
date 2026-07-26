---
name: chaos-redux-event-assets
description: Use when creating, sourcing, processing, converting, organizing, wiring, or documenting visual assets for Chaos Redux.
---

# Chaos Redux Event Assets

Use this skill when a Chaos Redux task requires final visual assets.

This includes event assets, UI assets, focus tree assets, country assets, achievement assets, generated icons, sourced event art, generated icon art, animated sprites, animated portraits, sprite sheets, GIF previews, and any asset package that must be wired into the mod.

## 1. Core purpose

The goal is to turn asset needs from an event spec into real HOI4-ready files.

The asset workflow must produce:

- source artwork
- processed PNG previews
- final DDS files
- correct file placement
- sprite handoff notes for the main agent
- documentation of what was created

Do not leave assets as loose generated or downloaded images.

If an asset is used by the event, it must be processed, placed, documented, and handed off so the main agent can wire it cleanly.

## 2. When to use this skill

Use this skill for:

- event pictures
- report event pictures
- news event pictures
- super-event images
- decision icons
- decision category icons
- idea icons
- national spirit icons
- officer corps spirit icons
- focus icons
- achievement icons
- flags
- country leader, commander, and operative portraits
- explicitly authorized advisor, theorist, and high-command dossier portraits
- intelligence-agency and intelligence-operation icons
- commander-trait, medal, military-raid, state-modifier, MIO, faction, building, and modifier icons
- land, naval, and air equipment art, counters, emblems, and 3D unit visual references
- faction emblems
- UI panels
- progression-state variants
- animated sprites
- animated UI pieces
- animated leader portraits
- sprite sheets and GIF previews for review
- any other static or animated visual asset required by a Chaos Redux event or mechanic

Asset-type coverage is authorization-bounded. Do not infer a custom asset only
because the corresponding gameplay object exists. Create an asset family only
when an accepted spec row, asset manifest row, or explicit user instruction
requests it. Apply the same rule to optional portraits, route emblems,
animation, and other asset families not present in the accepted requirement
set.

Never infer an advisor, high-command, officer-corps, dossier-card, or other
small-portrait family from a character, idea, trait, or `portraits = { ... }`
consumer. Create that family only when the accepted requirement explicitly asks
for it; otherwise leave the family absent and report the authorization boundary.

Use this skill when the user asks the agent to create, source, process, or wire final visual assets.

Use this skill when the implementation task includes generated, sourced, or user-provided PNG files that must be turned into HOI4-ready assets.

Use `chaos-redux-frame-animation` together with this skill when an asset needs animation. Animated final assets must come from planned source frames, not from moving, scaling, rotating, warping, blurring, recoloring, or filtering one still image.


## 2.1 Custom subagent split

When actual files must be created, route the work through narrow project subagents instead of one broad asset worker.

The main agent decides which subagent to spawn, gives it a bounded asset prompt, reviews the output, and performs final wiring.

Use:

- `chaosx_asset_source_researcher` for real or archival image sourcing, immutable real-person source masters, subject-ownership evidence, exact portrait crops and crop-equality evidence, historical flag-design research, historically attested symbols, user-provided source photos, and report/news/super-event images that must depict real photographed material. For a real-person portrait it stops at the source-and-crop handoff and does not run Krea generation, approve likeness, or create the final DDS
- `chaosx_hoi4_portrait_pipeline` for bounded real-person ComfyUI Krea 2 production after the source-and-crop handoff, including preprocessing, masks, approved background composite, candidates, comparisons, manifests, and final PNG/DDS only after independent PASS
- `chaosx_portrait_identity_auditor` for independent read-only candidate review. It returns schema-valid likeness, style, mask, and provenance verdicts and cannot generate, edit, rank, select, or convert candidates
- `chaosx_generated_event_art` for generated non-icon event art, including fictional or alternate-history report images, news images, super-event images, fictional portraits and explicitly authorized fictional advisor masters, ImageGen-created flat flag designs, faction emblems, UI panels, and progression-state base art
- `chaosx_icon_artist` for focus, idea, national-spirit, officer-corps, decision, decision-category, mission, achievement, technology, intelligence-agency, intelligence-operation, commander-trait, medal, military-raid, state-modifier, MIO, faction, building, and modifier icons

Flags are a flat graphic-design pipeline, not event artwork. Historical flag research establishes the documented geometry, colours, and symbols; ImageGen still produces the final clean flat design under section 20.

For animated work, route by asset type first. Then require the chosen asset subagent to follow `chaos-redux-frame-animation` for frame plans, per-frame source art, normalization, contact sheets, preview GIFs, frame sheets, static fallbacks, and animation handoffs.

Asset subagents may create:

- source files
- processed PNG previews
- final DDS files
- contact sheets
- manifests
- `docs/assets/<event_id>_<event_slug>/gfx_handoff.md`

Asset subagents must not edit `.gfx`, localisation, GUI, event, focus, idea, decision, scripted effect, scripted trigger, on_action, history, country, or spreadsheet files unless the parent explicitly grants that scope.

The main agent owns final `.gfx` sprite definitions, gameplay references, docs alignment, spreadsheet alignment, and validation. When an asset change requires catalog alignment, update only the authoritative XLSX and run `python .tools/export_event_catalog_csv.py`; the three CSV files are export-only and must not be edited directly.

A good parent prompt to an asset subagent includes the event id, asset list, asset type, target size, source mode, final DDS folder, sprite name if already registered, reference folder, visual direction, source constraints, and anything the subagent must mark blocked instead of substituting.

For one-person country-leader or officeholder portraits, the parent prompt must also
state the polity's identity classification and the reason the selected source mode is
allowed. Use the portrait source-mode gate in section 3: grounded identities are
sourced, while generated one-person portraits are reserved for truly fictional
high-chaos countries or impossible/supernatural entities. Agents must fail closed when
that classification or source evidence is missing, contradictory, or unsupported.


## 2.2 Final asset placement and naming

Event-owned final assets should be grouped under an event-scoped folder whenever the engine surface uses explicit sprite or texture paths.

Use this folder form:

```text
<event_id>_<event_slug>
```

Place the event folder directly under the asset category folder, for example `gfx/event_pictures/014_cannibalism/` or `gfx/interface/ideas/014_cannibalism/`. Do not insert a project namespace layer such as `gfx/event_pictures/chaos_redux/014_cannibalism/`; the mod root already provides the project namespace.

Do not leave new event assets loose in category roots such as `gfx/event_pictures/`, `gfx/super_events/`, `gfx/interface/ideas/`, `gfx/interface/goals/`, `gfx/interface/decisions/`, or `gfx/leaders/` unless that root placement is an engine-facing lookup requirement.

Root-only and engine-convention exceptions:

- `gfx/achievements/` must keep achievement DDS files directly in the root. Do not create `gfx/achievements/<event_id>_<event_slug>/` subfolders unless a new engine behavior has been verified locally. Achievement filenames must match the full achievement ids from `common/achievements/`, so event-owned achievement ids and triplet filenames should use `<event_id>_<event_slug>_<achievement_name>{,_grey,_not_eligible}.dds` or the exact established id if it includes an ordinal.
- `gfx/flags/`, `gfx/flags/medium/`, and `gfx/flags/small/` must keep HOI4 tag/ideology filenames. Do not put flags into event folders; use cosmetic tags or route-specific tag filenames when an event needs transformed flags.

Shared or non-event systems may use a clear shared/system folder. Do not force shared assets into an event folder just to avoid a root directory.

When moving or adding an asset, update every `.gfx`, `.gui`, event, idea, decision, focus, localisation, and documentation reference that names the old path or sprite. Keep sprite names stable unless the engine-facing identifier itself has to change, as with achievement ids.

Super-event audio follows the `chaos-redux-super-events` convention. Final music belongs under `music/<event_id>_<event_slug>/super_event_<super_event_id>_<super_event_name>.ogg`, and matching sound-channel files belong under `sound/<event_id>_<event_slug>/super_event_<super_event_id>_<super_event_name>.wav`. Do not create persistent `music/source/` or `music/super_events/` folders; preserve source downloads under docs/assets source-audio paths instead.

## 2.3 Temporary event asset workspaces

Treat `docs/assets/<event_id>_<event_slug>/` as a temporary, event-scoped working and evidence folder, not as a shipped asset library. Use it during active implementation for source files, processed previews, contact sheets, prompts, provenance, manifests, animation plans and previews, source-audio downloads, and handoff notes. Keep it while the event is active, blocked, awaiting review, or undergoing acceptance scenarios.

Before declaring the event goal fully complete:

1. Confirm that every accepted asset row has a final runtime consumer and that no runtime reference points into `docs/assets/`.
2. Promote durable provenance, licensing, attribution, requirement-to-runtime crosswalks, review results, accepted handoff facts, and blocker or exception notes into permanent `docs/events/`, `docs/plans/`, `docs/specs/`, `docs/super_events/`, or another appropriate documentation surface.
3. Move final runtime assets into engine-facing folders and verify their `.gfx`, `.gui`, audio, or gameplay references.
4. Delete the complete event-scoped temporary workspace, including empty subfolders, and verify that it is absent.

An absent event-scoped `docs/assets/` folder is expected after a fully complete goal and is not an asset blocker. If the event is incomplete or blocked, retain the workspace and report the blocker. Never delete skill-local `assets/` reference libraries or an unrelated event workspace.

## 3. Asset source rules

Choose the source mode based on asset type.

### Scene-first and mood-first selection rule

Do not default event art to maps, cartographic overlays, arrows, staff tables, conference rooms, or generic war-room compositions unless that is the strongest visual for the specific asset.

For Chaos Redux, many event visuals should focus on the actor, force, symbol, ritual, creature, crowd, machine, government, army, leader, or strange condition behind the event. The image should usually make the event feel active and dangerous, not merely show that territory changed.

Prefer visuals that show:

- a country, movement, army, cult, council, machine, plague, or supernatural force as the subject
- people, banners, ruins, storms, fires, shadows, masks, relics, halls, crowds, weapons, monuments, or rituals
- obsession, wrath, zeal, panic, corruption, transformation, prophecy, dread, awe, or other event-specific mood
- fantasy, surreal, mythic, occult, symbolic, or unexplained elements when the event concept supports them
- a clear subject and strong atmosphere over neutral geography

Avoid making the main visual read like:

- a map has changed
- borders have shifted
- officers are discussing an expansion route
- the art is mainly a strategic diagram with decoration
- the scene is a generic command table without a strong event identity

Maps may still appear as secondary props when useful, but they should rarely be the main visual idea for fictional, alternate-history, high-chaos, supernatural, symbolic, or strange event assets.

### Use `$imagegen` for generated symbolic or fictional assets

Use Codex's official `$imagegen` skill by default for:

- idea icons
- focus icons
- decision icons
- decision category icons
- achievement icons
- fictional flag designs
- faction emblems
- fictional leader portraits
- UI panels
- progression-state base art
- other symbolic or fictional static assets

When creating generated assets, follow the `$imagegen` skill workflow. Do not define a separate image generation route in this skill.

For transparent icons, ask `$imagegen` for the required transparent output and follow the `$imagegen` skill's transparent image workflow. The final PNG must have real transparency, no fake checkerboard, no white halo, no white outline, and no opaque square background unless the asset type explicitly uses a painted backdrop.

If `$imagegen` is unavailable, report that clearly and stop before using an alternate route.

For generated animated assets, use `$imagegen` through `chaos-redux-frame-animation`. Each animation frame must be generated or edited as its own source frame according to a frame plan. Do not use local filters, transforms, glow pulses, or offsets as the source of final motion.

### Choose source mode for event photo assets

Report images, news images, and super-event images may be either internet-sourced or generated.

Use internet-sourced imagery when the asset must show a real photographed person, specific real battle, real place, real object, real newspaper, real poster, real map, real archive item, or other verifiable historical material.

Use `$imagegen` when the event is fictional, alternate-history, symbolic, supernatural, high-chaos, or when a unique scene is more important than matching an existing archive image. Generated event-photo assets should be prompted as period-authentic documentary material, not modern cinematic concept art.

For generated World War II-era report/news/super-event images:

- prompt for 1936-1945 photographic technology, period composition, period clothing, period vehicles, period architecture, and documentary realism
- avoid modern streets, uniforms, props, weapons, vehicles, signage, UI overlays, cinematic color grading, and readable generated text
- keep the source PNG, processed preview, final DDS, prompt, and manifest entry
- record the source mode as generated and explain why generation fit better than sourcing
- never use text-only generation, a name, a description, or a substitute face to fabricate a real person's likeness; an identity-preserving Krea 2 conversion of the unchanged sourced portrait is allowed only through the separate `hoi4-portrait-pipeline` workflow below

Follow the repository web research rules from `AGENTS.md` when searching for source images.

For internet-sourced event photo assets that are meant to represent the World War II era, search for period-matching source imagery from roughly 1936 to 1945 unless the event spec gives a narrower date range. Prefer contemporary photographs, war correspondents' photographs, press agency images, propaganda posters, maps, newspapers, official records, government or military archive images, museum scans, library scans, and period illustrations. Do not use modern photographs, reenactment images, film stills, AI-looking reconstructions, postwar uniforms, streets, weapons, vehicles, buildings, colorized tourist photos, reenactments, or modern props when they do not fit the era. If no suitable period source can be found, either generate a period-authentic fictional/documentary image when the asset does not require a real source, or mark the asset as blocked or `needs_user_review`.

Record the image source, source link, author or archive if available, license or public domain status if available, estimated date or date range, why the image fits the World War II era, and any uncertainty in the manifest.

### Portrait source-mode gate

Classify a country-leader, commander, named officeholder, or institutional-leader
portrait before routing it:

- **Grounded identity**: any country or polity that existed, partly existed,
  claims continuity from a real institution or community, or remains otherwise
  plausibly historical, including real, historical, restored, separatist, regional,
  indigenous, dynastic, or otherwise plausibly historical country, polity, or
  community. Use `chaosx_asset_source_researcher` and attributed source material:
  sourced real people for leaders, commanders, and named officeholders, or
  authentic archival institutional material for a governing body or symbolic
  institution. Match the time, place, role, and accepted demographic constraints.
  Never generate an invented officeholder, fictional face, or invented grounded
  institution, even when the route is absurd, alternate-history, or high-chaos. If
  no defensible source and usable image exists, mark the portrait/package `blocked`
  and do not substitute a generated portrait.
- **Fictional high-chaos identity**: a truly fictional country or an
  impossible/supernatural entity. A generated one-person leader is allowed only in
  this class, and only when the package itself is high-chaos. Reject an ordinary,
  conventionally dressed, or interchangeable generated officeholder. Make the
  leader visually memorable with
  extraordinary invented ceremonial dress, regalia, body adornment, ritual objects,
  altered uniforms, or another internally coherent motif belonging to the fictional
  polity's invented culture. The strangeness must come from that designed setting,
  not borrowed sacred objects or exaggerated traits of a real people. Avoid modern
  props, generic faces, meme aesthetics, gore, mockery, stereotypes, and caricatures
  of real cultures.

Record the classification, source mode, identity evidence, and any blocked decision in
the manifest and handoff. Missing, ambiguous, or contradictory classification is a
fail-closed source-mode error; stop and report it instead of choosing a convenient
fallback.

### Portrait subject ownership gate

Before sourcing or wiring any real-person leader, commander, operative, or named
officeholder token, search both installed vanilla and the current project for exact
and variant identity forms (including transliterations, titles, and name-order
variants). Check character definitions, country histories and recruitment, portrait
files, `.gfx`/interface consumers, leader/commander/operative/officeholder consumers,
and relevant localisation (normally `common/characters/`, `history/countries/`,
`gfx/leaders/`, `interface/`, and `localisation/`). A person already defined,
recruited, or meaningfully portrait-owned by a live character roster may not be
cloned into another country.

Reuse is allowed only through an explicit guarded existing-character transfer or
availability contract that removes or invalidates origin ownership before target
ownership and prevents simultaneous ownership. Without that contract, fail closed
and block the portrait/token. Literal ship names, production-line names, streets,
equipment, or incidental prose are not character ownership unless an actual
character, portrait, leader, commander, operative, or officeholder consumer resolves
to the person. Record search terms, roots/files and ids checked, matches or no-match
evidence, disposition, and any transfer guard in the manifest and handoff. Run it in
addition to the unchanged grounded-source-only (`grounded_source_only`) versus
`fictional_high_chaos` source-mode gate; it never authorizes a generated grounded
person.

### Real-person portraits

Do not generate, reconstruct, or substitute the identity of a real person. This applies to country leaders, commanders, operatives, and named officeholders. The identity master must be an unchanged attributed archival photograph of the real subject; for a male subject, it must be an unchanged attributed archival male photograph. An illustration, statue, reenactor, actor, text description, or generated reconstruction cannot serve as the identity master.

Use this mandatory fail-closed sequence for every real-person portrait: unchanged attributed archival photograph (archival male photograph for male subjects) -> explicit head-and-shoulders crop -> source-locked identity-preserving Krea 2 conversion through `hoi4-portrait-pipeline` in the matching HOI4 painted portrait family -> deterministic 156x210 processing -> independent likeness/style/provenance audit by someone other than the producer -> DDS conversion and runtime wiring only after PASS.

Make the explicit crop boundary before ImageGen with `.agents/skills/chaos-redux-event-assets/tools/extract_portrait_source_crop.py`, passing required decoded-master `left top right bottom` coordinates and retaining its lossless PNG plus JSON evidence. The utility uses Pillow as the single decode/crop backend, reopens the PNG, and fails closed unless its decoded pixels exactly equal the same decoded master rectangle; it never resizes, enhances, recolours, retouches, or overwrites without `--force`. An `ffmpeg` or ImageMagick crop that cannot retain an equivalent exact decoded-pixel equality proof is not an accepted immutable source crop.

Use the repository web research tools when a source image is needed, and prefer public domain, archival, official, or clearly licensed photographs. If the person belongs to the World War II setting, prefer contemporary portraits, wartime photographs, news photographs, official photographic portraits, military archive photographs, or passport or identity photographs. Archival illustrations may inform period context but never identity or likeness. Do not use modern actors, reenactors, statues, cosplay, later fictional depictions, postwar images, or modern images that do not fit the era unless the user explicitly approves them as placeholders.

Preserve the unchanged master as immutable evidence and use the exact crop as the ImageGen identity reference; role-specific canonical references may guide style only and may not supply, replace, or invent the person's face.

Identity preservation is a separate non-compensable pass/fail gate: style quality can never excuse identity drift. Preserve exact facial geometry, asymmetry, age, expression, hair and facial hair, pose, and source-visible clothing, and do not add hidden detail or unsupported clothing or insignia.

Compare the unchanged master, explicit crop, raw Krea candidate, processed 156x210 candidate, and role-specific canonical references at native size and an enlarged inspection scale of at least 4x nearest-neighbour.

Reject genericization, beautification, symmetrization, face substitution, invented hidden detail, unsupported clothing or insignia, weak likeness, or a mere filtered/resized photograph. Raw or merely resized sourced images are evidence only and never final runtime portraits.

Keep the source, crop, raw Krea candidate, processed candidate, audit sheet, and final DDS in distinct paths; never overwrite the source master or silently replace provenance.

Record the source link, attribution, archive, license or public-domain status when available, immutable source hash, crop coordinates, prompt or generation record, role/reference family, candidate hash, audit reviewer and date, separate likeness/style/provenance verdicts, final DDS path, and sprite name in the manifest and handoff. If any source, identity, provenance, or audit evidence is missing or fails, mark the portrait blocked and do not substitute a generated or generic person.

### Real-person ComfyUI production routing

After `chaosx_asset_source_researcher` creates the immutable source master, exact crop, crop-equality evidence, subject-ownership disposition, and provenance manifest, route production through `.agents/skills/hoi4-portrait-pipeline/SKILL.md`.

The portrait producer is `chaosx_hoi4_portrait_pipeline`. It uses the standalone project and one of the four registered profiles. Agent profiles receive a prompt beginning exactly with `hoi4_portrait,` and contain no automatic describer. Human profiles may use the approved describer. The person's name may remain in provenance records but must not appear in the model prompt.

The producer may create deterministic derivatives, masks, approved-background composites, Krea 2 candidates, comparison sheets, and a production manifest. It must not approve its own likeness. Before final PNG or DDS acceptance, spawn `chaosx_portrait_identity_auditor` with `fork_context=false`, randomized candidate order, source and comparison evidence, a calibrated threshold id, and no producer ranking. The auditor is read-only and returns the normative portrait audit schema.

A candidate is eligible only when every mandatory identity, structure, expression, accessory, foreground, mask, style, and provenance gate is PASS. Any FAIL or UNCERTAIN gate blocks autonomous finalization. Style quality cannot compensate for identity uncertainty.

The standalone controller may perform this separation through independent processes, but the producer and auditor identities and process ids must remain different. The parent agent chooses among independently eligible candidates, verifies checksums, copies the DDS to the runtime path, wires the character and GFX references, and proves a live in-game consumer.

Keep ComfyUI and MCP guidance in `hoi4-portrait-pipeline`. Do not create a central MCP skill or expose an unauthenticated public ComfyUI server. When the portrait project and Chaos Redux repository are on different machines, use a portable checksummed handoff instead of assuming one session can access both.

For generated or sourced one-person portraits, the asset handoff must identify the subject's role and gender presentation plus any matching name-pool or character-metadata requirement. Female-presenting portraits must not be paired with male names and should require `female = yes` where a country leader is created directly. Male-presenting portraits must not be paired with female names or `female = yes`. Council, board, office, crowd, and symbolic-institution portraits should keep institutional leader names instead of personal random-name pools.


### Fictional portraits

Fictional country leaders, commanders, operatives, invented councils, collective
bodies, supernatural leaders, and symbolic regime portraits must use `$imagegen`,
subject to the portrait source-mode gate above. A generated one-person country leader
is permitted only for a truly fictional high-chaos country or an impossible/supernatural
entity; a grounded polity always remains on the sourced-real-person path.

Generated country-leader and commander portraits should follow the full `156x210` HOI4 portrait convention. Generated operatives must follow the matching cataloged operative portrait and owning sprite. Use head-and-shoulders or restrained bust framing, a strong face or governing-body focal point, subdued painterly finish, period-appropriate uniform or civilian clothing, a HOI4-compatible background, and no text, labels, watermarks, modern UI, or meme-like exaggeration.

For generated one-person portraits, record the subject role, apparent gender
presentation, `fictional_high_chaos` classification, and the extraordinary invented
regalia or cultural motif in the manifest and handoff. Where name pools or gender
metadata apply, they must match the portrait. Never hand off a portrait in a way that
lets implementation randomly assign names from the opposite gender pool. Do not use
generic faces, modern props, meme aesthetics, gore, mockery, stereotypes, or
caricatures of real cultures as visual shorthand.

For a fictional council, committee, junta, board, office, crowd, or symbolic-body
leader, follow the accepted content brief and use an institutional name rather than a
random personal name pool. A people-free institutional composition may use one
readable symbol, empty chamber, desk, machinery, seal, document arrangement, or other
institution-specific subject. A staged governing group is allowed only when the brief
requires it and every visible subject satisfies the accepted demographic and period
constraints. For a grounded institution, use defensible sourced archival material for
the real institution or source a real officeholder; do not generate an invented body
or officeholder. If the design calls for a specific person, route it through the
one-person portrait rules instead of treating that person as an institution.

### User-provided assets

If the user provides an image, treat it as a source asset.

Record that the image was user-provided in the manifest.

Still crop, resize, convert, place, wire, and document it like any other source asset.

## 4. Reference asset examples

This skill owns its visual-reference library under:

`C:\Users\klimp\OneDrive\Documents\Paradox Interactive\Hearts of Iron IV\mod\chaos_redux\.agents\skills\chaos-redux-event-assets\assets`

`assets/vanilla_reference/` is the canonical semantic library, with Vanilla HOI4
as the primary source and explicitly marked Chaos Redux examples where needed.
`assets/leader_portraits/` is the user-requested, curated male-only quick-reference
pack for HOI4 country-leader and army/navy-commander styling. Do not route reference
work through project-root asset folders or another skill-local copy.

Start with:

- library rules and contact sheets: `assets/vanilla_reference/README.md`
- exact source provenance and dimensions: `assets/vanilla_reference/CATALOG.md`
- leader-portrait routing: `assets/leader_portraits/README.md`
- copied portrait provenance and hashes: `assets/leader_portraits/REFERENCE_MANIFEST.md`

Unless a path below begins with `assets/`, interpret it relative to
`assets/vanilla_reference/`.

Every semantic reference directory contains its own `contact_sheet.png`; there is no shared `contact_sheets/` directory. Contact sheets are labeled with filenames and native dimensions, and are review aids rather than reference examples themselves. Common icon families (focus, ideas, decisions, decision categories, technologies, and achievement states) have at least 15 references; other tracked families have at least 5.

Canonical portrait paths:

- country leaders: `assets/vanilla_reference/portraits/leaders/`
- army and navy commanders: `assets/vanilla_reference/portraits/commanders/`
- operatives: `assets/vanilla_reference/portraits/operatives/`
- advisors and high-command dossier cards: `assets/vanilla_reference/portraits/advisors/`
Country leaders, commanders, and operatives are full `156x210` portrait
textures. For portrait work, inspect both the canonical role-specific contact sheet
and the matching `assets/leader_portraits/leaders/` or
`assets/leader_portraits/commanders/` quick-reference contact sheet. The copied pack
is reference-only; its source mapping and hashes are recorded in
`assets/leader_portraits/REFERENCE_MANIFEST.md`.
Advisor and high-command dossier references are native `65x67` cards and use
their own canonical contact sheet; do not substitute the full portrait or
quick-reference packs for this family.

Canonical flag and event-art paths:

- flat flags: `flags/normal/`, `flags/medium/`, and `flags/small/`
- report-event art: `event_art/report/`
- news-event art: `event_art/news/`
- super-event art: `event_art/super_event/`

Canonical gameplay-icon paths:

- national focus: `icons/national_focus/`
- ideas and national spirits: `icons/ideas/`
- decisions: `icons/decisions/`
- missions: `icons/missions/`
- decision categories: `icons/decision_categories/`
- achievement state triplets: `icons/achievements/`
- officer corps spirits: `icons/officer_corps_spirits/`
- technologies: `icons/technologies/`
- special projects: `icons/special_projects/`
- balance of power: `icons/balance_of_power/`
- intelligence agencies: `icons/intelligence_agency/`
- intelligence operations: `icons/intelligence_operations/`
- commander traits: `icons/commander_traits/`
- medals: `icons/medals/`
- military raids: `icons/military_raids/`
- state modifiers: `icons/state_modifiers/`
- military industrial organizations: `icons/military_industrial_organizations/`
- factions: `icons/factions/`
- buildings: `icons/buildings/`
- modifiers: `icons/modifiers/`

After placing a technology or doctrine icon, use `hoi4.tech_inspect` in `explain` or `lint` mode to verify the sprite and texture references, then use the `assets` or affected folder view in `hoi4.tech_render` for deterministic review. Missing or ambiguous assets remain implementation findings; this skill still owns source art, processing, DDS conversion, placement, manifests, and sprite handoff.

Canonical unit-visual paths:

- equipment and technology art: `units/equipment/technology_art/`
- large land-unit counters: `units/land/counters_large/`
- land map counters: `units/land/map_counters/`
- division-template emblems: `units/land/division_template_emblems/`
- air map counters: `units/air/map_counters/`
- naval map counters: `units/naval/map_counters/`
- land model materials: `units/models_3d/land_materials/`
- air model materials: `units/models_3d/air_materials/`
- naval model materials: `units/models_3d/naval_materials/`

The tree is semantic, not a bank of interchangeable pictures. Use the folder for the exact owning UI or model surface, then follow the cataloged source, native canvas, frame count, transparency, and owning definition.

The canonical `assets/vanilla_reference/` tree remains the source of truth for exact
engine surfaces and semantic ownership. The curated `assets/leader_portraits/` pack
is the deliberate portrait-review aid requested for agents and must stay aligned with
its manifest; it is never a runtime asset source.

The reusable achievement not-eligible compositing overlay lives at
`icons/achievements/overlay.png`. It is a workflow
input rather than a reference example, so it is excluded from the achievement
contact sheet and coverage count.

Do not add new reference images outside the skill-local `assets/` root. Add semantic
references under `assets/vanilla_reference/`; add male leader or commander review
copies under `assets/leader_portraits/` only with exact provenance, dimensions,
hashes, and contact-sheet coverage recorded in its manifest.

Before generating, sourcing, processing, or wiring an asset, read the library
rules, inspect the matching category and contact sheet, and follow the vanilla
source path in the catalog to its owning `.gfx`, `.gui`, `.asset`, or `.mesh`
definition when engine behavior matters. Reference PNGs are never final assets:
do not wire, recolor, trace, or ship them. If no category matches, inspect the
closest canonical category plus a direct vanilla or established Chaos Redux
precedent before choosing a style.

## 5. Generated artwork rules

Do not create core artwork from simple shapes, placeholders, contact sheets, layout-only mockups, empty UI boxes, or generated charts. Final art must be real generated, sourced, or user-provided artwork, not circles, rectangles, lines, gradients, geometric diagrams, or other primitive-shape stand-ins.

For super-event images, this rule is strict: final art must be a real scene, archival image, painted illustration, or generated documentary-style image. Do not use symbolic diagrams, flat icons, abstract geometry, title cards, or UI-like compositions as the final super-event image unless the user explicitly requests that exact visual approach and the exception is documented.

Use `$imagegen` for generated artwork and follow the `$imagegen` skill workflow for the source image.

Generated artwork must be real source art that can be processed into the final game asset. Final assets must be clean: must not have sticking artifacts, an icon is centered in the image, etc. Do not use contact sheets, review boards, or layout drafts as final source art.

## 5.1 Icon creation rules

Small gameplay icons must be readable at their final in-game size.

- Use transparent backgrounds for asset types that are transparent in vanilla, especially idea and decision icons and small symbolic interface icons.
- Keep unused pixels fully transparent. Do not leave a square opaque fill behind icons unless the asset type explicitly uses a painted frame or backdrop.
- Give the icon silhouette a dark or black outline and a subtle drop shadow when the icon is displayed over variable UI backgrounds. Do not leave some chroma green outline on the icon.
- Avoid tiny interior detail that disappears at 45x45 or 64x64. Favor one clear subject, strong value contrast, and a centered silhouette.
- Avoid fake checkerboard pixels, white halos, white outlines, oversized medallion fills, and square opaque backdrops.

For every generated icon, follow the `$imagegen` skill's transparent image workflow. Preserve the original generated image, create a processed PNG preview, convert to DDS, and validate the final appearance over a checker background before treating the icon as complete.

The final icon should have transparent unused canvas, no fake checker or matte pixels, no transparent holes inside the painted subject, a slight black outline, a subtle drop shadow, and a centered subject that remains readable at final size.

Generated icon packages must keep visible `$imagegen` source evidence: save the source atlas or source PNGs, record the prompt and source mode in the manifest, process to real transparent backgrounds, and include a contact sheet that shows final alignment, dimensions, transparency, and absence of white matte or opaque square backgrounds. Do not mark a generated icon complete if the final art is a primitive local drawing, a resized unrelated icon, or a locally assembled shape substitute instead of imagegen or sourced artwork.

## 5.2 Icon type separation rules

Focus, idea, national-spirit, officer-corps, decision, mission, decision-category, achievement, technology, special-project, balance-of-power, intelligence-agency, intelligence-operation, commander-trait, medal, military-raid, state-modifier, MIO, faction, building, and modifier icons are separate asset types.

Never treat focus, idea, and decision icons as interchangeable.

Do not create focus icons first and then satisfy idea icons or decision icons by resizing, cropping, shrinking, recoloring, padding, or lightly editing the focus icon. This is not a valid asset workflow.

Each icon type must have its own asset-type-specific brief, reference inspection, source artwork, prompt or source choice, crop, target size, filename prefix, manifest entry, and final DDS output.

Shared visual themes are allowed only when every icon is still designed for its own in-game use:

- focus icons should read as full HOI4 focus art at 94x86 with focus-tree style detail and composition
- idea and national spirit icons should read as compact 64x64 symbolic spirit art without borrowing the full focus icon frame
- decision icons should read clearly at 32x32 with simpler shapes, stronger silhouettes, and less interior detail
- decision category icons should be designed for the category button or scripted GUI surface, not derived from a focus icon
- officer corps spirit icons should follow the vanilla officer corps spirit look and 45x45 transparent style
- achievement icons should follow achievement presentation rules and variant rules
- intelligence-agency and intelligence-operation icons must follow their own agency or operation UI precedent rather than a generic decision treatment
- commander traits, medals, military raids, state modifiers, MIOs, factions, buildings, and modifier icons must follow the matching canonical folder and owning vanilla definition; do not force these families onto a blanket 32x32 or 64x64 canvas
- frame strips, indexed building sprites, and multi-state modifier art must retain their frame order and frame count rather than being treated as a single standalone icon

If a mechanic needs matching focus, idea, and decision visuals, build them as a coordinated icon family. A coordinated family can share subject matter, symbols, colors, and lore cues, but each member still needs separate source art or a separate generated output designed for its target size and UI role.

The manifest must record the exact asset type for every icon and should note when icons are part of a coordinated family. Do not mark an icon complete if it only exists as a resized version of another icon type.

## 6. Required asset workflow

For every asset package:

1. Read the event spec, asset prompt, or implementation task.
2. Identify every required visual asset.
3. Group assets by usage type.
4. Split every icon family named in section 5.2 into its own asset-type work item. Never satisfy one UI surface by resizing, relabeling, or lightly editing art created for another surface.
5. Assign each asset a stable filename.
6. Assign each asset a sprite name if it needs one.
7. Identify the target size.
8. Identify the intended in-game use.
9. Inspect the matching reference folder from section 4 before generating, sourcing, processing, or wiring the asset.
10. Decide the source mode for each asset:
   - `$imagegen`
   - internet source image
   - user-provided source image
   For one-person country-leader or officeholder portraits, record the grounded or
   `fictional_high_chaos` identity classification before selecting a mode. A grounded
   identity must use a sourced real person; an unavailable defensible source is
   `blocked`, never a generated substitute. Before sourcing or wiring a real-person
   leader, commander, operative, or named officeholder, apply the portrait subject
   ownership gate above and record its evidence. Missing or contradictory source-mode
   or ownership evidence fails closed.
11. For every real-person leader, commander, operative, or named-officeholder portrait, create the explicit archival crop and JSON equality evidence with the section 3 utility, then hand the immutable source package to `chaosx_hoi4_portrait_pipeline`. The sourced researcher stops before Krea generation, identity approval, final PNG processing, or DDS conversion.
12. Run `chaosx_portrait_identity_auditor` or the standalone controller's verified independent auditor on randomized candidates. Compare the unchanged master, crop, raw Krea candidate, processed 156x210 candidate, and role-specific references at native and enlarged sizes. Record separate likeness, style, mask, and provenance verdicts. A pending, failed, or uncertain identity gate is `needs_user_review` or `blocked`, never converted or wired.
13. If the asset is animated, follow `chaos-redux-frame-animation` before ordinary static processing. Write the animation brief and frame plan, create or approve the static fallback, generate or source every frame, then normalize the frame sequence.
14. For `$imagegen` assets, write a specific image generation prompt and create the base artwork by following the official `$imagegen` skill.
15. For internet-sourced assets, find a suitable source image and record its source link, author or archive if available, and license or public domain status if available.
16. For user-provided assets, record that the image was provided by the user.
17. Save the original generated, sourced, or provided image as a source PNG.
18. Crop and resize non-portrait assets to the target size; real-person portraits require the exact lossless source crop and JSON equality evidence before ImageGen, followed by the deterministic 156x210 candidate from section 3. Do not treat an `ffmpeg` or ImageMagick crop as immutable unless its decoded pixels are independently proven equal to the same decoded master rectangle.
19. Save a processed PNG preview.
20. Convert a real-person portrait to DDS only through the verified `hoi4-portrait-pipeline` finalization route after an independent all-PASS audit. Convert other processed assets to DDS 32 bit unsigned BGRB 8.8.8.8.
21. Move the DDS into the correct mod folder.
22. Create or update the asset manifest.
23. Create or update `gfx_handoff.md` for any asset that needs a sprite definition.
24. Update event docs or asset docs when the parent prompt grants that documentation scope.
25. Report all created files, proposed sprite names, final paths, independent audit status, blocked assets, and any handoff uncertainty.

Do not mark assets complete until the DDS files exist, the manifest is written, every real-person portrait has an independent all-PASS audit from a reviewer or process separate from the producer, and the main agent has enough handoff information to wire every sprite without guessing.

## Asset depth from improvement addenda

When an improvement addendum asks for richer presentation, the asset handoff should name the visual states instead of asking for generic polish. A good asset request says what the player sees before activation, while active, when locked, when dangerous, when complete, and when the route has failed.

For scripted GUI, plan asset families. A panel usually needs a background, header, button states, value icons, warning indicators, progress frames, locked overlays, selected overlays, hover states, and any animated glow, particle, float, or pulse layers. The main agent owns `.gui` and `.gfx` wiring, but the asset package must provide clear sprite names, sizes, frame counts, static fallbacks, and contact sheets.

## 7. Asset package structure

When creating a new event asset package, use a stable temporary working folder.

Recommended working structure:

```text
docs/assets/<event_id>_<event_slug>/
  manifest.md
  prompts/
  source_png/
  processed_png/
  contact_sheets/
  notes/
```

Final DDS files must be moved into the correct gameplay asset folders.

Do not keep final assets under `docs/assets/`.

Keep this workspace through active implementation, review, and validation only. Before the event goal is fully complete, preserve any durable provenance or coverage facts in permanent docs, then delete the entire event-scoped workspace. Do not require the deleted workspace to exist for a completion claim.

## 8. Manifest requirements

Every active event asset workspace must include a markdown manifest.

Recommended path while work is active:

```text
docs/assets/<event_id>_<event_slug>/manifest.md
```

The manifest must list every asset. Before deleting the temporary workspace, copy any durable provenance, licensing, attribution, coverage, review, and exception facts needed by the event documentation or audit handoff into a permanent documentation surface.

Each asset entry should include:

- asset name
- related event id
- related event slug
- asset type
- intended in-game use
- source mode: `$imagegen`, internet source image, or user-provided source image
- image generation prompt if generated with `$imagegen`
- source link if internet-sourced
- source author, archive, or collection if available
- source date or estimated date range if internet-sourced
- license or public domain status if available
- era-fit note for World War II-era assets
- source PNG path
- processed PNG path
- final DDS path
- target size
- sprite name
- `.gfx` file
- localisation key if relevant
- related focus, idea, event, decision, UI element, or super-event if relevant
- notes
- asset status
- frame count, frame timing, loop behavior, and anchor point for animated assets
- static fallback path and animated sheet or frame-sequence path for animated assets
- source mode and source note for every animation frame when animated
- for real-person portraits, immutable source-master path and hash, attribution, explicit crop coordinates, exact-crop PNG and JSON evidence paths and hashes, raw Krea candidate path and hash, deterministic processor/version with normalized arguments and hash, deterministic 156x210 candidate path and hash, role-specific reference folder and hashes, and native/enlarged comparison-sheet path
- for real-person portraits, independent reviewer identity and date, proof that the reviewer is not the producer, separate likeness/style/provenance verdicts, and the portrait gate state
- portrait subject-ownership search terms, roots/files and ids checked, matched owner or
  consumer (or explicit no-match evidence), disposition, and any guarded transfer/
  availability contract

Use `not_needed`, `planned`, `sourced`, `generated`, `processed`, `converted`, `handed_off`, `wired`, `complete`, `needs_user_review`, or `blocked` as asset statuses.

## 8.1 Requirement-to-runtime coverage audit

Before any asset completion claim, create or refresh a row-level coverage crosswalk from every accepted asset requirement in the current specs, manifest plans, and animation plans. Do not start from the assets that happen to be live. Each accepted row must identify:

- its requirement id and accepted design source
- its intended in-game purpose
- the exact source package and manifest entry
- the exact runtime registration: final asset path plus the `.gfx` sprite or texture, engine lookup id, or other owning definition as applicable
- the live consumer file and id
- the state or visibility binding when the asset is conditional or state-driven
- the current audit record path, evidence, and row status

For every animation family, also record the purpose and the direction or state semantics that distinguish the family, together with its frame, timing, and loop evidence. Frame totals, live animation-family totals, and registered sprite totals are not coverage proof.

For every real-person portrait row, the current audit record must link the unchanged source master, explicit crop, raw Krea candidate, deterministic 156x210 candidate, matching role-specific references, native/enlarged comparison evidence, independent reviewer identity, and separate likeness/style/provenance PASS; style quality cannot compensate for an identity failure, and DDS conversion or runtime wiring evidence is valid only after PASS.

Audit exact rows, not counts. An extra asset or animation cannot satisfy an absent accepted row unless an explicit accepted design amendment identifies that row and names the replacement; link that amendment in the crosswalk. Any missing source package, runtime registration, live consumer, required state or visibility binding, or current audit record leaves the row incomplete.

After a late user correction or accepted spec, manifest-plan, or animation-plan change, rebuild the crosswalk against the current repository and attach a fresh coverage diff listing added, removed or replaced, changed, and still-uncovered rows. Do not reuse the prior audit or its totals for the completion claim.

## 9. Standard HOI4 asset sizes

Use these sizes unless the event spec or an existing repo pattern gives a better project-specific requirement.

- report event images: 210x176
- news event images: 397x153, black and white
- country-leader portraits: 156x210
- commander portraits: 156x210 full portrait textures, never a fabricated 50x67 source texture
- operative portraits: 156x210 full portrait textures; still follow the cataloged owning sprite
- flags small: 10x7
- flags medium: 41x26
- flags normal: 82x52
- tech icons small: 64x64
- tech icons medium: 132x52
- achievements: 64x64
- super-event images: 457x328
- decision icons: 32x32
- idea and national spirit icons: 64x64
- focus icons: 94x86

Use other sizes when the event's UI or asset type requires it.

For every icon, counter, emblem, strip, or model material not listed above, take the canvas and frame behavior from the matching canonical catalog entry and owning vanilla definition. Do not infer a universal size from the folder name or from a visually similar asset family.

When unsure, inspect the existing Chaos Redux pattern and vanilla HOI4 assets before choosing.

## 9.1 Unit visual references

Treat every unit visual as a domain-and-surface-specific pipeline. Inspect the matching catalog entries, contact sheet, and owning vanilla definition before deciding what the task needs.

- `units/equipment/technology_art/` contains flat 2D equipment illustrations used by equipment and technology sprites. Native canvases vary; follow the owning `interface/*.gfx` sprite.
- `units/land/counters_large/` contains large frame-aware land-unit strips. Preserve the cataloged `noOfFrames`, frame order, per-frame footprint, and transparent bounds.
- `units/land/map_counters/` contains land map-counter art. It is not a large division-designer strip.
- `units/land/division_template_emblems/` contains division-template identity emblems. It is not equipment art or map-counter art.
- `units/air/map_counters/` and `units/naval/map_counters/` contain domain-specific map-counter art. Do not substitute land counters or resized equipment art.
- `units/models_3d/land_materials/`, `units/models_3d/air_materials/`, and `units/models_3d/naval_materials/` contain UV model materials paired with cataloged `.mesh`, `.asset`, and entity definitions. They are not 2D icons, finished renders, or concept sheets.

Classify the requested deliverable before creating art: equipment/technology illustration, large land counter, land/air/naval map counter, division-template emblem, or land/air/naval 3D model package. Give each class its own brief, source art, native canvas or UV layout, frame metadata, final path, and handoff. A 3D task must keep model geometry, materials, entity wiring, and any separately produced concept reference distinct. Do not derive one unit pipeline by resizing, relabeling, or recoloring another.

### 3D model package handoff

Route 3D model production to `chaos-redux-3d-model-pipeline` and `chaosx_3d_model_pipeline`. This is a separate pipeline from 2D equipment art, map counters, division emblems, and frame-sheet animation.

Before any provider or paid work, the 3D route must verify a nonblank `MESHY_API_KEY`, the selected pinned Meshy MCP route, the narrow Blender HOI4 adapter, the installed Blender version, and the checksum-locked `io_pdx_mesh` setup.

When a ready reference is absent, the route creates exactly one clean `meshy_input.png` for the asset. Never create or send side-profile sheets, turnaround boards, collages, or multi-view boards to Meshy. Contact sheets and Blender renders are QA evidence only.

Every 3D asset brief must identify the asset profile, deterministic job root, provider task lineage, reference checksum, named vanilla mesh and entity precedent, source geometry height, entity scale, effective runtime height, axes, origin, contact plane, required actions, root-motion policy, PDX material channels, texture dimensions, `.mesh` and `.anim` outputs, reimport proof, runtime hashes, and live consumer.

For humanoid units, calibrate against the installed vanilla infantry source mesh and entity rather than an assumed real-world height or arbitrary entity scale. Apply the entity scale exactly once and record the source-height-to-runtime-height crosswalk.

Provider source files are immutable evidence. Working geometry must be repaired so it has no holes, loose or non-manifold geometry, degenerate triangles, missing components, or zero-weight deforming vertices. Use the verified PDX shader and packed specular map convention; never route raw grayscale roughness into the PDX specular channel because that creates chrome-black surfaces.

For animated units, provider actions are candidates that must be cleaned, retargeted or authored, baked, checked for root policy, grounded contacts, deformation, FPS, frame range, and loop behavior, then exported and reimported as real `.anim` files. A static image or still mesh is not an acceptable substitute for a requested skeletal action.

The asset worker owns source files, checkpoints, processed textures, previews, exports, manifests, reports, reimport evidence, and a runtime handoff. The main implementation agent owns `.asset`, entity, `.gfx`, unit/building/gameplay wiring, final runtime synchronization, and in-game screenshots.

## 10. Naming rules

Use lowercase snake_case.

Keep names stable once they are wired into `.gfx`.

Recommended filename prefixes:

- idea icons: `idea_`
- focus icons: `goal_`
- decision icons: `decision_`
- decision category icons: `decision_category_`
- report event images: `report_event_`
- news event images: `news_event_`
- super-event images: `super_event_`
- achievement icons: `achievement_`
- country-leader portraits: `leader_`
- commander portraits: `commander_`
- operative portraits: `operative_`

For event-specific assets, include the event id or slug where useful. For example, all idea assets related to an event should go into one folder of that event.

## 11. Image generation prompt rules

Every `$imagegen` prompt should be specific enough to produce usable game art.

A good prompt should include:

- asset type
- target in-game use
- subject
- visual style
- readability requirements
- what must be avoided
- whether the result must be readable at small size

Do not ask for vague "cool icon" style outputs.

Do not rely on text inside generated images. Generated text is unreliable.

Prefer strong symbols, clear silhouettes, and readable composition.

For transparent icon prompts, explicitly request a transparent canvas, no fake checkerboard, no white rim, no white/colored outline, no glow, no sticker border, no opaque square background, and a clean silhouette suitable for HOI4 UI.

## 12. Internet source image rules

When using internet source images:

1. Search for images that fit the event tone, target use, and intended era.
2. For World War II-era event assets, search for source images from roughly 1936 to 1945 unless the event spec gives a narrower date range.
3. Prefer contemporary or near-contemporary public domain, archival, official, museum, library, newspaper, map, press photograph, propaganda poster, government record, military record, period illustration, or clearly licensed sources.
4. Reject modern photographs, reenactments, film stills, postwar streets, uniforms, props, weapons, vehicles, buildings, AI-looking reconstructions, and later stylized images when they do not fit the era.
5. Record source links, source date or estimated date range, and license or public domain status when available.
6. If licensing, date, or era fit is unclear, mark it as uncertain in the manifest.
7. Process the image into the correct HOI4 size and style.
8. Preserve the source image path and processed preview path.

For public-facing or uncertain assets, keep the manifest honest about the source status, date uncertainty, and World War II-era fit uncertainty.

## 13. Report event images

Report event images may use internet-sourced imagery or generated period-documentary imagery. Prefer generated report images when the event needs a unique fictional or alternate-history scene, staged document, invented location, or more specific visual than archive search can reliably provide. Use real sources when the image must depict a real person, real historical scene, or real archival document.

Report event images should look like documentary-style photographs, field documentation, or period documentary material.

For World War II-era subjects, prefer contemporary photographs, war correspondents' photographs, press agency images, propaganda posters, newspapers, maps, official records, military archive images, museum or library scans, or period illustrations. Do not use modern reenactment photos or modern documentary photos that visually belong to a later era.

Use:

- realistic or period-authentic source imagery
- black-and-white treatment with sepia applied
- World War II-era visual fit when the event belongs to that era
- period-appropriate framing where possible
- strong subject clarity
- natural composition
- no modern UI overlays
- no modern clothing, streets, weapons, vehicles, buildings, or props unless they are intentionally part of the event
- no generated text

Target size:

```text
210x176
```

Report event images must be black and white with sepia applied. Do not leave report event images in full colour unless the user explicitly requests a colour exception, and record that exception in the manifest.

### Report-event card treatment

Report-event images use a finished `210x176` RGBA canvas. The source photograph is processed as a slightly tilted documentary card with transparent edge space and a soft drop shadow. The transparent corners are part of the style.

Do not ask `$imagegen` to create the tilted card. Generate or source the documentary photograph first, then apply the card treatment locally. This keeps the tilt, shadow, and margins consistent.

```powershell
python -B .agents/skills/chaos-redux-event-assets/tools/process_report_event_image.py source.png processed_report_event.png
python -B .agents/skills/chaos-redux-event-assets/tools/process_report_event_image.py source_folder processed_folder
```

The script performs cover crop, black-and-white conversion, sepia application, grain, paper border, deterministic tilt, transparent canvas margin, and soft shadow. It writes RGBA PNG output. Convert the processed PNG to DDS through the normal repo workflow.

Validation:

- processed PNG is exactly `210x176`
- final DDS is exactly `210x176`
- corner pixels are transparent
- no hard photo pixels are clipped
- tilt is visible but subtle
- shadow is soft and not a thick border
- edge space is transparent, not black padding
- source remains readable after crop, tilt, shadow, and DDS conversion

Generated report images must still receive this local report-card treatment.

## 14. News event images

News event images may use internet-sourced imagery or generated period-news imagery. Prefer generated news images when the event needs a unique fictional or alternate-history scene, invented crisis, or scene that is unlikely to exist in archives. Use real sources when the image must depict a real person, real historical scene, or real archival item.

News images should look like black-and-white documentary photographs or period news illustrations.

For World War II-era subjects, prefer contemporary newspapers, news photographs, war correspondents' photographs, press agency images, propaganda posters, maps, official visual records, military archive images, museum or library scans, or period illustrations. Do not use modern reenactment photos, modern news photos, film stills, or later images that do not fit the era.

Use:

- old news photograph or period press illustration style
- World War II-era visual fit when the event belongs to that era
- clear central subject
- strong contrast
- period-appropriate composition
- no modern UI overlays
- no modern clothing, streets, weapons, vehicles, buildings, or props unless they are intentionally part of the event
- no generated text

Target size:

```text
397x153
```

News images must be black and white.

Generated news images must be converted to black and white during processing, with period press contrast/grain and no modern color remnants. Record the source link and license or public domain status for internet-sourced images, or the generation prompt and source-mode rationale for generated images.

## 15. Super-event images

Super-event images may use internet-sourced imagery or generated art. Prefer generated super-event images for fictional, alternate-history, symbolic, supernatural, high-chaos, or emotionally specific moments where a unique composed image better fits the super-event role. Use internet sources when the image must depict a real historical person, real photographed event, or real archival artifact.

Super-event images should have:

- strong central composition
- clear dramatic theme
- readable subject
- enough contrast for HOI4 UI
- World War II-era visual fit when the event belongs to that era
- no generated text
- no modern clothing, streets, weapons, vehicles, buildings, props, film stills, or reenactment imagery when they do not fit the era
- no cluttered small details that disappear at final size

Target size:

```text
457x328
```

If a super-event needs music, use `chaos-redux-super-events` and research suitable public domain or clearly licensed music. Final audio should use the event-scoped `music/<event_id>_<event_slug>/` and `sound/<event_id>_<event_slug>/` layout from that skill. Never create event or super-event audio from generated test tones, primitive waveforms, beeps, noise beds, or local oscillator output; that includes sine, square, triangle, and sawtooth waveforms.

For each track, document:

- title
- composer
- performer or recording source if relevant
- public domain status or license status
- source link
- why it fits
- suggested in-game use
- editing notes

Do not claim public domain status without checking.

If the license is unclear, mark it as uncertain or unsuitable.

## 16. Idea and national spirit icons

Idea and national spirit icons should look like compact HOI4-style icon art.

They should have:

- strong central symbol
- clear silhouette
- aged texture
- strong contrast
- readable meaning at 64x64
- no generated text

Target size:

```text
64x64
```

Use `idea_` filename prefix.

These icons usually do not need the full focus icon frame.

Do not derive idea or national spirit icons from focus icons. They must be designed as 64x64 spirit-style icons from their own prompt or source art, even when they share a theme with a focus.

Use `$imagegen` for the base artwork unless the user provides or requests a specific source image.

Follow the `$imagegen` skill's transparent image workflow when the icon should have a transparent background.

Inspect `icons/ideas/` and the matching row in `CATALOG.md` before generating or processing idea icons.

## 17. Focus icons

Focus icons should look like normal HOI4 focus icons.

They should have:

- strong central symbol
- clear silhouette
- aged texture
- painterly detail
- readable contrast
- meaningful relation to the focus
- no generated text

Target size:

```text
94x86
```

Use `goal_` filename prefix.

Do not make focus icons look like generic generated thumbnails.

Do not create a focus icon as the master artwork for idea icons, decision icons, or other smaller icon types. A focus icon can share a theme with those icons, but it must remain a separate focus-specific asset.

Every focus icon should support the focus tree's story, ideology, or gameplay purpose.

Use `$imagegen` for the base artwork unless the user provides or requests a specific source image.

Follow the `$imagegen` skill's transparent image workflow when the icon should have a transparent background.

Inspect `icons/national_focus/` and the matching row in `CATALOG.md` before generating or processing focus icons. Do not force every focus source onto an older nominal canvas when the owning sprite and current vanilla precedent use a different native canvas.

## 18. Decision icons

Decision icons must remain readable at very small size.

Use:

- simple symbolic composition
- strong contrast
- clear central shape
- limited small detail
- no generated text

Target size:

```text
32x32
```

Use `decision_` filename prefix.

Do not derive decision icons from focus icons or idea icons. They must be composed for 32x32 readability from their own prompt or source art.

Decision category icons may use:

```text
decision_category_
```

Use `$imagegen` for the base artwork unless the user provides or requests a specific source image.

Follow the `$imagegen` skill's transparent image workflow when the icon should have a transparent background.

Inspect `icons/decisions/`, `icons/missions/`, or `icons/decision_categories/` as appropriate before generating or processing decision-system icons. Missions use the decision icon pipeline but still need mission-specific semantic readability.

## Additional gameplay icon families

Route additional icon work by the exact UI surface:

- intelligence identity and action: `icons/intelligence_agency/` and `icons/intelligence_operations/`
- commander progression and honours: `icons/commander_traits/` and `icons/medals/`
- operations and world state: `icons/military_raids/` and `icons/state_modifiers/`
- organizations and map/economy identity: `icons/military_industrial_organizations/`, `icons/factions/`, and `icons/buildings/`
- generic or text-linked modifier presentation: `icons/modifiers/`

Read the matching canonical catalog entries and inspect the owning `.gfx`, `.gui`, or database definition before choosing canvas, frame layout, transparency, or filename. These families are not reskinned decision or idea icons. When a source is a strip or contains several UI states, preserve its frame semantics and document them in the manifest and handoff.

## 19. Achievement icons

Achievement icons should be compact and readable at 64x64.

Generate the completed achievement icon first with `$imagegen`.

Then create:

- grey variant (simply black and white)
- not-eligible variant by copying the grey variant and compositing `icons/achievements/overlay.png` on top

The variants may be created after the completed icon exists.

Do not create not-eligible achievement icons by red-tinting, filtering, darkening, recoloring, or manually redrawing the grey icon. If the overlay file is missing or cannot be applied cleanly, stop and report the asset as blocked instead of substituting another treatment.

Target size:

```text
64x64
```

Use an `achievement_` prefix for source or intermediate art when it helps distinguish the asset type.

For Chaos Redux final files, achievements are a root-only exception. Put completed, grey, and not-eligible DDS files directly under `gfx/achievements/`, and name them after the exact achievement id registered in `common/achievements/`:

```text
gfx/achievements/<achievement_id>.dds
gfx/achievements/<achievement_id>_grey.dds
gfx/achievements/<achievement_id>_not_eligible.dds
```

When renaming or adding achievement ids, update `common/achievements/`, `localisation/english/chaosx_achievements_l_english.yml`, `interface/chaosx_achievements.gfx`, the three DDS variants in `gfx/achievements/`, and any docs or manifests that list the final DDS paths. If the achievement registry owns a single `unique_id`, keep it as one root-level registry file and group event-owned achievements by event section inside the file instead of splitting it into per-event achievement files.

Inspect `icons/achievements/` before generating or processing achievement icons. The reference set includes a completed, grey, and not-eligible triplet; keep all three states aligned to the exact achievement id.

## 20. Flags

Flags should use clean symbolic designs that look like intentional flag designs, not simple-shape placeholders, palette swaps, ugly filters, or flipped/recolored variants. Treat flags as flat identity assets, not artwork or illustrated scenes.

Inspect the complete flat flag ladders in `flags/normal/`, `flags/medium/`, and `flags/small/` before creating or processing flags. Compare all three sizes together in `flags/contact_sheet.png`.

They must remain readable at HOI4 sizes.

Required flag sizes:

- small: 10x7
- medium: 41x26
- normal: 82x52

HOI4 flag TGAs must use the same origin/header convention as vanilla flags. Validate with `file`; completed flag TGAs should read as Targa image data at the correct size and must not end with `- top`. If a flag displays upside down in-game while the artwork looks correct in an image viewer, fix the TGA encoding/origin on the flag files themselves. Do not add custom UI sprites, scripted-localisation routing, DDS display copies, or other workarounds for flag orientation.

Use enough heraldic detail to prove that the design is authored rather than a basic-shape placeholder, while keeping the principal emblem readable at `10x7`. Prefer a layered civic, heraldic, industrial, botanical, maritime, or institutional emblem with a clear outer silhouette over an isolated circle, star, arrow, stripe, or geometric blob.

Avoid generated text unless the design absolutely requires it and the final output is manually checked.

Always use `$imagegen` for every new flag, including historically attested and real-world designs. Historical research still comes first: save and cite a reliable design reference, then use it as an image input and strict design constraint for imagegen. The generated result must be a clean, flat flag reconstruction, not an illustration of a flag. Reject waving fabric, folds, flagpoles, skies, lighting, gradients, painterly texture, vignettes, fake lettering, invented seals, perspective, shadows, or any scene around the flag. Manually compare geometry, colour fields, symbol count, symbol orientation, and heraldic details with the cited reference before resizing it. Imagegen is not permission to reinterpret a documented historical design.

For existing countries that already have game-provided or repository-approved base flags, do not replace the no-suffix base flag as part of an ideology pass. Keep the base flag unchanged, or restore it from the approved prior asset if an asset pass damaged it, unless the user explicitly asks for that base flag to be redone or the country receives a deliberate focus/event/cosmetic-tag transformation. Ideology variants should be separate assets for `_communism`, `_democratic`, `_fascism`, and `_neutrality`, not mutations of the base flag with one small shape, a palette swap, a color filter, a vertical flip, or a copied emblem.

For focus-tree or event route flag changes, use explicit cosmetic tags or route-specific flag files and document the trigger/focus that changes the flag. Do not create default flag overrides or new base flags for vanilla-supported or already-existing countries just because they participate in an event.

Historical or historically grounded flags must use sourced motifs, documented heraldry, period symbols, or clearly explained alternate-history synthesis. If no directly attested flag exists, state that in the manifest and produce a historically grounded design from relevant motifs instead of inventing unrelated symbols.

Generated fictional or alternate-history flag variants must come from a separate `$imagegen` result for each visually distinct design and then be processed into final flag sizes. Preserve the generated emblem geometry, internal heraldic construction, and identifying details through export. Do not replace the generated design with local rectangles, circles, stars, arrows, traced silhouettes, or other programmatically drawn geometry. Do not use a solid-fill normalizer, aggressive palette quantizer, vector trace, or edge simplifier that reduces generated detail to primitive shapes. Mechanical cropping, colour management, edge cleanup, orientation correction, resizing, and TGA export are allowed, but they must not become the source of the design.

Keep the full ImageGen source master and create a comparison sheet containing that master plus the normal, medium, and small exports. Reject a flag when its normal export no longer contains the distinctive generated emblem or when its small export reads as an accidental blob. Flags are designs/assets, not event artwork: the source and final files must still be flat, orthographic flag graphics without fabric, folds, a flagpole, a scene, perspective, lighting, shadows, or painterly surface texture.

Before marking any flag complete, verify normal, medium, and small TGA files:

- normal: 82x52
- medium: 41x26
- small: 10x7
- correct visual orientation in a contact sheet
- TGA origin/header convention consistent with vanilla HOI4 flags; `file` output must not show `- top`
- no byte-identical ideology variants unless the design is intentionally shared and documented
- no upside-down copies
- no accidental no-suffix base-flag replacement for countries that were only meant to receive ideology variants

## 21. Country-leader, commander, operative, and named-officeholder portraits

For real country-leader, commander, operative, and named-officeholder portraits, apply the section 3 sequence exactly: unchanged attributed archival photograph (archival male photograph for male subjects) -> explicit head-and-shoulders crop -> source-locked identity-preserving Krea 2 conversion through `hoi4-portrait-pipeline` in the matching HOI4 painted portrait family -> deterministic 156x210 processing -> independent likeness/style/provenance audit by someone other than the producer -> DDS conversion and runtime wiring only after PASS.

The full-size processor keeps positional mode `leader` for backward compatibility and defaults `--role-family leader`. Commanders must pass `--role-family commander`; this selects the canonical commander directory and commander-only style references (Montgomery and Witzleben) for the processor review sheet and evidence. The review sheet's first panel is the `processor input crop`, meaning the crop of the supplied processed source or raw Krea candidate; it is not the immutable archival crop. The independent auditor must still compare the archival master, explicit archival crop, raw Krea candidate, processed candidate, and role-specific references separately, because the processor sheet cannot replace provenance evidence.

Before the full-size invocation, create the immutable source crop with the exact decoded-master boundary and retain the utility's JSON equality evidence:

```powershell
python -B .agents/skills/chaos-redux-event-assets/tools/extract_portrait_source_crop.py `
	<archival_master.jpg> <archival_crop.png> `
	--crop <left> <top> <right> <bottom> `
	--metadata <archival_crop.json>
```

The metadata must record the Pillow/tool version and hash, master/output hashes and dimensions, decode modes, crop rectangle, equality result and hashes, and normalized command. Do not accept an `ffmpeg` or ImageMagick crop as immutable source evidence when it cannot prove exact decoded-pixel equality against the same master rectangle.

Use this full-size commander boundary exactly:

```powershell
python -B .agents/skills/chaos-redux-event-assets/tools/advisor_icon_processing.py leader `
	<processed_source_or_imagegen_result.png> <candidate.png> --role-family commander `
	--source-kind real --crop <left> <top> <right> <bottom> --review-sheet <review.png>
```

Choose the canonical reference family by role before starting:

- country leader: `portraits/leaders/`
- army or navy commander: `portraits/commanders/`
- operative: `portraits/operatives/`
- named officeholder: the canonical family owned by its consuming leader, commander, operative, advisor, or high-command surface

Use role-specific references as style-family controls only and never as a source for the person's face. Compare the unchanged master, explicit crop, raw Krea candidate, processed 156x210 candidate, and role-specific canonical references at native size and an enlarged inspection scale of at least 4x nearest-neighbour.

Preserve exact facial geometry, asymmetry, age, expression, hair and facial hair, pose, and source-visible clothing. Reject genericization, beautification, symmetrization, face substitution, invented hidden detail, unsupported clothing or insignia, weak likeness, or a mere filtered/resized photograph. Raw or merely resized sourced images are evidence only and never final runtime portraits.

Record:

- source link if internet-sourced
- author or archive if available
- license or public domain status if available
- original image path
- immutable source hash, explicit crop coordinates, raw Krea candidate path and hash, deterministic 156x210 candidate hash, matching reference folder and hashes, comparison-sheet path, independent reviewer identity and date, and separate likeness/style/provenance verdicts
- processed PNG path
- final DDS path

For fictional people, non-human beings, supernatural entities, aliens, zombies, monsters, symbolic leaders, or other invented characters, `$imagegen` may be used to create the base portrait only when the portrait source-mode gate classifies the identity as `fictional_high_chaos`. Grounded real, historical, restored, separatist, regional, indigenous, dynastic, or otherwise plausibly historical polities must use sourced real-person candidates; if no defensible candidate and usable image exists, mark the portrait `blocked`. Give an allowed generated portrait the matching leader, commander, or operative references as style inputs and request the vanilla HOI4 painted portrait treatment, head-and-shoulders or restrained bust framing, extraordinary invented ceremonial dress or regalia, a quiet painted background, and controlled contrast. Reject normal-looking, conventionally dressed, or interchangeable fictional leaders. Require culturally coherent absurdity designed for the invented polity without borrowing or distorting sacred objects or traits of a real people. Allow no modern props, generic face, meme aesthetics, gore, mockery, stereotype, caricature, text, or photographic/modern concept-art finish.

Country-leader, commander, operative, and named-officeholder identity candidates are deterministic `156x210` portraits. Advisor and high-command cards then follow section 21.1's separate native `65x67` dossier pipeline after the shared identity gate. A commander reference is a full `156x210` vanilla portrait, even if a particular UI view displays it at a smaller apparent size; never manufacture or document a 50x67 commander source texture. Operatives also use the full portrait pipeline; follow their cataloged owning sprite.

## 21.1 Advisor and high-command portrait icons

Advisor, theorist, military-high-command, and officer-corps portrait icons are a
separate asset type. Inspect `assets/vanilla_reference/portraits/advisors/` before
work. The final target is native `65x67`, with a recognisable HOI4-styled
head-and-shoulders portrait, dark irregular dossier framing, and transparent outer
corners. Do not infer this family from a character or small-portrait consumer; it
must be present in the accepted requirement set.

Apply the section 3 source-mode gate to the advisor subject: grounded, historical,
restored, separatist, regional, indigenous, dynastic, or otherwise plausibly
historical advisor identities use sourced real people, while generated one-person
advisors are limited to truly fictional high-chaos or impossible/supernatural
entities. Missing or contradictory classification fails closed. For a fictional
advisor in the allowed class, generate a distinct full-resolution portrait master
with `$imagegen`; do not reuse a leader crop or manufacture card artwork with a
local drawing script. For real people, complete the shared real-person identity gate through an independently approved 156x210 candidate before following this separate dossier-card pipeline, and preserve source attribution. Institutional or collective briefs must state whether the result is people-free or includes a governing group; never imply that invented faces are sourced historical individuals.

Every advisor run requires a repo-contained schema-1 portrait-provenance manifest
through `--portrait-provenance-manifest`. A manifest may contain several approved
portrait-source records, but each processor invocation must select exactly one
`approved_for_processing` record by the invoked source path. The selected record
must pin the source kind, source hash and dimensions, exact-source-copy assertion,
approved crop and face box, prompt record/section/hash, generation mode and inputs,
and either an ImageGen handle for fictional, collective, or symbolic art or
attribution and license for a real archival portrait. Do not split out or bypass an
individual source to avoid these checks.

The visible dossier kit must also be authored with `$imagegen`. Use a shadowless,
unrotated frame source and a separate shadowless, unrotated, visibly opaque
textured-paper source. The paper must have continuous material and clean edges with
no transparent holes, cut-out fringe, chroma fringe, white matte, or fake
translucency. Derive each overlay from its retained ImageGen source through the
manifest-pinned alpha extraction and despill only; do not redraw, repair, recolour,
relight, texture, seal, write on, or otherwise change its visible RGB artwork
locally. Both retained sources, both alpha-extracted overlays, their prompt and
generation-input records, the frozen keyer and arguments, and the six canonical
style-reference hashes must remain in the self-contained provenance-schema-4
overlay manifest. If a genuinely different dossier treatment is required, retain
and manifest a complete new frame-and-paper source/overlay pair.

Do not shrink, pad, or directly wire a `156x210` leader, commander, or operative
portrait. Choose an explicit source-pixel crop and compose the subject independently
inside the native card with processor/render v5.0 at
`.agents/skills/chaos-redux-event-assets/tools/advisor_icon_processing.py advisor`.
Pass `--face-box`, both provenance manifests, and both retained ImageGen
source/overlay pairs. There is no paperless, procedural, primitive-drawn,
synthesized, or unpinned-source fallback. The processor may crop, grade, resize,
angle, derive soft RGB shadows from authored alpha, composite, validate, and export;
it must never draw or reconstruct visible frame, paper, seal, bevel, patina, emblem,
writing, or shadow artwork from primitive geometry.

Processor/render v5.0 always exports an exact `65x67` native PNG. Its pinned native
composition uses a `40x58` frame at `(1,1)` rotated `5` degrees and a `25x30` paper
at `(29,26)` rotated `-4.25` degrees. It validates frame and paper geometry,
palette, alpha coverage, portrait window, overlap, face placement, paper opacity,
and RGB support rather than trusting a resized source. The frame must remain
narrow, irregular, and neutral charcoal/black. The paper must remain pale,
low-chroma, textured, visually opaque across its support, and free of holes or
fringe.

Freeze the v5 execution contract before processing: Python `3.9.12`, Pillow
`11.1.0`, processor SHA-256
`e248979f21784c016e69c5458b9925c32177d6af29f2cca1a82bfaaffbe1f23c`, and advisor
render-configuration SHA-256
`e9f8d54d1ea7fc8845bf22675c09686acc7196556a56f96f5a1b46268b134637`. Stop and
re-review the pipeline if any frozen value differs. Preserve the full seed payload,
normalised command and argument hash, runtime, configuration, processor/source/
input hashes, and artifact hashes in metadata.

The final native composite must sit inside all nine frozen six-reference style bands
with a minimum normalized interior margin of `0.03`:
`top_frame_variation`, `left_rail_variation`, `left_rail_mean`, `left_rail_std`,
`paper_mean`, `paper_std`, `paper_samples`, `portrait_mean`, and
`bottom_area_variation`. These mechanical family gates prove measured placement,
value, texture, and variation compatibility at native size; they do not claim
one-to-one visual equivalence and do not grant visual approval.

At runtime, v5 derives and verifies both canonical six-reference families from the
actual skill-local reference PNGs. The rounded per-pixel mean alpha envelope must
hash to
`5d33afdd1adc0349e33b52bb141ddd1449107fd34727d19fcc45bcd7809d2993`, and the
derived aggregate paper-family record must hash to
`c751cbe5f1178c8b894c56a4cebe01bb4dae88ae859b7238c2c68f39a6224dbc`. The vanilla
alpha envelope is opacity data only. Visible RGB may originate only from the
approved portrait, ImageGen-authored frame and paper, their authored-alpha-derived
shadows, and the permitted faint black backing at the low-alpha fringe. Never copy,
blend, trace, expose, or ship visible vanilla RGB.

The v5 identity-preservation search has an authored-edge-preserving unsmoothed
stage and a face-protected background-smoothing last-resort stage. Every retained
candidate must pass background structure gates plus both the strict face gate
against the post-grade baseline and the source-face gate against the mapped
original source. Frame and paper identity, palette, opacity, and geometry remain
separate fail-closed gates; passing one gate cannot compensate for another.

Use this invocation shape for the dossier-card processor:

```powershell
python -B .agents/skills/chaos-redux-event-assets/tools/advisor_icon_processing.py advisor `
	<portrait_master.png> <advisor_icon.png> --source-kind fictional `
	--crop <left> <top> <right> <bottom> `
	--face-box <left> <top> <right> <bottom> `
	--portrait-provenance-manifest <portrait_provenance_manifest.json> `
	--advisor-overlay-manifest .agents/skills/chaos-redux-event-assets/assets/advisor_dossier_overlays/advisor_dossier_overlay_manifest.json `
	--advisor-frame-source .agents/skills/chaos-redux-event-assets/assets/advisor_dossier_overlays/v3/advisor_frame_shadowless_imagegen_source.png `
	--advisor-frame-overlay .agents/skills/chaos-redux-event-assets/assets/advisor_dossier_overlays/v3/advisor_frame_shadowless_overlay.png `
	--advisor-paper-source .agents/skills/chaos-redux-event-assets/assets/advisor_dossier_overlays/v3/advisor_paper_shadowless_imagegen_source.png `
	--advisor-paper-overlay .agents/skills/chaos-redux-event-assets/assets/advisor_dossier_overlays/v3/advisor_paper_shadowless_overlay.png `
	--review-sheet <advisor_review.png> `
	--metadata <advisor_icon.json>
```

Never omit the portrait-provenance manifest, self-contained overlay manifest, or
either source/overlay pair, and never provide an overlay without its retained
generated source. A candidate that cannot satisfy the complete provenance,
runtime, identity, style-band, frame, paper, face-placement, palette, opacity,
alpha/paper-family, and RGB-support gates must be regenerated or recropped; it must
not be accepted through a weaker mode.

Apply this same dossier-card pipeline when a character explicitly defines a
`portraits = { army = { small = ... } }` sprite. Vanilla army-character precedents
point that small slot to a `65x67` dossier portrait while the character's
`army.large` sprite remains the full `156x210` commander portrait. Do not create a
plain `50x67` resize or crop for the army-small slot, and do not replace or downsize
the approved full commander texture. Independently compose the approved portrait
master inside the dossier overlays, keep the large and small sprite names stable,
and validate both runtime textures separately.

Protect all provenance inputs as immutable. The candidate PNG, review PNG, and
metadata JSON must use three distinct repo-contained output paths that do not alias
the portrait source, manifests, frame/paper sources or overlays, prompt records,
generation inputs, keyer, processor, or six vanilla references. The processor
prepares and verifies the exact PNG decodes and JSON payload first, then commits the
three artifacts transactionally with rollback. Retain the portrait master,
provenance manifests, generated overlay sources, alpha-extracted overlays, prompts,
processor arguments, hashes, metadata, and reference comparison sheet.

The review sheet must show the candidate and every one of the six frozen references
both at native `65x67` and at `4x` nearest-neighbour size. The reviewer must inspect
face readability and identity, frame silhouette and palette, paper geometry and
opacity, texture continuity, holes/fringe, alpha-derived shadows, transparent
corners, and overall vanilla-family fit at both scales. Automated validation
produces a candidate, never visual approval; keep metadata at
`candidate_requires_visual_approval`. The producing agent may not approve its own
candidate. Convert only an independently approved PNG with
`python -B .agents/skills/chaos-redux-event-assets/tools/convert_to_dds.py --input <approved.png> --output <runtime.dds> --width 65 --height 67`.


## Animated leader portraits

Leader portraits can be animated for special routes, high-chaos leaders, supernatural leaders, rare formables, major transformations, or dramatic council reveals. They should not be required for every normal country leader.

Animated leader portrait packages must include:

- static fallback portrait
- animated sheet or frame source
- final DDS files
- final sprite names
- character or leader key that will use the portrait
- source mode and source documentation
- whether the leader is real, fictional, symbolic, collective, supernatural, or alternate-history
- note on motion type, such as glow, smoke, flicker, eye-light, flag shadow, slow breathing, office light, map projection, or particle drift

## 22. UI panels and custom windows

For UI panels, investigation windows, ledgers, and similar assets, separate artwork from functional UI.

Use `$imagegen` for:

- illustrated background panels
- thematic decorations
- symbolic seals
- propaganda visuals
- report board visual elements

Use normal UI editing for:

- exact layout slicing
- cropping
- button states
- state variants
- meter fills
- final export preparation

Do not let generated art decide exact interactive layout.

The implementation must still follow HOI4 UI rules and existing repo patterns.

## Decision category and scripted GUI visual packs

For a decision category with a scripted GUI or mechanic window, the asset handoff should cover the full interface state set.

Useful assets include:

- category icon
- category header plate
- background panel
- tab buttons
- normal, hover, selected, locked, disabled, and warning button states
- progress bars and fill variants
- meter frames
- target cards
- status seals
- warning overlays
- animated glow overlays
- animated particle overlays
- animated float emblems
- static fallback for every animated element
- tooltip icon set
- close and open buttons
- mechanic-specific leader, council, or envoy portrait

The asset prompt should state which sprites are decorative and which represent mechanic state. State-driven sprites need clear names that match the mechanic value or route state.

## 23. Progression-state variants

Progression-state variants may include:

- selected
- dim
- active
- inactive
- locked
- completed
- rejected
- damaged
- corrupted
- urgent
- meter-fill
- bar-fill

Progression-state variants should use the same target size as the base asset.

## Formable nation asset coverage

Every formable nation needs visible identity assets.

Asset planning should cover:

- formable flag in normal, medium, and small sizes
- ideology variants where relevant
- cosmetic-tag flags where relevant
- leader portrait or council portrait
- animated leader portrait when the formable is a rare dramatic route
- focus icons for the formation route
- decision icon for the formation decision
- decision category or scripted GUI assets if formation progress is managed visually
- news, report, or super-event image if the formation is globally important
- faction emblem if the formable creates a league, empire, federation, bloc, mandate, compact, or coalition
- achievement icon if the formable has achievement hooks

Historical or culturally attested formable symbols need source review. Fictional, alternate-history, supernatural, and high-chaos variants may use generated art with clear manifest notes.


## Animated sprites, scripted GUI assets, and animated portraits

Use `chaos-redux-frame-animation` for every final animated visual asset. Some Chaos Redux mechanics should have animated visual layers when motion improves readability, atmosphere, or feedback. Examples include floating seals, glowing route emblems, particle drift, meter pulses, warning frames, active-button glows, occult pressure effects, sponsor influence networks, and final formable proclamations.

Animated leader portraits should be handled as major identity assets. Real people require sourced base images. Fictional or impossible leaders can be generated. The asset handoff must say whether the animation is subtle, such as breathing light or smoke, or symbolic, such as eye glow, map shadow, glitch, or spectral overlay. The portrait should still read clearly at in-game size.

Final animated assets must be built from planned source frames. Do not create final animation by taking one still image and shifting, scaling, rotating, warping, blurring, recoloring, brightening, or pulsing it with a script. Local scripts may normalize, align, crop, resize, assemble sheets, create previews, and convert frames after the real frames exist.

## 24. DDS conversion

Final PNG assets must be converted to DDS using the repository's standard DDS conversion workflow. The converter lives only at `.agents/skills/chaos-redux-event-assets/tools/convert_to_dds.py`; `.tools/convert_to_dds.py` is obsolete, and active skills, agents, scripts, and handoffs must not restore or call it.

The output must be compatible with Chaos Redux's expected 32-bit BGRA or B8G8R8A8-style DDS workflow.

Run the bundled converter from the mod root:

```powershell
python -B .agents/skills/chaos-redux-event-assets/tools/convert_to_dds.py --input <processed.png> --output <final.dds> [--width <pixels> --height <pixels>]
```

If a retained custom mechanical processor must write uncompressed BGRA DDS directly, mirror that converter's `write_bgra_dds` layout exactly instead of inventing another header layout.

For a standard legacy, one-level, uncompressed BGRA DDS, require all of the following:

- a 128-byte file header in total: `DDS ` magic at byte 0, `DDS_HEADER` size `124` at byte 4, and 11 reserved dwords before the pixel-format block
- `DDS_PIXELFORMAT` at byte 76 with size `32`, flags `65` (`RGB | ALPHAPIXELS`), fourCC `0`, bit count `32`, and BGRA masks `0x00FF0000`, `0x0000FF00`, `0x000000FF`, and `0xFF000000`
- `DDSCAPS_TEXTURE` (`0x1000`) at byte 108
- no mipmaps unless the target asset deliberately requires them

Validate each uncompressed one-level BGRA output by checking the declared width and height, exact file length `128 + width * height * 4`, actual alpha-byte minimum and maximum against the asset's intended transparency, and successful registration of the final path in `.gfx`. Dimension and alpha checks alone are insufficient: reject shifted pixel-format blocks, missing texture caps, or any other malformed header even when an image decoder can report plausible dimensions.

If a processing script is retained as provenance, rerun it after correcting its DDS writer and validate every DDS it produces, not only the asset that exposed the defect.

If conversion fails, stop and report the error. Do not invent another conversion route unless the user approves it.

After conversion, confirm that:

- the DDS exists
- the dimensions are correct
- the background is transparent for icons
- the filename is stable
- the file is in the correct mod folder, including the event-scoped folder or documented root-only exception
- the `.gfx` path points to the DDS
- the manifest records the final path

Do not leave only PNG files when the game expects DDS.

## 25. `.gfx` handoff and main-agent wiring

Asset subagents do not edit `.gfx` files by default.

When an asset needs a sprite definition, the asset package must include a handoff note for the main agent.

Recommended path while the event asset workspace is active:

```text
docs/assets/<event_id>_<event_slug>/gfx_handoff.md
```

The handoff must include:

1. Final DDS path.
2. Proposed sprite name or the exact sprite name already provided by the parent.
3. Suggested target `.gfx` file.
4. Ready-to-copy sprite definition snippet when useful.
5. Related localisation key, GUI element, event id, focus id, idea id, decision id, achievement id, or super-event slot when known.
6. Any uncertainty about sprite naming or target file placement.
7. Any blocked or needs-review asset.

If the main agent already registered `.gfx` sprites or texture paths before requesting art, the asset subagent must follow those filenames, sprite names, DDS paths, and target sizes exactly. It should only propose names or paths when they were not provided.

The main agent then:

1. Finds the correct existing `.gfx` file if one exists.
2. Follows the existing naming and formatting pattern.
3. Adds the sprite definition.
4. Points the texture file to the final DDS path.
5. Keeps sprite names stable.
6. Updates localisation, GUI, event, focus, idea, or decision references that use the sprite.
7. Updates docs and spreadsheet rows when relevant.

When wiring event-owned sprite-backed art, the texture path should point to the event-scoped folder for that asset category. If an asset must stay root-only, document the engine reason in the handoff or manifest.

Do not create a new `.gfx` file if an existing one is clearly the right place. If a new `.gfx` file is needed, the main agent must name it consistently and document why.

`gfx_handoff.md` is temporary evidence while the event asset workspace is active. Before the event goal is fully complete, copy any durable sprite, path, ownership, and uncertainty facts into the event or plan documentation that remains after cleanup, then delete the event-scoped workspace with the rest of `docs/assets/<event_id>_<event_slug>/`.

## 26. Documentation updates

When generated or sourced assets are part of an event or mechanic, update the relevant docs.

The docs should mention:

- what assets exist
- where the DDS files live
- which `.gfx` file the main agent should use or has used
- which sprite names are used or proposed
- which assets are placeholders, if any
- what still needs final art, if anything

Do not leave the docs describing old or missing assets.

## 27. Contact sheets

When an asset package contains many generated or sourced images, create a contact sheet for review.

Contact sheets are for review only.

Do not use contact sheets as final game assets.

The contact sheet should make it easy to see:

- asset name
- asset type
- selected final version
- rejected alternatives if relevant

## 28. Handling blocked assets

If an asset cannot be created or processed cleanly, mark it as blocked.

Record:

- asset name
- reason blocked
- what was attempted
- what is needed from the user
- whether implementation can continue without it

Do not invent a substitute asset unless the user explicitly approves it.

## 29. Final checklist

Before finishing, confirm:

1. The requirement-to-runtime coverage crosswalk accounts for every accepted spec, manifest-plan, and animation-plan row, with no extra asset counted as a substitute without an explicit accepted design amendment.
2. Every asset uses the correct source mode: `$imagegen` for every flat flag design and for generated symbolic, fictional, alternate-history, or unique report/news/super-event assets; cited internet or user-provided sources for real historical materials; and attributed real source images for every real-person portrait. One-person portraits for grounded real, historical, restored, separatist, regional, indigenous, dynastic, or otherwise plausibly historical identities are sourced only; truly fictional high-chaos or impossible/supernatural identities are the only one-person portrait cases that may be generated. Missing or unsupported classification fails closed.
3. The matching reference folder from section 4 was inspected before generation, sourcing, processing, or wiring.
4. During active work, every generated, sourced, or provided asset has a retained source PNG in the temporary workspace, with durable provenance recorded before cleanup.
5. During active work, every final asset has a processed PNG preview in the temporary workspace, with the final runtime path and relevant QA facts recorded before cleanup.
6. Every final asset has a DDS output.
7. DDS files use 32 bit unsigned BGRB 8.8.8.8.
8. DDS files are moved into the correct mod folders.
9. During active work, a `gfx_handoff.md` exists for every asset that needs a sprite definition, and the main agent has enough information to wire it. Before cleanup, durable wiring facts are copied into permanent docs.
10. During active work, the asset manifest and requirement-to-runtime crosswalk exist and are current. At fully complete state, their durable facts have been promoted and the temporary workspace has been deleted.
11. Internet-sourced assets record source links, source date or estimated date range, license or public domain status if available, and era-fit notes for World War II-era assets.
12. Fictional or non-human portraits generated with `$imagegen` are clearly marked as `fictional_high_chaos` or impossible/supernatural in the manifest, show a memorable internally coherent invented motif, and contain no generic, modern, meme, gore, mocking, stereotyped, or caricatured treatment. Grounded identities never use a generated officeholder; if sourcing fails, the leader portrait is `blocked`.
13. Docs are updated where relevant.
14. The event implementation or parent handoff knows which sprite names to use.
15. No final asset remains only in a temporary folder.
16. Every icon family in section 5.2 was treated as its own asset type, and no UI surface was satisfied by resizing, cropping, recoloring, padding, relabeling, or lightly editing an icon made for another surface.
17. Every animated asset used `chaos-redux-frame-animation`, has real source frames, has a static fallback, has no transform-only final motion, and proves its animation family's purpose and direction or state semantics rather than only its frame count.
18. Every uncompressed one-level BGRA DDS passes the complete legacy-header, exact-length, declared-dimension, actual-alpha, and `.gfx` path checks from section 24.
19. Every real country-leader, commander, operative, and named-officeholder portrait follows the fail-closed sequence of unchanged attributed archival photograph (archival male photograph for male subjects), explicit head-and-shoulders crop created with the exact-pixel Pillow utility and retained JSON equality evidence, source-locked identity-preserving Krea 2 conversion through `hoi4-portrait-pipeline` in the matching HOI4 family, deterministic `156x210` processing, and independent likeness/style/provenance audit by someone other than the producer before DDS conversion or runtime wiring. The audit compares the unchanged photograph, crop, raw Krea candidate, processed candidate, and role-specific references at native and enlarged sizes, keeps identity as a separate non-compensable gate, records subject-ownership evidence and a guarded transfer contract when reused, and rejects genericization, beautification, symmetrization, face substitution, invented hidden detail, unsupported clothing or insignia, weak likeness, and raw or merely resized sourced images; commander textures are full `156x210` portraits, never fabricated `50x67` sources. An illustration cannot serve as the identity master, and an ffmpeg or ImageMagick crop without exact decoded-pixel equality evidence fails this checklist.
20. Every flag has visible imagegen source evidence, and historical flags also have a cited design reference plus a documented geometry/colour/symbol comparison. No final flag is a fabric scene or painterly flag artwork.
21. Every unit visual is classified by domain and surface as equipment/technology art, a large land counter, a land/air/naval map counter, a division-template emblem, or a land/air/naval 3D model package; one pipeline was not resized or relabeled to substitute for another. A 3D package also proves the one-image Meshy input rule, provider lineage, vanilla scale calibration, PDX material mapping, topology repair, required skeletal actions, `.mesh`/`.anim` reimport, hash-aware runtime synchronization, parent-owned wiring, and a live consumer.
22. Every strip, indexed icon family, counter, and multi-state asset preserves the cataloged frame order, frame count, per-frame footprint, and owning definition.
23. When the event goal is fully complete, `docs/assets/<event_id>_<event_slug>/` is absent and no runtime reference points into it. If the event is blocked or incomplete, retain the workspace with a clear blocker instead.
