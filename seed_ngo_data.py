import sqlite3
import random
import time
import hashlib
from datetime import datetime, timedelta

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def seed_ngo_details():
    db = get_db()
    c = db.cursor()
    
    # 1. Get all the 6 NGO campaigns we seeded earlier by name
    ngo_names = ('PM-CARES Fund', 'Goonj', 'CARE India', 'HelpAge India', 'SEEDS India', 'CRY')
    query = f"SELECT id, name FROM campaigns WHERE name IN {ngo_names}"
    c.execute(query)
    ngos = c.fetchall()
    
    if not ngos:
        print("No NGOs found. Run seed_ngos.py first.")
        return

    # List of Indian names for realism
    first_names = ["Rahul", "Priya", "Amit", "Neha", "Vikram", "Anjali", "Rohan", "Sneha", "Karan", "Pooja", "Arjun", "Kavita", "Suresh", "Sunita", "Raj"]
    last_names = ["Sharma", "Patel", "Kumar", "Singh", "Gupta", "Mehta", "Reddy", "Rao", "Desai", "Jain", "Das", "Bose", "Nair", "Iyer"]
    states = ["Maharashtra", "Kerala", "Assam", "Odisha", "Bihar", "Gujarat", "Karnataka", "Tamil Nadu", "West Bengal", "Delhi"]
    methods = ["UPI", "Credit Card", "Net Banking", "Crypto"]

    donations_added = 0
    beneficiaries_added = 0

    for ngo in ngos:
        campaign_id = ngo['id']
        campaign_name = ngo['name']
        
        # Add 5-12 random recent donations for each NGO
        num_donations = random.randint(5, 12)
        for _ in range(num_donations):
            donor_name = f"{random.choice(first_names)} {random.choice(last_names)}"
            amount = random.randint(10, 500) * 100
            method = random.choice(methods)
            
            # Random time in the last 7 days
            days_ago = random.randint(0, 7)
            hours_ago = random.randint(0, 23)
            mins_ago = random.randint(0, 59)
            dt = datetime.now() - timedelta(days=days_ago, hours=hours_ago, minutes=mins_ago)
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            
            tx_id = f"TX{random.randint(100000, 999999)}"
            
            c.execute("""
                INSERT INTO donations (tx_id, donor_name, amount, campaign_id, payment_method, status, timestamp)
                VALUES (?, ?, ?, ?, ?, 'completed', ?)
            """, (tx_id, donor_name, amount, campaign_id, method, timestamp))
            
            # Let's add it to the ledger too so it shows up as verified
            block_hash = hashlib.sha256(f"{tx_id}{amount}{timestamp}".encode()).hexdigest()
            c.execute("""
                INSERT INTO ledger (block_number, transaction_type, amount, from_entity, to_entity, campaign, tx_id, hash, prev_hash)
                VALUES (?, 'donation', ?, ?, 'Pending Assignment', ?, ?, ?, ?)
            """, (random.randint(20, 100), amount, donor_name, campaign_name, tx_id, f"0x{block_hash[:60]}", "0x00000000000000000000"))
            
            donations_added += 1

        # Add 3-8 random verified beneficiaries for each NGO
        num_bens = random.randint(3, 8)
        for _ in range(num_bens):
            ben_name = f"{random.choice(first_names)} {random.choice(last_names)}"
            phone = f"+91 {random.randint(6000000000, 9999999999)}"
            aadhaar = f"{random.randint(2000, 9999)} {random.randint(1000, 9999)} {random.randint(1000, 9999)}"
            state = random.choice(states)
            trust_score = random.randint(85, 99)
            allocated = random.randint(2, 25) * 1000
            
            c.execute("""
                INSERT INTO beneficiaries (name, aadhaar, phone, state, trust_score, aid_amount, status, campaign_id)
                VALUES (?, ?, ?, ?, ?, ?, 'verified', ?)
            """, (ben_name, aadhaar, phone, state, trust_score, allocated, campaign_id))
            
            beneficiaries_added += 1

    db.commit()
    print(f"✅ Successfully added {donations_added} donations and {beneficiaries_added} beneficiaries across {len(ngos)} NGOs!")

if __name__ == '__main__':
    seed_ngo_details()
