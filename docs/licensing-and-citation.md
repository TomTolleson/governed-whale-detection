# Data citation, attribution and licence terms (as found on the source)

| | |
|---|---|
| Written | 2026-11-16 by claude-code, for the owner's public-readiness check. **Nothing has been published.** The repository stays private |
| Method | Read directly from the source, with nothing filled in from general knowledge. Sources: (1) the SanctSound README in the bucket (`sanctsound_README.pdf`, SHA-256 `76671dd8…5c177`, git-ignored); (2) the ISO 19115 metadata XML of all 36 `humpbackwhale_1d` products used (sb01, sb02, sb03, deployments 01-12) and the sb02_01 deployment metadata JSON, fetched anonymously from `https://storage.googleapis.com/noaa-passive-bioacoustic/sanctsound/` on 2026-11-16; (3) the two NCEI landing pages that the DOIs below resolve to (data.noaa.gov metaview), read 2026-11-16 |

## What the source states

**Licence: none stated.**
- No CC0, Creative Commons, public-domain or other licence statement appears in the README.
- None appears in any of the 36 product metadata records, in the deployment metadata JSON, or on either
  NCEI landing page.
- The metadata codes its access and use constraints as `otherRestrictions`.
- The licence question was emailed to NCEI (`pad.info@noaa.gov`) on 2026-11-09. **No reply is recorded.**

**Citation required.** The metadata's `useLimitation` reads "Cite as: …".

The raw audio, as given in the README, the deployment JSON and the NCEI page:
> NOAA Office of National Marine Sanctuaries and U.S Navy. 2020. SanctSound Raw Passive Acoustic Data.
> NOAA National Centers for Environmental Information. https://doi.org/10.25921/saca-sp25 [access date]

Each humpback label product has **its own DOI and citation**, of the form:
> NOAA Office of National Marine Sanctuaries and U.S Navy. 2021. Humpback Whale Sound Production Recorded at
> SanctSound Site SB0X_NN, SanctSound Data Products. NOAA National Centers for Environmental Information.
> https://doi.org/10.25921/… [access date].

On the product citations' year: the citation text says 2021, but the NCEI page for sb02_01 shows a
publication date of 2023-06-15. The citation text is reproduced as printed.

**Constraints:** the same text appears in all 36 product records, and on both NCEI pages.
- *Distribution liability:* NOAA and NCEI make no warranty, express or implied, and accept no liability for
  errors or omissions. They certify only that a copy is authentic.
- *Use liability:* there is no warranty of accuracy, reliability or completeness. Users must decide whether
  the data is usable, and are responsible for any use outside its intended purpose.
- The NCEI page's purpose statement says the data is available to the public for a wide range of uses,
  including scientific research and analysis. Electronic downloads are usually free.

**Attribution and endorsement:**
- The source states **no attribution requirement beyond the citation**, and **no statement about
  endorsement**.
- The NCEI pages' acknowledgments say the project received funding from the U.S. Navy. The README describes
  SanctSound as a NOAA and U.S. Navy collaboration.
- *Not found, and therefore not claimed:* any source statement that permits or forbids implying NOAA
  endorsement. The no-endorsement wording in this repository is the project's own choice.

**Model terms** (from `docs/model_notes.md`; the Kaggle page, read by the owner on 2026-11-09): Google
`multispecies-whale` is Apache 2.0, with Terms of Use asking for use in wildlife conservation, research or
education, not for profit.

## Humpback label products used (36), each to be cited

| Deployment | DOI |
|---|---|
| sb01_01 | https://doi.org/10.25921/34s0-d728 |
| sb01_02 | https://doi.org/10.25921/031d-yg11 |
| sb01_03 | https://doi.org/10.25921/smbv-jy13 |
| sb01_04 | https://doi.org/10.25921/582k-4c86 |
| sb01_05 | https://doi.org/10.25921/j65a-9k58 |
| sb01_06 | https://doi.org/10.25921/b44a-gf17 |
| sb01_07 | https://doi.org/10.25921/q812-0b80 |
| sb01_08 | https://doi.org/10.25921/gj0x-vj92 |
| sb01_09 | https://doi.org/10.25921/2745-1n07 |
| sb01_10 | https://doi.org/10.25921/12mx-er78 |
| sb01_11 | https://doi.org/10.25921/14pp-9d51 |
| sb01_12 | https://doi.org/10.25921/9zhe-se70 |
| sb02_01 | https://doi.org/10.25921/3hf1-jk31 |
| sb02_02 | https://doi.org/10.25921/jzda-0t10 |
| sb02_03 | https://doi.org/10.25921/4s42-t075 |
| sb02_04 | https://doi.org/10.25921/m3as-x078 |
| sb02_05 | https://doi.org/10.25921/4401-dd56 |
| sb02_06 | https://doi.org/10.25921/s8yq-mn89 |
| sb02_07 | https://doi.org/10.25921/mgms-1a35 |
| sb02_08 | https://doi.org/10.25921/0sq0-c417 |
| sb02_09 | https://doi.org/10.25921/1dbv-qg42 |
| sb02_10 | https://doi.org/10.25921/4bdh-jn58 |
| sb02_11 | https://doi.org/10.25921/nz8m-4451 |
| sb02_12 | https://doi.org/10.25921/34pc-z289 |
| sb03_01 | https://doi.org/10.25921/54er-1b93 |
| sb03_02 | https://doi.org/10.25921/akgp-8228 |
| sb03_03 | https://doi.org/10.25921/c6n2-4s25 |
| sb03_04 | https://doi.org/10.25921/4er4-2e90 |
| sb03_05 | https://doi.org/10.25921/hddv-5d43 |
| sb03_06 | https://doi.org/10.25921/xbbq-xp09 |
| sb03_07 | https://doi.org/10.25921/884g-vz82 |
| sb03_08 | https://doi.org/10.25921/aa7j-gp09 |
| sb03_09 | https://doi.org/10.25921/fkxj-d643 |
| sb03_10 | https://doi.org/10.25921/n9pc-dn32 |
| sb03_11 | https://doi.org/10.25921/q3x6-ga83 |
| sb03_12 | https://doi.org/10.25921/26yy-w670 |

## Proposed licence for the project's own code *(proposal; owner to decide; no LICENSE file added)*

**Proposal: Apache License 2.0** for the code in `src/`, `tools/` and `tests/`.

Why:
- It matches the licence of the model the code depends on.
- It includes an explicit patent grant.
- It requires a NOTICE and a record of changes, which suits an audit-focused project.

Other options:
- **MIT**: shorter, with no patent grant.
- **BSD-3-Clause**: has a non-endorsement clause, which would back up the no-NOAA-endorsement statement.

Points for the owner:
- A code licence does **not** relicense the SanctSound data, the labels or the Google model. Those keep their
  own terms, above.
- The README's "non-commercial research" wording describes how the project uses the model under Google's
  terms. If the code were licensed under Apache 2.0, MIT or BSD, others could use the **code** commercially.
  If the owner wants to restrict that, a non-OSI licence such as PolyForm Noncommercial would be needed
  instead.
- **Documentation and results** (`docs/`) could take CC BY 4.0, if the owner wants a separate licence for them.
- **Derived data** (the per-day features and scores in git-ignored `data/`): no licence should be chosen while
  the source licence is unconfirmed (NCEI email of 2026-11-09, no reply recorded).
