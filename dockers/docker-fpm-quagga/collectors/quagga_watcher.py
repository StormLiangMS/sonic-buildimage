#!/usr/bin/env python

import os
import sys
import subprocess
import re
import json
import netaddr
import datetime
import time
import syslog
import traceback
import signal

from pprint import pprint


g_run = True


def is_announced_by_bgp(dm, addr):
    bgpd_config = dm.get_output('show run')
    if addr in bgpd_config:
        for l in bgpd_config.split('\n'):
            if 'network' in l and addr in l:
                return True

    return False

def read_config_db(dm):
    with open("/etc/sonic/config_db.json") as fp:
      j = json.load(fp)

    lo_ipv4_prefixes = [str(r.split('|')[1]) for r in j["LOOPBACK_INTERFACE"] if '.' in r]
    lo_ipv6_prefixes = [str(r.split('|')[1]) for r in j["LOOPBACK_INTERFACE"] if ':' in r]
    # We use /64 for loopback interfaces to save ASIC resources
    lo_ipv6_prefixes = ["%s/64" % a.split('/')[0] for a in lo_ipv6_prefixes]

    lo_ipv4_prefixes = filter(lambda addr: is_announced_by_bgp(dm, addr), lo_ipv4_prefixes)
    lo_ipv6_prefixes = filter(lambda addr: is_announced_by_bgp(dm, addr), lo_ipv6_prefixes)

    vlan_ipv4_prefixes = []
    vlan_ipv6_prefixes = []
    for r in j["VLAN_INTERFACE"]:
        a = netaddr.IPNetwork(r.split('|')[1])
        addr = "%s/%d" % (a.network, a.prefixlen)
        if is_announced_by_bgp(dm, addr):
            if '.' in addr:
                vlan_ipv4_prefixes.append(addr)
            elif ':' in r:
                vlan_ipv6_prefixes.append(addr)

    prefixes = {
        'ip':   { 'lo':lo_ipv4_prefixes, 'vlan':vlan_ipv4_prefixes },
        'ipv6': { 'lo':lo_ipv6_prefixes, 'vlan':vlan_ipv6_prefixes },
    }

    return prefixes


class DataManager(object):
    def __init__(self):
        self.collected = {}

    def run_cmd(self, cmd):
        process = subprocess.Popen(cmd,
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        return_code = process.returncode

        return stdout, stderr, return_code

    def vty(self, cmd):
        out, err, exit_code = self.run_cmd("vtysh -c '%s'" % cmd)
        if exit_code == 0:
            return True, out
        else:
            syslog.syslog(syslog.LOG_ERR, "Error running a cmd '%s': %s" % (cmd, str(err)))
        return False, None

    def get_output(self, cmd):
        if cmd not in self.collected:
            res, out = self.vty(cmd)
            if not res:
                return ""
            self.collected[cmd] = out

        return self.collected[cmd]

    def clear(self):
        self.collected = {}


def get_bgp_speakers(dm, family): # FIXME: if len < 20,
    txt = dm.get_output('show %s bgp summary' % family)
    t = txt.split('\n')
    # Add a lint if it starts with *, has length more than 10 don't have something on second position and has Established session
    lines = [line for line in t if line.startswith('*') and len(line) > 10 and line[1] != ' ' and line.strip().split(' ')[-1].isdigit()]
    speakers = [line.split()[0].replace('*', '') for line in lines if int(line.split()[-1]) != 0]
    return [s for s in speakers if family == 'ip' and '.' in s or family == 'ipv6' and ':' in s]


def get_bgp_t1s(dm, family, # FIXME: if len < 20,
        pat_v4=re.compile("\A\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3} "),
        pat_v6=re.compile("\A[:0-9a-fA-F]+:[:0-9a-fA-F]+(\Z| )")):
    txt = dm.get_output('show %s bgp summary' % family)
    t = txt.split('\n')
    pat = pat_v4 if family == 'ip' else pat_v6
    t_combined = [] # sometimes ipv6 addresses so long, so quagga put a long
                    # address on one line, and all other information on other
                    # Example:
                    #
                    # 2603:1090:f08:40::49
                    #                4 64801  112718  112055        0    0    0 08w0d00h       93
    acc = ""
    for l in t:
        if l == "":
            continue
        if len(l) <= 40: # length of full ipv6 address: XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX:XXXX
            acc = l
        else:
            t_combined.append(acc + l)
            acc = ""
    return [pat.match(line).group(0).strip() for line in t_combined if pat.match(line) and line.strip().split(' ')[-1].isdigit()]


def get_routes(dm, routes_family, nei,
    pat_v4=re.compile("\A\*(>|=| ) \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}"),
    pat_v6=re.compile("\A\*(>|=| ) [:/0-9a-fA-F]+ ")):
    txt = dm.get_output('show %s bgp neigh %s routes' % (routes_family, nei))
    t = txt.split('\n')
    pat = pat_v4 if routes_family == 'ip' else pat_v6
    return [pat.match(line).group(0)[3:].strip() for line in t if pat.match(line)]


def get_bgp_sp_routes(dm, routes_family, speakers):
    prefixes = set()
    for speaker in speakers:
        routes = get_routes(dm, routes_family, speaker)
        prefixes = prefixes | set(routes)
    return list(prefixes)


def get_missing_adv(dm, family, t1s, expected_prefixes):
    if len(expected_prefixes) == 0:
        return [], [], []
    adv = {}
    for t1 in t1s:
        adv[t1] = dm.get_output('show %s bgp neigh %s advertised-routes' % (family, t1))

    result = list()
    result_prefix = []
    result_no_adv = []
    for prefix in expected_prefixes:
        counter = 0
        not_found = []
        for t1 in t1s:
            if prefix in adv[t1]:
                counter += 1
            else:
                not_found.append(t1)
        if (len(t1s) - counter) > 0:
            s = "%s: Missing on [%s]" % (prefix, ", ".join(sorted(not_found)))
            percent = (counter*100) / len(t1s)
            s += " { active_t1s=%d available_on_t1s=%d percent=%02d%% }" % (len(t1s), counter, percent)
            result.append(s)
            result_prefix.append(prefix)
        if counter == 0:
            result_no_adv.append(prefix)
    return result, result_prefix, result_no_adv


def check(dm, family, t1s, prefixes):
    lo_missing, lo_miss_pr, lo_no_adv = get_missing_adv(dm, family, t1s, prefixes['lo'])
    vl_missing, vl_miss_pr, vl_no_adv = get_missing_adv(dm, family, t1s, prefixes['vlan'])
    sp_missing, sp_miss_pr, sp_no_adv = get_missing_adv(dm, family, t1s, prefixes['vip'])

    syslog_messages = []
    alert_messages  = []
    if len(lo_missing) > 0:
        syslog_messages.append("!!! Loopback address is missing: %s" % ", ".join(lo_missing))
    if len(vl_missing) > 0:
        syslog_messages.append("!!! Vlan address is missing: %s" % ", ".join(vl_missing))
    if len(sp_missing) > 0:
        syslog_messages.append("!!! Speaker advertised addresses are missing: %s" % ", ".join(sp_missing))

    if len(lo_no_adv) > 0:
        syslog_messages.append("Loopback no adv on all T1 for [ %s ]" % ", ".join(lo_no_adv))

    if len(vl_no_adv) > 0:
        alert_messages.append("VLANs no adv on all T1 for [ %s ]" % ", ".join(lo_no_adv))

    if len(sp_no_adv) > 0:
        alert_messages.append("VIPs no adv on all T1 for [ %s ]" % ", ".join(lo_no_adv))

    return syslog_messages, alert_messages


def one_run(dm, state, prefixes):
    syslog_messages = set()
    alert_messages = set()
    for adv_family in ['ip', 'ipv6']:
        family_prefixes = prefixes[adv_family]
        t1s = get_bgp_t1s(dm, adv_family)
        for rcv_family in ['ip', 'ipv6']:
            speakers = get_bgp_speakers(dm, rcv_family)
            family_prefixes['vip'] = get_bgp_sp_routes(dm, adv_family, speakers)
            syslog_msg, alert_msg = check(dm, adv_family, t1s, family_prefixes)
            syslog_messages.update(syslog_msg)
            alert_messages.update(alert_msg)

    if len(syslog_messages) > 0:
        if state['counter'] >= 2:
            for message in syslog_messages:
                syslog.syslog(syslog.LOG_ERR, message)
            for message in alert_messages:
                syslog.syslog(syslog.LOG_ALERT, message)
        state['counter'] += 1
    else:
        state['counter'] = 0
    dm.clear()


def check_type():
    with open('/etc/sonic/config_db.json') as fp:
        j = json.load(fp)
    if 'DEVICE_METADATA' in j \
      and 'localhost' in j['DEVICE_METADATA'] \
      and 'type' in j['DEVICE_METADATA']['localhost'] \
      and str(j['DEVICE_METADATA']['localhost']['type']) == 'ToRRouter':
        return True

    return False


def signal_handler(signum, frame):
    global g_run
    g_run = False


def main():
    if not check_type():
        syslog.syslog(syslog.LOG_NOTICE, "only ToR is supported. exiting")
        return

    syslog.syslog(syslog.LOG_NOTICE, "started")
    try:
        dm = DataManager()
        prefixes = read_config_db(dm)
        syslog.syslog(syslog.LOG_NOTICE, "start watching")
        while g_run:
            state = { 'counter': 0 }
            for _ in range(3):
                if not g_run:
                    break
                one_run(dm, state, prefixes)
                time.sleep(60) # sleep a minute between runs
            if not g_run:
                break
            time.sleep(3600-180) # sleep an hour between checks
    except Exception as e:
        raise
    finally:
        syslog.syslog(syslog.LOG_NOTICE, "stop watching")


if __name__ == '__main__':
    try:
        syslog.openlog('quagga_watcher')
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        main()
    except KeyboardInterrupt:
        syslog.syslog(syslog.LOG_NOTICE, "SIGINT received")
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, "Got an exception %s: Traceback: %s" % (str(e), traceback.format_exc()))
    finally:
        syslog.closelog()
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)
