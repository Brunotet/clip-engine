# n8n flow (self-hosted wenlinco-creaty.hf.space)

Every Grok (xAI) call is preceded by a **Wait node = 60 s** so you never hit the rate limit.
The worker header is 'x-api-key: {{WORKER_API_KEY}}'. Base URL = the 'worker_url' your Kaggle notebook posts to an n8n webhook (store it in a static-data/variable node).

1. Trigger (manual / Form / schedule) -> inputs: 'url', optional 'start', 'end'
2. HTTP POST '/ingest'           -> job_id
3. Loop: Wait 20s -> GET '/status/{job}' until state=done (error -> stop + notify)
4. HTTP POST '/analyze/{job}'    -> same poll loop
5. HTTP GET '/analysis/{job}'    -> outline + candidates
6. HTTP GET '/formats'
7. **Wait 60s** -> Grok: prompts/1_format_selector.md  (format = "skip" -> end)
8. **Wait 60s** -> Grok: prompts/2_planner.md (vision: attach the frames of the chosen
   candidates as URLs: {{worker}}/files/{job}/frames/cX_N.jpg)
9. HTTP POST '/validate' with the plan
   - errors -> **Wait 60s** -> Grok: prompts/3_repair.md -> back to 9 (max 3 loops, then stop)
10. For each clip: Chatterbox TTS (your Modal endpoint) on narration_text -> mp3 URL
    -> put it in clip.narration_url (and narration_sec if the endpoint returns it)
11. HTTP POST '/validate' again (now with real narration seconds), then POST '/render'
12. Poll '/status/{job}' until done -> output 'files/{job}/final.mp4'
13. Review queue (Telegram/Email/Sheet) with preview link -> on approve: upload to
    YouTube (native OAuth2 node) with title/description from the plan.

Batching: queue several VODs and process them in ONE Kaggle session. The worker shuts
itself down 5 minutes after the last request.

Grok model name: set it in one n8n variable (check the xAI console for the current
model that supports vision) so you can swap it without editing nodes.
