import os
import time
import logging
from prometheus_client import start_http_server, Gauge
from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import Connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

ROUTER_ADDRESS  = os.environ.get('ROUTER_ADDRESS')
ROUTER_USER     = os.environ.get('ROUTER_USER')
ROUTER_PASS     = os.environ.get('ROUTER_PASS')
PROM_PORT       = int(os.environ.get('PROM_PORT', 8080))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', 30))

if not ROUTER_ADDRESS:
    raise SystemExit('ROUTER_ADDRESS must be set')
if not ROUTER_USER or not ROUTER_PASS:
    raise SystemExit('ROUTER_USER and ROUTER_PASS must be set')

# Signal quality
rsrp = Gauge('rsrp', 'Reference Signal Received Power (dBm)')
rsrq = Gauge('rsrq', 'Reference Signal Received Quality (dB)')
rssi = Gauge('rssi', 'Received Signal Strength Indicator (dBm)')
sinr = Gauge('sinr', 'Signal to Interference and Noise Ratio (dB)')

# Network identity
band      = Gauge('router_band',      'Active LTE band number')
pci       = Gauge('router_pci',       'Physical Cell ID')
enodeb_id = Gauge('router_enodeb_id', 'eNodeB ID (base station)')
tac       = Gauge('router_tac',       'Tracking Area Code')
plmn      = Gauge('router_plmn',      'PLMN (operator identifier)')

# Radio parameters
cqi0         = Gauge('router_cqi0',             'Channel Quality Indicator carrier 0')
cqi1         = Gauge('router_cqi1',             'Channel Quality Indicator carrier 1')
dlfrequency  = Gauge('router_dl_frequency_khz', 'Downlink frequency (kHz)')
ulfrequency  = Gauge('router_ul_frequency_khz', 'Uplink frequency (kHz)')
dl_bandwidth = Gauge('router_dl_bandwidth_mhz', 'Downlink bandwidth (MHz)')
ul_bandwidth = Gauge('router_ul_bandwidth_mhz', 'Uplink bandwidth (MHz)')

# Traffic
rx_bytes = Gauge('router_rx_bytes_total', 'Total bytes received')
tx_bytes = Gauge('router_tx_bytes_total', 'Total bytes transmitted')
rx_rate  = Gauge('router_rx_rate_bps',    'Current download rate (bps)')
tx_rate  = Gauge('router_tx_rate_bps',    'Current upload rate (bps)')


def parse_numeric(raw, key):
    """Extract numeric value from strings like '-97dBm', '6dB', '20MHz'."""
    val = raw.get(key)
    if val is None:
        return None
    try:
        return float(''.join(c for c in str(val) if c in '0123456789.-'))
    except ValueError:
        return None


def collect():
    try:
        url = f'http://{ROUTER_USER}:{ROUTER_PASS}@{ROUTER_ADDRESS}/'
        with Connection(url) as conn:
            client = Client(conn)

            signal = client.device.signal()
            log.debug("signal raw: %s", signal)

            # Signal quality
            for metric, key in [(rsrp, 'rsrp'), (rsrq, 'rsrq'),
                                 (rssi, 'rssi'), (sinr, 'sinr')]:
                val = parse_numeric(signal, key)
                if val is not None:
                    metric.set(val)

            # Network identity
            for metric, key in [(band, 'band'), (pci, 'pci'), (tac, 'tac'),
                                 (plmn, 'plmn'), (cqi0, 'cqi0'), (cqi1, 'cqi1')]:
                val = parse_numeric(signal, key)
                if val is not None:
                    metric.set(val)

            enb = parse_numeric(signal, 'enodeb_id')
            if enb is not None:
                enodeb_id.set(enb)

            # Frequencies and bandwidth
            for metric, key in [(dlfrequency, 'dlfrequency'), (ulfrequency, 'lteulfreq'),
                                 (dl_bandwidth, 'dlbandwidth'), (ul_bandwidth, 'ulbandwidth')]:
                val = parse_numeric(signal, key)
                if val is not None:
                    metric.set(val)

            # Traffic
            traffic = client.monitoring.traffic_statistics()
            log.debug("traffic raw: %s", traffic)

            rx_bytes.set(float(traffic.get('CurrentDownload', 0)))
            tx_bytes.set(float(traffic.get('CurrentUpload', 0)))
            rx_rate.set(float(traffic.get('CurrentDownloadRate', 0)))
            tx_rate.set(float(traffic.get('CurrentUploadRate', 0)))

            log.info("OK — RSRP=%s RSRQ=%s SINR=%s band=%s pci=%s enodeb=%s cqi0=%s cqi1=%s",
                     signal.get('rsrp'), signal.get('rsrq'), signal.get('sinr'),
                     signal.get('band'), signal.get('pci'), signal.get('enodeb_id'),
                     signal.get('cqi0'), signal.get('cqi1'))

    except Exception as e:
        log.error("Scrape failed: %s", e)


if __name__ == '__main__':
    log.info("Starting exporter on port %d, scraping every %ds", PROM_PORT, SCRAPE_INTERVAL)
    start_http_server(PROM_PORT)
    while True:
        collect()
        time.sleep(SCRAPE_INTERVAL)