# Assets

| File | Use | Notes |
|---|---|---|
| `guara-mascot.png` | README header, talks, slides | Two domains in one image: the guará fox flying a multirotor (thread A, PX4 + ROS 2) and the same fox operating a satellite (threads B and C, F´). |
| `guara-mascot-air.png` | Air-thread material only | The original single-domain mascot, kept for documents that are strictly about the PX4 work. |

## Sizes, and where the full-resolution originals are

Both files are web-sized: the hero renders at 460 px in the README, so it is stored at 920 px
for a 2× display, quantised to a 256-colour palette with dithering. That took the pair from
2.3 MB to 227 KB with no visible loss — a README visitor was pulling 1.8 MB before the first
sentence.

The full-resolution originals (1672 × 941 and 720 × 720, full RGBA) are in the git history at
`1acf292` and earlier:

```bash
git show 1acf292:docs/assets/guara-mascot.png > guara-mascot-full.png
```

Use those for print, talks and slides; use the files here for anything rendered on the web.

Both images are illustrations commissioned for this project, released with the repository under
the Apache License, Version 2.0 (see `NOTICE`). They depict a guará
(*Chrysocyon brachyurus*, the maned wolf), the animal the project is named after; they are
decoration, not a claim about any hardware, mission or endorsement.
