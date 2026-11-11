# Garmin Swim Analytics

A local-first Python project for measuring pool-swimming progress from Garmin Swim 2 workouts, starting with freestyle and breaststroke in a 25 m pool. The starter includes offline FIT discovery and archival, a Garmin connector interface, and a device-independent stroke-aware quality module. The [project handoff](docs/handoff.md) defines the remaining analytics and dashboard work.

## Set up locally

Use Python 3.12 or newer on macOS or Linux.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[fit]'
swim-analytics --help
```

## Download directly from Garmin

Create a Personal API key in Garmin Connect Web and put it in the local `.env` at the project root. Use the following format without quotes and set owner-only permissions with `chmod 600 .env`.

```dotenv
GARMIN_PERSONAL_API_KEY=
```

From the project root, run:

```sh
swim-analytics sync-garmin
```

The command walks the available pool-swim history and downloads only activity IDs missing from the private archive. Each successful download is committed independently, so you can rerun the command after an interruption. Each run checks all available pages to catch older activities uploaded later. Use a separate archive for each Garmin account.

For a single session, add `--activity-id 123456789` with the numeric ID from the Garmin Connect activity URL. This explicitly requests the download again. The environment variable takes precedence over `.env`. If neither provides a key, the interactive command prompts for it. [Garmin Personal API setup](https://developer.garmin.com/gc-developer-program/personal/personal-api/), [API endpoints](https://developer.garmin.com/gc-developer-program/personal/swagger-docs/)

Install third-party adapters separately and select them with `sync-garmin --connector NAME`.

## Import an existing FIT offline

In Garmin Connect on the web, open a pool-swimming activity and select **Export Original**. Extract the FIT file locally if the download is an archive. Then run:

```sh
swim-analytics import-fit /path/to/private/activity.fit
```

The command validates the pool-swim session, prints FIT message counts and saves the original bytes to a private local archive. Reimporting identical bytes adds no second raw copy. Multiple inputs are processed in order and each successful import is committed independently. No Garmin login is needed for offline import. [Garmin export instructions](https://support.garmin.com/en-US/?faq=W1TvTPW8JZ6LfJSfK512Q8)

## See your data

After importing, run `swim-analytics analyze` from the project root. It reads the private archive without calling Garmin or exporting a file. The overview shows session count, Garmin-reported monthly volume, active lengths, rests, and mean and median pace for freestyle and breaststroke grouped by pool size. Month uses the FIT session timestamp. Pace uses timer seconds from recorded active lengths and still includes statistical outliers.

Run `swim-analytics progress` for monthly medians of time per length and SWOLF for freestyle and breaststroke in a 25 m pool. Use `--pool-m` for another recorded pool size or `--raw` to include flagged lengths. SWOLF is active timer seconds plus recorded strokes. Lengths with a missing or zero stroke count still contribute to the time metric. The report shows the sample count for each metric.

Use `swim-analytics progress --distance-m 100` to compare pace from complete, non-overlapping blocks within recorded intervals. Blocks require consecutive active lengths of one recorded stroke, and a rest, stroke change or missing length breaks the sequence. The report includes monthly and last-30-day medians and sample sizes. Compare the same distance and similar effort when interpreting pace. Stroke labels come from the watch.

The progress view puts time outliers in quarantine when the recorded interval has enough comparable lengths of the same stroke. This initial filter uses the existing MAD thresholds, keeps suspect lengths in the summary, and leaves intervals with sparse data or no reliable membership unfiltered. It never modifies the original FIT. Monthly changes can reflect workout mix or intensity. [Garmin Swim terminology](https://support.garmin.com/en-US/?faq=z7QHGpBDDH7wDJsSKjxRi9)

## Confirm strokes from your notes

Inspect the recorded FIT intervals for a Garmin activity, then map one or more intervals to the stroke and distance you actually swam. Interval numbers are the one-based FIT lap numbers shown by `session`. A range such as `5-7` can cover multiple recorded intervals in one annotated block.

```sh
swim-analytics session --activity-id 123456789
swim-analytics annotate --activity-id 123456789 \
  --block 3:crol:100 --block 5-7:pecho:200 --note "From my poolside notes"
swim-analytics progress --confirmed
swim-analytics progress --confirmed --distance-m 100
```

In the Garmin Connect activity note, list the distance and stroke in workout order on one line. Other lines may contain free text.

```text
SWIM: 100 crol, 200 pecho
```

List the complete workout. Consecutive entries of the same stroke are combined. The importer uses the order and active lengths in the recorded intervals, and allows a difference of one length per block when finding the best match. It requires a unique best match. If the workout cannot be matched or there is a tie, use the explicit format (for example, `SWIM: 3:crol:100, 5-7:pecho:200`).

After saving the note in Garmin Connect and syncing the original FIT, import the mapping. Repeat this command after editing the note. It reads the activity description through the Personal API and saves only the `SWIM:` line locally. [Garmin Personal API endpoints](https://developer.garmin.com/gc-developer-program/personal/swagger-docs/)

```sh
swim-analytics annotate --activity-id 123456789 --from-garmin
```

Each annotation saves a new local revision with the complete mapping for that activity. To change or add a block, include any previous blocks you want to keep. The original FIT is preserved. Confirmed reports use only mapped blocks whose recorded active distance agrees with the annotation. A distance mismatch stays saved for review, without guessing which length to add or remove. Free-text notes entered with `--note` are saved locally. Reports without `--confirmed` display Garmin's detected labels.

## Project documentation

- [Handoff and remaining milestones](docs/handoff.md)
- [Architecture and FIT discovery](docs/architecture.md)
- [Quality and progress methodology](docs/quality.md)
- [Privacy and release checklist](docs/privacy.md)
- [Contributing](CONTRIBUTING.md) and [reporting security issues](SECURITY.md)

## License

The project's code and documentation are available under the [MIT License](LICENSE). The [public repository](https://github.com/aletto/garmin-swim-analytics) is hosted on GitHub.
