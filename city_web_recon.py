import requests
import pandas as pd
from google.cloud import bigquery
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

bq = bigquery.Client()
project_dataset = 'project-743aab84-f9a5-4ec7-954.ppp_rico'

city_domains = [
    'hbpd.org',
    'huntingtonbeachca.gov',
    'volunteer.huntingtonbeachca.gov',
    'newportbeachca.gov',
    'nbpd.org',
    'santamonica.gov',
    'santamonicapd.org',
    'cityofirvine.org',
    'irvinepd.org',
    'fullertonca.gov',
    'anaheim.net'
]

admin_paths = [
    '/admin', '/cpanel', '/webmail', '/login', '/wp-admin',
    '/administrator', '/backup', '/temp', '/config', '/.env',
    '/phpmyadmin', '/mysql', '/server-status', '/logs', '/shell',
    '/cgi-bin', '/vendor', '/composer.json', '/package.json',
    '/.git', '/.svn', '/robots.txt', '/sitemap.xml'
]

def check_path(domain, path):
    url = f"https://{domain}{path}"
    try:
        resp = requests.head(url, timeout=5, verify=False, allow_redirects=False)
        return {
            "domain": domain,
            "path": path,
            "status_code": resp.status_code,
            "is_exposed": resp.status_code in [200, 301, 302, 401, 403]
        }
    except Exception as e:
        return {
            "domain": domain,
            "path": path,
            "status_code": 0,
            "is_exposed": False
        }

def main():
    print("Starting OSINT Recon Scan on City Domains...")
    results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for domain in city_domains:
            for path in admin_paths:
                futures.append(executor.submit(check_path, domain, path))
                
        for future in as_completed(futures):
            res = future.result()
            if res['is_exposed']:
                results.append(res)
                print(f"[!] Exposed Path Found: {res['domain']}{res['path']} (HTTP {res['status_code']})")

    if not results:
        print("No exposed paths found.")
        return

    df = pd.DataFrame(results)
    
    table_id = f"{project_dataset}.city_cyber_recon"
    print(f"Uploading {len(df)} exposed paths to {table_id}...")
    
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
    )
    job = bq.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    print("Upload complete!")

if __name__ == "__main__":
    main()
