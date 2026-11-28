import json, re, os, sys
from pathlib import Path
from datetime import date, datetime

ROOT = Path(r"C:\Users\PC\Desktop\Sou9na-Projet")
sys.path.insert(0, str(ROOT / "02-backend"))
envpath = ROOT / "02-backend" / ".env"
for line in envpath.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

import psycopg

# Region mapping (city -> region)
REGION_MAP = {
    "rabat": "rabat-sale-kenitra",
    "casablanca": "casa-settat",
    "tanger": "tanger-tetouan-al-hoceima",
    "fes": "fes-meknes",
    "marrakech": "marrakech-safi",
    "agadir": "souss-massa",
    "oujda": "oriental",
    "meknes": "fes-meknes",
    "tetouan": "tanger-tetouan-al-hoceima",
    "kenitra": "rabat-sale-kenitra",
    "sale": "rabat-sale-kenitra",
    "el jadida": "casa-settat",
    "mohammedia": "casa-settat",
    "beni mellal": "beni-mellal-khenifra",
    "errachidia": "draa-tafilalet",
    "ouarzazate": "draa-tafilalet",
    "laayoune": "laayoune-sakia-el-hamra",
    "dakhla": "dakhla-oued-ed-dahab",
    "guelmim": "guelmim-oued-noun",
    "settat": "casa-settat",
    "safi": "marrakech-safi",
    "essaouira": "marrakech-safi",
    "nador": "oriental",
    "taza": "fes-meknes",
    "khouribga": "beni-mellal-khenifra",
    "khemisset": "rabat-sale-kenitra",
    "berrechid": "casa-settat",
    "bouskoura": "casa-settat",
    "ain harrouda": "casa-settat",
}

def parse_amount(amount_str):
    """Extract montant_mad and caution_mad from amount string like '2 880 000,00 Caution provisoire (en DH) : 55 000,00'"""
    montant = 0
    caution = 0
    m = re.search(r'([\d\s]+,\d{2})', amount_str)
    if m:
        montant = int(m.group(1).replace(' ', '').replace(',', ''))
    cm = re.search(r'caution[^:]*:\s*([\d\s]+,\d{2})', amount_str, re.IGNORECASE)
    if cm:
        caution = int(cm.group(1).replace(' ', '').replace(',', ''))
    return montant, caution

def map_region(city):
    city_lower = city.lower().strip() if city else ''
    for key, region in REGION_MAP.items():
        if key in city_lower:
            return region
    return "casa-settat"  # default

# Load scraped data
scraped = json.load(open(ROOT / "tenders_scraped.json", encoding="utf-8"))
print(f"Loaded {len(scraped)} scraped tenders")

# Map to DB schema
tenders_to_insert = []
for item in scraped:
    ref = item.get("source_ref", "")
    if not ref:
        continue
    ref = ref.replace("portal:", "")
    montant, caution = parse_amount(item.get("amount", ""))
    deadline = item.get("deadline")
    if deadline:
        try:
            datetime.fromisoformat(deadline)
        except ValueError:
            deadline = None
    tenders_to_insert.append({
        "reference": ref,
        "organisme": item.get("buyer", "")[:200],
        "objet": item.get("title", "")[:500],
        "secteur": item.get("sector", "services").lower()[:50] or "services",
        "region": map_region(item.get("city", "")),
        "montant_mad": montant,
        "caution_mad": caution,
        "lots": [],
        "qualifications_exigees": [],
        "delai_jours": 90,
        "date_remise": deadline,
        "date_publication": date.today().isoformat(),
        "date_collecte": date.today().isoformat(),
        "statut": "ouvert",
        "source": "portail",
        "source_url": item.get("url", ""),
    })

# Insert into DB
conn = psycopg.connect(os.environ["DATABASE_URL"])
inserted = 0
with conn.cursor() as cur:
    for t in tenders_to_insert:
        # montant_mad must be > 0 (check constraint)
        if t["montant_mad"] <= 0:
            t["montant_mad"] = 1
        try:
            cur.execute("""
                INSERT INTO tenders (reference, organisme, objet, secteur, region, montant_mad, caution_mad,
                    lots, qualifications_exigees, delai_jours, date_remise, date_publication, date_collecte,
                    statut, source, source_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (reference) DO NOTHING
            """, (
                t["reference"], t["organisme"], t["objet"], t["secteur"], t["region"],
                t["montant_mad"], t["caution_mad"], t["lots"], t["qualifications_exigees"],
                t["delai_jours"], t["date_remise"], t["date_publication"], t["date_collecte"],
                t["statut"], t["source"], t["source_url"],
            ))
            inserted += cur.rowcount
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error inserting {t['reference']}: {e}")

with conn.cursor() as cur:
    cur.execute("SELECT count(*) FROM tenders")
    total = cur.fetchone()[0]
conn.close()

print(f"Inserted: {inserted} new tenders")
print(f"Total tenders in DB: {total}")
