import pandas as pd
import requests
import json
import numpy as np
import re

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

def getcoindata(address):
    if address[-3:]=='LWF':
        url='https://wallet.lwf.io/api/'
        #coin='LWF'
        payaccts=json.load(open('LWFPayoutAccts.json'))
        pools=getpools('LWFPools.txt')
    elif address[-1:]=='X':
        url='https://wallet.oxycoin.io/api/'
        #coin='OXY'
        payaccts=json.load(open('OXYPayoutAccts.json'))
        pools=getpools('OXYPools.txt')
    else:
        url=None
        payaccts=None
    if payaccts is not None:
        payaccts={i['address']:i['payaddress'] for i in payaccts}
    return url,payaccts,pools    
def getpools(file):
    pools = open(file, 'r').read()
    pools = pools.replace('`','').lower()
    pools = max(pools.split('*'), key=len).split(';')
    pools = pd.DataFrame(pools,columns=['string'])
    pools['delegate'] = pools['string'].str.extract('^\s*([a-z0-9_.]*)', expand=False)
    pools['listed % share'] = pools['string'].str.extract('\(*[x]*([0-9.]*)\%', expand=False)
    pools['listed frequency'] = pools['string'].str.extract('\%-([a-z0-9]*)\,*\)*', expand=False)
    pools.loc[pools['listed frequency']=='w', ['listed frequency']] = 7
    pools.loc[pools['listed frequency']=='d', ['listed frequency']] = 1
    pools.loc[pools['listed frequency']=='2d', ['listed frequency']] = 2
    pools['listed frequency']=pd.to_numeric(pools['listed frequency'])
    del pools['string']
    return pools

def getpayoutstats(address,days=35):
    url,payaccts,pools=getcoindata(address)
    if (url is None) or (payaccts is None):
        return None
    incomingtxs=getincomingtxs(url,address,days)
    votes=getvotes(url,address)
    votes['address']=votes['address'].replace(payaccts)
    balance=getbalance(url,address)
    txstats=incomingtxs.sort_values(by=['senderId','timestamp'],ascending=False)
    txstats['frequency']=txstats['Days_Elapsed'].diff()
    txstats.loc[txstats['frequency']<0, 'frequency'] = None
    txstats['count']=1
    txstats['payments']=txstats['amount']
    txstats=txstats.groupby('senderId').agg({'Days_Elapsed':'first','frequency':'mean','amount':'sum','payments':'mean','count':'count'}).reset_index()
    txstats=txstats[txstats['amount']>0]
    payoutstats=pd.merge(votes,txstats,how='left',left_on='address',right_on='senderId')
    payoutstats['vote count'] = payoutstats.groupby('senderId')['senderId'].transform('count')
    payoutstats['total approval'] = payoutstats.groupby('senderId')['approval'].transform('sum')
    payoutstats['amount']=pd.to_numeric(payoutstats['amount'])/100000000
    payoutstats['amount']=payoutstats['amount']*payoutstats['total approval']/(payoutstats['approval']*payoutstats['vote count'])/payoutstats['vote count']
    payoutstats['payments']=payoutstats['payments']*payoutstats['total approval']/(payoutstats['approval']*payoutstats['vote count'])/payoutstats['vote count']
    payoutstats['vote']=pd.to_numeric(payoutstats['vote'])/100000000
    payoutstats['payments']=pd.to_numeric(payoutstats['payments'])/100000000
    payoutstats['frequency']=pd.to_numeric(payoutstats['frequency'])
    payoutstats['portion']=((days*5*24*60*4/201)*(balance/payoutstats['vote']))
    payoutstats['% shared']=payoutstats['amount']/payoutstats['portion']
    payoutstats['paid x approval']=payoutstats['amount']*payoutstats['approval']/100
    payoutstats.loc[payoutstats['count']>1,'% shared'] = payoutstats['payments']/((payoutstats['frequency']*5*24*60*4/201)*(balance/payoutstats['vote']))
    payoutstats.loc[payoutstats['rank']>201, ['% shared','portion']] = None
    cols=['count','frequency','amount','Days_Elapsed','paid x approval']
    for i in cols:
        payoutstats[i]=payoutstats[i].round(2)
    payoutstats=payoutstats.sort_values(by='paid x approval',ascending=False)
    payoutstats.rename(columns={'username': 'delegate', 'Days_Elapsed': 'last paid (days)','amount':'total paid','count':'payouts','frequency':'pay freq (days)','% shared':'percent shared'}, inplace=True)
    dropcols=['address','productivity','senderId','rate','publicKey','producedblocks','missedblocks','approval','vote','payments','portion','vote count','total approval','percent shared','payouts']
    payoutstats=payoutstats.drop(dropcols,axis=1)
    payoutstats = pd.merge(payoutstats,pools,how='left',on='delegate')
    payoutstats=payoutstats.set_index('delegate')
    payoutstats.index.name = None
    payoutstats['comments']=''
    payoutstats.loc[((payoutstats['listed frequency']+(7/payoutstats['listed frequency'])*(50000/balance)<payoutstats['last paid (days)'])&(payoutstats['listed frequency'])>0), ['comments']] = 'payout overdue'
    payoutstats.loc[(payoutstats['last paid (days)'].isnull()&(payoutstats['listed frequency'])>0), ['comments']] = 'no payouts yet'
    payoutstats.loc[payoutstats['rank']>201, ['comments']] = 'not forging'
    payoutstats = payoutstats.replace(np.nan, '', regex=True)
    return payoutstats
