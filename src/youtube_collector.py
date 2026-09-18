import csv
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from yt_dlp import YoutubeDL

from tracks import SEARCH_QUERIES, TRACKS, TRACK_ALIAS

ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "raw" / "youtube_courses_raw.csv"
PROCESSED_FILE = ROOT / "data" / "processed" / "courses.csv"

FIELDS = [
    "course_id", "title", "provider", "platform", "track", "subtrack",
    "description", "skills", "prerequisites", "difficulty", "duration_hours",
    "language", "is_free", "course_type", "url", "thumbnail", "source",
    "published_date", "collected_at",
]

SKILL_KEYWORDS = {
    # programming
    "python": ["python"], "c++": ["c++"], "java": ["java"],
    "javascript": ["javascript", "js"], "typescript": ["typescript"],
    "c#": ["c#", "csharp"], "go": ["golang", "go programming"],
    "rust": ["rust programming"], "php": ["php"], "kotlin": ["kotlin"],
    "swift": ["swift programming"], "oop": ["object oriented", "oop"],
    "data structures": ["data structures"], "algorithms": ["algorithms"],
    "git": ["git", "github"],
    # web
    "html": ["html"], "css": ["css"], "react": ["react"], "angular": ["angular"],
    "vue": ["vue.js", "vuejs"], "node.js": ["node.js", "nodejs"],
    "django": ["django"], "flask": ["flask"], "asp.net": ["asp.net", ".net"],
    "flutter": ["flutter"], "dart": ["dart"], "android": ["android"],
    "react native": ["react native"],
    # data / AI
    "sql": ["sql"], "pandas": ["pandas"], "numpy": ["numpy"],
    "matplotlib": ["matplotlib"], "power bi": ["power bi"],
    "tableau": ["tableau"], "statistics": ["statistics"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning", "dl"], "tensorflow": ["tensorflow"],
    "pytorch": ["pytorch"], "scikit-learn": ["scikit-learn", "sklearn"],
    "computer vision": ["computer vision", "opencv"], "opencv": ["opencv"],
    "nlp": ["nlp", "natural language processing"],
    "generative ai": ["generative ai", "genai"], "llm": ["llm", "large language model"],
    # infra
    "aws": ["aws", "amazon web services"], "azure": ["azure"],
    "gcp": ["google cloud", "gcp"], "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"], "linux": ["linux"],
    # security / other
    "cybersecurity": ["cybersecurity", "cyber security"],
    "ethical hacking": ["ethical hacking"], "networking": ["computer networks", "networking"],
    "unity": ["unity"], "unreal engine": ["unreal engine"],
    "blockchain": ["blockchain"], "iot": ["internet of things", "iot"],
    "robotics": ["robotics"], "ui ux": ["ui/ux", "ui ux", "user experience", "user interface"],
}

PREREQ_PATTERNS = [
    r"prerequisites?\s*[:\-]?\s*([^\.\n]+)",
    r"you (?:should|need to|must) know\s+([^\.\n]+)",
    r"before (?:taking|starting|learning)\s+([^\.\n]+)",
]

EXCLUDE_TERMS = [
    "paid course", "course preview", "trailer", "promotional", "promo",
    "buy my course", "sponsor", "giveaway",
]

EDUCATIONAL_TERMS = [
    "course", "tutorial", "bootcamp", "learn", "lesson", "training",
    "beginner", "complete", "from scratch", "class", "roadmap",
]


def parse_timestamp(value):
    if not value:
        return ""
    value = str(value)
    if re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value[:10]


def detect_skills(text: str):
    text = (text or "").lower()
    found = []
    for skill, patterns in SKILL_KEYWORDS.items():
        if any(p.lower() in text for p in patterns):
            found.append(skill)
    return sorted(found)


def detect_prerequisites(text: str):
    text = re.sub(r"\s+", " ", text or "").strip()
    found = []
    for pattern in PREREQ_PATTERNS:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            cleaned = match.strip(" :-;,.\"")
            if 2 <= len(cleaned) <= 220:
                found.append(cleaned)
    return list(dict.fromkeys(found))


def detect_difficulty(text: str):
    t = (text or "").lower()
    if any(x in t for x in ["advanced", "expert", "senior"]):
        return "Advanced"
    if any(x in t for x in ["intermediate", "mid level", "mid-level"]):
        return "Intermediate"
    if any(x in t for x in ["beginner", "beginners", "from scratch", "zero to hero"]):
        return "Beginner"
    return "Unknown"


def detect_course_type(title: str):
    t = (title or "").lower()
    if any(x in t for x in ["full course", "complete course", "crash course", "bootcamp"]):
        return "Full Course"
    if "playlist" in t:
        return "Playlist"
    if "course" in t:
        return "Course"
    if any(x in t for x in ["roadmap", "guide"]):
        return "Guide"
    return "Tutorial"


def likely_educational(title: str, description: str):
    text = f"{title} {description}".lower()
    if any(term in text for term in EXCLUDE_TERMS):
        return False
    return any(term in text for term in EDUCATIONAL_TERMS)


def make_ydl():
    return YoutubeDL({
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
        "geo_bypass": True,
    })


def search_youtube(query: str, max_results: int, ydl: YoutubeDL):
    """Search YouTube without an API key using yt-dlp's ytsearch extractor."""
    search_url = f"ytsearch{max_results}:{query}"
    info = ydl.extract_info(search_url, download=False)
    if not info:
        return []
    return [entry for entry in (info.get("entries") or []) if entry]


def enrich_video(url: str, ydl: YoutubeDL):
    """Fetch public page metadata for one video without downloading media."""
    try:
        return ydl.extract_info(url, download=False) or {}
    except Exception as exc:
        print(f"      metadata warning: {exc}")
        return {}


def build_row(item, track, subtrack, details=None):
    details = details or item
    video_id = item.get("id") or details.get("id")
    if not video_id:
        return None

    title = (details.get("title") or item.get("title") or "").strip()
    description = (details.get("description") or item.get("description") or "").strip()
    channel = (
        details.get("channel")
        or details.get("uploader")
        or item.get("channel")
        or item.get("uploader")
        or ""
    )
    url = details.get("webpage_url") or item.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"
    duration = details.get("duration")

    return {
        "course_id": video_id,
        "title": re.sub(r"\s+", " ", title),
        "provider": channel,
        "platform": "YouTube",
        "track": track,
        "subtrack": subtrack,
        "description": description,
        "skills": "|".join(detect_skills(f"{title} {description}")),
        "prerequisites": "|".join(detect_prerequisites(description)),
        "difficulty": detect_difficulty(f"{title} {description}"),
        "duration_hours": round(float(duration) / 3600, 2) if duration else None,
        "language": details.get("language") or details.get("audio_language") or "Unknown",
        "is_free": True,
        "course_type": detect_course_type(title),
        "url": url,
        "thumbnail": details.get("thumbnail") or item.get("thumbnail") or "",
        "source": "YouTube via yt-dlp",
        "published_date": parse_timestamp(details.get("upload_date") or item.get("upload_date")),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def save_csv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def collect(max_results_per_query: int = 20, enrich: bool = True):
    collected = {}
    per_track_count = {}

    with make_ydl() as ydl:
        total_tracks = len(TRACKS)

        for idx, (track, subtrack) in enumerate(TRACKS, start=1):
            alias = TRACK_ALIAS.get(track, track)
            queries = SEARCH_QUERIES.get(track, [f"{alias} free full course tutorial"])
            print(f"[{idx}/{total_tracks}] {track}")
            track_added = 0

            for query in queries:
                print(f"    search: {query}")
                try:
                    items = search_youtube(query, max_results_per_query, ydl)
                except Exception as exc:
                    print(f"      ERROR: {exc}")
                    continue

                for item in items:
                    video_id = item.get("id")
                    if not video_id or video_id in collected:
                        continue

                    url = item.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"
                    details = enrich_video(url, ydl) if enrich else item
                    row = build_row(item, track, subtrack, details)
                    if not row:
                        continue

                    if likely_educational(row["title"], row["description"]):
                        collected[video_id] = row
                        track_added += 1

                    # Keep a modest request pace; YouTube changes can make aggressive
                    # automated collection less reliable.
                    time.sleep(0.15)

            per_track_count[track] = track_added
            print(f"    kept: {track_added}")

    rows = list(collected.values())
    save_csv(rows, RAW_FILE)
    save_csv(rows, PROCESSED_FILE)

    print("\nDone.")
    print(f"Total unique educational videos: {len(rows)}")
    print(f"Raw: {RAW_FILE}")
    print(f"Processed: {PROCESSED_FILE}")
    print("\nPer-track counts:")
    for track, count in per_track_count.items():
        print(f"  {track}: {count}")


if __name__ == "__main__":
    collect(max_results_per_query=20, enrich=True)
