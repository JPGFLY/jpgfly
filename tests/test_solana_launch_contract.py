import ast
import json
import unittest
from pathlib import Path

from solana_launch_contract import (
    SolanaLaunchContractError,
    build_solana_prep_intent,
    public_prep_receipt,
    validate_prep_policy,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "solana_launch_policy.prep.json"


class SolanaLaunchContractTests(unittest.TestCase):
    def policy(self):
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def token(self):
        return {
            "name": "JPGFLY",
            "symbol": "JPGFLY",
            "decimals": 9,
            "metadata_uri": "",
        }

    def test_prep_policy_is_non_executable(self):
        checked = validate_prep_policy(self.policy())
        self.assertTrue(checked["policy_hash"].startswith("sha256:"))
        self.assertFalse(checked["execution_enabled"])
        self.assertFalse(checked["rpc_access"])
        self.assertFalse(checked["wallet_access"])
        self.assertFalse(checked["private_key_access"])
        self.assertFalse(checked["generic_signing"])
        self.assertFalse(checked["browser_wallet_access"])
        self.assertFalse(checked["publish_signer_identity"])
        self.assertEqual(checked["adapter"], "UNSET")
        self.assertEqual(checked["allowed_program_ids"], [])
        self.assertEqual(checked["max_total_lamports"], 0)
        self.assertEqual(checked["max_transactions"], 0)

    def test_prep_intent_is_deterministic_and_hash_bound(self):
        first = build_solana_prep_intent(self.token(), self.policy())
        second = build_solana_prep_intent(self.token(), self.policy())
        self.assertEqual(first, second)
        self.assertTrue(first["intent_hash"].startswith("sha256:"))
        self.assertTrue(first["policy_hash"].startswith("sha256:"))
        self.assertFalse(first["controls"]["execution_enabled"])
        self.assertFalse(first["controls"]["broadcast"])

    def test_token_intent_rejects_signer_key_rpc_and_transaction_fields(self):
        forbidden = (
            "private_key",
            "secret_key",
            "mnemonic",
            "seed_phrase",
            "wallet_address",
            "signer_pubkey",
            "rpc_url",
            "recipient",
            "raw_transaction",
            "serialized_transaction",
            "instructions",
        )
        for field in forbidden:
            token = self.token()
            token[field] = "not allowed"
            with self.subTest(field=field):
                with self.assertRaises(SolanaLaunchContractError):
                    build_solana_prep_intent(token, self.policy())

    def test_policy_cannot_be_armed_by_flipping_one_flag(self):
        guarded = (
            "execution_enabled",
            "rpc_access",
            "wallet_access",
            "private_key_access",
            "generic_signing",
            "browser_wallet_access",
            "publish_signer_identity",
            "store_private_key",
            "store_seed_phrase",
        )
        for field in guarded:
            policy = self.policy()
            policy[field] = True
            with self.subTest(field=field):
                with self.assertRaises(SolanaLaunchContractError):
                    validate_prep_policy(policy)

    def test_policy_rejects_adapter_budget_transactions_or_program_authority(self):
        changes = {
            "adapter": "anything-live",
            "max_total_lamports": 1,
            "max_transactions": 1,
            "allowed_program_ids": ["11111111111111111111111111111111"],
            "max_launches_per_arm": 2,
        }
        for field, value in changes.items():
            policy = self.policy()
            policy[field] = value
            with self.subTest(field=field):
                with self.assertRaises(SolanaLaunchContractError):
                    validate_prep_policy(policy)

    def test_metadata_uri_rejects_credentials_and_non_public_schemes(self):
        for uri in (
            "http://example.com/token.json",
            "file:///tmp/token.json",
            "https://user:password@example.com/token.json",
        ):
            token = self.token()
            token["metadata_uri"] = uri
            with self.subTest(uri=uri):
                with self.assertRaises(SolanaLaunchContractError):
                    build_solana_prep_intent(token, self.policy())

    def test_public_receipt_contains_no_signer_or_secret_identity(self):
        receipt = public_prep_receipt(build_solana_prep_intent(self.token(), self.policy()))
        encoded = json.dumps(receipt, sort_keys=True).casefold()
        for forbidden in (
            "private_key",
            "secret_key",
            "mnemonic",
            "seed_phrase",
            "wallet_address",
            "signer_pubkey",
            "rpc_url",
            "raw_transaction",
        ):
            self.assertNotIn(forbidden, encoded)
        self.assertFalse(receipt["execution_enabled"])
        self.assertFalse(receipt["broadcast"])

    def test_prep_module_has_no_network_wallet_cli_or_blockchain_imports(self):
        source = (ROOT / "solana_launch_contract.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        forbidden = {
            "socket",
            "urllib",
            "requests",
            "httpx",
            "aiohttp",
            "subprocess",
            "solana",
            "solders",
            "web3",
            "keyring",
        }
        self.assertFalse(imported & forbidden, f"forbidden imports: {sorted(imported & forbidden)}")


if __name__ == "__main__":
    unittest.main()
