import io
import json
import os
import unittest
from unittest import mock

from zebracns import artistic_zebracns_state, public_zebracns_state


class FakeResponse:
    def __init__(self,payload):
        self.body=io.BytesIO(json.dumps(payload).encode("utf-8"))
    def __enter__(self): return self
    def __exit__(self,*_args): return False
    def read(self,*args): return self.body.read(*args)


class ZebraCNSBackboneTests(unittest.TestCase):
    def setUp(self):
        self.names=(
            "JPGFLY_ZEBRACNS_ENABLED","JPGFLY_ZEBRACNS_URL","JPGFLY_ZEBRACNS_AUTH_TOKEN",
            "JPGFLY_OLLAMA_AUTH_TOKEN","JPGFLY_CONTROL_TOKEN",
        )
        self.previous={name:os.environ.get(name) for name in self.names}
        for name in self.names:
            os.environ.pop(name,None)

    def tearDown(self):
        for name,value in self.previous.items():
            if value is None:
                os.environ.pop(name,None)
            else:
                os.environ[name]=value

    def test_disabled_backbone_is_honest_and_dormant(self):
        state=public_zebracns_state()
        self.assertTrue(state["ok"])
        self.assertFalse(state["enabled"])
        self.assertFalse(state["connected"])
        self.assertFalse(state["biological_data_loaded"])
        self.assertFalse(state["connectome_loaded"])
        self.assertEqual(state["status"],"BACKBONE_ONLY")
        self.assertEqual(state["action"],"NONE")
        self.assertEqual(state["nodes"],[])
        self.assertIn("No real zebrafish activity data",state["note"])
        self.assertEqual(artistic_zebracns_state(),{})

    def test_remote_bridge_requires_authentication(self):
        os.environ["JPGFLY_ZEBRACNS_ENABLED"]="true"
        os.environ["JPGFLY_ZEBRACNS_URL"]="https://example.invalid/zebracns"
        state=public_zebracns_state(max_age=0)
        self.assertFalse(state["ok"])
        self.assertEqual(state["status"],"AUTH_REQUIRED")
        self.assertFalse(state["biological_data_loaded"])

    def test_existing_model_gateway_token_can_authenticate_zebracns(self):
        os.environ["JPGFLY_ZEBRACNS_ENABLED"]="true"
        os.environ["JPGFLY_ZEBRACNS_URL"]="https://example.invalid/zebracns"
        os.environ["JPGFLY_OLLAMA_AUTH_TOKEN"]="x"*40
        payload={
            "status":"RUNNING_REAL_ACTIVITY",
            "dataset":"ZAPBench 240930 whole-brain traces",
            "source":"gs://zapbench-release/volumes/20240930/traces/",
            "license":"CC-BY 4.0",
            "activity_loaded":True,
            "biological_data_loaded":True,
            "connectome_loaded":False,
            "frame":17,
            "sampled_neurons":288,
            "total_neurons":71721,
            "action":"LEFT",
            "signals":{
                "arousal":.7,"persistence":.6,"novelty_seek":.8,
                "attention_lock":.3,"escape_drive":.5,"repetition_drive":.4,
                "state_instability":.55,"completion_pressure":.2,"tempo":.75,
            },
            "game":{"fish":[.4,.5],"food":[.8,.2],"predator":[.1,.8],"score":9,"episode":1},
            "nodes":[{"id":"12","x":.3,"y":.4,"activity":.9}],
        }
        with mock.patch("zebracns.urllib.request.urlopen",return_value=FakeResponse(payload)) as opened:
            state=public_zebracns_state(max_age=0)
        self.assertTrue(state["biological_data_loaded"])
        self.assertFalse(state["connectome_loaded"])
        self.assertEqual(state["dataset"],"ZAPBench 240930 whole-brain traces")
        self.assertEqual(state["sampled_neurons"],288)
        self.assertEqual(state["action"],"LEFT")
        self.assertEqual(artistic_zebracns_state()["signals"]["novelty_seek"],.8)
        request=opened.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"),"Bearer "+"x"*40)


if __name__=="__main__":
    unittest.main()
