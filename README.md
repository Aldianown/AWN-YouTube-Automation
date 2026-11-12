# AWN YouTube Automation — LATE Gaming v1.0

Free-first GitHub Actions project for creating one original English gaming Shorts video per day.
No VPS and no always-on phone required. GitHub Actions runs the job on a schedule.

## What v1 does
- Runs daily at 20:00 Japan time (11:00 UTC).
- Selects one original gaming tip/fact from `content/topics.json`.
- Generates English narration with the free `edge-tts` service.
- Creates a vertical 1080x1920 MP4 with original graphic slides and narration.
- Uploads the MP4 as a GitHub Actions artifact for 7 days.
- Can be run manually from the Actions tab.

## Important limitations
- This is scheduled execution, not an always-on n8n server. GitHub may delay scheduled jobs.
- Free services have limits and can change. `edge-tts` is an unofficial client to Microsoft's online TTS service; availability is not guaranteed.
- v1 does NOT automatically publish to YouTube. Download the artifact and upload it using YouTube Studio. This avoids storing YouTube OAuth credentials before the channel owner has reviewed the content.
- The topic list is a starter set. Review facts and wording before publishing. Expand `content/topics.json` with original, accurate material.
- Public repositories can have scheduled workflows disabled after 60 days without repository activity. Keep the repo active and check Actions regularly.

## Android setup
1. Sign in at https://github.com in Chrome.
2. Create a repository named `AWN-YouTube-Automation`, choose **Public** to use standard GitHub-hosted runners free of charge, and initialize with a README.
3. Upload all files/folders from this ZIP into the repository. Keep `.github/workflows/daily-shorts.yml` at exactly that path.
4. Open **Actions** in the repository. If asked, enable workflows.
5. Select **AWN LATE Gaming Shorts** > **Run workflow** to test it once.
6. Wait for the run to finish. Open the run, scroll to **Artifacts**, and download `late-gaming-short`.
7. Extract the ZIP on Android and open the MP4. If it looks good, upload it in YouTube Studio.
8. The scheduled run is set for 20:00 Japan time daily. GitHub schedules are best-effort and may start later than the exact minute.

## YouTube upload
For the first version, use YouTube Studio manually:
- Open https://studio.youtube.com in Chrome (desktop site may be easier).
- Create > Upload videos.
- Select the generated MP4.
- Review title/description, audience setting, copyright, and visibility.
- Publish or schedule it.

Automatic upload can be added in a later version after setting up Google Cloud OAuth and securely storing a refresh token in GitHub Secrets. Do not paste OAuth tokens into chat or commit them to the repository.

## Change schedule
Edit `.github/workflows/daily-shorts.yml`.
`cron: "0 11 * * *"` means 11:00 UTC = 20:00 JST (Japan has no daylight-saving change).

## Change topics
Edit `content/topics.json`. Each item needs:
- `title`: short video title
- `hook`: opening line
- `body`: narration text
- `takeaway`: closing line
Use original wording. Do not add unverified claims or copyrighted gameplay/music.

## Troubleshooting
- If Actions is disabled: repository > Actions > enable workflows.
- If no artifact appears: open the failed run and inspect the first red step in the log.
- If TTS fails: rerun later; the free online service may be temporarily unavailable.
- If the workflow does not run at exactly 20:00: scheduled jobs can be delayed by GitHub.
