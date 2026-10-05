import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
from app.models.search import SearchHistory

def seed_history():
    print("🗄️ Forcefully adding dummy history...")
    init_db()
    db = SessionLocal()
    
    ref_no = "19131331109052"
    disco = "fesco"
    
    # 4 Purane months ki dummy bills
    dummy_data = [
        {"units": 240, "grand_total": 15000, "date": datetime(2024, 9, 15, 10, 0, 0)},  # Sep
        {"units": 310, "grand_total": 21000, "date": datetime(2024, 8, 12, 10, 0, 0)},  # Aug
        {"units": 180, "grand_total": 11000, "date": datetime(2024, 7, 20, 10, 0, 0)},  # Jul
        {"units": 290, "grand_total": 19000, "date": datetime(2024, 6, 5, 10, 0, 0)},   # Jun
    ]

    try:
        for data in dummy_data:
            record = SearchHistory(
                reference_no=ref_no,
                disco=disco,
                consumer_name="Mehnaz Fatima",
                units=data["units"],
                grand_total=data["grand_total"],
                searched_at=data["date"]
            )
            db.add(record)
        
        db.commit()
        print("🚀 Success! 4 months ka dummy data FORCEFULLY add ho gaya hai.")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_history()