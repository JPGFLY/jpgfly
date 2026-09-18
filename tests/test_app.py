from __future__ import annotations

import asyncio
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

os.environ.setdefault("JPGFLY_AUTONOMOUS_STUDIO","false")
os.environ.setdefault("JPGFLY_TEXT_PROVIDER","procedural")
os.environ.setdefault("JPGFLY_BRAIN_PROVIDER","procedural")

import app as jpgfly


def observation(sequence,physical=0):
    return {
        "sequence":sequence,"canvasOccupancy":.2,"negativeSpace":.8,"intersections":3,
        "directionalUniformity":.3,"densityContrast":.3,"localDensity":.3,"repetition":.2,
        "meaningfulChangeRate":.8,"consecutiveLowChange":0,"physicalActionCount":physical,
        "occupiedRegions":5,"regionalContrast":.3,"familyCounts":{},"currentForelegPosition":[735.,48.],
    }


async def finish_session(seed=7):
    session=await jpgfly.create_session(jpgfly.StartRequest(seed=seed,complexity=.8,mutation=.5,density=.5,limits={"maxBrainDecisions":320,"maxPhysicalActions":320,"maxSessionDurationMs":240000,"maxConsecutiveLowChange":60}))
    session_id=session["session_id"]
    jpgfly.SESSIONS[session_id]["_brain"].desired_decisions=190
    actions=[]
    for sequence in range(320):
        result=await jpgfly.session_decision(session_id,jpgfly.DecisionRequest(sequence=sequence))
        actions.append(result["action"])
        if result["action"]["intent"]=="FINISH_ARTWORK":break
    final=jpgfly.finalize_session(session_id,jpgfly.FinalizeRequest(client_fingerprint="test"))
    return final,actions


class JPGFLYAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.previous_data=os.environ.get("JPGFLY_DATA_DIR");os.environ["JPGFLY_DATA_DIR"]=self.tmp.name
        jpgfly.SESSIONS.clear();jpgfly.ARTWORKS.clear();jpgfly.NEXT_ROOM_NUMBER=1

    def tearDown(self):
        if self.previous_data is None:os.environ.pop("JPGFLY_DATA_DIR",None)
        else:os.environ["JPGFLY_DATA_DIR"]=self.previous_data
        self.tmp.cleanup()

    def test_project_config_is_backrooms(self):
        self.assertEqual(jpgfly.app.title,"JPGFLY Backrooms")


    def test_room_born_agents_are_distinct_and_public(self):
        for profile,name in (("jpgfly","JPGFLY"),("sprayfly","SPRAYFLY"),("dreamfly","DREAMFLY")):
            session=asyncio.run(jpgfly.create_session(jpgfly.StartRequest(seed=41,agent_profile=profile)))
            self.assertEqual(session["agent_profile"],profile);self.assertEqual(session["agent_name"],name);self.assertTrue(session["agent_lore"])

    def test_descendant_lineage_stays_stable_and_cross_line_echoes_come_first(self):
        jpgfly.ARTWORKS.update({
            "1"*64:{"session_id":"1"*64,"room_code":"ROOM-0001","agent_profile":"jpgfly","agent_name":"JPGFLY","room_title":"Origin","completed_at":"2026-09-12T00:00:00+00:00","spawned_from":None},
            "2"*64:{"session_id":"2"*64,"room_code":"ROOM-0002","agent_profile":"sprayfly","agent_name":"SPRAYFLY","room_title":"First Spray","completed_at":"2026-09-13T00:00:00+00:00","spawned_from":"ROOM-0001"},
            "3"*64:{"session_id":"3"*64,"room_code":"ROOM-0003","agent_profile":"dreamfly","agent_name":"DREAMFLY","room_title":"First Dream","completed_at":"2026-09-14T00:00:00+00:00","spawned_from":"ROOM-0001"},
        })
        session=asyncio.run(jpgfly.create_session(jpgfly.StartRequest(seed=42,agent_profile="sprayfly")))
        self.assertEqual(session["spawned_from"],"ROOM-0001")
        echoes=[item["agent_profile"] for item in session["room_echoes"]]
        self.assertEqual(echoes[:3],["dreamfly","jpgfly","sprayfly"])

    def test_session_creation_has_no_external_identity(self):
        session=asyncio.run(jpgfly.create_session(jpgfly.StartRequest(seed=9)));self.assertEqual(session["status"],"CREATED")

    def test_public_active_session_summary_hides_working_history(self):
        session=asyncio.run(jpgfly.create_session(jpgfly.StartRequest(seed=9)));live=jpgfly.active_session_summary(jpgfly.SESSIONS[session["session_id"]]);self.assertNotIn("brain_decisions",live);self.assertNotIn("events",live);self.assertNotIn("_brain",live)

    def test_public_deployment_validation_requires_control_token(self):
        names=("JPGFLY_PUBLIC_DEPLOYMENT","RAILWAY_ENVIRONMENT","RAILWAY_VOLUME_MOUNT_PATH","JPGFLY_ALLOW_EPHEMERAL_STORAGE","JPGFLY_CONTROL_TOKEN")
        previous={name:os.environ.get(name) for name in names}
        try:
            os.environ["JPGFLY_PUBLIC_DEPLOYMENT"]="true";os.environ.pop("RAILWAY_ENVIRONMENT",None);os.environ.pop("RAILWAY_VOLUME_MOUNT_PATH",None)
            os.environ["JPGFLY_CONTROL_TOKEN"]="short"
            with self.assertRaises(RuntimeError):
                jpgfly.validate_deployment_environment()
            os.environ["JPGFLY_CONTROL_TOKEN"]="x"*40
            jpgfly.validate_deployment_environment()
        finally:
            for name,value in previous.items():
                if value is None:os.environ.pop(name,None)
                else:os.environ[name]=value

    def test_decision_endpoint_is_idempotent_and_ordered(self):
        session=asyncio.run(jpgfly.create_session(jpgfly.StartRequest(seed=4)));request=jpgfly.DecisionRequest(sequence=0);first=asyncio.run(jpgfly.session_decision(session["session_id"],request));second=asyncio.run(jpgfly.session_decision(session["session_id"],request));self.assertEqual(first["action"],second["action"]);self.assertTrue(second["replayed"])
        with self.assertRaises(HTTPException):asyncio.run(jpgfly.session_decision(session["session_id"],jpgfly.DecisionRequest(sequence=2)))

    def test_high_complexity_develops_vocabulary_layers_and_motifs(self):
        brain=jpgfly.create_fly_brain(77,complexity=1,mutation=.85,density=.68);brain.duration_profile="LONG";brain.desired_decisions=490;families=set();layers=set();transforms=set();brushes=set();techniques=set();scales=[];position=[735.,48.]
        limits=jpgfly.BrainLimits(max_session_duration_ms=480000,max_brain_decisions=500,max_physical_actions=500,max_consecutive_low_change=100)
        action_count=0
        for sequence in range(500):
            current=observation(sequence,sequence);current.update(currentForelegPosition=position[:],familyCounts={family:1 for family in families},directionalUniformity=.68 if sequence%3 else .25,densityContrast=.08 if sequence%4 else .4,localDensity=.76 if sequence%7==0 else .35,canvasOccupancy=min(.55,sequence*.007),meaningfulChangeRate=.8)
            action=brain.decide(jpgfly.BrainRequest(observation=current),limits)
            if action.intent=="FINISH_ARTWORK":break
            action_count+=1;position=[max(24,min(776,position[0]+math.cos(action.targetDirection)*action.movementDistance)),max(24,min(476,position[1]+math.sin(action.targetDirection)*action.movementDistance))]
            if action.brushDown:families.add(action.movementStyle);layers.add(action.layerRole);brushes.add(action.brushTool);techniques.add(action.technique);scales.append(action.scale)
            if action.motifTransform!="none":transforms.add(action.motifTransform)
        self.assertGreaterEqual(action_count,240);self.assertLess(action_count,500);self.assertEqual(action.intent,"FINISH_ARTWORK");self.assertGreaterEqual(len(families),16);self.assertEqual(layers,{"PRIMARY","SECONDARY","TERTIARY"});self.assertGreaterEqual(len(transforms),6);self.assertGreaterEqual(len(brushes),1);self.assertLessEqual(len(brushes),3);self.assertGreaterEqual(len(techniques),2);self.assertGreater(max(scales)-min(scales),1)

    def test_finish_creates_image_and_llm_text_only_room_record(self):
        final,actions=asyncio.run(finish_session());self.assertEqual(final["status"],"COMPLETED");self.assertEqual(actions[-1]["intent"],"FINISH_ARTWORK");self.assertNotIn("artifact_uri",final);self.assertNotIn("events",final);self.assertNotIn("brain_decisions",final);self.assertEqual(final["storage"]["schema"],4);self.assertEqual(final["storage"]["mode"],"image+text");self.assertEqual(final["room_number"],1);self.assertEqual(final["room_code"],"ROOM-0001");self.assertTrue(final["room_title"]);self.assertTrue(final["room_description"]);self.assertTrue(final["memory_thread"]);self.assertTrue(final["anomaly_report"]);self.assertTrue(final["fly_statement"]);self.assertIn("visual_context",final);self.assertIn("room_tension",final["visual_context"]);self.assertIn("This is finished.",final["thought_fragments"]);self.assertNotIn(final["session_id"],jpgfly.SESSIONS)

    def test_completed_room_becomes_memory_for_the_next_brain_without_replay(self):
        final,_=asyncio.run(finish_session(seed=21))
        self.assertFalse((jpgfly.storage_root()/f"{final['session_id']}.replay.json.gz").exists())
        next_session=asyncio.run(jpgfly.create_session(jpgfly.StartRequest(seed=22)))
        brain=jpgfly.SESSIONS[next_session["session_id"]]["_brain"]
        snapshot=brain.context_snapshot()
        self.assertGreaterEqual(snapshot["rooms_seen"],1)

    def test_finalize_keeps_history_hashes_but_not_history_payloads(self):
        final,_=asyncio.run(finish_session(seed=5));self.assertIn("eventHistoryHash",final["provenance"]);self.assertIn("decisionHistoryHash",final["provenance"]);self.assertIn("evaluationHistoryHash",final["provenance"]);self.assertNotIn("movementReplayEvents",final["provenance"]);self.assertNotIn("completeFlyActionHistory",final["provenance"])

    def test_archive_exposes_room_fields(self):
        final,_=asyncio.run(finish_session(seed=13));record=jpgfly.load_artwork_record(final["session_id"]);self.assertTrue(record["room_title"]);self.assertTrue(record["room_description"]);self.assertTrue(record["memory_thread"]);self.assertTrue(record["anomaly_report"]);self.assertTrue(record["fly_statement"])

    def test_archive_keeps_only_compressed_image_and_text_manifest(self):
        final,_=asyncio.run(finish_session(seed=14));root=jpgfly.storage_root();sid=final["session_id"]
        self.assertTrue((root/f"{sid}.svg.gz").exists());self.assertTrue((root/f"{sid}.json").exists());self.assertFalse((root/f"{sid}.svg").exists());self.assertFalse((root/f"{sid}.replay.json.gz").exists())

    def test_archive_storage_stats_report_zero_replays_and_videos(self):
        asyncio.run(finish_session(seed=15));stats=jpgfly.archive_storage_stats();self.assertEqual(stats["replays"],0);self.assertEqual(stats["videos"],0);self.assertGreaterEqual(stats["artworks"],1)

    def test_room_completion_time_and_provenance_are_utc(self):
        final,_=asyncio.run(finish_session(seed=16));self.assertTrue(final["completed_at"].endswith("+00:00"));self.assertEqual(final["time_standard"],"UTC")

    def test_room_numbers_are_atomic_and_monotonic(self):
        self.assertEqual(jpgfly.next_room_number(),1);self.assertEqual(jpgfly.next_room_number(),2)

    def test_persistence_preserves_the_room_number_assigned_at_finalize(self):
        jpgfly.NEXT_ROOM_NUMBER=7
        final,_=asyncio.run(finish_session(seed=17))
        self.assertEqual(final["room_number"],7)
        self.assertEqual(final["room_code"],"ROOM-0007")

    def test_support_node_outage_does_not_downgrade_a_normal_room(self):
        with patch("candidate_brain._support_nodes_online",return_value=False):
            final,_=asyncio.run(finish_session(seed=18))
        self.assertEqual(final["quality_tier"],"FULL_BRAIN")
        self.assertTrue(final["launch_eligible"])
        self.assertFalse(final["visual_context"]["fallback_summary"]["archive_dumb_dumb"])

    def test_python_brain_is_incremental_and_authoritative(self):
        brain=jpgfly.create_fly_brain(12);action=brain.decide(jpgfly.BrainRequest(observation=observation(0)),jpgfly.BrainLimits());self.assertIn(action.intent,{"MOVE","FINISH_ARTWORK"});self.assertGreaterEqual(action.movementDistance,0)

    def test_validator_uses_exact_mechanics_brush_profile(self):
        expected=jpgfly.expected_brush_profile({"brushTool":"fine_pen","pressure":.5});actual=jpgfly.brush_profile("fine_pen",.5);self.assertEqual(expected,(actual["baseWidth"],actual["width"],actual["opacity"]))

    def test_browser_contains_no_artistic_brain(self):
        web=Path(__file__).resolve().parents[1]/"web";combined="\n".join(path.read_text(encoding="utf-8") for path in web.glob("*.mjs"));self.assertNotIn("create_fly_brain",combined);self.assertNotIn("ProceduralFlyBrain",combined)

    def test_canonical_favicon_uses_fly_icon(self):
        self.assertTrue((Path(__file__).resolve().parents[1]/"web"/"images"/"jpgfly-icon-white.png").exists())
