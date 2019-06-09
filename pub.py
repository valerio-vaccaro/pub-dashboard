from flask import Flask, flash, redirect, render_template, request, session, abort
from flask_stache import render_view, render_template
from flask_qrcode import QRcode
from bitcoin_rpc_class import RPCHost
import os
import time
import configparser
import json

app = Flask(__name__, static_url_path='/static')
qrcode = QRcode(app)
torBaseDir = "/var/lib/tor/hidden_service"

config = configparser.RawConfigParser()
config.read('liquid.conf')

admin = config.get('GENERAL', 'admin') == "True"
liquid_instance = config.get('GENERAL', 'liquid_instance')
username = config.get('GENERAL', 'username')
password = config.get('GENERAL', 'password')

rpcHost = config.get(liquid_instance, 'host')
rpcPort = config.get(liquid_instance, 'port')
rpcUser = config.get(liquid_instance, 'username')
rpcPassword = config.get(liquid_instance, 'password')
rpcPassphrase = config.get(liquid_instance, 'passphrase')
rpcWallet = config.get(liquid_instance, 'wallet')
rpcVersion = config.get(liquid_instance, 'version')
rpcChain = config.get(liquid_instance, 'chain')
policyasset = config.get(liquid_instance, 'policyasset')

if (len(rpcWallet) > 0):
    serverURL = 'http://' + rpcUser + ':' + rpcPassword + '@'+rpcHost+':' + str(rpcPort) + '/wallet/' + rpcWallet
else:
    serverURL = 'http://' + rpcUser + ':' + rpcPassword + '@'+rpcHost+':' + str(rpcPort)

host = RPCHost(serverURL)
if (len(rpcPassphrase) > 0):
    result = host.call('walletpassphrase', rpcPassphrase, 60)
    print(result)

@app.route('/', methods = ['GET', 'POST'])
def home():
    if not session.get('logged_in'):
        data = {
        }
        return render_template('login', **data)
    else:
        command = ""
        action = ""
        result = ""
        if request.method == 'POST':
            if admin:
                command = request.form.get('command')
                action = request.form.get('action')

            if command == 'linux':
                if action == 'stop':
                    status = os.popen("halt -t now").read()
            elif command == 'liquid':
                if action == 'start':
                    status = os.popen("systemctl start liquidd").read()
                elif action == 'stop':
                    status = os.popen("systemctl stop liquidd").read()
                elif action == 'restart':
                    status = os.popen("systemctl restart liquidd").read()
            elif command == 'tor':
                if action == 'start':
                    status = os.popen("systemctl start tor").read()
                elif action == 'stop':
                    status = os.popen("systemctl stop tor").read()
                elif action == 'restart':
                    status = os.popen("systemctl restart tor").read()
                elif action == 'change':
                    status = os.popen("systemctl stop tor").read()
                    status = os.popen("#mv "+torBaseDir+" "+torBaseDir+"/../backup/").read()
                    status = os.popen("systemctl start tor").read()

        info = host.call('getblockchaininfo')
        data = {
            'info': info,
            'torAddr': os.popen("cat "+torBaseDir+"/hostname").read(),
            'uptime': os.popen("uptime").read(),
            'uname': os.popen("uname -a").read(),
            'torStatus': os.popen("systemctl is-active tor").read(),
            'liquidStatus': os.popen("systemctl is-active liquidd").read(),
            'result' : result,
            'admin' : admin,
        }
        return render_template('home', **data)

@app.route('/login', methods = ['POST'])
def do_admin_login():
    if request.form['password'] == password and request.form['username'] == username:
        session['logged_in'] = True
    else:
        flash('wrong password!')
    return home()

@app.route("/logout")
def logout():
    session['logged_in'] = False
    return home()

@app.route('/tx', methods = ['GET'])
def tx():
    if not session.get('logged_in'):
        data = {
        }
        return render_template('login', **data)
    else:
        result = "ERR"

        if request.method == 'GET':
            tx = request.args.get('hex')
            print(tx)
            result = host.call('getrawtransaction', tx, True)

        data = {
            'tx' : tx,
            'results' : json.dumps(result, indent=4, sort_keys=True),
        }
        return render_template('tx', **data)

@app.route('/blocks', methods = ['GET'])
def blocks():
    if not session.get('logged_in'):
        data = {
        }
        return render_template('login', **data)
    else:
        result = "ERR"

        max = host.call('getblockcount')
        min = max-10

        results = []

        for i in range (max, min, -1):
            print(i)
            hash = host.call('getblockhash', i)
            block = host.call('getblock', hash)
            results.append({'id':i, 'hash':hash, 'size':block['size'], 'time':block['time'], 'nTx':block['nTx']})

        data = {
            'results' : results,
        }
        return render_template('blocks', **data)

@app.route('/block', methods = ['GET'])
def block():
    if not session.get('logged_in'):
        data = {
        }
        return render_template('login', **data)
    else:
        result = "ERR"

        if request.method == 'GET':
            height = request.args.get('height')
            print(height)
            id = host.call('getblockhash', int(height))
            result = host.call('getblock', id, 2)

        data = {
            'tx' : id,
            'results' : json.dumps(result, indent=4, sort_keys=True),
        }
        return render_template('block', **data)


@app.route('/lbtc', methods = ['GET', 'POST'])
def lbtc():
    if not session.get('logged_in'):
        data = {
        }
        return render_template('login', **data)
    else:
        newaddress = ""
        qrcodeaddress = ""
        result = ""
        assets_sent=[]
        assets_received=[]
        txs = host.call('listtransactions', '*', 1000000)
        for tx in txs:
            item={}
            item['tx'] = tx['txid'][:8]+"..."
            item['transaction'] = tx['txid']
            item['transaction_url'] = "./tx?hex="+tx['txid']
            item['asset'] = tx['asset']
            item['amount'] = tx['amount']
            if item['amount'] > 0 and item['asset'] == policyasset :
                assets_received.append(item)
            if item['amount'] < 0 and item['asset'] == policyasset :
                assets_sent.append(item)
        if request.method == 'POST':
            command = request.form.get('command')
            action = request.form.get('action')

            if command == 'address':
                if action == 'new':
                    address = host.call('validateaddress', host.call('getnewaddress'))
                    newaddress = address
                    qrcodeaddress = qrcode(address['address'])
            elif command == 'lbtc':
                if action == 'send':
                    address = request.form.get('address')
                    amount = request.form.get('amount')
                    if host.call('validateaddress', address)['isvalid']:
                        tx = host.call('sendtoaddress', address, amount)
                        result = "Sent "+str(amount)+" LBTC to address "+address+" with transaction "+tx+"."
                    else:
                        result = "ERR"
                elif action == 'generate':
                    result = host.call('generate', 1)
                elif action ==  'broadcast':
                    tx = request.form.get('tx')
                    result = host.call('sendrawtransaction', tx)

        balances = host.call('getbalance')
        wallets = host.call('listwallets')

        data = {
            'assets_received' : assets_received,
            'assets_sent' : assets_sent,
            'newaddress' : newaddress,
            'newaddress_qr' : qrcodeaddress,
            'balances' : balances,
            'result' : result,
            'wallets' : wallets,
        }
        if (rpcChain=='regtest'):
            data['generate'] = True

        return render_template('lbtc', **data)

@app.route('/asset',  methods = ['GET', 'POST'])
def asset():
    if not session.get('logged_in'):
        data = {
        }
        return render_template('login', **data)
    else:
        balances = host.call('getbalance')
        results=[]
        assets_sent=[]
        assets_received=[]
        issuances = host.call('listissuances')
        for asset in issuances:
            item={}
            item['asset'] = asset['asset']
            item['amount'] = asset['assetamount']
            try:
                item['actual'] = balances[item['asset']]
            except:
                print("ERR")
            results.append(item)
        txs = host.call('listtransactions', '*', 1000000)
        for tx in txs:
            item={}
            item['tx'] = tx['txid'][:8]+"..."
            item['transaction'] = tx['txid']
            item['transaction_url'] = "./tx?hex="+tx['txid']
            item['asset'] = tx['asset']
            item['amount'] = tx['amount']
            item['actual'] = 0
            try:
                item['actual'] = balances[item['asset']]
            except:
                print('error')
            if item['amount'] > 0 and item['asset'] != policyasset and item['asset'] != '0000000000000000000000000000000000000000000000000000000000000000':
                assets_received.append(item)
            if item['amount'] < 0 and item['asset'] != policyasset and item['asset'] != '0000000000000000000000000000000000000000000000000000000000000000':
                assets_sent.append(item)

        command = request.form.get('command')
        action = request.form.get('action')
        result = ""
        if command == 'asset':
            if action == 'create':
                asset_amount = request.form.get('asset_amount')
                token_amount = request.form.get('token_amount')
                tx = host.call('issueasset', asset_amount, token_amount)
                result = "Generate "+str(asset_amount)+" of asset "+tx['asset']+" and "+str(token_amount)+" of reissuance tokens"+tx['token']+"."
            if action == 'send':
                address = request.form.get('address')
                asset = request.form.get('asset')
                amount = request.form.get('amount')
                if host.call('validateaddress', address)['isvalid']:
                    tx = host.call('sendtoaddress', address, amount, "", "", False, False, 100, "ECONOMICAL", asset)
                    result = "Sent "+str(amount)+" "+amount+" to address "+address+" with transaction "+tx+"."
                else:
                    result = "Wrong address!"

        data = {
            'balances' : balances,
            'results': results,
            'assets_sent': assets_sent,
            'assets_received': assets_received,
            'result' : result,
        }
        return render_template('asset', **data)

@app.route('/about')
def about():
    data = {
    }
    return render_template('about', **data)

if __name__ == '__main__':
    app.import_name = '.'
    app.secret_key = os.urandom(12)
    #app.debug = True
    app.run(host='0.0.0.0', port=5000)
