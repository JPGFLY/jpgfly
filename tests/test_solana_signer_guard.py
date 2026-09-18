import ast
import json
import unittest
from pathlib import Path

from solana_signer_guard import (
    SolanaSignerGuardError,
    authorize_execution_plan,
    validate_signer_policy,
)


ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/"solana_signer_policy.template.json"
H1="sha256:"+"1"*64
H2="sha256:"+"2"*64
H3="sha256:"+"3"*64
PROGRAM="A"*32


class SolanaSignerGuardTests(unittest.TestCase):
    def template(self):
        return json.loads(TEMPLATE.read_text(encoding="utf-8"))

    def locked_policy(self):
        policy=self.template()
        policy.update({
            "mode":"LOCKED_EXECUTION",
            "enabled":True,
            "adapter_id":"reviewed-adapter-v1",
            "allowed_program_ids":[PROGRAM],
            "max_total_lamports":5000000,
            "max_transactions":2,
            "required_intent_hash":H1,
            "required_prep_policy_hash":H2,
            "required_simulation_hash":H3,
        })
        return policy

    def plan(self):
        return {
            "intent_hash":H1,
            "prep_policy_hash":H2,
            "adapter_id":"reviewed-adapter-v1",
            "program_ids":[PROGRAM],
            "estimated_total_lamports":4000000,
            "transaction_count":2,
            "simulation_hash":H3,
        }

    def test_template_has_zero_authority_and_cannot_authorize(self):
        checked=validate_signer_policy(self.template())
        self.assertFalse(checked["enabled"])
        self.assertEqual(checked["adapter_id"],"UNSET")
        self.assertEqual(checked["allowed_program_ids"],[])
        self.assertEqual(checked["max_total_lamports"],0)
        self.assertEqual(checked["max_transactions"],0)
        with self.assertRaises(SolanaSignerGuardError):
            authorize_execution_plan(self.plan(),self.template())

    def test_exact_locked_plan_is_hash_bound_and_authorized(self):
        receipt=authorize_execution_plan(self.plan(),self.locked_policy())
        self.assertTrue(receipt["authorized"])
        self.assertEqual(receipt["intent_hash"],H1)
        self.assertEqual(receipt["prep_policy_hash"],H2)
        self.assertEqual(receipt["simulation_hash"],H3)
        self.assertEqual(receipt["program_ids"],[PROGRAM])
        self.assertTrue(receipt["authorization_hash"].startswith("sha256:"))

    def test_enabled_policy_requires_exact_adapter_program_budget_and_artifact_hashes(self):
        mutations={
            "adapter_id":"UNSET",
            "allowed_program_ids":[],
            "max_total_lamports":0,
            "max_transactions":0,
            "required_intent_hash":"",
            "required_prep_policy_hash":"",
            "required_simulation_hash":"",
        }
        for key,value in mutations.items():
            policy=self.locked_policy()
            policy[key]=value
            with self.subTest(key=key):
                with self.assertRaises(SolanaSignerGuardError):
                    validate_signer_policy(policy,require_enabled=True)

    def test_any_plan_mismatch_fails_closed(self):
        mutations={
            "intent_hash":"sha256:"+"4"*64,
            "prep_policy_hash":"sha256:"+"5"*64,
            "simulation_hash":"sha256:"+"6"*64,
            "adapter_id":"other-adapter",
            "program_ids":["B"*32],
            "estimated_total_lamports":5000001,
            "transaction_count":3,
        }
        for key,value in mutations.items():
            plan=self.plan()
            plan[key]=value
            with self.subTest(key=key):
                with self.assertRaises(SolanaSignerGuardError):
                    authorize_execution_plan(plan,self.locked_policy())

    def test_plan_rejects_recipient_key_rpc_and_raw_transaction_fields(self):
        for field in (
            "recipient","wallet_address","signer_pubkey","private_key","secret_key",
            "seed_phrase","mnemonic","rpc_url","raw_transaction","serialized_transaction",
            "instructions",
        ):
            plan=self.plan()
            plan[field]="not allowed"
            with self.subTest(field=field):
                with self.assertRaises(SolanaSignerGuardError):
                    authorize_execution_plan(plan,self.locked_policy())

    def test_dangerous_signer_capabilities_cannot_be_enabled(self):
        for field in (
            "allow_arbitrary_recipient","allow_raw_transaction_input","allow_generic_signing",
            "allow_key_export","allow_browser_signing","publish_signer_identity",
        ):
            policy=self.locked_policy()
            policy[field]=True
            with self.subTest(field=field):
                with self.assertRaises(SolanaSignerGuardError):
                    validate_signer_policy(policy,require_enabled=True)

    def test_guard_module_has_no_network_cli_wallet_or_blockchain_imports(self):
        source=(ROOT/"solana_signer_guard.py").read_text(encoding="utf-8")
        tree=ast.parse(source)
        imported=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node,ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        forbidden={"socket","urllib","requests","httpx","aiohttp","subprocess","solana","solders","web3","keyring"}
        self.assertFalse(imported & forbidden,f"forbidden imports: {sorted(imported & forbidden)}")


if __name__=="__main__":
    unittest.main()
