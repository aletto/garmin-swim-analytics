# Architecture

Input adapters yield original FIT bytes and an optional provider activity ID through `ActivitySource`. Both adapters use the same FIT validation and archive path. The SQLite archive stores each payload once by SHA-256 and records its source, external ID and digest. Different payloads for the same provider ID are retained as versions. A batch can replay safely after interruption. Downstream normalization and query storage are planned as Parquet and DuckDB.

## Garmin provider contract

Register a zero-argument factory in the provider package:

```toml
[project.entry-points."swim_analytics.garmin"]
personal = "my_swim_provider:make_source"
```

`make_source()` returns an object with `activities()` yielding `FitActivity(payload, external_id)` for pool swims. Install the provider in the same environment and run `swim-analytics sync-garmin --connector personal`. The provider is executable local code and owns authentication, pagination and download. Give each account a distinct local archive when using the same adapter. Incremental providers must advance checkpoints only after a successful ingest, or deliberately overlap and replay from a safe earlier point.

## FIT field discovery

The scaffold uses Garmin's decoder and inventories session, lap, length and record message counts. It accepts a decoded session tagged swimming and lap swimming. The mapping below is a discovery checklist. Verify each field, unit, missing-value convention and grouping rule against private exports before normalizing. [Garmin FIT activity decoding guide](https://developer.garmin.com/fit/articles/cookbook/decoding_activity_files.html), [Garmin Python FIT SDK](https://github.com/garmin/fit-python-sdk)

| Entity | Inspect in FIT or provider | Preserve |
| --- | --- | --- |
| Activity | Session start, pool length and unit, total distance, timer/elapsed duration, HR summaries | Source ID when supplied, raw digest, session key and original values |
| Interval | Lap indices, times, distances, and length membership | Recorded set boundaries and evidence for rest or drill |
| Length | Active/idle length type, swim stroke, timer/elapsed time, strokes and index | Measured values and explicit missing fields |
| Samples | Timestamped record HR or other samples when present | Sampling coverage and timestamp alignment |
| Quality assessment | Rule version, reference, score and evidence | Status, reason, sample size and observed value |
| Correction | Length key, prior version, edited fields and reason | Append-only audit history and restoration |

Keep elapsed time, timer time and rest distinct. Verify any recorded SWOLF and stroke rate fields before using them. Document derived SWOLF or stroke rate separately, calculate them only with valid inputs, and never invent per-length heart rate from a session average. Normalize yards to meters while preserving original units. Validate multisession grouping before publishing aggregates.
