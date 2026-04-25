"""
Dragon Empire — Telegram Bot + API Backend
==========================================
Stack: Python + FastAPI + python-telegram-bot + Supabase
Deploy: Railway / Render / VPS

Install:
  pip install fastapi uvicorn python-telegram-bot supabase python-dotenv httpx

Run:
  uvicorn main:app --host 0.0.0.0 --port 8000
"""

import os
import math
import logging
from datetime import datetime, date
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx

from supabase import create_client, Client
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

# ===== CONFIG =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # service_role key!
WEBAPP_URL = os.getenv("WEBAPP_URL")  # e.g. https://dragon-empire.vercel.app
API_SECRET = os.getenv("API_SECRET", "change-this-secret")  # shared secret frontend→backend

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== SUPABASE CLIENT =====
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ===== FASTAPI APP =====
app = FastAPI(title="Dragon Empire API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[WEBAPP_URL, "http://localhost:3000", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== TELEGRAM BOT =====
telegram_app: Application = None


# ===================================================
#  HELPER: verify Telegram WebApp initData
# ===================================================
import hashlib
import hmac
from urllib.parse import unquote, parse_qs

def verify_telegram_init_data(init_data: str) -> Optional[dict]:
    """Verify Telegram WebApp initData signature and return parsed user."""
    try:
        parsed = dict(item.split("=", 1) for item in init_data.split("&") if "=" in item)
        received_hash = parsed.pop("hash", "")

        data_check_string = "\n".join(
            f"{k}={unquote(v)}" for k, v in sorted(parsed.items())
        )

        secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if hmac.compare_digest(expected_hash, received_hash):
            import json
            user_data = json.loads(unquote(parsed.get("user", "{}")))
            return user_data
        return None
    except Exception as e:
        logger.error(f"initData verify error: {e}")
        return None


def get_or_create_player(telegram_id: int, first_name: str = "", username: str = "", referred_by: int = None):
    """Get existing player or create new one."""
    result = supabase.table("players").select("*").eq("telegram_id", telegram_id).execute()

    if result.data:
        # Regen energy
        supabase.rpc("regen_energy", {"p_telegram_id": telegram_id}).execute()
        # Update last seen
        supabase.table("players").update({"last_seen": datetime.utcnow().isoformat()}).eq("telegram_id", telegram_id).execute()
        return supabase.table("players").select("*").eq("telegram_id", telegram_id).single().execute().data

    # New player
    new_player = {
        "telegram_id": telegram_id,
        "first_name": first_name,
        "username": username,
        "hero_name": first_name or "Hero",
        "referred_by": referred_by,
    }
    created = supabase.table("players").insert(new_player).execute()
    player = created.data[0]

    # Handle referral bonus
    if referred_by:
        ref_result = supabase.table("players").select("id,gold,referral_count,referral_earnings").eq("telegram_id", referred_by).execute()
        if ref_result.data:
            ref_player = ref_result.data[0]
            supabase.table("players").update({
                "gold": ref_player["gold"] + 500,
                "referral_count": ref_player["referral_count"] + 1,
                "referral_earnings": ref_player["referral_earnings"] + 500,
            }).eq("telegram_id", referred_by).execute()

    # Seed daily quests
    seed_daily_quests(player["id"])
    return player


def seed_daily_quests(player_id: int):
    """Create today's quest progress rows for new/returning player."""
    quests = supabase.table("quests").select("id").eq("is_active", True).execute().data
    today = date.today().isoformat()
    for q in quests:
        try:
            supabase.table("player_quests").insert({
                "player_id": player_id,
                "quest_id": q["id"],
                "progress": 0,
                "completed": False,
                "quest_date": today,
            }).execute()
        except Exception:
            pass  # already exists


# ===================================================
#  API ROUTES
# ===================================================

class InitRequest(BaseModel):
    init_data: str
    referred_by: Optional[int] = None

@app.post("/api/init")
async def init_player(req: InitRequest):
    """Called when WebApp opens. Verifies Telegram user and returns player state."""
    user = verify_telegram_init_data(req.init_data)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid Telegram initData")

    player = get_or_create_player(
        telegram_id=user["id"],
        first_name=user.get("first_name", ""),
        username=user.get("username", ""),
        referred_by=req.referred_by,
    )

    # Get inventory
    inventory = supabase.table("player_inventory") \
        .select("*, items(*)") \
        .eq("player_id", player["id"]).execute().data

    # Get daily quests
    today = date.today().isoformat()
    quests = supabase.table("player_quests") \
        .select("*, quests(*)") \
        .eq("player_id", player["id"]) \
        .eq("quest_date", today).execute().data

    return {"player": player, "inventory": inventory, "quests": quests}


class BattleRequest(BaseModel):
    init_data: str
    enemy_id: int

@app.post("/api/battle")
async def do_battle(req: BattleRequest):
    """Process a battle."""
    user = verify_telegram_init_data(req.init_data)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid initData")

    player = get_or_create_player(user["id"])

    if player["is_banned"]:
        raise HTTPException(status_code=403, detail="Player is banned")

    if player["energy"] < 2:
        raise HTTPException(status_code=400, detail="Not enough energy")

    enemy = supabase.table("enemies").select("*").eq("id", req.enemy_id).single().execute().data
    if not enemy:
        raise HTTPException(status_code=404, detail="Enemy not found")

    # Battle calculation
    import random
    player_power = player["attack"] + random.randint(-10, 10)
    crit = random.random() < (player["crit_chance"] / 100)
    if crit:
        player_power = int(player_power * 1.5)

    damage_needed_to_kill = enemy["hp_max"]
    hits_to_kill = math.ceil(damage_needed_to_kill / player_power)
    won = hits_to_kill <= 4  # 4 hit limit per battle round

    total_damage = min(player_power * 4, enemy["hp_max"])

    # Update player
    updates = {"energy": player["energy"] - 2}
    gold_earned = 0
    xp_earned = 0

    if won:
        gold_earned = enemy["reward_gold"]
        xp_earned = enemy["reward_xp"]
        new_gold = player["gold"] + gold_earned
        new_xp = player["xp"] + xp_earned
        new_battles_won = player["battles_won"] + 1

        # Level up check
        new_level = player["level"]
        new_xp_next = player["xp_next"]
        if new_xp >= player["xp_next"]:
            new_level += 1
            new_xp_next = int(player["xp_next"] * 1.5)
            updates.update({
                "attack": player["attack"] + 10,
                "defense": player["defense"] + 7,
                "hp_max": player["hp_max"] + 50,
            })

        updates.update({
            "gold": new_gold,
            "xp": new_xp,
            "xp_next": new_xp_next,
            "level": new_level,
            "battles_won": new_battles_won,
            "battles_total": player["battles_total"] + 1,
        })

        # Quest progress
        supabase.table("player_quests").rpc or None  # simplified
        today = date.today().isoformat()
        battle_quests = supabase.table("player_quests") \
            .select("*, quests(*)") \
            .eq("player_id", player["id"]) \
            .eq("quest_date", today).execute().data

        for pq in battle_quests:
            if pq["quests"]["type"] == "battles" and not pq["completed"]:
                new_progress = pq["progress"] + 1
                completed = new_progress >= pq["quests"]["target_count"]
                if completed:
                    updates["gold"] = updates.get("gold", player["gold"]) + pq["quests"]["reward_gold"]
                    xp_earned += pq["quests"]["reward_xp"]
                supabase.table("player_quests").update({
                    "progress": new_progress, "completed": completed
                }).eq("id", pq["id"]).execute()
    else:
        updates["battles_total"] = player["battles_total"] + 1

    supabase.table("players").update(updates).eq("id", player["id"]).execute()

    # Log battle
    supabase.table("battle_log").insert({
        "player_id": player["id"],
        "enemy_id": req.enemy_id,
        "won": won,
        "damage_dealt": total_damage,
        "gold_earned": gold_earned,
        "xp_earned": xp_earned,
    }).execute()

    return {
        "won": won,
        "damage_dealt": total_damage,
        "crit": crit,
        "gold_earned": gold_earned,
        "xp_earned": xp_earned,
        "level_up": updates.get("level", player["level"]) > player["level"],
    }


class BuyRequest(BaseModel):
    init_data: str
    item_id: int

@app.post("/api/shop/buy")
async def buy_item(req: BuyRequest):
    """Purchase an item from shop."""
    user = verify_telegram_init_data(req.init_data)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid initData")

    player = get_or_create_player(user["id"])
    item = supabase.table("items").select("*").eq("id", req.item_id).single().execute().data

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if player["gold"] < item["price_gold"]:
        raise HTTPException(status_code=400, detail="Not enough gold")

    # Deduct gold, apply stats
    new_gold = player["gold"] - item["price_gold"]
    stat_updates = {"gold": new_gold}
    if item["atk_bonus"]: stat_updates["attack"] = player["attack"] + item["atk_bonus"]
    if item["def_bonus"]: stat_updates["defense"] = player["defense"] + item["def_bonus"]
    if item["hp_bonus"]: stat_updates["hp_max"] = player["hp_max"] + item["hp_bonus"]

    supabase.table("players").update(stat_updates).eq("id", player["id"]).execute()

    # Add to inventory
    try:
        supabase.table("player_inventory").insert({
            "player_id": player["id"],
            "item_id": req.item_id,
        }).execute()
    except Exception:
        # Already has it — increment quantity
        inv = supabase.table("player_inventory").select("id,quantity") \
            .eq("player_id", player["id"]).eq("item_id", req.item_id).single().execute().data
        supabase.table("player_inventory").update({"quantity": inv["quantity"] + 1}).eq("id", inv["id"]).execute()

    # Log transaction
    supabase.table("transactions").insert({
        "player_id": player["id"],
        "type": "purchase",
        "amount": -item["price_gold"],
        "currency": "gold",
        "description": f"Bought {item['name']}",
    }).execute()

    return {"success": True, "new_gold": new_gold, "stats": stat_updates}


@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10):
    """Get global leaderboard."""
    result = supabase.table("leaderboard").select("*").order("rank").limit(limit).execute()
    return {"leaderboard": result.data}


@app.get("/api/enemies")
async def get_enemies():
    result = supabase.table("enemies").select("*").eq("is_active", True).order("level").execute()
    return {"enemies": result.data}


@app.get("/api/shop")
async def get_shop():
    result = supabase.table("items").select("*").eq("is_active", True).execute()
    return {"items": result.data}


class AdClickRequest(BaseModel):
    init_data: str
    ad_type: str = "banner"

@app.post("/api/ad/click")
async def record_ad_click(req: AdClickRequest):
    """Record ad click and give player +5 gold."""
    user = verify_telegram_init_data(req.init_data)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid initData")

    player = get_or_create_player(user["id"])
    supabase.table("players").update({"gold": player["gold"] + 5}).eq("id", player["id"]).execute()
    supabase.table("ad_clicks").insert({"player_id": player["id"], "ad_type": req.ad_type}).execute()

    return {"success": True, "bonus_gold": 5}


# ===================================================
#  TELEGRAM BOT HANDLERS
# ===================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command — show WebApp button."""
    user = update.effective_user
    referred_by = None

    # Check referral: /start ref_12345678
    if context.args and context.args[0].startswith("ref_"):
        try:
            referred_by = int(context.args[0].replace("ref_", ""))
        except ValueError:
            pass

    webapp_url = WEBAPP_URL
    if referred_by:
        webapp_url = f"{WEBAPP_URL}?ref={referred_by}"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text="⚔️ Dragon Empire-ში შესვლა",
            web_app=WebAppInfo(url=webapp_url)
        )
    ]])

    await update.message.reply_text(
        f"🐉 *Dragon Empire-ში კეთილი იყოს შენი მობრძანება, {user.first_name}!*\n\n"
        "⚔️ იბრძოლე მოწინააღმდეგეებთან\n"
        "🏰 გაიარე Dungeons\n"
        "🏆 მოხვდი Leaderboard-ზე\n"
        "💰 შეაგროვე Gold & Gems\n\n"
        "დააჭირე ღილაკს და დაიწყე თამაში!",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show player stats in chat."""
    telegram_id = update.effective_user.id
    result = supabase.table("players").select("*").eq("telegram_id", telegram_id).execute()

    if not result.data:
        await update.message.reply_text("❌ ჯერ არ გაქვს პერსონაჟი! /start")
        return

    p = result.data[0]
    await update.message.reply_text(
        f"🧙 *{p['hero_name']}* — Level {p['level']}\n\n"
        f"❤️ HP: {p['hp']}/{p['hp_max']}\n"
        f"🔮 Mana: {p['mana']}/{p['mana_max']}\n"
        f"⚡ Energy: {p['energy']}/{p['energy_max']}\n"
        f"💰 Gold: {p['gold']:,}\n"
        f"💎 Gems: {p['gems']}\n"
        f"⚔️ Attack: {p['attack']} | 🛡️ Defense: {p['defense']}\n"
        f"🏆 Battles: {p['battles_won']}/{p['battles_total']}\n",
        parse_mode="Markdown",
    )


async def cmd_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send referral link."""
    telegram_id = update.effective_user.id
    bot = context.bot
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{telegram_id}"

    await update.message.reply_text(
        f"🎁 *Referral პროგრამა*\n\n"
        f"მოიწვიე მეგობარი და მიიღე *500💰 Gold* ყოველ რეფერალზე!\n\n"
        f"შენი ლინკი:\n`{ref_link}`\n\n"
        f"დააკოპირე და გაუგზავნე მეგობრებს! 📤",
        parse_mode="Markdown",
    )


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top 5 leaderboard."""
    result = supabase.table("leaderboard").select("*").order("rank").limit(5).execute()
    lines = ["🏆 *Top 5 მოთამაშე*\n"]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, row in enumerate(result.data):
        lines.append(f"{medals[i]} {row['hero_name']} — ⚔️ {row['power']:,}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ===================================================
#  WEBHOOK SETUP
# ===================================================

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram updates via webhook."""
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


@app.on_event("startup")
async def startup():
    global telegram_app

    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", cmd_start))
    telegram_app.add_handler(CommandHandler("stats", cmd_stats))
    telegram_app.add_handler(CommandHandler("referral", cmd_referral))
    telegram_app.add_handler(CommandHandler("top", cmd_leaderboard))

    await telegram_app.initialize()
    await telegram_app.start()

    # Set webhook
    webhook_url = f"{os.getenv('BACKEND_URL', '')}/webhook"
    if webhook_url.startswith("https"):
        await telegram_app.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set: {webhook_url}")


@app.on_event("shutdown")
async def shutdown():
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()


@app.get("/")
async def health():
    return {"status": "Dragon Empire API running 🐉", "version": "1.0.0"}
