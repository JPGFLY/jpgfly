import json
import unittest

from solana_launch_readiness import (
    REQUIRED_CHECKS,
    SolanaLaunchReadinessError,
    evaluate_launch_readiness,
)


class SolanaLaunchReadinessTests(unittest.TestCase):
    def all_green(self):
        return {name: True for name in REQUIRED_CHECKS}

    def test_all_checks_green_is_ready(self):
        result = evaluate_launch_readiness(self.all_green())
        self.assertTrue(result["ready"])
        self.assertEqual(result["blockers"], [])
        self.assertEqual(set(result), {"schema", "ready", "checks", "blockers"})

    def test_any_single_failed_check_blocks_launch(self):
        for name in REQUIRED_CHECKS:
            facts = self.all_green()
            facts[name] = False
            with self.subTest(name=name):
                result = evaluate_launch_readiness(facts)
                self.assertFalse(result["ready"])
                self.assertIn(name, result["blockers"])

    def test_missing_unknown_and_non_boolean_facts_fail_closed(self):
        missing = self.all_green()
        missing.pop(REQUIRED_CHECKS[0])
        with self.assertRaises(SolanaLaunchReadinessError):
            evaluate_launch_readiness(missing)

        unknown = self.all_green()
        unknown["wallet_address"] = True
        with self.assertRaises(SolanaLaunchReadinessError):
            evaluate_launch_readiness(unknown)

        wrong_type = self.all_green()
        wrong_type[REQUIRED_CHECKS[0]] = "yes"
        with self.assertRaises(SolanaLaunchReadinessError):
            evaluate_launch_readiness(wrong_type)

    def test_readiness_result_cannot_contain_wallet_key_rpc_or_transaction_identity(self):
        encoded = json.dumps(evaluate_launch_readiness(self.all_green()), sort_keys=True).casefold()
        for forbidden in (
            "wallet_address",
            "signer_pubkey",
            "private_key",
            "secret_key",
            "seed_phrase",
            "mnemonic",
            "rpc_url",
            "raw_transaction",
            "serialized_transaction",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_launch_day_blockers_match_current_safe_prep_state(self):
        facts = self.all_green()
        for name in (
            "local_stack_healthy",
            "gateway_credential_separated",
            "signer_isolated",
            "adapter_locked",
            "program_allowlist_locked",
            "spend_cap_locked",
            "simulation_passed",
            "one_shot_armed",
        ):
            facts[name] = False
        result = evaluate_launch_readiness(facts)
        self.assertFalse(result["ready"])
        self.assertEqual(set(result["blockers"]), {name for name, value in facts.items() if not value})


if __name__ == "__main__":
    unittest.main()
