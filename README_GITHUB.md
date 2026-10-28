# GitHub publishing checklist

- This source archive excludes original/translated item catalogs, game tables, user saves and backups. It includes the documented original icon set and application/evidence screenshots.
- Never commit `catalog_builtin.json`, `catalog_english.json`, `t_item*.tbl`, user-specific PNG caches, `saveXXX.dat` or private backups. The intentional bundled icon set is `icons/original`, with hashes and provenance in `sources.json`.
- Users must supply source tables from their own legally installed copy; source releases read them locally.
- Do not imply affiliation with Nihon Falcom, NIS America or Steam. The code license does not grant any rights to game content.
- Review runtime dependencies and their licenses when publishing compiled builds.


This version includes `.github/workflows/tests.yml` and a Windows build workflow.
The workflows must be run on GitHub before claiming CI or EXE compatibility.
