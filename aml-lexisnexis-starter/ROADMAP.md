# Roadmap â€” Name Screening (Phase 1.5)

## âœ… Current Status
- Core pipeline: normalization â†’ KB â†’ screen()
- ISO20022 preprocessing audit working
- Git hygiene: large archives removed; entities.csv via Git LFS
- Transaction Monitoring: **on hold**

---

## í·© Next 10 Name Screening Enhancements
1. **Normalization hardening**
   - ICU transliteration; zero-width / fancy whitespace handling.
   - Golden tests for mixed-script names.
2. **Alias expansion coverage**
   - Measure per-entity alias completeness; CI threshold <80% flagged.
3. **Text feature calibration**
   - Tune Levenshtein, Jaroâ€“Winkler, token overlap weights; record Precision@k, FPR.
4. **Context feature weighting**
   - DOB, country canonicalization, ID-tail; YAML-driven weights.
5. **Embeddings (optional)**
   - Add multilingual model via `AML_EMB_MODEL`; measure latency/recall vs FTS5.
6. **FAISS recall path (optional)**
   - Build index + top-k recall tests; ensure integrity at load.
7. **Decision thresholds**
   - Tune `block_threshold` / `clear_threshold` in `NameMatchConfig`; baseline ops metrics.
8. **Monitoring & Explainability**
   - Feature contribution dump; SHAP plots for top-k hits.
9. **KB update & audit**
   - Diff new vs existing KB; dry-run; signed JSONL snapshot.
10. **CI/CD gates**
    - Lint, smoke `screen()` run, and test dataset; README badge.

---

## í²¤ Parked â€” Transaction Monitoring (Phase 2)
- Ingest & feature store scaffolding
- Model baselines (IForest/Autoencoder/Graph rules)
- Alert explanation pipeline
- Performance / cost benchmarks

---

## í³ˆ Guiding Principles
- Small, composable modules (sanctions/screening split)
- SQLite first; FAISS optional
- LFS for large data; lightweight CI
