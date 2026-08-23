import sys

from click.testing import CliRunner

import utilities_common.cli as clicommon

sys.path.append('../cli/config/plugins/')
import dhcp_server


IPV4_COMMAND = dhcp_server.dhcp_server.commands["ipv4"]
MATCH_COMMAND = IPV4_COMMAND.commands["match"]
BINDING_COMMAND = IPV4_COMMAND.commands["binding"]


def invoke(mock_db, command, args):
    db = clicommon.Db()
    db.db = mock_db
    return CliRunner().invoke(command, args, obj=db)


class TestConfigDHCPServerMatch:
    def test_add_interface_in_match_mode(self, mock_db):
        result = invoke(
            mock_db,
            IPV4_COMMAND.commands["add"],
            [
                "Vlan200",
                "--mode=MATCH",
                "--lease_time=1000",
                "--gateway=100.1.2.2",
                "--netmask=255.255.255.0",
            ],
        )

        assert result.exit_code == 0, result.output
        assert mock_db.get("CONFIG_DB", "DHCP_SERVER_IPV4|Vlan200", "mode") == "MATCH"

    def test_update_disabled_interface_to_match_mode(self, mock_db):
        result = invoke(mock_db, IPV4_COMMAND.commands["update"], ["Vlan300", "--mode=MATCH"])

        assert result.exit_code == 0, result.output
        assert mock_db.get("CONFIG_DB", "DHCP_SERVER_IPV4|Vlan300", "mode") == "MATCH"

    def test_update_enabled_interface_to_match_mode(self, mock_db):
        result = invoke(mock_db, IPV4_COMMAND.commands["update"], ["Vlan100", "--mode=MATCH"])

        assert result.exit_code == 0, result.output
        assert mock_db.get("CONFIG_DB", "DHCP_SERVER_IPV4|Vlan100", "mode") == "MATCH"

    def test_update_enabled_interface_to_match_mode_without_binding(self, mock_db):
        mock_db.delete("CONFIG_DB", "DHCP_SERVER_IPV4_BINDING|Vlan100|maia-a")
        mock_db.delete("CONFIG_DB", "DHCP_SERVER_IPV4_BINDING|Vlan100|fallback")

        result = invoke(mock_db, IPV4_COMMAND.commands["update"], ["Vlan100", "--mode=MATCH"])

        assert result.exit_code == 2
        assert "requires at least one binding" in result.output
        assert mock_db.get("CONFIG_DB", "DHCP_SERVER_IPV4|Vlan100", "mode") == "PORT"

    def test_enable_match_interface_with_valid_bindings(self, mock_db):
        mock_db.set("CONFIG_DB", "DHCP_SERVER_IPV4|Vlan100", "mode", "MATCH")
        mock_db.set("CONFIG_DB", "DHCP_SERVER_IPV4|Vlan100", "state", "disabled")

        result = invoke(mock_db, IPV4_COMMAND.commands["enable"], ["Vlan100"])

        assert result.exit_code == 0, result.output
        assert mock_db.get("CONFIG_DB", "DHCP_SERVER_IPV4|Vlan100", "state") == "enabled"

    def test_enable_match_interface_without_binding(self, mock_db):
        mock_db.set("CONFIG_DB", "DHCP_SERVER_IPV4|Vlan300", "mode", "MATCH")

        result = invoke(mock_db, IPV4_COMMAND.commands["enable"], ["Vlan300"])

        assert result.exit_code == 2
        assert "requires at least one binding" in result.output
        assert mock_db.get("CONFIG_DB", "DHCP_SERVER_IPV4|Vlan300", "state") == "disabled"

    def test_delete_interface_referenced_by_match_binding(self, mock_db):
        for key in list(mock_db.keys("CONFIG_DB", "DHCP_SERVER_IPV4_PORT|Vlan100|*")):
            mock_db.delete("CONFIG_DB", key)

        result = invoke(mock_db, IPV4_COMMAND.commands["del"], ["Vlan100"])

        assert result.exit_code == 2
        assert "has match bindings" in result.output

    def test_match_add(self, mock_db):
        result = invoke(
            mock_db,
            MATCH_COMMAND.commands["add"],
            ["vendor-c", "--type", "option60", "--value", "MAIA-C"],
        )

        assert result.exit_code == 0, result.output
        assert mock_db.get_all("CONFIG_DB", "DHCP_SERVER_IPV4_MATCH|vendor-c") == {
            "type": "option60",
            "value": "MAIA-C",
        }

    def test_match_add_invalid_type(self, mock_db):
        result = invoke(
            mock_db,
            MATCH_COMMAND.commands["add"],
            ["client-mac", "--type", "mac", "--value", "00:11:22:33:44:55"],
        )

        assert result.exit_code == 2
        assert "Only match types" in result.output

    def test_match_add_empty_value(self, mock_db):
        result = invoke(
            mock_db,
            MATCH_COMMAND.commands["add"],
            ["empty-match", "--type", "option60", "--value", ""],
        )

        assert result.exit_code == 2
        assert "Match value must be between 1 and 255 characters" in result.output

    def test_match_add_overlength_value(self, mock_db):
        result = invoke(
            mock_db,
            MATCH_COMMAND.commands["add"],
            ["long-match", "--type", "option60", "--value", "x" * 256],
        )

        assert result.exit_code == 2
        assert "Match value must be between 1 and 255 characters" in result.output

    def test_match_update_referenced_value(self, mock_db):
        result = invoke(
            mock_db,
            MATCH_COMMAND.commands["update"],
            ["vendor-a", "--value", "MAIA-C"],
        )

        assert result.exit_code == 0, result.output
        assert mock_db.get("CONFIG_DB", "DHCP_SERVER_IPV4_MATCH|vendor-a", "value") == "MAIA-C"

    def test_match_update_ignores_unrelated_malformed_binding(self, mock_db):
        mock_db.hmset(
            "CONFIG_DB",
            "DHCP_SERVER_IPV4_BINDING|Vlan300|malformed",
            {"matches@": "vendor-b,,unused-match", "ips@": "100.1.3.20"},
        )

        result = invoke(
            mock_db,
            MATCH_COMMAND.commands["update"],
            ["vendor-a", "--value", "MAIA-C"],
        )

        assert result.exit_code == 0, result.output
        assert mock_db.get("CONFIG_DB", "DHCP_SERVER_IPV4_MATCH|vendor-a", "value") == "MAIA-C"

    def test_match_update_rejects_duplicate_type_in_binding(self, mock_db):
        result = invoke(
            mock_db,
            MATCH_COMMAND.commands["update"],
            ["vendor-a", "--type", "circuit_id", "--value", "etp4"],
        )

        assert result.exit_code == 2
        assert "multiple matches of type circuit_id" in result.output
        assert mock_db.get("CONFIG_DB", "DHCP_SERVER_IPV4_MATCH|vendor-a", "type") == "option60"

    def test_match_update_rejects_alias_outside_vlan(self, mock_db):
        result = invoke(
            mock_db,
            MATCH_COMMAND.commands["update"],
            ["port-etp2", "--value", "etp5"],
        )

        assert result.exit_code == 2
        assert "is not a member of vlan Vlan100" in result.output
        assert mock_db.get("CONFIG_DB", "DHCP_SERVER_IPV4_MATCH|port-etp2", "value") == "etp2"

    def test_match_delete(self, mock_db):
        result = invoke(mock_db, MATCH_COMMAND.commands["del"], ["unused-match"])

        assert result.exit_code == 0, result.output
        assert not mock_db.exists("CONFIG_DB", "DHCP_SERVER_IPV4_MATCH|unused-match")

    def test_match_delete_referenced(self, mock_db):
        result = invoke(mock_db, MATCH_COMMAND.commands["del"], ["port-etp2"])

        assert result.exit_code == 2
        assert "is referenced" in result.output

    def test_binding_add_with_ips(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "maia-b", "100.1.1.30,100.1.1.31", "--match", "vendor-b,port-etp2"],
        )

        assert result.exit_code == 0, result.output
        assert mock_db.get_all("CONFIG_DB", "DHCP_SERVER_IPV4_BINDING|Vlan100|maia-b") == {
            "matches@": "port-etp2,vendor-b",
            "ips@": "100.1.1.30,100.1.1.31",
        }

    def test_binding_add_sorts_ips_numerically(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "maia-b", "100.1.1.30,100.1.1.9", "--match", "vendor-b,port-etp2"],
        )

        assert result.exit_code == 0, result.output
        assert mock_db.get("CONFIG_DB", "DHCP_SERVER_IPV4_BINDING|Vlan100|maia-b", "ips@") == (
            "100.1.1.9,100.1.1.30"
        )

    def test_binding_add_with_range(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "maia-b", "--match", "port-etp2,vendor-b", "--range", "range3"],
        )

        assert result.exit_code == 0, result.output
        assert mock_db.get_all("CONFIG_DB", "DHCP_SERVER_IPV4_BINDING|Vlan100|maia-b") == {
            "matches@": "port-etp2,vendor-b",
            "ranges@": "range3",
        }

    def test_binding_add_nonexistent_interface(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan200", "maia-b", "100.1.2.30", "--match", "port-etp2,vendor-b"],
        )

        assert result.exit_code == 2
        assert "not a valid dhcp interface" in result.output

    def test_binding_add_nonexistent_match(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "maia-b", "100.1.1.30", "--match", "missing-match"],
        )

        assert result.exit_code == 2
        assert "Match missing-match does not exist" in result.output

    def test_binding_add_duplicate_match_name(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "maia-b", "100.1.1.30", "--match", "vendor-b,vendor-b"],
        )

        assert result.exit_code == 2
        assert "Match list cannot contain duplicate values" in result.output

    def test_binding_add_duplicate_ip(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "maia-b", "100.1.1.30,100.1.1.30", "--match", "vendor-b,port-etp2"],
        )

        assert result.exit_code == 2
        assert "IP list cannot contain duplicate values" in result.output

    def test_binding_add_duplicate_match_type(self, mock_db):
        mock_db.hmset(
            "CONFIG_DB",
            "DHCP_SERVER_IPV4_MATCH|port-etp4",
            {"type": "circuit_id", "value": "etp4"},
        )

        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "two-ports", "100.1.1.30", "--match", "port-etp2,port-etp4"],
        )

        assert result.exit_code == 2
        assert "multiple matches of type circuit_id" in result.output

    def test_binding_add_with_both_pool_types(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            [
                "Vlan100",
                "maia-b",
                "100.1.1.30",
                "--match",
                "port-etp2,vendor-b",
                "--range",
                "range3",
            ],
        )

        assert result.exit_code == 2
        assert "Exactly one of IP list or range list" in result.output

    def test_binding_add_without_pool(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "maia-b", "--match", "port-etp2,vendor-b"],
        )

        assert result.exit_code == 2
        assert "Exactly one of IP list or range list" in result.output

    def test_binding_add_invalid_ip(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "maia-b", "100.1.1", "--match", "port-etp2,vendor-b"],
        )

        assert result.exit_code == 2
        assert "Illegal IP address" in result.output

    def test_binding_add_ip_out_of_subnet(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "maia-b", "100.1.2.30", "--match", "port-etp2,vendor-b"],
        )

        assert result.exit_code == 2
        assert "not in any subnet of vlan Vlan100" in result.output

    def test_binding_add_nonexistent_range(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "maia-b", "--match", "port-etp2,vendor-b", "--range", "range4"],
        )

        assert result.exit_code == 2
        assert "Range range4 does not exist" in result.output

    def test_binding_add_range_out_of_subnet(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "maia-b", "--match", "port-etp2,vendor-b", "--range", "range5"],
        )

        assert result.exit_code == 2
        assert "not in any subnet of vlan Vlan100" in result.output

    def test_binding_add_nonexistent_circuit_alias(self, mock_db):
        mock_db.hmset(
            "CONFIG_DB",
            "DHCP_SERVER_IPV4_MATCH|missing-port",
            {"type": "circuit_id", "value": "etp99"},
        )

        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "missing-port", "100.1.1.30", "--match", "missing-port"],
        )

        assert result.exit_code == 2
        assert "Circuit ID alias etp99 does not exist" in result.output

    def test_binding_add_ambiguous_circuit_alias(self, mock_db):
        mock_db.hmset("CONFIG_DB", "PORT|Ethernet6", {"alias": "etp2"})

        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "ambiguous-port", "100.1.1.30", "--match", "port-etp2"],
        )

        assert result.exit_code == 2
        assert "Circuit ID alias etp2 is ambiguous" in result.output

    def test_binding_add_circuit_alias_outside_vlan(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "wrong-port", "100.1.1.30", "--match", "port-etp5"],
        )

        assert result.exit_code == 2
        assert "Circuit ID alias etp5 is not a member of vlan Vlan100" in result.output

    def test_binding_add_equal_specificity_overlap(self, mock_db):
        result = invoke(
            mock_db,
            BINDING_COMMAND.commands["add"],
            ["Vlan100", "vendor-only", "100.1.1.30", "--match", "vendor-a"],
        )

        assert result.exit_code == 2
        assert "overlap with equal specificity" in result.output

    def test_binding_delete(self, mock_db):
        result = invoke(mock_db, BINDING_COMMAND.commands["del"], ["Vlan100", "maia-a"])

        assert result.exit_code == 0, result.output
        assert not mock_db.exists("CONFIG_DB", "DHCP_SERVER_IPV4_BINDING|Vlan100|maia-a")

    def test_range_delete_referenced_by_binding(self, mock_db):
        mock_db.delete("CONFIG_DB", "DHCP_SERVER_IPV4_PORT|Vlan100|Ethernet7")

        result = invoke(mock_db, IPV4_COMMAND.commands["range"].commands["del"], ["range3"])

        assert result.exit_code == 2
        assert "DHCP_SERVER_IPV4_BINDING|Vlan100|fallback" in result.output
