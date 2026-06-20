import os
from google.cloud import bigquery

GCP_PROJECT = "noble-beanbag-497411-m4"
BQ_DATASET = "national_audits"

def check_counts():
    try:
        client = bigquery.Client(project=GCP_PROJECT)
        
        # Check Gmail
        gmail_query = f"SELECT COUNT(*) as count FROM `{GCP_PROJECT}.{BQ_DATASET}.gmail_index`"
        gmail_job = client.query(gmail_query)
        gmail_count = list(gmail_job.result())[0].count
        print(f"Gmail Total: {gmail_count}")

        # Check Photos
        photos_query = f"SELECT COUNT(*) as count FROM `{GCP_PROJECT}.{BQ_DATASET}.google_photos_index`"
        photos_job = client.query(photos_query)
        photos_count = list(photos_job.result())[0].count
        print(f"Photos Total: {photos_count}")

    except Exception as e:
        print(f"Error checking counts: {e}")

if __name__ == "__main__":
    check_counts()
