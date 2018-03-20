import pandas as pd
import requests
import json

def getpubkey(url,address):
    pubkey = requests.get(url+'accounts/getPublicKey?address='+address).json()['publicKey']
    return pubkey

def getbalance(url,address):
    balance = float(requests.get(url+'accounts/getBalance?address='+address).json()['balance'])/100000000
    return balance

def getvotes(url,address):
    votes = pd.DataFrame(requests.get(url+'accounts/delegates?address='+address).json()['delegates'])
    return votes

def getvoters(url,address):
    pubkey = getpubkey(url,address)
    voters = pd.DataFrame(requests.get(url+'delegates/voters?publicKey='+pubkey).json()['accounts'])
    return voters

def getdelegates(url):
    delegates = pd.DataFrame(requests.get(url+'delegates?orderBy=vote').json()['delegates'])
    delegates['vote']=pd.to_numeric(delegates['vote'])
    return delegates

def getincomingtxs(url,address,days=35):
    i=0
    incomingtxs = pd.DataFrame(requests.get(url+'transactions?recipientId='+address+'&offset='+str(i)+'&orderBy=timestamp:desc').json()['transactions'])
    incomingtxs.sort_values(by='timestamp',ascending=False)
    now = incomingtxs['timestamp'].iloc[0]
    incomingtxs['Days_Elapsed']=(now-incomingtxs['timestamp'])/(24*60*60)
    last = incomingtxs['Days_Elapsed'].iloc[-1]
    length = len(incomingtxs)
    while last <= days:
        i=i+length
        incomingtxs1 = pd.DataFrame(requests.get(url+'transactions?recipientId='+address+'&offset='+str(i)+'&orderBy=timestamp:desc').json()['transactions'])
        if not incomingtxs1.empty:
            incomingtxs1['Days_Elapsed']=(now-incomingtxs1['timestamp'])/(24*60*60)
            incomingtxs=incomingtxs.append(incomingtxs1,ignore_index=True)
            last = incomingtxs['Days_Elapsed'].iloc[-1]
        else:
            last = days+1
    incomingtxs=incomingtxs[incomingtxs['Days_Elapsed']<=days]
    return incomingtxs

def getpayoutstats(address,days=35):
    if address[-3:]=='LWF':
        url='https://wallet.lwf.io/api/'
        #coin='LWF'
        payoutaccts=json.load(open('LWFPayoutAccts.json'))['payoutaccts']
    elif address[-1:]=='X':
        url='https://wallet.oxycoin.io/api/'
        #coin='OXY'
        payoutaccts=json.load(open('OXYPayoutAccts.json'))['payoutaccts']
    else:
        return None
    incomingtxs=getincomingtxs(url,address,days)
    votes=getvotes(url,address)
    votes['address']=votes['address'].replace(payoutaccts)
    balance=getbalance(url,address)
    txstats=incomingtxs.sort_values(by=['senderId','timestamp'],ascending=False)
    txstats['frequency']=txstats['Days_Elapsed'].diff()
    txstats.loc[txstats['frequency']<0, 'frequency'] = None
    txstats['count']=1
    txstats['payments']=txstats['amount']
    txstats=txstats.groupby('senderId').agg({'Days_Elapsed':'first','frequency':'mean','amount':'sum','payments':'mean','count':'count'}).reset_index()
    txstats=txstats[txstats['amount']>0]
    payoutstats=pd.merge(votes,txstats,how='left',left_on='address',right_on='senderId')
    payoutstats['amount']=pd.to_numeric(payoutstats['amount'])/100000000
    payoutstats['vote']=pd.to_numeric(payoutstats['vote'])/100000000
    payoutstats['payments']=pd.to_numeric(payoutstats['payments'])/100000000
    payoutstats['portion']=((days*5*24*60*4/201)*(balance/payoutstats['vote']))
    payoutstats['% shared']=payoutstats['amount']/payoutstats['portion']
    payoutstats.loc[payoutstats['count']>1,'% shared'] = payoutstats['payments']/((payoutstats['frequency']*5*24*60*4/201)*(balance/payoutstats['vote']))
    payoutstats.loc[payoutstats['rank']>201, ['% shared','portion']] = None
    cols=['count','frequency','amount','Days_Elapsed']
    for i in cols:
        payoutstats[i]=payoutstats[i].round(1)
    payoutstats=payoutstats.sort_values(by='amount',ascending=False)
    payoutstats.rename(columns={'username': 'delegate', 'Days_Elapsed': 'days since last payout','amount':'total paid','count':'payout count','frequency':'days between payouts','% shared':'percent shared'}, inplace=True)
    dropcols=['address','productivity','senderId','rate','publicKey','producedblocks','missedblocks','approval','vote','payments','portion']
    payoutstats=payoutstats.drop(dropcols,axis=1)
    payoutstats=payoutstats.set_index('delegate')
    payoutstats.index.name = None
    return payoutstats
