"""Demo knowledge for trying BUI. All products/brands below are FICTIONAL sample data.

Usage:
    python -m app.seeds.demo            # add demo data (idempotent)
    python -m app.seeds.demo --remove   # remove everything tagged 'demo'
    python -m app.seeds.demo --users    # also create demo admin/team accounts
"""
import argparse
import logging

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import FAQ, DocumentVersion, KnowledgeDocument, Product, ProductCategory, Role, User
from app.rag.indexer import index_document, index_faq, index_product, remove_source
from app.services.bootstrap import ensure_roles
from app.services.products import snapshot_product

log = logging.getLogger(__name__)

CATEGORIES = [
    ("Water Pumps", "Domestic and agricultural water pumps"),
    ("Solar Inverters", "Grid-tie and hybrid solar inverters"),
    ("UPS Systems", "Uninterruptible power supplies"),
]

PRODUCTS = [
    dict(
        name="AquaFlow 500", brand="Demoline", model_number="AF-500", category="Water Pumps",
        description="AquaFlow 500 is a 0.5 HP self-priming domestic water pump for lifting water to overhead tanks in homes and small offices.",
        specifications={"Motor Power": "0.5 HP (370 W)", "Voltage": "220-240 V AC, 50 Hz", "Maximum Head": "30 m", "Maximum Flow": "2,100 litres/hour",
                        "Suction Lift": "8 m", "Pipe Size": "25 mm x 25 mm (1 inch)", "Motor Winding": "100% copper", "Weight": "7.2 kg", "Insulation Class": "Class B"},
        features=["Self-priming design – no foot valve priming needed after first fill", "Thermal overload protector prevents motor burnout", "Corrosion-resistant brass impeller", "Low-noise operation (below 60 dB)"],
        applications=["Lifting water to overhead tanks", "Gardening and lawn sprinklers", "Small apartments and offices"],
        compatibility=["Demoline AutoSwitch AS-1 water level controller", "Standard 1-inch PVC and GI pipes"],
        accessories=["AS-1 Automatic water level controller", "Foot valve FV-25", "Pressure tank PT-24"],
        warranty="24 months from the date of purchase against manufacturing defects. Warranty does not cover damage from dry running, voltage fluctuation above 260 V, or unauthorised repairs. Keep the original invoice for claims.",
        installation="1. Install the pump on a level, dry, ventilated surface at most 8 m above the water source.\n2. Use a foot valve and keep the suction pipe as short and straight as possible.\n3. Fill the pump casing with water through the priming plug before first start.\n4. Connect to a dedicated 6 A socket with proper earthing.\n5. Run for 2 minutes and check for leaks at all joints.",
        maintenance="Check the priming plug and pipe joints every 3 months. Clean the foot valve strainer every 6 months. Never run the pump dry.",
        troubleshooting="Pump runs but no water: re-prime the casing and check the foot valve for air leaks.\nMotor hums but does not start: check supply voltage (minimum 180 V) and capacitor.\nThermal protector trips frequently: check for dry running or a blocked impeller.",
        pricing="Dealer price list 2026: contact the sales team for current dealer pricing.",
        tags=["demo", "pump", "domestic"],
    ),
    dict(
        name="AquaFlow 700", brand="Demoline", model_number="AF-700", category="Water Pumps",
        description="AquaFlow 700 is a 1 HP self-priming water pump for larger homes, multi-storey buildings and light agricultural use.",
        specifications={"Motor Power": "1 HP (750 W)", "Voltage": "220-240 V AC, 50 Hz", "Maximum Head": "45 m", "Maximum Flow": "3,300 litres/hour",
                        "Suction Lift": "8 m", "Pipe Size": "25 mm x 25 mm (1 inch)", "Motor Winding": "100% copper", "Weight": "11.5 kg", "Insulation Class": "Class F"},
        features=["Higher head for buildings up to 4 floors", "Thermal overload protector", "Brass impeller and stainless steel shaft", "Class F insulation for continuous duty"],
        applications=["Multi-storey residential buildings", "Garden and farm irrigation", "Water transfer between tanks"],
        compatibility=["Demoline AutoSwitch AS-1 water level controller", "Pressure tank PT-24 and PT-50"],
        accessories=["AS-1 Automatic water level controller", "Foot valve FV-25", "Pressure tank PT-50"],
        warranty="36 months from the date of purchase against manufacturing defects. Warranty does not cover damage from dry running, voltage above 260 V, or unauthorised repairs.",
        installation="Follow the AquaFlow installation guide. Use a dedicated 10 A socket with earthing. Prime the pump before first start and ensure the suction lift does not exceed 8 m.",
        maintenance="Inspect mechanical seal every 12 months. Clean foot valve strainer every 6 months.",
        troubleshooting="Low pressure: check for air leaks in the suction line and clean the foot valve.\nWater leaking from the shaft: the mechanical seal may need replacement (service centre).",
        tags=["demo", "pump"],
    ),
    dict(
        name="SolarMax 3K", brand="Demoline", model_number="SMX-3000", category="Solar Inverters",
        description="SolarMax 3K is a 3 kW single-phase on-grid solar inverter with dual MPPT and Wi-Fi monitoring.",
        specifications={"Rated AC Output": "3,000 W", "Max PV Input Power": "4,500 Wp", "MPPT Trackers": "2", "MPPT Voltage Range": "80-550 V DC",
                        "Max DC Input Voltage": "600 V", "Max Efficiency": "97.6%", "Grid Connection": "Single phase, 230 V, 50 Hz",
                        "Protection Rating": "IP65", "Monitoring": "Wi-Fi with SolarMax mobile app", "Weight": "10.5 kg"},
        features=["Dual MPPT for panels on two roof orientations", "97.6% maximum efficiency", "IP65 for outdoor installation", "Free mobile app monitoring", "Anti-islanding protection"],
        applications=["Residential rooftop solar", "Small commercial rooftops"],
        compatibility=["Mono and poly-crystalline PV panels", "Net-metering approved by most distribution companies (check local rules)"],
        accessories=["SolarMax Wi-Fi dongle (included)", "DC isolator DCI-2", "Smart energy meter SEM-1"],
        warranty="5 years standard warranty, extendable to 10 years with the SolarMax Care plan purchased within 6 months of installation.",
        installation="Must be installed by a certified solar installer. Mount vertically on a wall away from direct sunlight with 30 cm clearance on all sides. Install a DC isolator between panels and inverter, and an AC MCB of 20 A on the grid side.",
        troubleshooting="Error E01 (Grid voltage high): check grid voltage; contact the utility if persistent.\nError E07 (Isolation fault): check PV cables and connectors for moisture or damage.\nNo Wi-Fi data: re-pair the dongle using the SolarMax app.",
        tags=["demo", "solar"],
    ),
    dict(
        name="PowerGuard 1500", brand="Demoline", model_number="PG-1500", category="UPS Systems",
        description="PowerGuard 1500 is a 1.5 kVA line-interactive UPS for home offices, workstations and network equipment.",
        specifications={"Capacity": "1500 VA / 900 W", "Topology": "Line-interactive", "Input Voltage Range": "140-300 V AC", "Output Waveform": "Pure sine wave (battery mode)",
                        "Battery": "2 x 12 V 9 Ah sealed lead-acid", "Backup Time": "Approx. 15 minutes at half load", "Transfer Time": "4-6 ms", "Outlets": "4 x Indian 3-pin", "Weight": "12 kg"},
        features=["Pure sine wave output", "Automatic voltage regulation (AVR)", "USB monitoring port", "Cold start capability"],
        applications=["Home office computers", "Routers and network equipment", "Point-of-sale systems"],
        compatibility=["Windows and Linux via PowerGuard monitoring software"],
        accessories=["Replacement battery kit PG-BAT9", "USB monitoring cable (included)"],
        warranty="24 months on the UPS and 12 months on batteries.",
        installation="Charge the batteries for 8 hours before first use. Do not connect laser printers or heaters to the UPS outlets.",
        troubleshooting="Continuous beeping: UPS is overloaded – disconnect non-essential equipment.\nShort backup time: batteries may need replacement after 2-3 years.",
        tags=["demo", "ups"],
    ),
]

DOCUMENTS = [
    dict(
        title="About Demoline Industries (demo company profile)", category="company_information",
        content="## Company overview\n\nDemoline Industries is a fictional demo manufacturer used to showcase BUI. Demoline makes water pumps, solar inverters and UPS systems.\n\n## Customer support\n\nCustomer support is available Monday to Saturday, 9:00 to 18:00, through the toll-free number 1800-000-0000 (demo) and support@demoline.example.\n\n## Service network\n\nDemoline has 120 authorised service centres. Service requests are usually attended to within 48 hours in metro cities and 72 hours elsewhere.",
    ),
    dict(
        title="Warranty Claim Policy", category="warranty_information",
        content="## Warranty claim process\n\n1. The customer contacts customer support with the product serial number and purchase invoice.\n2. A service engineer inspects the product on site or at the service centre.\n3. Approved claims are repaired or replaced within 7 working days.\n\n## Exclusions\n\nWarranty is void if the product has been opened by unauthorised persons, damaged by fire, flood or lightning, or used outside the rated voltage.\n\n## Replacement policy\n\nA product is replaced instead of repaired if the same defect occurs three times within the warranty period.",
    ),
    dict(
        title="Dealer Returns and Sales Policy 2026", category="sales_information", visibility="restricted",
        content="## Dealer returns\n\nDealers may return unsold, unopened stock within 30 days of invoice for a credit note, minus a 5% restocking fee.\n\n## Confidential margins\n\nDealer margin bands are confidential and visible only to administrators.",
    ),
]

FAQS = [
    ("Does the AquaFlow 500 need priming every time?", "No. AquaFlow 500 is self-priming. Fill the casing with water before the first start; after that it primes itself as long as the foot valve holds water.", "AquaFlow 500"),
    ("Can the SolarMax 3K work during a power cut?", "No. SolarMax 3K is an on-grid inverter. For safety (anti-islanding) it shuts down when the grid fails, so it does not supply power during power cuts.", "SolarMax 3K"),
    ("How do I register a warranty?", "Warranty is linked to the purchase invoice. Keep the invoice and the product serial number; no separate registration is needed.", None),
]

DEMO_USERS = [
    ("admin@demo.bui", "Demo Admin", "admin", "DemoAdmin2026!"),
    ("member@demo.bui", "Demo Team Member", "team_member", "DemoMember2026!"),
]


def seed(with_users: bool = False) -> None:
    db = SessionLocal()
    try:
        ensure_roles(db)
        cats = {}
        for name, desc in CATEGORIES:
            c = db.scalar(select(ProductCategory).where(ProductCategory.name == name))
            if not c:
                c = ProductCategory(name=name, description=desc)
                db.add(c)
                db.flush()
            cats[name] = c
        products = {}
        for data in PRODUCTS:
            data = dict(data)
            cat = cats[data.pop("category")]
            p = db.scalar(select(Product).where(Product.model_number == data["model_number"]))
            if not p:
                p = Product(**data, category_id=cat.id, status="verified", version=1)
                db.add(p)
                db.flush()
                snapshot_product(db, p, None, "Demo data")
                db.refresh(p)
                index_product(db, p)
            products[p.name] = p
        for d in DOCUMENTS:
            if not db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.title == d["title"])):
                doc = KnowledgeDocument(**d, source_type="manual", status="published", processing_status="ready", tags=["demo"], current_version=1)
                db.add(doc)
                db.flush()
                doc.versions.append(DocumentVersion(version=1, title=doc.title, content=doc.content, change_note="Demo data"))
                index_document(db, doc)
        for q, a, pname in FAQS:
            if not db.scalar(select(FAQ).where(FAQ.question == q)):
                f = FAQ(question=q, answer=a, product_id=products[pname].id if pname else None, tags=["demo"])
                db.add(f)
                db.flush()
                index_faq(db, f)
        if with_users:
            for email, name, role, pw in DEMO_USERS:
                if not db.scalar(select(User).where(User.email == email)):
                    rid = db.scalar(select(Role.id).where(Role.name == role))
                    db.add(User(email=email, full_name=name, password_hash=hash_password(pw), role_id=rid))
        db.commit()
        print("Demo data loaded.")
    finally:
        db.close()


def remove() -> None:
    db = SessionLocal()
    try:
        for p in db.scalars(select(Product)).all():
            if "demo" in (p.tags or []):
                remove_source(db, "product", p.id)
                db.delete(p)
        for d in db.scalars(select(KnowledgeDocument)).all():
            if "demo" in (d.tags or []):
                remove_source(db, "document", d.id)
                db.delete(d)
        for f in db.scalars(select(FAQ)).all():
            if "demo" in (f.tags or []):
                remove_source(db, "faq", f.id)
                db.delete(f)
        for name, _ in CATEGORIES:
            c = db.scalar(select(ProductCategory).where(ProductCategory.name == name))
            if c is not None and not db.scalar(select(Product).where(Product.category_id == c.id)):
                db.delete(c)
        for email, *_ in DEMO_USERS:
            u = db.scalar(select(User).where(User.email == email))
            if u:
                db.delete(u)
        db.commit()
        print("Demo data removed.")
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--users", action="store_true")
    args = ap.parse_args()
    remove() if args.remove else seed(args.users)
