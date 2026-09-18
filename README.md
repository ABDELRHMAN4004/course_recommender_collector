# Free Technology Course Collector — No YouTube API

This collector is the YouTube course/resource collection component for the Computer Science Student Guide / Recommendation System.

## Important

This version **does not use the YouTube Data API and does not require an API key**.

It uses `yt-dlp`'s YouTube search extractor (`ytsearch...`) to search public YouTube results, then reads public metadata without downloading the media. `yt-dlp` documents the `ytsearch` prefix and supports Python embedding through `YoutubeDL`. It is an unofficial extraction approach, so YouTube changes can occasionally break or limit it; keep request rates reasonable and update `yt-dlp` when needed.

## What it collects

For each educational result:

- course/video title
- provider/channel
- platform
- technology track
- category/subtrack
- description
- heuristic skills
- heuristic prerequisites
- heuristic difficulty
- duration in hours
- language when available
- free/public flag
- course type
- URL
- thumbnail
- source
- publish date
- collection timestamp

It intentionally does **not** collect or calculate ratings.

## Output

```text
data/
├── raw/
│   └── youtube_courses_raw.csv
└── processed/
    └── courses.csv
```

## Setup

PowerShell:

```powershell
cd D:\Recommendation-System-Courses\course_recommender_collector
python -m pip install -r requirements.txt
```

## Run

```powershell
python src/youtube_collector.py
```

The first run searches all configured technology tracks using multiple queries per track. The script deduplicates by YouTube video ID and writes CSV files.

## Why yt-dlp here?

We do not want API keys or YouTube Data API quota for this MVP. `yt-dlp` supports YouTube search with the `ytsearch` prefix and can be embedded in Python. This lets the project collect public search results without setting up Google Cloud credentials.

## Notes

- `is_free=True` means the YouTube item is publicly watchable; it is not a claim that every external resource linked inside the description is free.
- Skills, prerequisites, and difficulty are heuristic fields and should be validated/cleaned before becoming training features.
- Search results can contain channels or other non-course content; the collector applies educational keyword filtering and removes obvious promotional results.
- The collector never downloads the course videos.
- If YouTube starts requiring additional extraction components for a particular environment, update `yt-dlp` and review its current extractor requirements.
