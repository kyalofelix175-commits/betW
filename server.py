import os
import requests
import random
import sqlite3
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import base64
from datetime import datetime, timedelta
import json
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

import time
import threading
import math
from flask_socketio import SocketIO, emit


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
app.secret_key = os.urandom(24)
CORS(
    app,
    supports_credentials=True,
    origins=["http://192.168.1.121:5500", "http://127.0.0.1:5500"],
)

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "993f927dfcb003e19c0605bfbed125b")
MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "wZ0PSLUA8EPTxHyR8VPnwLjt5wYrpD5JlRV7LnwxyeoOTTaa")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "MfvCI8YAuJ3rCjAoD3FzzGTPFmfs9OHSftZFob4I10CO7dp04K5AkJunNW2yr4zE")

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            balance REAL DEFAULT 500.0,
            is_verified INTEGER DEFAULT 0,
            verification_code TEXT,
            code_expires_at TIMESTAMP
        )
    """)
    
    # Bets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            stake REAL NOT NULL,
            total_odds REAL NOT NULL,
            possible_payout REAL NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            selections TEXT NOT NULL
        )
    """)
    
    # Transactions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'COMPLETED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# Example helper using Africa's Talking / SMS API
AT_USERNAME = "sandbox" # or your live username
AT_API_KEY = "YOUR_AFRICASTALKING_API_KEY"

def send_otp_sms(phone_number, code):
    url = "https://api.africastalking.com/version1/messaging"
    headers = {
        "ApiKey": AT_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    payload = {
        "username": AT_USERNAME,
        "to": phone_number,
        "message": f"Your verification code is {code}. It expires in 10 minutes."
    }
    try:
        response = requests.post(url, headers=headers, data=payload)
        return response.status_code == 201
    except Exception as e:
        print(f"SMS Sending Exception: {e}")
        return False


# --- AUTH ENDPOINTS ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    if len(phone) < 9 or len(password) != 4 or not password.isdigit():
        return jsonify({"success": False, "message": "Enter a valid phone number and a 4-digit PIN."}), 400

    hashed_pw = generate_password_hash(password)

    # Generate 6-digit code and 10-minute expiry
    otp_code = str(random.randint(100000, 999999))
    expires_at = datetime.now() + timedelta(minutes=10)

    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        # Fixed SQL parameters order: phone, password_hash, is_verified (0), verification_code, code_expires_at, balance (0.0)
        cursor.execute(
            "INSERT INTO users (phone, password_hash, is_verified, verification_code, code_expires_at, balance) VALUES (?, ?, 0, ?, ?, 0.0)", 
            (phone, hashed_pw, otp_code, expires_at)
        )
        conn.commit()
        conn.close()
        session["user_phone"] = phone
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "Phone number already registered.Please log in to your account."}), 400

    # Attempt SMS sending
    sms_sent = send_otp_sms(phone, otp_code)

    if sms_sent:
        return jsonify({"success": True, "message": "Account created! Verification code sent via SMS."})
    else:
        return jsonify({"success": True, "message": "Account created successfully! Enter PIN to log in."})

    
@app.route("/api/verify_otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    phone = data.get("phone")
    user_code = data.get("code")

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT verification_code, code_expires_at FROM users WHERE phone = ?
    """, (phone,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"success": False, "message": "User not found"}), 404

    saved_code, expires_at_str = row
    expires_at = datetime.fromisoformat(expires_at_str)

    if datetime.now() > expires_at:
        conn.close()
        return jsonify({"success": False, "message": "Verification code expired. Request a new one."}), 400

    if saved_code == user_code:
        cursor.execute("UPDATE users SET is_verified = 1, verification_code = NULL WHERE phone = ?", (phone,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Phone number verified successfully!"})
    
    conn.close()
    return jsonify({"success": False, "message": "Invalid verification code"}), 400

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE phone = ?", (phone,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user[0], password):
        session["user_phone"] = phone
        return jsonify({"success": True, "message": "Login successful!"})
    
    return jsonify({"success": False, "message": "Invalid phone number or 4-digit PIN."}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("user_phone", None)
    return jsonify({"success": True, "message": "Logged out successfully."})

@app.route("/api/user_info", methods=["GET"])
def user_info():
    phone = session.get("user_phone")
    if not phone:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT phone, balance FROM users WHERE phone = ?", (phone,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return jsonify({"success": True, "phone": user[0], "balance": user[1]})
    return jsonify({"success": False, "message": "User not found"}), 404

@app.route("/api/delete_account", methods=["POST"])
def delete_account():
    phone = session.get("user_phone")
    if not phone:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE phone = ?", (phone,))
    cursor.execute("DELETE FROM bets WHERE phone = ?", (phone,))
    cursor.execute("DELETE FROM transactions WHERE phone = ?", (phone,))
    conn.commit()
    conn.close()
    
    session.pop("user_phone", None)
    return jsonify({"success": True, "message": "Account permanently deleted."})

# --- ODDS & MATCHES ENDPOINTS ---

@app.route("/api/matches", methods=["GET"])
def get_matches():
    sport = request.args.get("sport", "soccer").lower()
    
    # Map request categories to Odds API sport keys
    sport_map = {
        "soccer": "soccer_epl",
        "basketball": "basketball_nba",
        "cricket": "cricket_test_match",
        "tennis": "tennis_atp_aus_open_singles",
        "volleyball": "volleyball",
        "upcoming": "upcoming",
        "live": "is_live"
    }
    
    api_sport = sport_map.get(sport, "soccer_epl")
    url = f"https://api.the-odds-api.com/v4/sports/{api_sport}/odds/?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h"
    
    # Inside server.py under /api/matches
    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            raw_data = resp.json()
            # Process Odds API data...

            matches = []
            for item in raw_data[:15]:
                home = item.get("home_team", "Home")
                away = item.get("away_team", "Away")
                
                home_odds, draw_odds, away_odds = 2.10, 3.20, 3.10
                bookmakers = item.get("bookmakers", [])
                if bookmakers:
                    markets = bookmakers[0].get("markets", [])
                    if markets:
                        outcomes = markets[0].get("outcomes", [])
                        for o in outcomes:
                            if o.get("name") == home:
                                home_odds = o.get("price", 2.10)
                            elif o.get("name") == away:
                                away_odds = o.get("price", 3.10)
                            elif o.get("name") == "Draw":
                                draw_odds = o.get("price", 3.20)
                
                # Extract the ISO commence time string from the API
                commence_raw = item.get("commence_time", "")

                if commence_raw:
                    # Converts ISO string (e.g., "2026-09-27T14:00:00Z") to Python datetime object
                    dt = datetime.fromisoformat(commence_raw.replace("Z", "+00:00"))
                    match_date_str = dt.strftime("%d %b")  # e.g., "27 Sep" or "28 Sep"
                    start_time_str = dt.strftime("%H:%M")  # e.g., "14:00" or "16:30"
                else:
                    match_date_str = "Today"
                    start_time_str = "18:00"

                league_name = item.get("sport_title", sport.replace("_", " ").title())    

                matches.append({
                    "id": item.get("id"),
                    "home_team": home,
                    "away_team": away,
                    "sport": sport,
                    "league_name": league_name,
                    "is_live": False,
                    "match_date": match_date_str,
                    "start_time": start_time_str,
                    "score": "0 - 0",
                    "home_odds": round(home_odds, 2),
                    "draw_odds": round(draw_odds, 2),
                    "away_odds": round(away_odds, 2),
                    
                })
            if matches:
                return jsonify({"success": True, "matches": matches})
    
 
        else:
            raise Exception("API limit reached or error code")
        #local odd simulator
    except Exception as e:
        print(f"Odds API credits exhausted/error ({e}). Using local simulator!")

        # Direct Local Fallback Generator
        matches = []
        now = datetime.now()
        mock_leagues = [
            ("EPL", "soccer", ["Arsenal", "Man City", "Liverpool", "Chelsea"]),
            ("La Liga", "soccer", ["Real Madrid", "Barcelona", "Atletico", "Sevilla"]),
            ("UEFA champions league", "soccer", ["PSG", "Bayern", "Inter", "Dortmund"]),
            ("NBA", "basketball", ["Lakers", "Celtics", "Warriors", "Bulls"]),
        ]

        for i in range(1000):
            lg_name, lg_sport, t_list = random.choice(mock_leagues)
            h_team, a_team = random.sample(t_list, 2)
            dt = now + timedelta(hours=random.randint(1, 48))

            matches.append({
                "id": f"sim_{i+100}",
                "home_team": h_team,
                "away_team": a_team,
                "sport": lg_sport,
                "league_name": lg_name,
                "is_live": False,
                "match_date": dt.strftime("%d %b"),
                "start_time": dt.strftime("%H:%M"),
                "score": "0 - 0",
                "home_odds": round(random.uniform(1.35, 3.80), 2),
                "draw_odds": round(random.uniform(3.10, 4.00), 2),
                "away_odds": round(random.uniform(1.40, 4.50), 2),
            })

        return jsonify({"success": True, "matches": matches})

# --- BETTING ENDPOINTS ---

@app.route("/api/place_bet", methods=["POST"])
def place_bet():
    phone = session.get("user_phone")
    if not phone:
        return jsonify({"success": False, "message": "Please log in to place bets."}), 401

    data = request.get_json() or {}
    stake = float(data.get("stake", 0))
    total_odds = float(data.get("total_odds", 1.0))
    selections = str(data.get("selections", "[]"))

    if stake < 10:
        return jsonify({"success": False, "message": "Minimum stake is KES 10."}), 400

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE phone = ?", (phone,))
    user = cursor.fetchone()

    if not user or user[0] < stake:
        conn.close()
        return jsonify({"success": False, "message": "Insufficient balance."}), 400

    new_balance = user[0] - stake
    possible_payout = round(stake * total_odds, 2)

    cursor.execute("UPDATE users SET balance = ? WHERE phone = ?", (new_balance, phone))
    cursor.execute(
        "INSERT INTO bets (phone, stake, total_odds, possible_payout, status, selections) VALUES (?, ?, ?, ?, 'ACTIVE', ?)",
        (phone, stake, total_odds, possible_payout, selections)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Bet placed successfully!", "new_balance": new_balance})

@app.route("/api/my_bets", methods=["GET"])
def my_bets():
    phone = session.get("user_phone")
    if not phone:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, stake, total_odds, possible_payout, status, created_at, selections FROM bets WHERE phone = ? ORDER BY id DESC", (phone,))
    rows = cursor.fetchall()
    conn.close()

    bets = []
    for r in rows:
        bets.append({
            "id": r[0],
            "stake": r[1],
            "total_odds": r[2],
            "possible_payout": r[3],
            "status": r[4],
            "created_at": r[5],
            "selections": r[6]
        })

    return jsonify({"success": True, "bets": bets})

@app.route("/api/cancel_bet", methods=["POST"])
def cancel_bet():
    phone = session.get("user_phone")
    if not phone:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    data = request.get_json() or {}
    bet_id = data.get("bet_id")

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT stake, status FROM bets WHERE id = ? AND phone = ?", (bet_id, phone))
    bet = cursor.fetchone()

    if not bet:
        conn.close()
        return jsonify({"success": False, "message": "Bet not found."}), 404

    if bet[1] != "ACTIVE":
        conn.close()
        return jsonify({"success": False, "message": "Only active bets can be cancelled."}), 400

    refund_amount = bet[0]
    cursor.execute("UPDATE bets SET status = 'CANCELLED' WHERE id = ?", (bet_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE phone = ?", (refund_amount, phone))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Bet cancelled. KES {refund_amount} refunded to wallet."})

# --- WALLET & M-PESA ENDPOINTS ---
# -------------------------------------------------------------------
# SAFARICOM DARAJA CONFIGURATION (SANDBOX DEFAULTS)
# -------------------------------------------------------------------

MPESA_ENV = "sandbox"  # Change to 'production' when live

# Sandbox default shortcodes
SHORTCODE = "174379"  # Paybill shortcode for STK Push
PASSKEY = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"  # Sandbox Passkey
B2C_SHORTCODE = "600981"  # Sandbox B2C shortcode
INITIATOR_NAME = "testapi"  # Sandbox Initiator
INITIATOR_PASSWORD = "Safaricom2026!"

# Set your public Ngrok domain here so Safaricom can call your webhook
CALLBACK_BASE_URL = "https://your-ngrok-subdomain.ngrok-free.app"

BASE_URL = (
    "https://sandbox.safaricom.co.ke"
    if MPESA_ENV == "sandbox"
    else "https://api.safaricom.co.ke"
)


# Helper: Generate OAuth Access Token
def get_mpesa_access_token():
  url = f'{BASE_URL}/oauth/v1/generate?grant_type=client_credentials'

  # Add custom headers to bypass Incapsula WAF blocking
  headers = {
      'User-Agent': (
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
          ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      ),
      'Accept': 'application/json',
  }

  response = requests.get(
      url,
      auth=(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET),
      headers=headers,
      timeout=15,
  )

  if response.status_code == 200:
    return response.json().get('access_token')

  # If blocked or failed, print human-readable output
  print(f'Token Error Status: {response.status_code}')
  print(f'Token Error Response: {response.text[:200]}')
  raise Exception(f'Failed to fetch token: HTTP {response.status_code}')


# Helper: Format Phone Numbers to 254XXXXXXXXX
def format_phone(phone):
  phone = str(phone).strip().replace("+", "")
  if phone.startswith("0"):
    return "254" + phone[1:]
  elif phone.startswith("7") or phone.startswith("1"):
    return "254" + phone
  return phone


# -------------------------------------------------------------------
# 1. DEPOSIT (STK PUSH / M-PESA EXPRESS)
# -------------------------------------------------------------------
@app.route("/api/deposit", methods=["POST"])
def deposit():
  data = request.get_json() or {}
  amount = data.get("amount")
  phone = data.get("phone") or session.get("user_phone")

  if not phone or not amount:
    return (
        jsonify({"success": False, "message": "Phone and amount are required"}),
        400,
    )

  formatted_phone = format_phone(phone)
  timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
  password = base64.b64encode(
      f"{SHORTCODE}{PASSKEY}{timestamp}".encode()
  ).decode("utf-8")
  token = get_mpesa_access_token()

  headers = {
      "Authorization": f"Bearer {token}",
      "Content-Type": "application/json",
  }

  payload = {
      "BusinessShortCode": SHORTCODE,
      "Password": password,
      "Timestamp": timestamp,
      "TransactionType": "CustomerPayBillOnline",
      "Amount": int(amount),
      "PartyA": formatted_phone,
      "PartyB": SHORTCODE,
      "PhoneNumber": formatted_phone,
      "CallBackURL": f"{CALLBACK_BASE_URL}/api/mpesa/callback",
      "AccountReference": "betW_Deposit",
      "TransactionDesc": "Wallet Deposit",
  }

  response = requests.post(
      f"{BASE_URL}/mpesa/stkpush/v1/processrequest",
      json=payload,
      headers=headers,
  )
  res_data = response.json()

  if res_data.get("ResponseCode") == "0":
    return jsonify({
        "success": True,
        "message": "STK Push sent to your phone. Enter PIN to complete.",
        "checkout_id": res_data.get("CheckoutRequestID"),
    })
  else:
    return (
        jsonify({
            "success": False,
            "message": res_data.get(
                "CustomerMessage", "STK Push failed to initiate"
            ),
        }),
        400,
    )

# Webhook Callback for STK Push Result
@app.route("/api/mpesa/callback", methods=["POST"])
def mpesa_callback():
    data = request.get_json() or {}
    stk_result = data.get("Body", {}).get("stkCallback", {})
    result_code = stk_result.get("ResultCode")

    if result_code == 0:
        items = stk_result.get("CallbackMetadata", {}).get("Item", [])
        amount = 0
        raw_phone = ""

        for item in items:
            if item.get("Name") == "Amount":
                amount = float(item.get("Value", 0))
            elif item.get("Name") == "PhoneNumber":
                raw_phone = str(item.get("Value"))

        # Create formats to match database variations (0712345678 and 254712345678)
        phone_local = "0" + raw_phone[3:] if raw_phone.startswith("254") else raw_phone
        phone_intl = raw_phone if raw_phone.startswith("254") else format_phone(raw_phone)

        if (phone_local or phone_intl) and amount > 0:
            conn = sqlite3.connect("users.db")
            cursor = conn.cursor()
            
            # Update user wallet balance matching either format
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE phone = ? OR phone = ?",
                (amount, phone_local, phone_intl)
            )
            
            # Log successful transaction record
            cursor.execute(
                "INSERT INTO transactions (phone, type, amount, status) VALUES (?, 'DEPOSIT', ?, 'COMPLETED')",
                (phone_local, amount)
            )
            
            conn.commit()
            conn.close()

    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})

# -------------------------------------------------------------------
# 2. WITHDRAWAL (B2C DISBURSEMENT)
# -------------------------------------------------------------------
@app.route("/api/withdraw", methods=["POST"])
def withdraw():
  data = request.get_json() or {}
  amount = float(data.get("amount", 0))
  phone = data.get("phone") or session.get("user_phone")

  if not phone or amount <= 0:
    return (
        jsonify(
            {"success": False, "message": "Valid phone and amount required"}
        ),
        400,
    )

  formatted_phone = format_phone(phone)

  # 1. Verify user balance in database
  conn = sqlite3.connect("users.db")
  cursor = conn.cursor()
  cursor.execute("SELECT balance FROM users WHERE phone = ?", (phone,))
  user = cursor.fetchone()

  if not user or user[0] < amount:
    conn.close()
    return (
        jsonify({"success": False, "message": "Insufficient wallet balance"}),
        400,
    )

  # 2. Deduct balance immediately
  cursor.execute(
      "UPDATE users SET balance = balance - ? WHERE phone = ?", (amount, phone)
  )
  conn.commit()
  conn.close()

  # 3. Call M-Pesa B2C API
  try:
    token = get_mpesa_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "InitiatorName": INITIATOR_NAME,
        "SecurityCredential": "ENCRYPTED_CREDENTIAL_STRING",  # Requires RSA public key encryption in production
        "CommandID": "BusinessPayment",
        "Amount": int(amount),
        "PartyA": B2C_SHORTCODE,
        "PartyB": formatted_phone,
        "Remarks": "betW Withdrawal",
        "QueueTimeOutURL": f"{CALLBACK_BASE_URL}/api/mpesa/b2c_timeout",
        "ResultURL": f"{CALLBACK_BASE_URL}/api/mpesa/b2c_result",
        "Occasion": "Withdrawal",
  }

    response = requests.post(
        f"{BASE_URL}/mpesa/b2c/v1/paymentrequest", json=payload, headers=headers
    )
    res_data = response.json()

    return jsonify({
        "success": True,
        "message": (
            "Withdrawal request submitted. Funds will arrive shortly via"
            " M-Pesa."
        ),
    })

  except Exception as e:
    return (
        jsonify(
            {"success": False, "message": f"Withdrawal error: {str(e)}"}
        ),
        500,
    )


@app.route("/api/wallet/transactions", methods=["GET"])
def wallet_transactions():
    phone = session.get("user_phone")
    if not phone:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, type, amount, status, created_at FROM transactions WHERE phone = ? ORDER BY id DESC", (phone,))
    rows = cursor.fetchall()
    conn.close()

    txs = []
    for r in rows:
        txs.append({
            "id": r[0],
            "type": r[1],
            "amount": r[2],
            "status": r[3],
            "created_at": r[4]
        })

    return jsonify({"success": True, "transactions": txs})


# ==========================================
# AVIATOR GAME CONFIGURATION & ENGINE
# ==========================================

game_state = {
    'status': 'WAITING',  # WAITING, IN_FLIGHT, CRASHED
    'multiplier': 1.00,
    'crash_point': 1.00,
    'countdown': 5.0,
    'history': [1.24, 5.60, 1.05, 12.30, 2.10],
    'active_bets': {} # { socket_id_panel: { ... } }
}

loop_lock = threading.Lock()
game_loop_started = False

def update_user_balance(user_id, amount_change):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount_change, user_id))
    conn.commit()
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    new_bal = row['balance'] if row else 0.0
    conn.close()
    return new_bal

def process_cashout(sid, panel_id, mult):
    bet_key = f"{sid}_{panel_id}"
    bet = game_state['active_bets'].get(bet_key)
    if not bet or bet['status'] != 'IN_GAME':
        return

    win_amount = round(bet['amount'] * mult, 2)
    bet['status'] = 'CASHED_OUT'
    bet['cashout_multiplier'] = mult
    bet['win_amount'] = win_amount

    new_balance = None
    if bet['mode'] == 'LIVE':
        new_balance = update_user_balance(bet['user_id'], win_amount)

    socketio.emit('cashout_success', {
        'panel_id': panel_id,
        'multiplier': mult,
        'win_amount': win_amount,
        'mode': bet['mode'],
        'new_balance': new_balance
    }, to=sid)
    socketio.emit('live_bets_update', {'players': list(game_state['active_bets'].values())})

def game_loop():
    while True:
        # 1. WAITING STAGE
        game_state['status'] = 'WAITING'
        game_state['multiplier'] = 1.00
        game_state['active_bets'] = {}
        game_state['crash_point'] = round(max(1.00, random.paretovariate(1.5)), 2)
        
        countdown = 5.0
        while countdown > 0:
            game_state['countdown'] = round(countdown, 1)
            socketio.emit('round_waiting', {'countdown': game_state['countdown']})
            socketio.sleep(0.1)
            countdown -= 0.1

        # 2. IN_FLIGHT STAGE
        game_state['status'] = 'IN_FLIGHT'
        start_time = time.time()
        growth_rate = 0.3  
        
        while game_state['multiplier'] < game_state['crash_point']:
            elapsed_seconds = time.time() - start_time
            current_mult = round(math.exp(elapsed_seconds * growth_rate), 2)
            
            if current_mult >= game_state['crash_point']:
                break
                
            game_state['multiplier'] = current_mult

            # Check Auto Cashouts
            for sid_panel, bet in list(game_state['active_bets'].items()):
                if bet['status'] == 'IN_GAME' and bet.get('auto_enabled'):
                    if game_state['multiplier'] >= bet['auto_rate']:
                        process_cashout(bet['sid'], bet['panel_id'], game_state['multiplier'])

            socketio.emit('multiplier_update', {
                'multiplier': game_state['multiplier'],
                'players': list(game_state['active_bets'].values())
            })
            socketio.sleep(0.1)

        # 3. CRASHED STAGE
        game_state['status'] = 'CRASHED'
        game_state['history'].insert(0, game_state['crash_point'])
        game_state['history'] = game_state['history'][:15]
        
        socketio.emit('round_crashed', {
            'crash_point': game_state['crash_point'],
            'history': game_state['history']
        })
        socketio.sleep(3.0)

# ==========================================
# SOCKET & ROUTE HANDLERS
# ==========================================

@socketio.on('connect')
def handle_connect():
    start_game_loop_once()
    emit('round_waiting', {'countdown': game_state['countdown']})

@app.route('/aviator')
def aviator():
    return render_template('aviator.html')

@app.route('/api/user_info', methods=['GET'])
def get_user_info():
    phone = session.get("user_phone")
    if not phone:
        return jsonify({'phone': 'Guest', 'live_balance': 0.00})
    
    conn = sqlite3.connect("users.db")
    user = conn.execute("SELECT id, phone, balance FROM users WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user['id']
        return jsonify({'phone': user['phone'], 'live_balance': float(user['balance'])})
    return jsonify({'phone': 'Guest', 'live_balance': 0.00})

@socketio.on('place_bet')
def handle_place_bet(data):
    if game_state['status'] != 'WAITING':
        emit('error_msg', {'message': 'Wait for the next round!'})
        return

    user_id = session.get('user_id', 1)
    panel_id = int(data['panel_id'])
    amount = float(data['amount'])
    mode = data['mode']
    
    new_balance = None
    if mode == 'LIVE':
        conn = sqlite3.connect("users.db")
        user = conn.execute("SELECT balance, phone FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if not user or float(user['balance']) < amount:
            emit('error_msg', {'message': 'Insufficient Live Balance!'})
            return
        new_balance = update_user_balance(user_id, -amount)
        phone = user['phone']
    else:
        phone = "DemoUser"

    bet_key = f"{request.sid}_{panel_id}"
    game_state['active_bets'][bet_key] = {
        'sid': request.sid,
        'user_id': user_id,
        'phone': phone[:4] + '****' + phone[-2:] if len(phone) > 6 else phone,
        'panel_id': panel_id,
        'amount': amount,
        'mode': mode,
        'status': 'IN_GAME',
        'auto_enabled': data.get('auto_enabled', False),
        'auto_rate': float(data.get('auto_rate', 2.00)),
        'win_amount': 0
    }

    emit('bet_accepted', {
        'panel_id': panel_id, 
        'amount': amount, 
        'mode': mode, 
        'new_balance': new_balance
    })
    socketio.emit('live_bets_update', {'players': list(game_state['active_bets'].values())})

@socketio.on('manual_cashout')
def handle_manual_cashout(data):
    if game_state['status'] == 'IN_FLIGHT':
        process_cashout(request.sid, int(data['panel_id']), game_state['multiplier'])

def start_game_loop_once():
    global game_loop_started
    with loop_lock:
        if not game_loop_started:
            game_loop_started = True
            socketio.start_background_task(target=game_loop)


# CASINO
# ... [Keep your existing app initialization and database code] ...

@app.route('/casino')
def casino():
    return render_template('casino.html')

# Wheel multipliers with controlled probabilities to protect system reserves
SEGMENT_OPTIONS = [
    {"index": 0,  "multiplier": 10.0, "weight": 2},   # High multiplier (rare)
    {"index": 1,  "multiplier": 0.1,  "weight": 25},  # Low payout (frequent)
    {"index": 2,  "multiplier": 2.0,  "weight": 10},
    {"index": 3,  "multiplier": 0.5,  "weight": 20},
    {"index": 4,  "multiplier": 5.0,  "weight": 4},
    {"index": 5,  "multiplier": 0.0,  "weight": 15},  # Zero payout
    {"index": 6,  "multiplier": 1.5,  "weight": 12},
    {"index": 7,  "multiplier": 0.2,  "weight": 20},
    {"index": 8,  "multiplier": 3.0,  "weight": 6},
    {"index": 9,  "multiplier": 0.8,  "weight": 15},
    {"index": 10, "multiplier": 10.0, "weight": 2},   # High multiplier (rare)
    {"index": 11, "multiplier": 0.1,  "weight": 25}
]

@app.route('/api/casino/spin', methods=['POST'])
def casino_spin():
    data = request.get_json() or {}
    mode = data.get('mode', 'demo')
    stake = 10.0  # Fixed 10 Bob spin cost

    # Select winning segment based on weighted probability
    weights = [item['weight'] for item in SEGMENT_OPTIONS]
    selected_item = random.choices(SEGMENT_OPTIONS, weights=weights, k=1)[0]
    
    multiplier = selected_item['multiplier']
    payout = stake * multiplier

    if mode == 'demo':
        # Demo mode logic (Handled on client-side state)
        return jsonify({
            'success': True,
            'segment_index': selected_item['index'],
            'multiplier': multiplier,
            'payout': payout,
            'new_balance': 1000.0  # Dummy returning reference
        })

    # Real Money Mode Logic
    phone = session.get("user_phone")
    if not phone:
        return jsonify({'error': 'Please log in to play with real money.'}), 401

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Query latest user balance
    cursor.execute("SELECT balance FROM users WHERE phone = ?", (phone,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': 'User not found.'}), 404

    current_balance = float(row[0])

    if current_balance < stake:
        conn.close()
        return jsonify({'error': 'Insufficient balance for KES 10 stake.'}), 400

    # Deduct stake and add payout
    new_balance = current_balance - stake + payout

    cursor.execute("UPDATE users SET balance = ? WHERE phone = ?", (new_balance, phone))
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'segment_index': selected_item['index'],
        'multiplier': multiplier,
        'payout': payout,
        'new_balance': new_balance
    })

@app.route('/jackpot')
def jackpot():
    return render_template('jackpot.html')

@app.route('/crash')
def crash():
    return render_template('crash.html')

if __name__ == "__main__":
    start_game_loop_once()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=False)