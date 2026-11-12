# AWN YouTube Automation — LATE Gaming v1.1

Free-first GitHub Actions project for creating one original English gaming Shorts video per day.
No VPS and no always-on phone required. GitHub Actions runs the job on a schedule.

## What v1.1 does
- Runs daily at 20:00 Japan time (11:00 UTC).
- Selects one original gaming tip/fact from `content/topics.json`.
- Generates English narration with the free `edge-tts` service.
- Creates a vertical 1080x1920 MP4 with original graphic slides and narration.
- Splits long body text into multiple slides at sentence boundaries.
- Uploads the MP4 as a GitHub Actions artifact for 7 days.
- Can be run manually from the Actions tab.

## Important limitations
- This is scheduled execution, not an always-on n8n server. GitHub may delay scheduled jobs.
- Free services have limits and can change. `edge-tts` is an unofficial client to Microsoft's online TTS service; availability is not guaranteed.
- v1.1 does NOT automatically publish to YouTube. Download the artifact and upload it using YouTube Studio.
- The topic list is a starter set. Review facts and wording before publishing. Expand `content/topics.json` with original, accurate material.
- Public repositories can have scheduled workflows disabled after 60 days without repository activity. Keep the repo active and check Actions regularly.

## Repository structure