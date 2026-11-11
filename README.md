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

The progress view puts time outliers in quarantine when the recorded interval has enough comparable lengths of the same stroke. This initial filter uses the existing MAD thresholds, keeps suspect lengths in the summary, and leaves intervals with sparse data or no reliable membership unfiltered. It never modifies the original FIT. Monthly changes can reflect workout mix or intensity. [Garmin Swim terminology](https://support.garmin.com/en-US/?faq=z7QHGpBDDH7wDJsSKjxRi9)

## Project documentation

- [Handoff and remaining milestones](docs/handoff.md)
- [Architecture and FIT discovery](docs/architecture.md)
- [Quality and progress methodology](docs/quality.md)
- [Privacy and release checklist](docs/privacy.md)
- [Contributing](CONTRIBUTING.md) and [reporting security issues](SECURITY.md)

## License

The project's code and documentation are available under the [MIT License](LICENSE). The [public repository](https://github.com/aletto/garmin-swim-analytics) is hosted on GitHub.
