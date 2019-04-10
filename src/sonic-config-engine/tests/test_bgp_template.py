import filecmp
import os
import subprocess
import json
import shutil

from unittest import TestCase

class TestBgpTemplate(TestCase):
    def setUp(self):
        self.test_dir = os.path.dirname(os.path.realpath(__file__))
        self.minigraph_dir = os.path.join(self.test_dir, 'minigraph')
        self.script_file = os.path.join(self.test_dir, '..', 'sonic-cfggen')
        self.t1_minigraph = os.path.join(self.minigraph_dir, 'CO4SCH04001AALF.xml')
        self.tycoon_t1_minigraph = os.path.join(self.minigraph_dir, 'SN1-0102-0201-11T1.xml')
        self.m0_minigraph = os.path.join(self.minigraph_dir, 'MWH01-0100-0202-01M0.xml')
        self.dell_s6000_port_config = os.path.join(self.test_dir, 't0-sample-port-config.ini')
        self.hlx_port_config = os.path.join(self.test_dir, 'hlx-port-config.ini')
        self.a7060_port_config = os.path.join(self.test_dir, 'a7060-port-config.ini')
        self.deployment_id_asn_map = os.path.join(self.test_dir, 'deployment_id_asn_map.yml')
        self.device_metadata = os.path.join(self.test_dir, 'device_metadata.json')
        self.output_file = os.path.join(self.test_dir, 'output')

    def run_script(self, argument):
        print 'CMD: sonic-cfggen ' + argument
        return subprocess.check_output(self.script_file + ' ' + argument, shell=True)
    
    def run_diff(self, file1, file2):
        return subprocess.check_output('diff -u {} {} || true'.format(file1, file2), shell=True)

    def run_bgpd_test(self, minigraph, portconfig, valid_result_file):
        conf_template = os.path.join(self.test_dir, '..', '..', '..', 'dockers', 'docker-fpm-quagga', 'bgpd.conf.j2')
        argument = '-m ' + minigraph + ' -p ' + portconfig + ' -t ' + conf_template + ' -y ' + self.deployment_id_asn_map + ' -j ' + self.device_metadata + ' > ' + self.output_file
        self.run_script(argument)
        original_filename = os.path.join(self.test_dir, 'sample_output', valid_result_file)
        r = filecmp.cmp(original_filename, self.output_file)
        diff_output = self.run_diff(original_filename, self.output_file) if not r else ""
        self.assertTrue(r, "Diff:\n" + diff_output)

    def test_bgpd_t1(self):
        return self.run_bgpd_test(self.t1_minigraph, self.dell_s6000_port_config, 'CO4SCH04001AALF.bgpd.conf')

    def test_bgpd_tycoon_t1(self):
        return self.run_bgpd_test(self.tycoon_t1_minigraph, self.a7060_port_config, 'SN1-0102-0201-11T1.bgpd.conf')

    def test_bgpd_m0(self):
        return self.run_bgpd_test(self.m0_minigraph, self.hlx_port_config, 'MWH01-0100-0202-01M0.bgpd.conf')

    def tearDown(self):
        try:
            os.remove(self.output_file)
        except OSError:
            pass
