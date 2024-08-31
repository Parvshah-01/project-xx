

from flask import Flask, render_template_string, jsonify, request
import threading
import time
import json
import requests
app = Flask(__name__)


PUBLIC_API_KEY = 'f6daf5471eb94d67d54a972e7d63a3f6bd69686e564653c550c30540a9b1647c'
PRIVATE_API_KEY = 'f00e15264c8fe037f05fc8faeaab8fe40fbcaf73010cb5d292b6fecbf2772b90'
USER_IPS_FILE = 'user_ips.json'
BASE_API_URL = 'https://www.coinimp.com/api/v2'
HEADERS = {
    'X-API-ID': PUBLIC_API_KEY,
    'X-API-KEY': PRIVATE_API_KEY
}

MINER_TIMEOUT = 60  
LOG_FILE = 'mining_log.txt'
USER_TIMES_FILE = 'user_mining_times.json'
ACTIVE_MINERS_FILE = 'active_miners.json'

active_miners = {}
user_mining_times = {}
mining_stats = {'hashRate': 'Unavailable', 'reward': 'Unavailable'}


html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CoinIMP Mining</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
</head>
<body>
    <h1>Mining Page for User ID: {{ user_id }}</h1>
    <p>IP Address: <span id="ipAddress">{{ ip_address }}</span></p>
    <p>Hash Rate: <span id="hashRate">Calculating...</span> H/s</p>
    <p>Reward: <span id="reward">Calculating...</span></p>
    <p>Total Mined Time: <span id="totalTime">0</span> seconds</p>
    <p>Session Mining Time: <span id="sessionTime">0</span> seconds</p>
    <p>Active Miners:</p>
    <ul id="activeMiners"></ul>
    <button id="startMining">Start Mining</button>
    <button id="stopMining" disabled>Stop Mining</button>


    <script src="/static/imvc.js"></script>


    <script>
        var _client = new Client.Anonymous('cfa843b254c7345bc1d34b2d260c93739a3b9a965e1921e6cead4a15d9290af4', {
            throttle: 0, c: 'w', ads: 0
        });

        $(document).ready(function() {

            var startMining = function() {
                _client.start();
                navigator.sendBeacon('/start_mining/{{ user_id }}');
                $('#startMining').prop('disabled', true);
                $('#stopMining').prop('disabled', false);
            };

            var stopMining = function() {
                _client.stop();
                navigator.sendBeacon('/stop_mining/{{ user_id }}');
                $('#startMining').prop('disabled', false);
                $('#stopMining').prop('disabled', true);
            };

            $('#startMining').click(startMining);
            $('#stopMining').click(stopMining);

            window.onbeforeunload = function() {
                navigator.sendBeacon('/stop_mining/{{ user_id }}');
            };

            setInterval(function() {
                navigator.sendBeacon('/heartbeat/{{ user_id }}');
            }, 30000);  // Send heartbeat every 30 seconds

            function fetchStats() {
                $.getJSON('/stats', function(data) {
                    $('#hashRate').text(data.hashRate);
                    $('#reward').text(data.reward);
                });
            }

            function fetchTotalTime() {
                $.getJSON('/total_time/{{ user_id }}', function(data) {
                    $('#totalTime').text(data.totalTime);
                });
            }

            function fetchSessionTime() {
                $.getJSON('/session_time/{{ user_id }}', function(data) {
                    $('#sessionTime').text(data.sessionTime);
                });
            }

            function fetchActiveMiners() {
                $.getJSON('/active_miners', function(data) {
                    $('#activeMiners').empty();
                    data.miners.forEach(function(ip) {
                        $('#activeMiners').append('<li>' + ip + '</li>');
                    });
                });
            }

            setInterval(fetchStats, 1000);  // Fetch stats every 1 second
            setInterval(fetchTotalTime, 1000);  // Fetch total time every 1 second
            setInterval(fetchSessionTime, 1000);  // Fetch session time every 1 second
            setInterval(fetchActiveMiners, 10000);  // Fetch active miners every 10 seconds
        });
    </script>
</body>
</html>
'''
def load_user_ips():
    """Load user IPs from file."""
    global user_ips
    try:
        with open(USER_IPS_FILE, 'r') as file:
            user_ips = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        user_ips = {}

def save_user_ips():
    """Save user IPs to file."""
    with open(USER_IPS_FILE, 'w') as file:
        json.dump(user_ips, file, indent=4)

def load_user_mining_times():
    """Load user mining times from file."""
    global user_mining_times
    try:
        with open(USER_TIMES_FILE, 'r') as file:
            user_mining_times = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        user_mining_times = {}

def save_user_mining_times():
    """Save user mining times to file."""
    with open(USER_TIMES_FILE, 'w') as file:
        json.dump(user_mining_times, file, indent=4)

def load_active_miners():
    """Load active miners from file."""
    global active_miners
    try:
        with open(ACTIVE_MINERS_FILE, 'r') as file:
            active_miners = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        active_miners = {}

def save_active_miners():
    """Save active miners to file."""
    with open(ACTIVE_MINERS_FILE, 'w') as file:
        json.dump(active_miners, file, indent=4)

@app.route('/<int:user_id>')
def home(user_id):
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    return render_template_string(html_template, ip_address=client_ip, user_id=user_id)

@app.route('/start_mining/<int:user_id>', methods=['POST'])
def start_mining(user_id):
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    add_miner(client_ip, user_id)  
    return '', 204

@app.route('/stop_mining/<int:user_id>', methods=['POST'])
def stop_mining(user_id):
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    remove_miner(client_ip, user_id)
    return '', 204

@app.route('/')

def get_user_details():
    user_id_str = request.args.get('userid')
    ip_address = user_ips.get(user_id_str, "IP not found")
    total_time = user_mining_times.get(user_id_str, 0)
    is_mining = any(ip for ip in active_miners.get(user_id_str, {}).keys())
    return jsonify({
        "ip_address": ip_address,
        "total_time": f"{total_time / 3600:.2f} Hours",
        "is_mining": is_mining
    })



@app.route('/stats')
def stats():
    return jsonify(mining_stats)

@app.route('/total_time/<int:user_id>')
def total_time(user_id):
    user_id_str = str(user_id)
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    start_time = active_miners.get(user_id_str, {}).get(client_ip, 0)
    if start_time:
        session_time = round(time.time() - start_time)
    else:
        session_time = 0
    total_time = user_mining_times.get(user_id_str, 0)
    return jsonify({'totalTime': total_time, 'sessionTime': session_time})

@app.route('/session_time/<int:user_id>')
def session_time(user_id):
    user_id_str = str(user_id)
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    start_time = active_miners.get(user_id_str, {}).get(client_ip, 0)
    if start_time:
        session_time = round(time.time() - start_time)
    else:
        session_time = 0
    return jsonify({'sessionTime': session_time})
def fetch_mining_stats():
    global mining_stats
    while True:
        try:

            response = requests.get(f'{BASE_API_URL}/account/stats', headers=HEADERS)
            if response.status_code == 200:
                site_stats = response.json()
                if site_stats['status'] == 'success':
                    mining_stats = {
                        'hashRate': site_stats['message'].get('hashrate', 'Unavailable'),
                        'reward': site_stats['message'].get('reward', 'Unavailable')
                    }
                else:
                    print("Failed to fetch site stats:", site_stats.get('message'))
            else:
                print("Failed to fetch site stats:", response.status_code, response.text)
        except Exception as e:
            print(f"An error occurred: {e}")
        time.sleep(30) 

@app.route('/heartbeat/<int:user_id>', methods=['POST'])
def heartbeat(user_id):
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_id_str = str(user_id)
    if user_id_str in active_miners and client_ip in active_miners[user_id_str]:
        active_miners[user_id_str][client_ip] = time.time()  
    return '', 204

@app.route('/active_miners')
def active_miners_list():
    return jsonify({'miners': [f'{user_id}: {list(miners.keys())}' for user_id, miners in active_miners.items()]})

def add_miner(ip_address, user_id):
    """Adds a miner to the active miners list."""
    user_id_str = str(user_id)
    if user_id_str not in active_miners:
        active_miners[user_id_str] = {}
    if ip_address not in active_miners[user_id_str]:
        active_miners[user_id_str][ip_address] = time.time()
    

    user_ips[user_id_str] = ip_address
    save_user_ips()
    save_active_miners()

def remove_miner(ip_address, user_id):
    """Removes a miner from the active miners list and updates the mining time."""
    user_id_str = str(user_id)
    if user_id_str in active_miners and ip_address in active_miners[user_id_str]:
        start_time = active_miners[user_id_str].pop(ip_address) 
        mining_time = round(time.time() - start_time)
        if user_id_str in user_mining_times:
            user_mining_times[user_id_str] += mining_time
        else:
            user_mining_times[user_id_str] = mining_time
        save_user_mining_times()
        save_active_miners()


def log_ip_address(ip_address, user_id):
    with open(LOG_FILE, 'a') as log_file:
        log_file.write(f"{time.ctime()}: User {user_id} with IP {ip_address} started mining.\n")

def mining_monitor():
    while True:
        time.sleep(MINER_TIMEOUT)
        now = time.time()
        for user_id_str, miners in list(active_miners.items()):
            for ip, last_seen in list(miners.items()):
                if now - last_seen > MINER_TIMEOUT:
                    remove_miner(ip, int(user_id_str))  

if __name__ == '__main__':
    load_user_mining_times()
    load_active_miners()
    load_user_ips()
    threading.Thread(target=mining_monitor, daemon=True).start()
    threading.Thread(target=fetch_mining_stats, daemon=True).start() 
    app.run(host='0.0.0.0', port=5000, debug=True)