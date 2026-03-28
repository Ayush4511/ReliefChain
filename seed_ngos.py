"""One-time script to seed 6 NGO Partners into the campaigns table."""
import sqlite3

db = sqlite3.connect('database.db')
db.row_factory = sqlite3.Row
c = db.cursor()

ngos = [
    ('PM-CARES Fund', 'Government emergency relief fund for disaster response across India', 50000000, 32500000, 18500, 'Pan India', 'Emergency Relief', 'active', '🏛️'),
    ('Goonj', 'Disaster relief, livelihood support and rural development across India', 10000000, 6200000, 4200, 'Pan India', 'Disaster Relief', 'active', '👕'),
    ('CARE India', 'Health, women empowerment and humanitarian aid for vulnerable communities', 25000000, 18700000, 9800, 'Pan India', 'Health', 'active', '❤️'),
    ('HelpAge India', 'Elderly care, pension support and healthcare for senior citizens', 8000000, 4100000, 3200, 'Pan India', 'Elderly Care', 'active', '🧓'),
    ('SEEDS India', 'Disaster preparedness, resilience building and community recovery programs', 6000000, 2800000, 1500, 'Pan India', 'Disaster Preparedness', 'active', '🌱'),
    ('CRY', 'Child rights, education and protection for underprivileged children', 12000000, 7600000, 5400, 'Pan India', 'Child Rights', 'active', '👶'),
]

for ngo in ngos:
    c.execute("SELECT id FROM campaigns WHERE name=?", (ngo[0],))
    if not c.fetchone():
        c.execute("INSERT INTO campaigns (name, description, target_amount, raised_amount, beneficiary_count, region, category, status, image_icon) VALUES (?,?,?,?,?,?,?,?,?)", ngo)
        print(f"  ✅ Seeded: {ngo[0]}")
    else:
        print(f"  ⏭️ Already exists: {ngo[0]}")

db.commit()
db.close()
print("\\n🎉 All NGO partners are now in the database!")
