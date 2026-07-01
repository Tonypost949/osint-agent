import requests
import pandas as pd
from google.cloud import bigquery
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

bq = bigquery.Client()
project_dataset = 'project-743aab84-f9a5-4ec7-954.ppp_rico'

# Complete 68-domain list from "html big search.html"
city_domains = [
    # --- 39 States + DC + PR ---
    'alabama.gov',
    'alaska.gov',
    'arizona.gov',
    'arkansas.gov',
    'ca.gov',
    'colorado.gov',
    'ct.gov',
    'delaware.gov',
    'myflorida.com',
    'georgia.gov',
    'hawaii.gov',
    'idaho.gov',
    'illinois.gov',
    'in.gov',
    'iowa.gov',
    'kansas.gov',
    'louisiana.gov',
    'michigan.gov',
    'mn.gov',
    'ms.gov',
    'nv.gov',
    'nj.gov',
    'newmexico.gov',
    'ny.gov',
    'nc.gov',
    'nd.gov',
    'ohio.gov',
    'ok.gov',
    'oregon.gov',
    'pa.gov',
    'ri.gov',
    'tn.gov',
    'texas.gov',
    'utah.gov',
    'virginia.gov',
    'wa.gov',
    'wisconsin.gov',
    'wv.gov',
    'wy.gov',
    'pr.gov',

    # --- Huntington Beach ---
    'hbpd.org',
    'huntingtonbeachca.gov',
    'volunteer.huntingtonbeachca.gov',
    'huntingtonbeachcu.org',

    # --- Newport Beach ---
    'newportbeachca.gov',
    'nbpd.org',

    # --- Santa Monica ---
    'santamonica.gov',
    'santamonicapd.org',
    'joinsmpd.com',

    # --- Irvine ---
    'cityofirvine.org',
    'irvinepd.org',
    'joinirvinepd.gov',

    # --- RICO-connected cities ---
    'sanpedroca.gov',
    'cudahyca.gov',
    'lacity.org',
    'ocgov.com',
    'orangecountyca.gov',
    'santaana.gov',
    'santa-ana.org',      # From intermediate run
    'santaanapd.org',     # From intermediate run
    'costamesaca.gov',    # From intermediate run
    'cmpd.org',           # From intermediate run
    'anaheim.net',
    'fullertoncity.com',
    'fullertonca.gov',    # From intermediate run
    'garden-grove.org',
    'lapd.org',
    'sheriff.lacounty.gov',

    # --- Southern California Edison ---
    'sce.com',
    'edison.com',

    # --- Turkey (National) ---
    'egm.gov.tr',
    'jandarma.gov.tr',
    'turkiye.gov.tr',

    # --- Turkey (Regional Police) ---
    'izmir.pol.tr',
    'duzce.pol.tr',
    'ankara.pol.tr',
    'istanbul.pol.tr'
]

# Complete 26 sensitive paths
admin_paths = [
    '/admin', '/cpanel', '/webmail', '/login', '/wp-admin',
    '/administrator', '/backup', '/temp', '/config', '/.env',
    '/phpmyadmin', '/mysql', '/server-status', '/logs', '/shell',
    '/cgi-bin', '/vendor', '/composer.json', '/package.json',
    '/.git', '/.svn', '/robots.txt', '/sitemap.xml',
    '/.htaccess', '/.aws', '/.ssh'
]

def check_path(domain, path):
    url = f"https://{domain}{path}"
    try:
        resp = requests.head(url, timeout=3, verify=False, allow_redirects=False)
        return {
            "domain": domain,
            "path": path,
            "status_code": resp.status_code,
            "is_exposed": resp.status_code in [200, 301, 302, 401, 403]
        }
    except Exception:
        # Fallback to HTTP check
        url_http = f"http://{domain}{path}"
        try:
            resp = requests.head(url_http, timeout=3, verify=False, allow_redirects=False)
            return {
                "domain": domain,
                "path": path,
                "status_code": resp.status_code,
                "is_exposed": resp.status_code in [200, 301, 302, 401, 403]
            }
        except Exception:
            return {
                "domain": domain,
                "path": path,
                "status_code": 0,
                "is_exposed": False
            }

def main():
    print(f"Starting OSINT Recon Scan on {len(city_domains)} Domains...")
    results = []
    
    # Run checks concurrently
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = []
        for domain in city_domains:
            for path in admin_paths:
                futures.append(executor.submit(check_path, domain, path))
                
        for future in as_completed(futures):
            res = future.result()
            if res['is_exposed']:
                results.append(res)
                print(f"[!] Exposed: {res['domain']}{res['path']} (HTTP {res['status_code']})")

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
