# create_sample_data.py
from sample_data import create_sample_scans

if __name__ == "__main__":
    print("📁 Creating sample scan data...")
    create_sample_scans(10)
    print("✅ Sample data created! Run 'python run.py' to start the server.")