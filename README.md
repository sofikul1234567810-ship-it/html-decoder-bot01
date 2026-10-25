# HTML Decode Telegram Bot

বাংলা ভাষায় HTML/JavaScript ফাইলের static analysis, beautify/format এবং কিছু safe literal decoding করার Telegram bot।

## Features
- `/start`, `/help`
- `/analyze` — obfuscation pattern-এর static analysis
- `/beautify` — lightweight HTML/JS formatting
- `/decode` — সীমিত literal decoding: quoted `\\xNN`/`\\uNNNN`, literal `atob("...")`, `String.fromCharCode(...)`
- Output file হিসেবে পাঠায়
- Flask `/` ও `/health` endpoint, যাতে Render web service চালু থাকে
- কোনো uploaded code execute করে না

## Limitations
এটি universal deobfuscator নয়। Formatting code-এর meaning বদলে দিতে পারে, বিশেষ করে unusual/minified JS/HTML-এ; output test/review করতে হবে। Encrypted payload, server-side code, missing keys, custom VM/packer বা complex control-flow obfuscation সাধারণত recover করা যাবে না। `eval`/`Function`-এর argument execute করা হয় না।

## Telegram bot token
1. Telegram-এ `@BotFather` খুলো।
2. `/newbot` পাঠাও, নির্দেশনা অনুসরণ করো।
3. BotFather যে token দেয় তা গোপন রাখো; GitHub code-এ token লিখবে না।

## GitHub-এ upload
1. GitHub-এ নতুন repository তৈরি করো, যেমন `html-decode-telegram-bot`।
2. ZIP extract করে সব ফাইল ও `decoder` folder repository-র root-এ upload করো।
3. `app.py`, `requirements.txt`, `render.yaml`, `.gitignore`, `README.md` root-এ থাকবে।

## Render deploy
1. Render dashboard-এ GitHub দিয়ে sign in করো।
2. **New + → Web Service** বেছে repository connect করো।
3. `render.yaml` detect হলে settings review করে deploy করো।
4. Render service-এর **Environment** tab-এ `BOT_TOKEN` নামে variable যোগ করো; value হবে BotFather token। Token কখনও public repo/কাউকে পাঠাবে না।
5. Save changes / deploy complete হওয়া পর্যন্ত অপেক্ষা করো।
6. Render URL খুলে `/health` যোগ করো। JSON-এ `{"ok":true}` এলে web process চালু।
7. Telegram-এ bot খুলে `/start` পাঠাও।

## ব্যবহার
1. `/analyze`, `/beautify`, বা `/decode` পাঠাও।
2. এরপর `.html`, `.htm`, `.js`, `.mjs`, `.cjs` বা `.txt` ফাইল document হিসেবে পাঠাও।
3. অথবা ফাইলের caption-এ `/analyze`, `/beautify`, `/decode` লিখতে পারো।
4. Beautify/decode output file হিসেবে ফেরত আসবে।

## Troubleshooting
- Bot reply না দিলে Render **Logs** দেখো; `BOT_TOKEN` ঠিক আছে কি না যাচাই করো।
- `BOT_TOKEN environment variable is missing` হলে Render Environment-এ variable যোগ করে redeploy করো।
- Deploy সফল কিন্তু bot বন্ধ হলে Render logs-এ Python exception দেখো।
- ফাইল 5 MB-এর বেশি হলে `MAX_FILE_MB` পরিবর্তন করা যায়; বেশি করলে RAM/processing সীমা মাথায় রাখো।
- Render-এর free plan/availability পরিবর্তিত হতে পারে; dashboard-এ বর্তমানে দেখানো plan ও sleep policy যাচাই করো।

## Security
Uploaded files untrusted input হিসেবে বিবেচনা করো। Bot কোড চালায় না, কিন্তু report/formatting result-ও review ছাড়া production-এ ব্যবহার করো না। Bot-এর token secret রাখো।
