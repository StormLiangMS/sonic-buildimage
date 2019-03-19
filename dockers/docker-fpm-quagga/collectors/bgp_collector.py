#!/usr/bin/env python

import sys
import os
import socket
import select
import ctypes
import struct
import binascii
import datetime
import time
import gzip
import json
import io
import os.path
from pprint import pprint
import syslog
import traceback
import signal


DIR = '/var/log/quagga/bgp_collector'


g_run = True


class Interface(object):
    ETH_P_ALL = 0x03
    RCV_TIMEOUT = 1000
    RCV_SIZE = 10000  # support jumbo frames

    def __init__(self, iface_name):
        self.iface_name = iface_name
        self.socket = None
        with open("/sys/class/net/%s/address" % self.iface_name) as fp:
            self.mac_address = fp.readline()

    def __del__(self):
        if self.socket:
            self.socket.close()

    def bind(self, bpf_src=None):
        SO_ATTACH_FILTER = 26

        self.socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(self.ETH_P_ALL))
        if bpf_src is not None:
            blob = ctypes.create_string_buffer(''.join(struct.pack("HBBI", *e) for e in bpf_src))
            address = ctypes.addressof(blob)
            bpf = struct.pack('HL', len(bpf_src), address)
            self.socket.setsockopt(socket.SOL_SOCKET, SO_ATTACH_FILTER, bpf)
        self.socket.bind((self.iface_name, 0))
        self.socket.settimeout(self.RCV_TIMEOUT)

    def handler(self):
        return self.socket.fileno()

    def recv(self):
        data = self.socket.recv(self.RCV_SIZE)
        return data

    def get_mac(self):
        return self.mac_address

    def name(self):
        return self.iface_name


class Poller(object):
    def __init__(self, interfaces, event_handler, cron_manager):
        self.event_handler = event_handler
        self.cron_manager = cron_manager
        self.mapping = { interface.handler() : interface for interface in interfaces }
        self.poller = select.epoll()
        for interface in interfaces:
            self.poller.register(interface.handler(), select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP)
            syslog.syslog(syslog.LOG_NOTICE, "enabling polling on interface %s" % interface.name())

    def __del__(self):
        self.poller.close()

    def poll(self):
        while g_run:
            try:
                events = self.poller.poll(timeout=10)
            except IOError as e:
                if e.errno == 4: # Interrupted system call
                    continue
                else:
                    raise
            for handler, event_type in events:
                self.event_handler.action(self.mapping[handler], event_type)
            ok = self.cron_manager.action()
            if not ok:
                return


class Writer(object):
    def __init__(self, iface_name):
        self.name = iface_name
        self.create_file()

    def __del__(self):
        self.close_file()

    def save(self, data):
        cur_time = datetime.datetime.utcnow()
        if self.last_time_created_file.day != cur_time.day: # rotate file every day at 00:00
            self.rotate()
        tv_sec = time.time()
        tv_usec = cur_time.microsecond
        packet_header = struct.pack('IIII', tv_sec, tv_usec, len(data), len(data))
        self.fd.write(packet_header)
        self.fd.write(data)

    def create_file(self):
        filename = self.name + '_' + datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S") + '.pcap.gz'
        full_name = os.path.join(DIR, filename)
        self.gz = gzip.open(full_name, "wb")
        self.fd = io.BufferedWriter(self.gz, buffer_size=2**20)
        pcap_header = struct.pack('IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, 0x40000, 0x1)
        self.fd.write(pcap_header)
        self.last_time_created_file = datetime.datetime.utcnow()

    def close_file(self):
        self.fd.flush()
        self.gz.flush()
        self.gz.close()

    def rotate(self):
        self.close_file()
        self.create_file()


class EventHandler(object):
    def __init__(self):
        self.writers = {}

    def action(self, interface, event_type):
        if interface.name() not in self.writers:
            self.writers[interface.name()] = Writer(interface.name())
        try:
            data = interface.recv()
        except socket.error as error:
            data = None
        if event_type == select.EPOLLIN and data is not None and len(data) != 0:
            self.writers[interface.name()].save(data)


class CronJob(object):
    def __init__(self, interval):
        self.next = None
        self.offset = datetime.timedelta(seconds = interval)

    def start(self):
        self.next = datetime.datetime.utcnow() + self.offset

    def run(self):
        if self.next is None:
            return True
        cur_time = datetime.datetime.utcnow()
        if cur_time > self.next:
            self.next = cur_time + self.offset
            return self.action()
        else:
            return True

    def action(self):
        return True


class CronManager(object):
    def __init__(self):
        self.jobs = []
        self.started = False

    def start(self):
        self.started = True
        for j in self.jobs:
            j.start()

    def add_job(self, job):
        self.jobs.append(job)
        if self.started:
            job.start()

    def action(self):
        ret = True
        if self.started:
            for j in self.jobs:
                ret = ret and j.run()
        return ret


class CleanJob(CronJob):
    def __init__(self, interval=300, max_dir_size=2**30, min_fs_free=2**30):
        super(CleanJob, self).__init__(interval=interval)
        self.max_dir_size = max_dir_size
        self.min_fs_free = min_fs_free

    def action(self):
        remove_size_dir = self.calculate_dir()
        remove_size_vfs = self.calculate_root_vfs()
        remove_size = max(remove_size_vfs, remove_size_dir)
        self.remove_files(remove_size)

        return True

    def calculate_dir(self):
        total_size = 0
        for filename in os.listdir(DIR):
            full_name = os.path.join(DIR, filename)
            total_size += os.stat(full_name).st_size
        ret = total_size < self.max_dir_size
        remove_size = 0 if ret else (total_size - self.max_dir_size)
        return remove_size

    def calculate_root_vfs(self):
        st = os.statvfs(DIR)
        free = st.f_bfree * st.f_bsize
        ret = free > self.min_fs_free
        remove_size = 0 if ret else (self.min_fs_free - free)
        return remove_size

    def remove_files(self, remove_size):
        if remove_size <= 0:
            return
        files_to_remove = []
        files = []
        for filename in os.listdir(DIR):
            full_name = os.path.join(DIR, filename)
            when_created = datetime.datetime.fromtimestamp(os.path.getmtime(full_name))
            file_size = os.stat(full_name).st_size
            files.append((full_name, when_created, file_size))
        sorted_files = sorted(files, key=lambda x: x[1]) # FIXME: check it
        target_size_to_remove = remove_size
        for f in sorted_files:
            files_to_remove.append(f[0])
            target_size_to_remove -= f[2]
            if target_size_to_remove <= 0:
                break
        for fname in files_to_remove:
            os.remove(fname)


class LimitJob(CronJob):
    def __init__(self, interval=600, max_dir_size=2**30, min_fs_free=2**30):
        super(LimitJob, self).__init__(interval=interval)
        self.max_dir_size = max_dir_size
        self.min_fs_free = min_fs_free

    def action(self):
        is_dir_ok = self.check_dir()
        is_root_ok = self.check_root_vfs()
        return is_dir_ok and is_root_ok

    def check_dir(self):
        total_size = 0
        for filename in os.listdir(DIR):
            full_name = os.path.join(DIR, filename)
            total_size += os.stat(full_name).st_size
        ret = total_size < self.max_dir_size
        if not ret:
            syslog.syslog(syslog.LOG_NOTICE, "the '%s' used more than %d > %d space" % (DIR, total_size, self.max_dir_size))
        return ret

    def check_root_vfs(self):
        st = os.statvfs(DIR)
        free = st.f_bfree * st.f_bsize
        ret = free > self.min_fs_free
        if not ret:
            syslog.syslog(syslog.LOG_NOTICE, "not enough free space on '/' fs: %d < %d" % (free, self.min_fs_free))
        return ret


def get_bpf_for_bgp():
    bpf_src = [
        ( 0x28,  0,  0, 0x0000000c ), # (000) ldh      [12]
        ( 0x15,  0,  6, 0x000086dd ), # (001) jeq      #0x86dd          jt 2  jf 8
        ( 0x30,  0,  0, 0x00000014 ), # (002) ldb      [20]
        ( 0x15,  0, 15, 0x00000006 ), # (003) jeq      #0x6             jt 4  jf 19
        ( 0x28,  0,  0, 0x00000036 ), # (004) ldh      [54]
        ( 0x15, 12,  0, 0x000000b3 ), # (005) jeq      #0xb3            jt 18 jf 6
        ( 0x28,  0,  0, 0x00000038 ), # (006) ldh      [56]
        ( 0x15, 10, 11, 0x000000b3 ), # (007) jeq      #0xb3            jt 18 jf 19
        ( 0x15,  0, 10, 0x00000800 ), # (008) jeq      #0x800           jt 9  jf 19
        ( 0x30,  0,  0, 0x00000017 ), # (009) ldb      [23]
        ( 0x15,  0,  8, 0x00000006 ), # (010) jeq      #0x6             jt 11 jf 19
        ( 0x28,  0,  0, 0x00000014 ), # (011) ldh      [20]
        ( 0x45,  6,  0, 0x00001fff ), # (012) jset     #0x1fff          jt 19 jf 13
        ( 0xb1,  0,  0, 0x0000000e ), # (013) ldxb     4*([14]&0xf)
        ( 0x48,  0,  0, 0x0000000e ), # (014) ldh      [x + 14]
        ( 0x15,  2,  0, 0x000000b3 ), # (015) jeq      #0xb3            jt 18 jf 16
        ( 0x48,  0,  0, 0x00000010 ), # (016) ldh      [x + 16]
        ( 0x15,  0,  1, 0x000000b3 ), # (017) jeq      #0xb3            jt 18 jf 19
        ( 0x06,  0,  0, 0x00040000 ), # (018) ret      #262144
        ( 0x06,  0,  0, 0x00000000 ), # (019) ret      #0
    ]
    return bpf_src


def get_ports():
    with open('/etc/sonic/config_db.json') as fp:
        j = json.load(fp)

    if 'PORTCHANNEL' in j:
        lag_ports = {str(port) for port in j['PORTCHANNEL'].keys()}
    else:
        lag_ports = set()

    lag_member_ports = set()
    if 'PORTCHANNEL_MEMBER' in j:
        lag_member_ports = {str(line.split('|')[1]) for line in j['PORTCHANNEL_MEMBER'].keys()}
    elif 'PORTCHANNEL' in j:
        for values in j['PORTCHANNEL'].values():
            if 'members' in values:
                lag_member_ports |= set(values['members'])

    all_ports = {str(port) for port in j['DEVICE_NEIGHBOR'].keys()}
    if len(lag_ports) > 0:
        # use portchannel port instead if it's memebers
        result = (all_ports | lag_ports) - lag_member_ports
    else:
        result = all_ports

    return list(result)


def wait_ports(ports):
    created = set()
    while created != set(ports):
       for port in ports:
           if port not in created:
               if os.path.exists("/sys/class/net/%s/address" % port):
                   created.add(port)

def check_platform():
    supported_list = {
        'Force10-S6000',
        'Force10-S6000-Q32',
        'Force10-S6100',
        'Force10-S6100-ITPAC-T1',
        'Force10-S6100-T1',
        'Arista-7260CX3-D108C8',
    }
    with open('/etc/sonic/config_db.json') as fp:
        j = json.load(fp)
    if 'DEVICE_METADATA' in j \
      and 'localhost' in j['DEVICE_METADATA'] \
      and 'hwsku' in j['DEVICE_METADATA']['localhost'] \
      and str(j['DEVICE_METADATA']['localhost']['hwsku']) in supported_list:
        return True

    return False


def signal_handler(signum, frame):
    global g_run
    g_run = False


def main():
    if not check_platform():
        syslog.syslog(syslog.LOG_NOTICE, "current platform is not supported. exiting")
        return

    syslog.syslog(syslog.LOG_NOTICE, "started")

    if not os.path.exists(DIR):
        os.makedirs(DIR)
        syslog.syslog(syslog.LOG_NOTICE, "directory '%s' was created" % DIR)

    cm = CronManager()
    cj = CleanJob()
    cm.add_job(cj)
    lj = LimitJob()
    cm.add_job(lj)
    cj.action()
    if not lj.action():
        syslog.syslog(syslog.LOG_ERR, "exiting without polling. not enough free space to continue")
        return

    ports = get_ports()
    wait_ports(ports)
    syslog.syslog(syslog.LOG_NOTICE, "the ports are ready for capturing")

    intfs = [Interface(port) for port in ports]
    bgp_bpf = get_bpf_for_bgp()
    for intf in intfs:
        intf.bind(bgp_bpf)

    syslog.syslog(syslog.LOG_NOTICE, "the ports are opened")
    data_handler = EventHandler()
    cm.start()
    poller = Poller(intfs, data_handler, cm)
    syslog.syslog(syslog.LOG_NOTICE, "start polling")
    poller.poll()
    syslog.syslog(syslog.LOG_NOTICE, "exit polling")


if __name__ == '__main__':
    try:
        syslog.openlog('bgp_collector')
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        main()
    except KeyboardInterrupt:
        syslog.syslog(syslog.LOG_NOTICE, "Keyboard interrupt")
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, "Got an exception %s: Traceback: %s" % (str(e), traceback.format_exc()))
    finally:
        syslog.closelog()
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)
