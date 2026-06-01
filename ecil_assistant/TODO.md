# TODO - ECIL Offline Knowledge Assistant (Accuracy +20% + Project Report)

## Step 1: Add project report text file
- [ ] Create `PROJECT_REPORT.txt` with:
  - pipeline
  - file layout
  - theory/concepts
  - limitations and run instructions

## Step 2: Add measurable evaluation harness
- [ ] Create `eval_engine.py` (or extend existing tests) to compute retrieval metrics from a labeled query set
  - top-1 correctness
  - top-3 hit rate
  - confidence-threshold hit rate
- [ ] Capture baseline metrics before retrieval/ranking changes

## Step 3: Retrieval quality improvements (target ~20% gain)
- [ ] Improve synonym expansion in `engine.py` (use reverse index consistently; remove costly fallback loop)
- [ ] Improve candidate generation (optional phrase tokens / bigram fallback)
- [ ] Improve ranking/boosting to align with token-level overlap

## Step 4: Response selection improvement for project queries
- [ ] Adjust `response_builder.py` to select 1 vs 2 docs based on confidence and query type

## Step 5: Increase scraped data from ecil.co.in
- [ ] Increase `MAX_CRAWL_PAGES` in `config.py`
- [ ] Improve crawler dedupe to reduce near-duplicates
- [ ] Update scraper logic to capture more relevant pages (category discovery / seed URLs)

## Step 6: Run end-to-end checks
- [ ] `python -m pip install -r requirements.txt`
- [ ] `python scraper.py` (refresh KB)
- [ ] `python eval_engine.py` (verify metrics improved vs baseline)
- [ ] Smoke test Flask: `python app.py`

