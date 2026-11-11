# Quality and progress

## Implemented quality rule

Compare active, comparable lengths within the same stroke, pool length and workout context. Freestyle and breaststroke have separate distributions. The caller selects reference lengths and excludes the target. A future normalization layer classifies rest, drill, mixed and unknown segments separately before computing performance metrics.

For timer seconds, use the median and median absolute deviation (MAD). The signed score is `0.6745 * (seconds - median) / MAD`. The default absolute thresholds are 2.5 for suspect and 3.5 for quarantine, applied strictly above each threshold. Eight usable reference lengths are required by default. Sparse references carry an explicit insufficient-reference reason. With zero MAD, a deviation is suspect with no numeric score. Use `Rules` to change these defaults. A quarantine flag excludes an observation from clean metrics once the quality rule is integrated, while preserving it for review and raw metrics.

## Quality integration requirements

- Build past-only historical and workout-local baselines from comparable sets. Store both scores and their sample sizes. Account for warm-up, recovery, sprint and training intensity where known.
- Check lap and session distances, elapsed/timer totals, active/idle sequences, adjacent lengths, stroke counts and SWOLF. Track hypotheses for missed turns, merged or extra lengths, rest counted as swimming, misclassification and implausible speed.
- Keep statistical deviation, suspected device error and plausible performance variation as separate evidence. A 50-second length in a 25 m pool could be a slow length or a missed turn. Record the ambiguity and await review before changing distance.
- Support `VALID`, `SUSPECT`, `QUARANTINED`, `MANUALLY_CORRECTED` and `EXCLUDED`. Review actions append a reasoned version without modifying raw data. Show counts, exclusion share, and the effect of cleaning on pace and efficiency.

## Progress analytics requirements

Group comparisons by stroke and comparable distance, interval type and effort where known. Report the last 30 days, the preceding 30 days, the last 90 days and all available history using explicit date boundaries. Include robust rolling trends and denominators for each measure.

| Measure | Outputs |
| --- | --- |
| Speed | Mean and median seconds per 100 m, distribution, variability and rolling pace at comparable distance |
| Efficiency | SWOLF, strokes per length, stroke rate and pace relative to stroke count |
| Endurance | Sustained pace over comparable continuous sets (e.g. 400, 800 and 1,000 m), longest continuous set and pace deterioration |
| Cardiovascular | Average/max HR and pace versus HR at comparable effort, with wrist-HR coverage and caveats |
| Consistency | Sessions, training frequency, workout distance and weekly/monthly volume |

Report speed, efficiency and endurance independently. Show raw and cleaned comparisons with coverage, sample sizes and changes in workout composition. Separate device-reported session volume from curated observed length totals.
