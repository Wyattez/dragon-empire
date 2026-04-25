# 🐉 Dragon Empire — Deployment Guide
## სრული ინსტრუქცია Telegram MiniApp გაშვებისთვის

---

## 📋 რა გვჭირდება
- ✅ Telegram Bot Token (უკვე გაქვს)
- ✅ GitHub ანგარიში (უფასო)
- ✅ Vercel ანგარიში (უფასო) — vercel.com
- ✅ Supabase ანგარიში (უფასო) — supabase.com
- ✅ Railway ანგარიში (Backend-ისთვის) — railway.app (~$5/თვე, ან Render.com უფასოა)

---

## ნაბიჯი 1: Supabase Database-ის შექმნა

1. გადადი **supabase.com** → Sign Up (GitHub-ით)
2. "New Project" → სახელი: `dragon-empire`
3. Region: `eu-central-1` (ევროპა, Georgia-სთვის სწრაფი)
4. პაროლი: შეინახე სადმე!
5. დაელოდე ~2 წუთი სანამ შეიქმნება

### SQL Schema-ს გაშვება:
1. Supabase Dashboard → **SQL Editor** → New Query
2. გახსენი `backend/supabase_schema.sql`
3. Ctrl+A → Copy → Paste SQL Editor-ში
4. "Run" (▶️ ღილაკი)
5. ✅ "Success. No rows returned" — სწორია!

### API Keys-ის კოპირება:
1. Settings → API
2. კოპირება:
   - `Project URL` → `SUPABASE_URL`
   - `service_role` key (secret!) → `SUPABASE_SERVICE_KEY`
   - **⚠️ service_role key არასოდეს გაუგზავნო frontend-ს!**

---

## ნაბიჯი 2: GitHub Repo-ს შექმნა

```bash
# შენ კომპიუტერზე:
git init dragon-empire
cd dragon-empire

# ჩააკოპირე ყველა ფაილი ამ папке-ში
# (frontend/, backend/, vercel.json)

git add .
git commit -m "Initial Dragon Empire"
git branch -M main
git remote add origin https://github.com/ᲨᲔᲜᲘ_USERNAME/dragon-empire.git
git push -u origin main
```

---

## ნაბიჯი 3: Backend-ის Deploy (Railway)

1. გადადი **railway.app** → Login with GitHub
2. "New Project" → "Deploy from GitHub repo"
3. არჩევე `dragon-empire` repo
4. "Add service" → Python
5. **Variables** ტაბი → "Add Variable":

```
TELEGRAM_BOT_TOKEN=შენი_ტოკენი_აქ
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
WEBAPP_URL=https://dragon-empire.vercel.app  (ჯერ dummy, შემდეგ შევცვლით)
BACKEND_URL=https://dragon-empire-api.up.railway.app
API_SECRET=random-string-123
```

6. "Settings" → Start Command:
```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

7. "Deploy" → დაელოდე build-ს (~3 წუთი)
8. ✅ Domain-ს დაამახსოვრე: `https://xxx.up.railway.app`

### ალტერნატივა — Render.com (სრულიად უფასო):
1. render.com → New → Web Service → GitHub repo
2. Build Command: `pip install -r backend/requirements.txt`
3. Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Environment Variables: ზემოთ იგივე
5. ⚠️ Render free tier "sleep"-ს — Railway უმჯობესია

---

## ნაბიჯი 4: Frontend-ის Deploy (Vercel)

1. გადადი **vercel.com** → Login with GitHub
2. "New Project" → Import `dragon-empire` repo
3. Framework Preset: **Other**
4. Root Directory: `./` (default)
5. "Deploy"!
6. ✅ URL მიიღებ: `https://dragon-empire-XXXX.vercel.app`

### Frontend-ში URL-ის განახლება:
1. გახსენი `frontend/index.html`
2. მოძებნე: `const API_BASE = "https://your-backend.railway.app"`
3. შეცვალე შენი Railway URL-ით
4. მოძებნე: `const botName = "your_bot_username"`
5. შეცვალე შენი Bot-ის username-ით
6. `git commit -am "Fix API URL" && git push`
7. Vercel ავტომატურად redeploy-ს!

### Railway-შიც განახლება:
1. Variables → `WEBAPP_URL` → შეცვალე Vercel URL-ით
2. Redeploy

---

## ნაბიჯი 5: BotFather-ში WebApp-ის დაკავშირება

Telegram-ში @BotFather-ს:
```
/mybots
→ შენი Bot
→ Bot Settings
→ Menu Button
→ Configure menu button
→ URL: https://dragon-empire-XXXX.vercel.app
→ Button Text: ⚔️ Dragon Empire
```

ასევე:
```
/setmenubutton
```

### Webhook-ის დაყენება (ავტომატურია, მაგრამ შეამოწმე):
```
https://api.telegram.org/bot{TOKEN}/setWebhook?url=https://YOUR_RAILWAY_URL/webhook
```

---

## ნაბიჯი 6: Admin Panel-ის Deploy

Admin panel ცალკე ფაილია (`admin.html`).
1. გადაიტანე `frontend/admin.html`-ში
2. Vercel ავტომატურად host-ავს: `https://dragon-empire.vercel.app/admin.html`
3. **⚠️ Password შეცვალე** `admin.html`-ში:
   ```javascript
   const ADMIN_PASSWORD = 'შენი_ძლიერი_პაროლი';
   ```

---

## ✅ შემოწმება

1. Telegram-ში Bot-ს გაუგზავნე `/start`
2. "⚔️ Dragon Empire-ში შესვლა" ღილაკი გამოჩნდება
3. დააჭირე → WebApp გაიხსნება
4. პირველი Login ავტომატურად შექმნის player-ს DB-ში
5. შეამოწმე Supabase → Table Editor → players ცხრილი

---

## 🐛 Troubleshooting

| პრობლემა | გადაწყვეტა |
|----------|------------|
| WebApp არ იხსნება | Bot Settings → Domain-ის დამატება |
| "Invalid initData" error | initData ვერიფიკაცია — გაუშვი Telegram-ში, არა browser-ში |
| DB connection error | SUPABASE_URL და SERVICE_KEY შეამოწმე |
| CORS error | Backend-ში WEBAPP_URL სწორია? |
| Energy 0 | regen_energy() ფუნქცია ავტომატურად მუშაობს |

---

## 💰 მონეტიზაციის შეჯამება

| წყარო | როგორ |
|-------|-------|
| **Banner Ads** | Ad click = +5 gold მოთამაშეს, შენ იღებ CTR revenue-ს |
| **Telegram Stars** | Shop-ში `price_stars` > 0 → Telegram Stars payment |
| **Referral** | ყოველი ref = +500 gold მომხმარებელს, retention გაზრდა |
| **Premium Pack** | Admin Panel-იდან special items, VIP status |

---

## 📁 File Structure

```
dragon-empire/
├── frontend/
│   ├── index.html          ← WebApp (Vercel-ზე)
│   └── admin.html          ← Admin Panel
├── backend/
│   ├── main.py             ← FastAPI + Bot (Railway-ზე)
│   ├── requirements.txt
│   ├── supabase_schema.sql ← DB Schema (Supabase-ში გაუშვი)
│   └── .env.example        ← Environment variables template
├── vercel.json             ← Vercel config
└── DEPLOYMENT.md           ← ეს ფაილი
```

---

*🐉 Dragon Empire v1.0 — Built with FastAPI + Supabase + Telegram WebApp*
