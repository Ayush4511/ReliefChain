import sqlite3
import hashlib
import os
import time
import random
import threading
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, g, session, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = 'reliefchain_hackathon_2024_secret'
app.config['SESSION_TYPE'] = 'filesystem'
DATABASE = 'database.db'

socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

from datetime import datetime as _dt
@app.context_processor
def inject_now():
    return {'now': _dt.now}

# ─────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def get_direct_db():
    db = sqlite3.connect(DATABASE, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db

# ─────────────────────────────────────────────
# INIT DB
# ─────────────────────────────────────────────
def init_db():
    with app.app_context():
        db = get_db()
        c = db.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'donor',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            target_amount INTEGER DEFAULT 1000000,
            raised_amount INTEGER DEFAULT 0,
            beneficiary_count INTEGER DEFAULT 0,
            region TEXT,
            category TEXT,
            status TEXT DEFAULT 'active',
            image_icon TEXT DEFAULT '🌊',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_id TEXT UNIQUE NOT NULL,
            donor_name TEXT NOT NULL,
            donor_email TEXT,
            amount INTEGER NOT NULL,
            campaign_id INTEGER,
            beneficiary TEXT,
            status TEXT DEFAULT 'completed',
            transaction_hash TEXT,
            payment_method TEXT DEFAULT 'UPI',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS beneficiaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            aadhaar TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            state TEXT,
            trust_score INTEGER DEFAULT 50,
            status TEXT DEFAULT 'pending',
            campaign_id INTEGER,
            aid_amount INTEGER DEFAULT 0,
            flagged INTEGER DEFAULT 0,
            flag_reason TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            block_number INTEGER NOT NULL,
            transaction_type TEXT DEFAULT 'donation',
            amount INTEGER NOT NULL,
            from_entity TEXT,
            to_entity TEXT,
            campaign TEXT,
            tx_id TEXT,
            hash TEXT NOT NULL,
            prev_hash TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            performed_by TEXT DEFAULT 'system',
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        db.commit()

        # Seed admin user
        c.execute("SELECT id FROM users WHERE email='admin@reliefchain.in'")
        if not c.fetchone():
            c.execute("INSERT INTO users (name, email, phone, password, role) VALUES (?,?,?,?,?)",
                      ('Admin ReliefChain', 'admin@reliefchain.in', '9000000000',
                       hashlib.sha256('admin123'.encode()).hexdigest(), 'admin'))

        # Seed campaigns
        c.execute("SELECT COUNT(*) as cnt FROM campaigns")
        if c.fetchone()['cnt'] == 0:
            campaigns = [
                ('Kerala Flood Relief 2024', 'Emergency relief for flood victims in Kerala covering food, shelter & medical aid', 5000000, 3421000, 1240, 'Kerala', 'Flood', 'active', '🌊'),
                ('Nepal Earthquake Fund', 'Rebuilding homes and hospitals after the devastating earthquake in Nepal', 8000000, 5870000, 2100, 'Nepal', 'Earthquake', 'active', '🏔️'),
                ('Odisha Cyclone Response', 'Immediate aid and recovery operations for cyclone-affected coastal areas', 3000000, 1980000, 780, 'Odisha', 'Cyclone', 'active', '🌀'),
                ('COVID Emergency India', 'Medical supplies, oxygen & food support for COVID-affected families', 10000000, 9200000, 5600, 'Pan India', 'Medical', 'active', '🏥'),
                ('Assam Drought Aid', 'Water purification & agricultural support for drought-hit Assam regions', 2000000, 450000, 320, 'Assam', 'Drought', 'active', '🌾'),
                ('Uttarakhand Landslide Relief', 'Rescue, evacuation & rehabilitation for landslide victims', 4000000, 4000000, 980, 'Uttarakhand', 'Landslide', 'completed', '⛰️'),
            ]
            for camp in campaigns:
                c.execute("INSERT INTO campaigns (name, description, target_amount, raised_amount, beneficiary_count, region, category, status, image_icon) VALUES (?,?,?,?,?,?,?,?,?)", camp)

        # Seed beneficiaries
        c.execute("SELECT COUNT(*) as cnt FROM beneficiaries")
        if c.fetchone()['cnt'] == 0:
            bens = [
                ('Ramesh Kumar', '234567890123', '9876543210', 'Thiruvananthapuram, Kerala', 'Kerala', 85, 'verified', 1, 12000, 0, None),
                ('Sunita Devi', '345678901234', '9765432109', 'Patna, Bihar', 'Bihar', 72, 'verified', 2, 8000, 0, None),
                ('Kiran Patel', '456789012345', '9654321098', 'Ahmedabad, Gujarat', 'Gujarat', 90, 'verified', 3, 15000, 0, None),
                ('Priya Sharma', '567890123456', '9543210987', 'Bhubaneswar, Odisha', 'Odisha', 45, 'pending', 1, 0, 0, None),
                ('Mohammed Ali', '678901234567', '9432109876', 'Hyderabad, Telangana', 'Telangana', 30, 'flagged', 4, 0, 1, 'Duplicate phone number'),
                ('Lakshmi Nair', '789012345678', '9321098765', 'Kochi, Kerala', 'Kerala', 88, 'verified', 1, 18000, 0, None),
                ('Arjun Singh', '890123456789', '9210987654', 'Jaipur, Rajasthan', 'Rajasthan', 60, 'verified', 5, 7500, 0, None),
                ('Meena Bai', '234567890123', '9999999999', 'Lucknow, UP', 'UP', 20, 'rejected', 2, 0, 1, 'Duplicate Aadhaar'),
            ]
            for b in bens:
                c.execute("INSERT INTO beneficiaries (name, aadhaar, phone, address, state, trust_score, status, campaign_id, aid_amount, flagged, flag_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?)", b)

        # Seed donations + ledger
        c.execute("SELECT COUNT(*) as cnt FROM donations")
        if c.fetchone()['cnt'] == 0:
            donors = [
                ('Ayush Sharma', 'ayush@gmail.com', 5000, 1, 'Ramesh Kumar', 'UPI'),
                ('Neha Verma', 'neha@gmail.com', 2500, 2, 'Sunita Devi', 'Card'),
                ('Rahul Mehta', 'rahul@gmail.com', 10000, 1, 'Lakshmi Nair', 'NetBanking'),
                ('Priya Joshi', 'priya@gmail.com', 3000, 3, 'Kiran Patel', 'UPI'),
                ('Amit Patel', 'amit@gmail.com', 7500, 4, 'Arjun Singh', 'Card'),
                ('Deepika Singh', 'deepika@gmail.com', 1500, 5, 'Ramesh Kumar', 'UPI'),
                ('Vikas Gupta', 'vikas@gmail.com', 20000, 2, 'Lakshmi Nair', 'NetBanking'),
                ('Anjali Roy', 'anjali@gmail.com', 4000, 3, 'Sunita Devi', 'Card'),
            ]
            block_num = 1
            prev_hash = '0' * 64
            for i, (dname, demail, amt, cid, beneficiary, pmethod) in enumerate(donors):
                ts_offset = -(len(donors) - i) * 3600 * 8
                ts = datetime.now() + timedelta(seconds=ts_offset)
                tx_id = f"RC-{int(time.time()) + i * 1000}"
                tx_data = f"{tx_id}{dname}{amt}{beneficiary}{ts.isoformat()}"
                tx_hash = hashlib.sha256(tx_data.encode()).hexdigest()

                c.execute("INSERT INTO donations (tx_id, donor_name, donor_email, amount, campaign_id, beneficiary, status, transaction_hash, payment_method, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (tx_id, dname, demail, amt, cid, beneficiary, 'completed', tx_hash, pmethod, ts.strftime('%Y-%m-%d %H:%M:%S')))

                c.execute("SELECT name FROM campaigns WHERE id=?", (cid,))
                camp_row = c.fetchone()
                camp_name = camp_row['name'] if camp_row else 'General'

                chain_data = f"{block_num}{tx_id}{amt}{prev_hash}"
                block_hash = hashlib.sha256(chain_data.encode()).hexdigest()
                c.execute("INSERT INTO ledger (block_number, transaction_type, amount, from_entity, to_entity, campaign, tx_id, hash, prev_hash, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (block_num, 'donation', amt, dname, beneficiary, camp_name, tx_id, block_hash, prev_hash, ts.strftime('%Y-%m-%d %H:%M:%S')))
                prev_hash = block_hash
                block_num += 1

            db.commit()

        # Seed audit logs
        c.execute("SELECT COUNT(*) as cnt FROM audit_log")
        if c.fetchone()['cnt'] == 0:
            logs = [
                ('beneficiary_verified', 'beneficiary', 1, 'admin@reliefchain.in', 'Approved Ramesh Kumar — trust score 85'),
                ('beneficiary_flagged', 'beneficiary', 5, 'system', 'Auto-flagged Mohammed Ali — duplicate phone'),
                ('donation_received', 'donation', 1, 'system', 'Donation ₹5000 from Ayush Sharma'),
                ('campaign_created', 'campaign', 1, 'admin@reliefchain.in', 'Created Kerala Flood Relief 2024'),
                ('fraud_detected', 'beneficiary', 8, 'system', 'Duplicate Aadhaar detected — Meena Bai rejected'),
            ]
            for log in logs:
                c.execute("INSERT INTO audit_log (action, entity_type, entity_id, performed_by, details) VALUES (?,?,?,?,?)", log)

        db.commit()

# ─────────────────────────────────────────────
# FRAUD DETECTION & TRUST SCORE
# ─────────────────────────────────────────────
def calculate_trust_score(aadhaar, phone, db_conn):
    score = 60  # base score
    c = db_conn.cursor()

    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE aadhaar=?", (aadhaar,))
    if c.fetchone()['cnt'] > 0:
        score -= 50

    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE phone=?", (phone,))
    if c.fetchone()['cnt'] > 0:
        score -= 30

    score += 20  # new user bonus

    return max(0, min(100, score))

def detect_fraud(aadhaar, phone, db_conn):
    c = db_conn.cursor()
    flags = []
    c.execute("SELECT name, aadhaar FROM beneficiaries WHERE aadhaar=?", (aadhaar,))
    dup = c.fetchone()
    if dup:
        flags.append(f"Duplicate Aadhaar — already registered as {dup['name']}")

    c.execute("SELECT name, phone FROM beneficiaries WHERE phone=?", (phone,))
    dup_phone = c.fetchone()
    if dup_phone:
        flags.append(f"Duplicate phone number — used by {dup_phone['name']}")

    return flags

# ─────────────────────────────────────────────
# LIVE DATA GENERATOR (background thread)
# ─────────────────────────────────────────────
DONOR_NAMES = ['Arjun Bhatia','Kavya Reddy','Siddharth Rao','Prisha Nair','Rohit Jain',
               'Ananya Iyer','Vikram Choudhary','Divya Menon','Aakash Tiwari','Shreya Gupta',
               'Manish Kapoor','Pooja Agarwal','Karthik Subramaniam','Riya Desai','Tarun Bhale']
BENEFICIARY_NAMES = ['Rajni Devi','Suresh Mandal','Ganga Bai','Hamid Sheikh','Lakshmi Pillai',
                     'Balram Yadav','Savita Kumari','Ratan Lal','Parveen Kumar','Sundar Rajan']
PAYMENT_METHODS = ['UPI', 'Card', 'NetBanking', 'Wallet']
AMOUNTS = [500, 1000, 1500, 2000, 2500, 3000, 5000, 7500, 10000]

live_block_counter = [9]  # mutable reference for thread

def live_data_generator():
    time.sleep(5)
    while True:
        try:
            db = get_direct_db()
            c = db.cursor()

            c.execute("SELECT id, name FROM campaigns WHERE status='active' ORDER BY RANDOM() LIMIT 1")
            camp = c.fetchone()
            if not camp:
                db.close()
                time.sleep(5)
                continue

            donor = random.choice(DONOR_NAMES)
            beneficiary = random.choice(BENEFICIARY_NAMES)
            amount = random.choice(AMOUNTS)
            pmethod = random.choice(PAYMENT_METHODS)
            tx_id = f"RC-{int(time.time())}-{random.randint(100,999)}"

            tx_data = f"{tx_id}{donor}{amount}{beneficiary}{datetime.now().isoformat()}"
            tx_hash = hashlib.sha256(tx_data.encode()).hexdigest()

            c.execute("INSERT INTO donations (tx_id, donor_name, donor_email, amount, campaign_id, beneficiary, status, transaction_hash, payment_method) VALUES (?,?,?,?,?,?,?,?,?)",
                      (tx_id, donor, f"{donor.lower().replace(' ','.')}@example.com", amount, camp['id'], beneficiary, 'completed', tx_hash, pmethod))

            live_block_counter[0] += 1
            block_num = live_block_counter[0]

            c.execute("SELECT hash FROM ledger ORDER BY block_number DESC LIMIT 1")
            prev_row = c.fetchone()
            prev_hash = prev_row['hash'] if prev_row else '0' * 64

            chain_data = f"{block_num}{tx_id}{amount}{prev_hash}"
            block_hash = hashlib.sha256(chain_data.encode()).hexdigest()

            c.execute("INSERT INTO ledger (block_number, transaction_type, amount, from_entity, to_entity, campaign, tx_id, hash, prev_hash) VALUES (?,?,?,?,?,?,?,?,?)",
                      (block_num, 'donation', amount, donor, beneficiary, camp['name'], tx_id, block_hash, prev_hash))

            c.execute("UPDATE campaigns SET raised_amount=raised_amount+?, beneficiary_count=beneficiary_count+1 WHERE id=?",
                      (amount, camp['id']))

            db.commit()

            # Emit via websocket
            with app.app_context():
                socketio.emit('new_donation', {
                    'tx_id': tx_id,
                    'donor': donor,
                    'amount': amount,
                    'campaign': camp['name'],
                    'beneficiary': beneficiary,
                    'hash': block_hash[:20] + '...',
                    'full_hash': block_hash,
                    'block': block_num,
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'method': pmethod
                })

            # Get updated totals
            c.execute("SELECT SUM(amount) as total, COUNT(*) as cnt FROM donations")
            row = c.fetchone()
            socketio.emit('dashboard_update', {
                'total_donations': int(row['total'] or 0),
                'total_txns': int(row['cnt'] or 0),
            })

            db.close()
        except Exception as e:
            print(f"[LiveGen Error] {e}")
        time.sleep(random.randint(4, 6))

# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
# PUBLIC ROUTES
# ─────────────────────────────────────────────
@app.route('/')
def index():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT SUM(amount) as total, COUNT(*) as cnt FROM donations")
    row = c.fetchone()
    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE status='verified'")
    ben_verified = c.fetchone()['cnt']
    return render_template('cinematic.html',
                           total_donations=int(row['total'] or 0),
                           total_txns=int(row['cnt'] or 0),
                           ben_verified=ben_verified)

@app.route('/home')
def home():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT SUM(amount) as total, COUNT(*) as cnt FROM donations")
    row = c.fetchone()
    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE status='verified'")
    ben_verified = c.fetchone()['cnt']
    c.execute("SELECT * FROM campaigns WHERE status='active' LIMIT 3")
    featured_campaigns = c.fetchall()
    c.execute("SELECT * FROM donations ORDER BY timestamp DESC LIMIT 5")
    recent = c.fetchall()
    return render_template('index.html',
                           total_donations=int(row['total'] or 0),
                           total_txns=int(row['cnt'] or 0),
                           ben_verified=ben_verified,
                           featured_campaigns=featured_campaigns,
                           recent_donations=recent)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        hashed = hashlib.sha256(password.encode()).hexdigest()
        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, hashed))
        user = c.fetchone()
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'beneficiary':
                return redirect(url_for('beneficiary_profile'))
            return redirect(url_for('donor_profile'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'donor')
        hashed = hashlib.sha256(password.encode()).hexdigest()
        db = get_db()
        c = db.cursor()
        try:
            c.execute("INSERT INTO users (name, email, phone, password, role) VALUES (?,?,?,?,?)",
                      (name, email, phone, hashed, role))
            db.commit()
            flash('Account created! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered.', 'error')
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/donate', methods=['GET', 'POST'])
def donate():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM campaigns WHERE status='active'")
    campaigns = c.fetchall()
    if request.method == 'POST':
        donor_name = request.form.get('name', '').strip()
        donor_email = request.form.get('email', '').strip()
        amount = int(request.form.get('amount', 0))
        campaign_id = int(request.form.get('campaign_id', 1))
        pmethod = request.form.get('payment_method', 'UPI')

        if amount <= 0:
            flash('Please enter a valid amount.', 'error')
            return redirect(url_for('donate'))

        tx_id = f"RC-{int(time.time())}"
        c.execute("SELECT name FROM campaigns WHERE id=?", (campaign_id,))
        camp = c.fetchone()
        camp_name = camp['name'] if camp else 'General'

        c.execute("SELECT name FROM beneficiaries WHERE status='verified' AND campaign_id=? ORDER BY RANDOM() LIMIT 1", (campaign_id,))
        ben = c.fetchone()
        beneficiary = ben['name'] if ben else 'General Fund Beneficiary'

        tx_data = f"{tx_id}{donor_name}{amount}{beneficiary}{datetime.now().isoformat()}"
        tx_hash = hashlib.sha256(tx_data.encode()).hexdigest()

        c.execute("INSERT INTO donations (tx_id, donor_name, donor_email, amount, campaign_id, beneficiary, status, transaction_hash, payment_method) VALUES (?,?,?,?,?,?,?,?,?)",
                  (tx_id, donor_name, donor_email, amount, campaign_id, beneficiary, 'completed', tx_hash, pmethod))

        c.execute("SELECT MAX(block_number) as maxb FROM ledger")
        maxb = c.fetchone()['maxb'] or 0
        block_num = maxb + 1
        c.execute("SELECT hash FROM ledger ORDER BY block_number DESC LIMIT 1")
        prev_row = c.fetchone()
        prev_hash = prev_row['hash'] if prev_row else '0' * 64
        chain_data = f"{block_num}{tx_id}{amount}{prev_hash}"
        block_hash = hashlib.sha256(chain_data.encode()).hexdigest()

        c.execute("INSERT INTO ledger (block_number, transaction_type, amount, from_entity, to_entity, campaign, tx_id, hash, prev_hash) VALUES (?,?,?,?,?,?,?,?,?)",
                  (block_num, 'donation', amount, donor_name, beneficiary, camp_name, tx_id, block_hash, prev_hash))
        c.execute("UPDATE campaigns SET raised_amount=raised_amount+? WHERE id=?", (amount, campaign_id))
        c.execute("INSERT INTO audit_log (action, entity_type, entity_id, performed_by, details) VALUES (?,?,?,?,?)",
                  ('donation_received', 'donation', campaign_id, donor_name, f"₹{amount} donated to {camp_name}"))
        db.commit()

        flash(f'✅ Donation Successful! TX ID: {tx_id}', 'success')
        return redirect(url_for('track_donation', tx_id=tx_id))
    return render_template('donate.html', campaigns=campaigns)

@app.route('/campaigns')
def campaigns():
    q = request.args.get('q', '').strip()
    db = get_db()
    c = db.cursor()
    if q:
        c.execute("SELECT * FROM campaigns WHERE name LIKE ? OR description LIKE ? ORDER BY status DESC, raised_amount DESC", (f"%{q}%", f"%{q}%"))
    else:
        c.execute("SELECT * FROM campaigns ORDER BY status DESC, raised_amount DESC")
    all_campaigns = c.fetchall()
    return render_template('campaigns.html', campaigns=all_campaigns, search_q=q)

@app.route('/fund/<path:name>')
def fund_by_name(name):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id FROM campaigns WHERE name LIKE ? OR category LIKE ? LIMIT 1", (f"%{name}%", f"%{name}%"))
    row = c.fetchone()
    if row:
        return redirect(url_for('campaign_detail', cid=row['id']))
    else:
        # Fallback to campaigns search if specific fund not matched exactly
        return redirect(url_for('campaigns', q=name))

@app.route('/campaign/<int:cid>')
def campaign_detail(cid):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM campaigns WHERE id=?", (cid,))
    campaign = c.fetchone()
    if not campaign:
        flash('Campaign not found.', 'error')
        return redirect(url_for('campaigns'))
    c.execute("SELECT * FROM donations WHERE campaign_id=? ORDER BY timestamp DESC LIMIT 20", (cid,))
    donations = c.fetchall()
    c.execute("SELECT * FROM beneficiaries WHERE campaign_id=? AND status='verified' LIMIT 10", (cid,))
    beneficiaries = c.fetchall()
    pct = int((campaign['raised_amount'] / campaign['target_amount']) * 100) if campaign['target_amount'] > 0 else 0
    return render_template('campaign_detail.html', campaign=campaign, donations=donations,
                           beneficiaries=beneficiaries, pct=min(pct, 100))

@app.route('/disasters')
def disasters():
    # Simulated live disaster alerts
    alerts = [
        {'type': 'Flood', 'location': 'Alappuzha, Kerala', 'severity': 'High', 'icon': '🌊', 'since': '2 days', 'affected': 12400},
        {'type': 'Cyclone Warning', 'location': 'Puri, Odisha', 'severity': 'Critical', 'icon': '🌀', 'since': '6 hours', 'affected': 45000},
        {'type': 'Earthquake', 'location': 'Kathmandu, Nepal', 'severity': 'High', 'icon': '🏔️', 'since': '1 day', 'affected': 8700},
        {'type': 'Drought', 'location': 'Vidarbha, Maharashtra', 'severity': 'Medium', 'icon': '🌾', 'since': '3 weeks', 'affected': 230000},
        {'type': 'Landslide', 'location': 'Chamoli, Uttarakhand', 'severity': 'High', 'icon': '⛰️', 'since': '12 hours', 'affected': 3200},
        {'type': 'Heat Wave', 'location': 'Rajasthan (Multiple Districts)', 'severity': 'Medium', 'icon': '🌡️', 'since': '5 days', 'affected': 890000},
    ]
    return render_template('disasters.html', alerts=alerts)

@app.route('/public-dashboard')
def public_dashboard():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT SUM(amount) as total, COUNT(*) as cnt FROM donations")
    row = c.fetchone()
    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE status='verified'")
    ben_verified = c.fetchone()['cnt']
    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE flagged=1")
    fraud_cases = c.fetchone()['cnt']
    c.execute("SELECT * FROM campaigns WHERE status='active'")
    active_campaigns = c.fetchall()
    c.execute("SELECT * FROM donations ORDER BY timestamp DESC LIMIT 10")
    recent = c.fetchall()
    c.execute("SELECT state, SUM(aid_amount) as total, COUNT(*) as cnt FROM beneficiaries GROUP BY state ORDER BY total DESC")
    region_data = c.fetchall()

    # Chart data
    c.execute("SELECT DATE(timestamp) as d, SUM(amount) as s FROM donations GROUP BY DATE(timestamp) ORDER BY d DESC LIMIT 7")
    chart_rows = c.fetchall()
    chart_labels = [r['d'] for r in reversed(chart_rows)]
    chart_data = [int(r['s']) for r in reversed(chart_rows)]

    # Campaign pie data
    c.execute("SELECT name, raised_amount FROM campaigns WHERE status='active'")
    pie_rows = c.fetchall()
    pie_labels = [r['name'][:20] for r in pie_rows]
    pie_data = [int(r['raised_amount']) for r in pie_rows]

    return render_template('public_dashboard.html',
                           total_donations=int(row['total'] or 0),
                           total_txns=int(row['cnt'] or 0),
                           ben_verified=ben_verified,
                           fraud_cases=fraud_cases,
                           active_campaigns=active_campaigns,
                           recent_donations=recent,
                           region_data=region_data,
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           pie_labels=pie_labels,
                           pie_data=pie_data)

@app.route('/ledger')
def ledger():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM ledger ORDER BY block_number DESC LIMIT 50")
    blocks = c.fetchall()
    return render_template('ledger.html', blocks=blocks)

@app.route('/transaction/<tx_id>')
def transaction_detail(tx_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM donations WHERE tx_id=?", (tx_id,))
    donation = c.fetchone()
    c.execute("SELECT * FROM ledger WHERE tx_id=?", (tx_id,))
    ledger_entry = c.fetchone()
    return render_template('transaction_detail.html', donation=donation, ledger_entry=ledger_entry, tx_id=tx_id)

@app.route('/hash-viewer', methods=['GET', 'POST'])
def hash_viewer():
    result = None
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM ledger WHERE tx_id=? OR hash LIKE ?", (query, f"{query}%"))
        result = c.fetchone()
    return render_template('hash_viewer.html', result=result)

@app.route('/track', methods=['GET', 'POST'])
def track_donation():
    tx_id = request.args.get('tx_id') or (request.form.get('tx_id') if request.method == 'POST' else None)
    donation = None
    ledger_entry = None
    if tx_id:
        db = get_db()
        c = db.cursor()
        c.execute("""SELECT d.*, c.name as campaign_name FROM donations d 
                     LEFT JOIN campaigns c ON d.campaign_id=c.id WHERE d.tx_id=?""", (tx_id,))
        donation = c.fetchone()
        c.execute("SELECT * FROM ledger WHERE tx_id=?", (tx_id,))
        ledger_entry = c.fetchone()
        if request.method == 'POST' and not donation:
            flash('Transaction ID not found.', 'error')
    return render_template('track_donation.html', donation=donation, ledger_entry=ledger_entry, tx_id=tx_id)

@app.route('/analytics')
def analytics():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT DATE(timestamp) as d, SUM(amount) as s, COUNT(*) as cnt FROM donations GROUP BY DATE(timestamp) ORDER BY d ASC")
    daily = c.fetchall()
    c.execute("SELECT c.name, SUM(d.amount) as total FROM donations d JOIN campaigns c ON d.campaign_id=c.id GROUP BY c.id")
    by_campaign = c.fetchall()
    c.execute("SELECT b.state, SUM(b.aid_amount) as total FROM beneficiaries b WHERE b.state IS NOT NULL GROUP BY b.state ORDER BY total DESC")
    by_region = c.fetchall()
    c.execute("SELECT payment_method, COUNT(*) as cnt, SUM(amount) as total FROM donations GROUP BY payment_method")
    by_payment = c.fetchall()
    return render_template('analytics.html', daily=daily, by_campaign=by_campaign,
                           by_region=by_region, by_payment=by_payment)

@app.route('/region-map')
def region_map():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT b.state, COUNT(*) as ben_count, SUM(b.aid_amount) as aid_total, COUNT(CASE WHEN b.flagged=1 THEN 1 END) as fraud_count FROM beneficiaries b GROUP BY b.state")
    regions = c.fetchall()
    c.execute("SELECT c.region, SUM(d.amount) as donated FROM donations d JOIN campaigns c ON d.campaign_id=c.id GROUP BY c.region")
    campaign_regions = c.fetchall()
    return render_template('region_map.html', regions=regions, campaign_regions=campaign_regions)

@app.route('/impact', methods=['GET', 'POST'])
def impact():
    donation = None
    tx_id = request.form.get('tx_id') if request.method == 'POST' else request.args.get('tx_id')
    if tx_id:
        db = get_db()
        c = db.cursor()
        c.execute("""SELECT d.*, c.name as campaign_name, c.category, c.region FROM donations d
                     LEFT JOIN campaigns c ON d.campaign_id=c.id WHERE d.tx_id=?""", (tx_id,))
        donation = c.fetchone()
        if not donation:
            flash('Donation not found.', 'error')
    return render_template('impact.html', donation=donation)

@app.route('/ngos')
def ngos():
    partners = [
        {'name': 'PM-CARES Fund', 'type': 'Government', 'focus': 'Emergency Relief', 'certified': True},
        {'name': 'Goonj', 'type': 'NGO', 'focus': 'Disaster Relief, Livelihood', 'certified': True},
        {'name': 'CARE India', 'type': 'International NGO', 'focus': 'Health, Women Empowerment', 'certified': True},
        {'name': 'HelpAge India', 'type': 'NGO', 'focus': 'Elderly Care', 'certified': True},
        {'name': 'SEEDS India', 'type': 'NGO', 'focus': 'Disaster Preparedness', 'certified': True},
        {'name': 'CRY', 'type': 'NGO', 'focus': 'Child Rights', 'certified': True},
    ]
    return render_template('ngos.html', partners=partners)

# ─────────────────────────────────────────────
# DONOR ROUTES (login required)
# ─────────────────────────────────────────────
@app.route('/profile')
@login_required
def donor_profile():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user = c.fetchone()
    c.execute("SELECT d.*, c.name as campaign_name FROM donations d LEFT JOIN campaigns c ON d.campaign_id=c.id WHERE d.donor_email=? ORDER BY d.timestamp DESC LIMIT 10",
              (session.get('user_email', ''),))
    my_donations = c.fetchall()
    total = sum(d['amount'] for d in my_donations)
    return render_template('donor_profile.html', user=user, my_donations=my_donations, total=total)

@app.route('/donation-history')
@login_required
def donation_history():
    db = get_db()
    c = db.cursor()
    page = int(request.args.get('page', 1))
    per_page = 15
    offset = (page - 1) * per_page
    c.execute("SELECT d.*, c.name as campaign_name FROM donations d LEFT JOIN campaigns c ON d.campaign_id=c.id WHERE d.donor_email=? ORDER BY d.timestamp DESC LIMIT ? OFFSET ?",
              (session.get('user_email', ''), per_page, offset))
    donations = c.fetchall()
    c.execute("SELECT COUNT(*) as cnt FROM donations WHERE donor_email=?", (session.get('user_email', ''),))
    total_rows = c.fetchone()['cnt']
    total_pages = (total_rows + per_page - 1) // per_page
    return render_template('donation_history.html', donations=donations, page=page,
                           total_pages=total_pages, total_rows=total_rows)

# ─────────────────────────────────────────────
# BENEFICIARY ROUTES
# ─────────────────────────────────────────────
@app.route('/beneficiary/register', methods=['GET', 'POST'])
def beneficiary_register():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM campaigns WHERE status='active'")
    campaigns = c.fetchall()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        aadhaar = request.form.get('aadhaar', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        state = request.form.get('state', '').strip()
        campaign_id = int(request.form.get('campaign_id', 1))

        trust_score = calculate_trust_score(aadhaar, phone, db)
        fraud_flags = detect_fraud(aadhaar, phone, db)
        flagged = 1 if fraud_flags else 0
        flag_reason = '; '.join(fraud_flags) if fraud_flags else None
        status = 'flagged' if flagged else 'pending'

        c.execute("INSERT INTO beneficiaries (name, aadhaar, phone, address, state, trust_score, status, campaign_id, flagged, flag_reason) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (name, aadhaar, phone, address, state, trust_score, status, campaign_id, flagged, flag_reason))
        db.commit()
        c.execute("INSERT INTO audit_log (action, entity_type, performed_by, details) VALUES (?,?,?,?)",
                  ('beneficiary_registered', 'beneficiary', name, f"Trust Score: {trust_score} | {'⚠️ FLAGGED: ' + flag_reason if flagged else 'Clean'}"))
        db.commit()

        if flagged:
            flash(f'⚠️ Registration submitted but flagged: {flag_reason}', 'error')
        else:
            flash(f'✅ Registered successfully. Trust Score: {trust_score}/100. Pending verification.', 'success')
        return redirect(url_for('beneficiary_status'))
    return render_template('beneficiary_register.html', campaigns=campaigns)

@app.route('/beneficiary/profile')
def beneficiary_profile():
    aadhaar = request.args.get('aadhaar', '')
    db = get_db()
    c = db.cursor()
    ben = None
    if aadhaar:
        c.execute("SELECT b.*, c.name as campaign_name FROM beneficiaries b LEFT JOIN campaigns c ON b.campaign_id=c.id WHERE b.aadhaar=?", (aadhaar,))
        ben = c.fetchone()
    return render_template('beneficiary_profile.html', ben=ben)

@app.route('/beneficiary/status', methods=['GET', 'POST'])
def beneficiary_status():
    ben = None
    if request.method == 'POST':
        aadhaar = request.form.get('aadhaar', '').strip()
        db = get_db()
        c = db.cursor()
        c.execute("SELECT b.*, c.name as campaign_name FROM beneficiaries b LEFT JOIN campaigns c ON b.campaign_id=c.id WHERE b.aadhaar=?", (aadhaar,))
        ben = c.fetchone()
        if not ben:
            flash('No beneficiary found with that Aadhaar.', 'error')
    return render_template('aid_status.html', ben=ben)

# ─────────────────────────────────────────────
# ADMIN ROUTES
# ─────────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        hashed = hashlib.sha256(password.encode()).hexdigest()
        db = get_db()
        c = db.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND password=? AND role='admin'", (email, hashed))
        admin = c.fetchone()
        if admin:
            session['user_id'] = admin['id']
            session['user_name'] = admin['name']
            session['user_email'] = admin['email']
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT SUM(amount) as total, COUNT(*) as cnt FROM donations")
    stats = c.fetchone()
    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE status='verified'")
    ben_v = c.fetchone()['cnt']
    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE flagged=1")
    fraud = c.fetchone()['cnt']
    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE status='pending'")
    pending = c.fetchone()['cnt']
    c.execute("SELECT * FROM donations ORDER BY timestamp DESC LIMIT 10")
    recent = c.fetchall()
    c.execute("SELECT * FROM campaigns")
    all_campaigns = c.fetchall()
    c.execute("SELECT DATE(timestamp) as d, SUM(amount) as s FROM donations GROUP BY DATE(timestamp) ORDER BY d ASC LIMIT 14")
    chart_rows = c.fetchall()
    chart_labels = [r['d'] for r in chart_rows]
    chart_data = [int(r['s']) for r in chart_rows]
    c.execute("SELECT * FROM beneficiaries WHERE flagged=1 ORDER BY created_at DESC LIMIT 5")
    flagged = c.fetchall()
    return render_template('admin_dashboard.html',
                           total_donations=int(stats['total'] or 0),
                           total_txns=int(stats['cnt'] or 0),
                           ben_verified=ben_v, fraud_count=fraud, pending_count=pending,
                           recent_donations=recent, campaigns=all_campaigns,
                           chart_labels=chart_labels, chart_data=chart_data,
                           flagged_beneficiaries=flagged)

@app.route('/admin/donations')
@admin_required
def manage_donations():
    db = get_db()
    c = db.cursor()
    status_filter = request.args.get('status', 'all')
    if status_filter != 'all':
        c.execute("SELECT d.*, c.name as campaign_name FROM donations d LEFT JOIN campaigns c ON d.campaign_id=c.id WHERE d.status=? ORDER BY d.timestamp DESC", (status_filter,))
    else:
        c.execute("SELECT d.*, c.name as campaign_name FROM donations d LEFT JOIN campaigns c ON d.campaign_id=c.id ORDER BY d.timestamp DESC")
    donations = c.fetchall()
    return render_template('manage_donations.html', donations=donations, status_filter=status_filter)

@app.route('/admin/beneficiaries')
@admin_required
def verify_beneficiaries():
    db = get_db()
    c = db.cursor()
    status_filter = request.args.get('status', 'pending')
    c.execute("SELECT b.*, c.name as campaign_name FROM beneficiaries b LEFT JOIN campaigns c ON b.campaign_id=c.id WHERE b.status=? ORDER BY b.created_at DESC", (status_filter,))
    beneficiaries = c.fetchall()
    return render_template('verify_beneficiaries.html', beneficiaries=beneficiaries, status_filter=status_filter)

@app.route('/admin/verify-action', methods=['POST'])
@admin_required
def verify_action():
    ben_id = int(request.form.get('ben_id'))
    action = request.form.get('action')
    db = get_db()
    c = db.cursor()
    if action == 'approve':
        c.execute("UPDATE beneficiaries SET status='verified' WHERE id=?", (ben_id,))
        c.execute("INSERT INTO audit_log (action, entity_type, entity_id, performed_by, details) VALUES (?,?,?,?,?)",
                  ('beneficiary_verified', 'beneficiary', ben_id, session.get('user_email'), 'Manually approved'))
    elif action == 'reject':
        c.execute("UPDATE beneficiaries SET status='rejected' WHERE id=?", (ben_id,))
        c.execute("INSERT INTO audit_log (action, entity_type, entity_id, performed_by, details) VALUES (?,?,?,?,?)",
                  ('beneficiary_rejected', 'beneficiary', ben_id, session.get('user_email'), 'Manually rejected'))
    db.commit()
    flash(f'Beneficiary {action}d successfully.', 'success')
    return redirect(url_for('verify_beneficiaries'))

@app.route('/admin/fraud')
@admin_required
def fraud_detection():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM beneficiaries WHERE flagged=1 ORDER BY created_at DESC")
    flagged = c.fetchall()
    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE flagged=1")
    fraud_count = c.fetchone()['cnt']
    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries")
    total_ben = c.fetchone()['cnt']
    c.execute("SELECT aadhaar, COUNT(*) as cnt, GROUP_CONCAT(name, ', ') as names FROM beneficiaries GROUP BY aadhaar HAVING cnt > 1")
    dup_aadhaar = c.fetchall()
    c.execute("SELECT phone, COUNT(*) as cnt, GROUP_CONCAT(name, ', ') as names FROM beneficiaries GROUP BY phone HAVING cnt > 1")
    dup_phone = c.fetchall()
    return render_template('fraud_detection.html', flagged=flagged, fraud_count=fraud_count,
                           total_ben=total_ben, dup_aadhaar=dup_aadhaar, dup_phone=dup_phone)

@app.route('/admin/campaigns', methods=['GET', 'POST'])
@admin_required
def campaign_management():
    db = get_db()
    c = db.cursor()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        target = int(request.form.get('target_amount', 1000000))
        region = request.form.get('region', '')
        category = request.form.get('category', '')
        icon = request.form.get('image_icon', '🌊')
        c.execute("INSERT INTO campaigns (name, description, target_amount, region, category, image_icon) VALUES (?,?,?,?,?,?)",
                  (name, description, target, region, category, icon))
        db.commit()
        flash('Campaign created successfully!', 'success')
    c.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
    all_campaigns = c.fetchall()
    return render_template('campaign_management.html', campaigns=all_campaigns)

@app.route('/admin/campaign/toggle/<int:cid>')
@admin_required
def toggle_campaign(cid):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT status FROM campaigns WHERE id=?", (cid,))
    camp = c.fetchone()
    new_status = 'paused' if camp['status'] == 'active' else 'active'
    c.execute("UPDATE campaigns SET status=? WHERE id=?", (new_status, cid))
    db.commit()
    flash(f'Campaign {new_status}.', 'success')
    return redirect(url_for('campaign_management'))

@app.route('/admin/users')
@admin_required
def user_management():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = c.fetchall()
    return render_template('user_management.html', users=users)

@app.route('/admin/audit')
@admin_required
def audit_trail():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 100")
    logs = c.fetchall()
    return render_template('audit_trail.html', logs=logs)

# ─────────────────────────────────────────────
# API ENDPOINTS (JSON)
# ─────────────────────────────────────────────
@app.route('/api/dashboard')
def api_dashboard():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT SUM(amount) as total, COUNT(*) as cnt FROM donations")
    row = c.fetchone()
    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE status='verified'")
    ben_v = c.fetchone()['cnt']
    c.execute("SELECT COUNT(*) as cnt FROM beneficiaries WHERE flagged=1")
    fraud = c.fetchone()['cnt']
    c.execute("SELECT COUNT(*) as cnt FROM campaigns WHERE status='active'")
    active_camps = c.fetchone()['cnt']
    return jsonify({'total_donations': int(row['total'] or 0), 'total_txns': int(row['cnt'] or 0),
                    'verified_beneficiaries': ben_v, 'fraud_count': fraud, 'active_campaigns': active_camps})

@app.route('/api/campaigns')
def api_campaigns():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM campaigns")
    camps = [dict(r) for r in c.fetchall()]
    return jsonify(camps)

@app.route('/api/ledger')
def api_ledger():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM ledger ORDER BY block_number DESC LIMIT 20")
    blocks = [dict(r) for r in c.fetchall()]
    return jsonify(blocks)

@app.route('/api/donations')
def api_donations():
    db = get_db()
    c = db.cursor()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    offset = (page - 1) * per_page
    c.execute("SELECT d.*, c.name as campaign_name FROM donations d LEFT JOIN campaigns c ON d.campaign_id=c.id ORDER BY d.timestamp DESC LIMIT ? OFFSET ?",
              (per_page, offset))
    rows = [dict(r) for r in c.fetchall()]
    return jsonify(rows)

@app.route('/api/fraud-detection')
def api_fraud():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM beneficiaries WHERE flagged=1")
    flagged = [dict(r) for r in c.fetchall()]
    return jsonify(flagged)

@app.route('/api/impact-stats')
def api_impact():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT SUM(aid_amount) as total_aid, COUNT(*) as total_ben FROM beneficiaries WHERE status='verified'")
    row = c.fetchone()
    c.execute("SELECT COUNT(*) as cnt FROM campaigns WHERE status='completed'")
    completed = c.fetchone()['cnt']
    return jsonify({'total_aid': int(row['total_aid'] or 0), 'total_beneficiaries': int(row['total_ben'] or 0), 'completed_campaigns': completed})

@app.route('/api/disaster-alerts')
def api_alerts():
    alerts = [
        {'type': 'Flood', 'location': 'Alappuzha, Kerala', 'severity': 'High', 'affected': 12400},
        {'type': 'Cyclone', 'location': 'Puri, Odisha', 'severity': 'Critical', 'affected': 45000},
        {'type': 'Earthquake', 'location': 'Kathmandu, Nepal', 'severity': 'High', 'affected': 8700},
    ]
    return jsonify(alerts)

@app.route('/api/analytics')
def api_analytics():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT DATE(timestamp) as d, SUM(amount) as s FROM donations GROUP BY d ORDER BY d ASC LIMIT 30")
    daily = [{'date': r['d'], 'amount': int(r['s'])} for r in c.fetchall()]
    return jsonify({'daily': daily})

@socketio.on('connect')
def handle_connect():
    emit('connected', {'message': 'Connected to ReliefChain live feed'})

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    # Start live data thread
    # t = threading.Thread(target=live_data_generator, daemon=True)
    # t.start()
    socketio.run(app, debug=True, port=5000, use_reloader=False, allow_unsafe_werkzeug=True)
