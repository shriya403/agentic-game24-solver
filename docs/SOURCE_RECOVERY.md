# Source recovery ledger

The submitted text identified a Windows Desktop project and the repository `shriya403/agentic-game24-solver`. The Linux workspace initially contained the instruction attachment and no project files. A recursive inventory preceded source edits. The recovering checkout used the following publicly reachable revisions.

| Revision | What it supplied |
|---|---|
| `02a6e7d69e5d1cdc614ca04e46e686b907617bb7` | Original TA1 application, linear and beam-search agents, exact engine/validator, experiment, eight tests, CSV, reports and original deck |
| `ab0cc7b21934fae2b4ec0747c566c12c22194b60` | Earlier TA2 extension, including the 68-line Streamlit client recovered as `ta2/prototype/app_ta2.py` |
| `b9fbe00f854f73abbc636a4fd18ffb24e7748741` | Later jury branch with the expanded 135-line TA2 client, SQLite, Chroma, LangGraph roles, acceptance runner, both original suites and saved Windows evidence |

A complete Git bundle of the remote refs was created and verified before changes. All integration work took place on a separate local enhancement branch. The remote's jury tip added files to the pinned TA1 tree without editing any of its 23 tracked blobs. The frozen snapshot contains all 23 files extracted from Git objects, including records and the binary deck. Shared runtime imports still resolve through the historical top-level `game24` package. Historical root entry points remain available. The integrated root uses its own README and pinned runtime requirements. The original copies of both are in `ta1/`.

The earlier TA2 client has 68 physical lines and blob ID `7c9ec139fda9259c59bce0dcd03ad771f284cbcc`. Its dependencies occupy separate modules. This count describes the UI file. The full TA2 system is larger. A distinct local assessment prototype or dashboard requires the Windows archive to identify.

## Line endings

For every pinned path, the audit computes SHA-1 over the bytes of `blob <byte length>\0` followed by file content, following the Git object format. For declared text files it also tries CRLF-to-LF normalization. A match only after normalization is reported separately. Binary files always use their raw bytes. Missing files and genuine content differences produce a nonzero exit status. Comparison is read-only.

```bat
py -3.12 scripts\audit_ta1.py ta1
py -3.12 scripts\audit_ta1.py "C:\Users\shind\Desktop\Game24_TA2_Jury"
```

The second argument must point to the folder containing the original TA1 `app.py` and `game24` package. A unified project may place them in a subdirectory. The pinned path list and pre-enhancement comparison are in `docs/audit/`. All 23 recovered files matched exactly. A regression test introduced CRLFs into a temporary copy, altered a separate text file and binary and omitted a source. The four statuses were distinguished. The cause of a past mismatch on the student's computer remains open.

## Windows-local material

The supplied Windows path was `C:\Users\shind\Desktop\Game24_Windows_For_Codex.zip`. The archive was supplied as a path only. The student then selected the repository as the delivery source. Unseen local edits and personal records remain outside the recovered source. The integrated repository build subsequently passed its launcher and suites on a native Windows CI runner. The archived Windows benchmark in Git is historical evidence from the earlier project. Fresh Linux traces use new stores.
