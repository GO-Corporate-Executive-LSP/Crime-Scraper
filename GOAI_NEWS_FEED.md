# GÖ.AI metadata feed contract

The existing scraper remains the collection engine. Its completed daily/manual
run now exports `metadata/news-metadata.json` for the GÖ.AI intake reader. The
workflow commits only that small metadata snapshot, not new article bodies,
identity fields, raw CSV changes or logs. Existing historical files are not
deleted by this change.

Only rows captured inside this workflow's current collection window qualify.
The workflow explicitly sets TZ=UTC before the legacy scraper writes its naive
`date_scraped`. Old accumulated rows do not become fresh just because a new
snapshot is generated. A run with no qualifying rows emits `no_fresh_candidates`.
If the workflow fails before export, the app must reject the last snapshot once
stale. The exporter does not prove collection succeeded against every source.

Schema 1 includes repository/revision, collection start/generation times, UTC
clock declaration and at most 500 article metadata entries / 512 KiB. Each entry
has canonical HTTPS source URL, bounded headline and location mentions, captured
time, publisher hostname and URL hash. Publication date remains null: the old
NLP `publication_date` can be extracted from body text and is not a verified
publisher timestamp. Neither capture nor generation time establishes incident
recency. No precise incident location, crime score or verification claim exists.
Headlines/mentions may include public names; this is not anonymized data.

The adapter in `goai-website` is the destination-scoped reader. It validates
freshness, limits and source/date semantics and passes metadata to the same
Gemini/Claude intake as other news providers. It does not download the 104 MB CSV
in the journey path. Geographic mentions and stories remain unverified.

Tests: `python -m unittest discover -s tests -p 'test_export_news_metadata.py'`.

Activation: merge this producer change, ensure Actions is enabled for the fork,
then run the existing `Daily Crime Data Scraper` workflow manually. Inspect the
committed snapshot status/count before accepting app-side live ingestion. The
existing daily schedule is retained, not proof it has run. There are no claimed
live collection receipts in this PR, and historical data is not relabeled fresh.
