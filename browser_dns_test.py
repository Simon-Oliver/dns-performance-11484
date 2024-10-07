import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
import json
import subprocess
import speedtest
import re
from datetime import datetime
import uuid
import concurrent.futures
import csv


def get_network_speed():
    try:
        st = speedtest.Speedtest()

        # Download speed test using speedtest.net
        download_speed = st.download() / 1000000  # Convert to Mbps

        # Upload speed test using speedtest.net
        upload_speed = st.upload() / 1000000  # Convert to Mbps
        latency = st.results.ping

        print("Download Speed: {:.2f} Mbps".format(download_speed))
        print("Upload Speed: {:.2f} Mbps".format(upload_speed))
        print("Latency: {:.2f} ms".format(latency))

        return download_speed, upload_speed, latency

    except speedtest.SpeedtestException as e:
        print("An error occurred during the speed test:", str(e))
        return 'error', 'error', 'error'


def set_dns_macos(interface_name, dns_server):
    # Setting the DNS server for macOS
    command = ['networksetup', '-setdnsservers', interface_name, dns_server]
    subprocess.run(command)


def parse_dnsping(dnsping_output):
    # Regex pattern to parse the dnsping output
    stats_pattern = r"(\d+) requests transmitted, (\d+) responses received, (\d+)% lost\nmin=(\d+\.\d+) ms, avg=(\d+\.\d+) ms, max=(\d+\.\d+) ms, stddev=(\d+\.\d+) ms"
    match = re.search(stats_pattern, dnsping_output)

    if match:
        # Extract values as floats and integers
        statistics = [int(match.group(1)), int(match.group(2)), int(match.group(3)),
                      float(match.group(4)), float(match.group(5)), float(match.group(6)), float(match.group(7))]

        return statistics


def run_dnsping(server, url, mode='dns', num_times=5):
    # Define the command to run dnsping.py based on the mode. Run 5 times by default
    try:
        if mode == 'doh':
            command = ['./dnsdiag/dnsping.py', '-c', f"{num_times}", '--doh', '-t', 'A', '-s', server, url]
            # Run the command and capture the output
            result = subprocess.run(command, capture_output=True, text=True)
        elif mode == 'dns':
            command = ['./dnsdiag/dnsping.py', '-c', f"{num_times}", '-t', 'A', '-s', server, url]
            # Run the command and capture the output
            result = subprocess.run(command, capture_output=True, text=True)

        res = parse_dnsping(result.stdout)
        if res is None:
            raise Exception
        return res
    except Exception as e:
        print("An error occurred during the dnsping test", e)
        return ['err', 'err', 'err', 'err', 'err', 'err', 'err']


def run_chrome(url, mode='dns', server='1.1.1.1'):
    chrome_options = Options()
    # Added window size to ensure website is rendered
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-cache')
    chrome_options.add_argument('--incognito')

    # Added because of issues when running multithreaded
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    # Setting the browser to either DNS or DoH based on the provided option
    if mode == 'dns':
        local_state = {
            "dns_over_https.mode": "off",
            "dns_over_https.templates": "",
        }
    else:
        local_state = {
            "dns_over_https.mode": "secure",
            "dns_over_https.templates": dns_servers[server][1],
        }

    chrome_options.add_experimental_option("localState", local_state)
    chrome_options.add_argument('--disk-cache-size=0')
    chrome = webdriver.Chrome(options=chrome_options)
    chrome.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
    chrome.get(url)

    # Set a timeout of 10 seconds to give enough time for the page to load
    WebDriverWait(chrome, 10).until(expected_conditions.presence_of_element_located((By.TAG_NAME, 'body')))

    # Use the Performance Timing API to get performance data
    performance_data = chrome.execute_script("return JSON.stringify(window.performance.timing);")
    performance_data = json.loads(performance_data)

    # Calculate page load time
    navigation_start = performance_data['navigationStart']
    load_event_end = performance_data['loadEventEnd']
    page_load_time = load_event_end - navigation_start

    chrome.quit()

    return page_load_time, 'Chrome'


def run_firefox(url, mode='dns', server='1.1.1.1'):
    firefox_options = FirefoxOptions()
    firefox_options.add_argument("--width=1920")
    firefox_options.add_argument("--height=1080")
    firefox_options.add_argument('-headless')
    firefox_options.add_argument('-private')
    firefox_options.set_preference("browser.cache.disk.enable", False)
    firefox_options.set_preference("browser.cache.memory.enable", False)
    firefox_options.set_preference("browser.cache.offline.enable", False)
    firefox_options.set_preference("network.http.use-cache", False)

    # DNS over HTTPS settings
    if mode == 'dns':
        firefox_options.set_preference("network.trr.mode", 5)  # Disable DoH
    else:
        firefox_options.set_preference("network.trr.mode", 2)  # Enable DoH
        firefox_options.set_preference("network.trr.uri", dns_servers[server][1])

    firefox = webdriver.Firefox(options=firefox_options)
    firefox.get(url)

    # Set a timeout of 10 seconds to give enough time for the page to load
    WebDriverWait(firefox, 10).until(expected_conditions.presence_of_element_located((By.TAG_NAME, 'body')))

    performance_data = firefox.execute_script("return JSON.stringify(window.performance.timing);")
    performance_data = json.loads(performance_data)

    # Calculate page load time
    navigation_start = performance_data['navigationStart']
    load_event_end = performance_data['loadEventEnd']
    page_load_time = load_event_end - navigation_start

    firefox.quit()

    return page_load_time, 'Firefox'


def run_edge(url, mode='dns', server='1.1.1.1'):
    edge_options = EdgeOptions()
    edge_options.add_argument("--window-size=1920,1080")
    edge_options.add_argument('--headless=new')
    edge_options.add_argument('--disable-cache')
    edge_options.add_argument('--inprivate')
    edge_options.add_argument('--disk-cache-size=0')

    # DNS over HTTPS settings
    if mode == 'dns':
        edge_options.add_argument('--dns-over-https-mode=off')
    else:
        edge_options.add_argument('--dns-over-https-mode=secure')
        edge_options.add_argument(dns_servers[server][1])

    edge = webdriver.Edge(options=edge_options)

    # Disable cache using CDP command
    edge.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
    edge.get(url)

    WebDriverWait(edge, 10).until(expected_conditions.presence_of_element_located((By.TAG_NAME, 'body')))

    performance_data = edge.execute_script("return JSON.stringify(window.performance.timing);")
    performance_data = json.loads(performance_data)

    # Calculate page load time
    navigation_start = performance_data['navigationStart']
    load_event_end = performance_data['loadEventEnd']
    page_load_time = load_event_end - navigation_start

    edge.quit()

    return page_load_time, 'Edge'


def get_page_load_average(browser_func, url, mode, server, num_runs=1):
    results = []

    for i in range(num_runs):
        result, browser_name = browser_func(url, mode=mode, server=server)
        results.append(result)

    average = sum(results) / num_runs

    return browser_name, min(results), max(results), round(average, 3)


def run_dns_pings(server, url):
    dns_ping = run_dnsping(server, url, 'dns')
    doh_ping = run_dnsping(server, url, 'doh')
    return {'dns': dns_ping, 'doh': doh_ping}


def run_browser_test(browser_func, url, mode, server, num_runs):
    results = get_page_load_average(browser_func, url, mode, server, num_runs)
    return [mode.upper()] + list(results)


def run_dns_page_load(url, server):
    # More than 2 workers seems to cause issues with the Chrome browser driver
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Start browser tests
        future_to_browser = {
            executor.submit(run_browser_test, run_chrome, url, 'dns', server, 3): 'Chrome DNS',
            executor.submit(run_browser_test, run_chrome, url, 'doh', server, 3): 'Chrome DOH',
            executor.submit(run_browser_test, run_firefox, url, 'dns', server, 3): 'Firefox DNS',
            executor.submit(run_browser_test, run_firefox, url, 'doh', server, 3): 'Firefox DOH',
            executor.submit(run_browser_test, run_edge, url, 'dns', server, 3): 'Edge DNS',
            executor.submit(run_browser_test, run_edge, url, 'doh', server, 3): 'Edge DOH'
        }

        # Start DNS pings
        dns_ping_future = executor.submit(run_dns_pings, server, url)

        results = []
        for future in concurrent.futures.as_completed(future_to_browser):
            browser = future_to_browser[future]
            try:
                data = future.result()
                results.append(data)
            except Exception as exc:
                print(f'{browser} generated an exception: {exc}')

        # DNS ping results
        dns_ping_results = dns_ping_future.result()

        # Combine browser and DNS ping results
        for result in results:
            if result[0] == 'DNS':
                result.extend(dns_ping_results['dns'])
            else:  # DOH
                result.extend(dns_ping_results['doh'])

    return results


websites = [
    "https://en.wikipedia.org",
    "https://youtube.com",
    "https://facebook.com",
    "https://instagram.com",
    "https://reddit.com",
    "https://amazon.com.au",
    "https://imdb.com",
    "https://nytimes.com",
    "https://kmart.com.au",
    "https://microsoft.com",
    "https://my.gov.au",
    "https://nsw.gov.au",
    "https://twitter.com",
    "https://apple.com",
    "https://bunnings.com.au"
]

dns_servers = {
    "8.8.8.8": ["Google", 'https://dns.google/dns-query'],
    "9.9.9.9": ["Quad9", "https://dns.quad9.net/dns-query"],
    "1.1.1.1": ["Cloudflare", "https://cloudflare-dns.com/dns-query"]
}


def main():
    results = []

    # Time of the test run and a random id to differentiate the runs
    time_of_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_id = str(uuid.uuid4())

    # Get the network stats once per run
    print("Measuring network speed...")
    download_speed, upload_speed, latency = get_network_speed()
    print(f"Network Speed: Download: {download_speed} Mbps, Upload: {upload_speed} Mbps, Latency: {latency} ms")

    for resolver, resolver_info in dns_servers.items():
        print(f"\nSetting DNS resolver to {resolver_info[0]} ({resolver})...")
        set_dns_macos("Wi-Fi", resolver)

        for website in websites:
            print(f"Testing {website} with resolver {resolver_info[0]}...")

            website_results = run_dns_page_load(website, resolver)

            for res in website_results:
                result = {
                    'id': run_id,
                    'date_time': time_of_run,
                    'website': website,
                    'resolver': resolver_info[0],
                    'network_download_mbps': download_speed,
                    'network_upload_mbps': upload_speed,
                    'network_latency_ms': latency,
                    'dns_type': res[0],
                    'browser': res[1],
                    'page_load_min_ms': res[2],
                    'page_load_max_ms': res[3],
                    'page_load_avg_ms': res[4],
                    'dns_requests_transmitted': res[5],
                    'dns_responses_received': res[6],
                    'dns_lost_percentage': res[7],
                    'dns_min_response_ms': res[8],
                    'dns_avg_response_ms': res[9],
                    'dns_max_response_ms': res[10],
                    'dns_stddev_ms': res[11]
                }
                results.append(result)

    # Column names for CSV
    fieldnames = ["id", "date_time", "website", "resolver", "network_download_mbps", "network_upload_mbps",
                  "network_latency_ms", "dns_type", "browser", "page_load_min_ms", "page_load_max_ms",
                  "page_load_avg_ms", "dns_requests_transmitted", "dns_responses_received", "dns_lost_percentage",
                  "dns_min_response_ms", "dns_avg_response_ms", "dns_max_response_ms", "dns_stddev_ms"]

    # Save as CSV
    csv_filename = f"dns_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(result)

    print(f"\nResults saved to {csv_filename}")


if __name__ == "__main__":
    start_time = time.time()
    main()
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"\nScript execution time: {execution_time:.2f} seconds")
