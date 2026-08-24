import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from dhcp_utilities.dhcpservd.dhcp_cfggen import DhcpServCfgGenerator
from dhcp_utilities.dhcpservd.dhcpservd import DhcpServd


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_TEMPLATE = REPOSITORY_ROOT / "dockers" / "docker-dhcp-server" / "kea-dhcp4.conf.j2"
DOCKER_DIRECTORY = REPOSITORY_ROOT / "dockers" / "docker-dhcp-server"


class MutableConfigDb:
    def __init__(self, tables):
        self.tables = tables

    def get_config_db_table(self, table_name):
        return self.tables.get(table_name, {})


def base_tables():
    return {
        "DEVICE_METADATA": {"localhost": {"hostname": "sonic-host"}},
        "VLAN_INTERFACE": {},
        "VLAN_MEMBER": {},
        "PORT": {},
        "PORTCHANNEL": {},
        "DPUS": {},
        "MID_PLANE_BRIDGE": {},
        "DHCP_SERVER_IPV4": {},
        "DHCP_SERVER_IPV4_CUSTOMIZED_OPTIONS": {},
        "DHCP_SERVER_IPV4_RANGE": {},
        "DHCP_SERVER_IPV4_PORT": {},
        "DHCP_SERVER_IPV4_MATCH": {},
        "DHCP_SERVER_IPV4_BINDING": {}
    }


def add_port_mode(tables, vlan="Vlan1000", subnet="192.168.0.1/24", port="Ethernet24",
                  alias="etp7", pool="192.168.0.20"):
    tables["VLAN_INTERFACE"].update({vlan: {}, "{}|{}".format(vlan, subnet): {}})
    tables["VLAN_MEMBER"]["{}|{}".format(vlan, port)] = {}
    tables["PORT"][port] = {"alias": alias}
    tables["DHCP_SERVER_IPV4"][vlan] = {
        "gateway": subnet.split("/")[0],
        "lease_time": "900",
        "mode": "PORT",
        "state": "enabled"
    }
    tables["DHCP_SERVER_IPV4_PORT"]["{}|{}".format(vlan, port)] = {"ips": [pool]}


def add_match_mode(tables, vlan="Vlan2000", subnet="192.168.1.1/24", pool="192.168.1.20",
                   match_name="vendor-a", match_value="MAIA-A"):
    tables["VLAN_INTERFACE"].update({vlan: {}, "{}|{}".format(vlan, subnet): {}})
    tables["DHCP_SERVER_IPV4"][vlan] = {
        "gateway": subnet.split("/")[0],
        "lease_time": "900",
        "mode": "MATCH",
        "state": "enabled"
    }
    tables["DHCP_SERVER_IPV4_MATCH"][match_name] = {
        "type": "option60",
        "value": match_value
    }
    tables["DHCP_SERVER_IPV4_BINDING"]["{}|{}".format(vlan, match_name)] = {
        "matches": [match_name],
        "ips": [pool]
    }


def create_service(connector, config_path):
    generator = DhcpServCfgGenerator(
        connector,
        "/usr/local/lib/kea/hooks/libdhcp_run_script.so",
        kea_conf_template_path=str(PRODUCTION_TEMPLATE)
    )
    monitor = MagicMock()
    service = DhcpServd(
        generator,
        connector,
        monitor,
        kea_dhcp4_config_path=str(config_path),
        kea_dhcp4_binary="kea-dhcp4"
    )
    return service, monitor


def validate_json_candidate(command, **kwargs):
    assert command[:2] == ["kea-dhcp4", "-t"]
    json.loads(Path(command[2]).read_text())
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def activate(service):
    with patch("dhcp_utilities.dhcpservd.dhcpservd.subprocess.run",
               side_effect=validate_json_candidate), \
         patch.object(service, "_notify_kea_dhcp4_proc") as notify:
        result = service.dump_dhcp4_config()
    return result, notify


@pytest.mark.parametrize("configuration", ["PORT", "MATCH", "MIXED"])
def test_container_runtime_startup_and_restart(tmp_path, configuration):
    tables = base_tables()
    if configuration in {"PORT", "MIXED"}:
        add_port_mode(tables)
    if configuration in {"MATCH", "MIXED"}:
        add_match_mode(tables)
    connector = MutableConfigDb(tables)
    config_path = tmp_path / "kea-dhcp4.conf"

    service, _ = create_service(connector, config_path)
    result, notify = activate(service)

    assert result
    notify.assert_called_once_with()
    first_config = config_path.read_text()
    parsed = json.loads(first_config)
    assert len(parsed["Dhcp4"]["subnet4"]) == (2 if configuration == "MIXED" else 1)
    class_names = {client_class["name"] for client_class in parsed["Dhcp4"]["client-classes"]}
    if configuration in {"PORT", "MIXED"}:
        assert "sonic-host:etp7" in class_names
    if configuration in {"MATCH", "MIXED"}:
        assert any(name.startswith("sonic_match_2000_") for name in class_names)

    saved_tables = json.loads(json.dumps(tables))
    restarted_service, _ = create_service(MutableConfigDb(saved_tables), config_path)
    restart_result, restart_notify = activate(restarted_service)

    assert restart_result
    restart_notify.assert_called_once_with()
    assert config_path.read_text() == first_config


def test_container_runtime_mode_changes(tmp_path):
    tables = base_tables()
    add_port_mode(tables)
    connector = MutableConfigDb(tables)
    config_path = tmp_path / "kea-dhcp4.conf"
    service, monitor = create_service(connector, config_path)

    assert activate(service)[0]
    port_config = config_path.read_text()
    assert service.enabled_port_interfaces == {"Vlan1000"}
    assert service.enabled_match_interfaces == set()

    add_match_mode(
        tables,
        vlan="Vlan1000",
        subnet="192.168.0.1/24",
        pool="192.168.0.30"
    )
    monitor.reset_mock()

    assert activate(service)[0]
    match_config = config_path.read_text()
    assert match_config != port_config
    assert service.enabled_port_interfaces == set()
    assert service.enabled_match_interfaces == {"Vlan1000"}
    monitor.disable_checkers.assert_called_once()
    monitor.enable_checkers.assert_called_once()

    tables["DHCP_SERVER_IPV4"]["Vlan1000"]["mode"] = "PORT"
    monitor.reset_mock()

    assert activate(service)[0]
    assert config_path.read_text() == port_config
    assert service.enabled_port_interfaces == {"Vlan1000"}
    assert service.enabled_match_interfaces == set()
    monitor.disable_checkers.assert_called_once()
    monitor.enable_checkers.assert_called_once()


def test_container_runtime_preserves_last_known_good_and_recovers(tmp_path):
    tables = base_tables()
    add_match_mode(tables)
    connector = MutableConfigDb(tables)
    config_path = tmp_path / "kea-dhcp4.conf"
    service, monitor = create_service(connector, config_path)

    assert activate(service)[0]
    good_config = config_path.read_text()
    good_matches = service.used_matches.copy()

    tables["DHCP_SERVER_IPV4_BINDING"]["Vlan2000|vendor-a"]["matches"] = ["missing"]
    monitor.reset_mock()

    with patch("dhcp_utilities.dhcpservd.dhcpservd.syslog.syslog") as syslog:
        failed, failed_notify = activate(service)

    assert not failed
    failed_notify.assert_not_called()
    assert config_path.read_text() == good_config
    assert service.used_matches == good_matches
    assert service.reload_pending
    monitor.enable_checkers.assert_called_once()
    assert "Cannot generate Kea candidate config" in syslog.call_args.args[1]

    tables["DHCP_SERVER_IPV4_MATCH"]["missing"] = {
        "type": "option60",
        "value": "MAIA-B"
    }

    recovered, recovered_notify = activate(service)

    assert recovered
    recovered_notify.assert_called_once_with()
    assert config_path.read_text() != good_config
    assert service.used_matches == {"missing"}
    assert not service.reload_pending
    assert service.recovery_checkers == set()


def test_container_manifest_preserves_startup_and_critical_process_contracts():
    dockerfile = (DOCKER_DIRECTORY / "Dockerfile.j2").read_text()
    supervisord = (DOCKER_DIRECTORY / "supervisord.conf").read_text()
    docker_init = (DOCKER_DIRECTORY / "docker_init.sh").read_text()
    critical_processes = (DOCKER_DIRECTORY / "critical_processes").read_text().splitlines()

    assert "kea-dhcp4-server" in dockerfile
    assert 'COPY ["kea-dhcp4.conf.j2", "/usr/share/sonic/templates/"]' in dockerfile
    assert 'COPY ["docker_init.sh", "start.sh", "wait_for_dhcpservd.sh", "/usr/bin/"]' in dockerfile
    assert "programs=dhcpservd,kea-dhcp4" in supervisord
    assert "dependent_startup_wait_for=dhcpservd-ready:exited" in supervisord
    assert "rm -f /tmp/dhcpservd_ready" in docker_init
    assert critical_processes == ["group:dhcp-server-ipv4"]
