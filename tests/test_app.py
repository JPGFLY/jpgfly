import asyncio, math, os, tempfile, unittest
from pathlib import Path
from fastapi import HTTPException
import app as jpgfly

def observation(sequence,physical):
    return {"currentForelegPosition":[735-sequence*3,48+sequence*2],"canvasOccupancy":min(.5,sequence*.012),"negativeSpace":[80,430],"focalArea":[400,250],"nearbyLines":sequence%6,"intersections":sequence//4,"densityPeak":sequence//5,"densityBalance":.82,"repetition":.2,"recentMarks":[],"visitedAreas":[[400,250]] if sequence else [],"familyCounts":{"sweep":max(1,sequence)},"meaningfulChangeRate":.8,"consecutiveLowChange":0,"elapsedDrawingTime":sequence*500,"decisionCount":sequence,"physicalActionCount":physical}

async def finish_session(seed=7):
    session=await jpgfly.create_session(jpgfly.StartRequest(seed=seed,limits={"maxBrainDecisions":8,"maxPhysicalActions":90,"maxSessionDurationMs":70000,"maxConsecutiveLowChange":50}))
    actions=[]
    while True:
        result=await jpgfly.session_decision(session["session_id"],jpgfly.DecisionRequest(sequence=len(actions),observation={"malicious":"ignored"}))
        actions.append(result["action"])
        if result["action"]["intent"]=="FINISH_ARTWORK":break
    final=jpgfly.finalize_session(session["session_id"],jpgfly.FinalizeRequest(client_fingerprint="browser-fingerprint"))
    return final,actions

class JPGFLYAppTests(unittest.TestCase):
    def setUp(self):
        self.data_dir=tempfile.TemporaryDirectory();os.environ["JPGFLY_DATA_DIR"]=self.data_dir.name
        jpgfly.SESSIONS.clear();jpgfly.ARTWORKS.clear();jpgfly.NEXT_ROOM_NUMBER=1

    def tearDown(self):
        jpgfly.SESSIONS.clear();jpgfly.ARTWORKS.clear();os.environ.pop("JPGFLY_DATA_DIR",None);self.data_dir.cleanup()

    def test_project_config_is_backrooms(self):
        config=jpgfly.public_config();self.assertEqual(config["project"],"JPGFLY");self.assertEqual(config["mode"],"BACKROOMS");self.assertEqual(config["archiveMode"],"image+text");self.assertFalse(config["replayStorage"]);self.assertFalse(config["videoStorage"]);self.assertEqual(config["timeStandard"],"UTC");self.assertEqual(config["agentWallet"],"0x977d02F5519be02Cc3B8905e1D39f916DC4A3e9D")

    def test_room_numbers_are_atomic_and_monotonic(self):
        self.assertEqual(jpgfly.next_room_number(),1);self.assertEqual(jpgfly.next_room_number(),2);self.assertEqual(jpgfly.next_room_number(),3)

    def test_session_creation_needs_no_wallet(self):
        session=asyncio.run(jpgfly.create_session(jpgfly.StartRequest(seed=1)))

    def test_python_brain_is_incremental_and_authoritative(self):
        session=asyncio.run(jpgfly.create_session(jpgfly.StartRequest(seed=3)))
        result=asyncio.run(jpgfly.session_decision(session["session_id"],jpgfly.DecisionRequest(sequence=0,observation={"currentForelegPosition":[1,1],"malicious":True})))
        action=result["action"];self.assertTrue(result["brainMode"].startswith("LOCAL PROCEDURAL FLY BRAIN"));self.assertEqual(action["intent"],"MOVE");self.assertNotIn("points",action);self.assertEqual(result["observation"]["currentForelegPosition"],[735.0,48.0]);self.assertNotIn("malicious",result["observation"]);self.assertTrue(result["events"]);self.assertIn("contextPass",action);self.assertIn("memoryContext",action)

    def test_public_active_session_summary_hides_working_history(self):
        session=asyncio.run(jpgfly.create_session(jpgfly.StartRequest(seed=31)))
        summary=jpgfly.active_session_summary(jpgfly.SESSIONS[session["session_id"]])
        self.assertEqual(summary["session_id"],session["session_id"])
        self.assertNotIn("brain_decisions",summary)
        self.assertNotIn("events",summary)
        self.assertNotIn("seed",summary)
        self.assertNotIn("parameters",summary)
        self.assertNotIn("limits",summary)

    def test_public_deployment_validation_requires_control_token(self):
        names=("JPGFLY_PUBLIC_DEPLOYMENT","JPGFLY_CONTROL_TOKEN","JPGFLY_TEXT_PROVIDER","JPGFLY_ALLOW_EPHEMERAL_STORAGE","RAILWAY_ENVIRONMENT","RAILWAY_VOLUME_MOUNT_PATH")
        previous={name:os.environ.get(name) for name in names}
        try:
            os.environ["JPGFLY_PUBLIC_DEPLOYMENT"]="true"
            os.environ["JPGFLY_TEXT_PROVIDER"]="procedural"
            os.environ.pop("RAILWAY_ENVIRONMENT",None)
            os.environ.pop("RAILWAY_VOLUME_MOUNT_PATH",None)
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
        self.assertGreaterEqual(action_count,240);self.assertLess(action_count,500);self.assertEqual(action.intent,"FINISH_ARTWORK");self.assertGreaterEqual(len(families),16);self.assertEqual(layers,{"PRIMARY","SECONDARY","TERTIARY"});self.assertGreaterEqual(len(transforms),6);self.assertGreaterEqual(len(brushes),7);self.assertGreaterEqual(len(techniques),7);self.assertGreater(max(scales)-min(scales),1)

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

    def test_room_completion_time_and_provenance_are_utc(self):
        final,_=asyncio.run(finish_session(seed=6));self.assertTrue(final["completed_at"].endswith("+00:00"));self.assertEqual(final["provenance"]["timeStandard"],"UTC");self.assertNotIn("agentWallet",final["provenance"])

    def test_archive_keeps_only_compressed_image_and_text_manifest(self):
        final,_=asyncio.run(finish_session())
        session_id=final["session_id"]
        self.assertNotIn("events",jpgfly.ARTWORKS[session_id])
        manifest=jpgfly.get_artwork(session_id)
        self.assertNotIn("events",manifest)
        self.assertNotIn("brain_decisions",manifest)
        self.assertNotIn("artifact_uri",manifest)
        self.assertEqual(manifest["storage"]["schema"],4)
        self.assertEqual(manifest["storage"]["mode"],"image+text")
        self.assertTrue(manifest["room_description"])
        self.assertTrue(manifest["memory_thread"])
        self.assertTrue(manifest["anomaly_report"])
        self.assertTrue(manifest["fly_statement"])
        root=jpgfly.storage_root()
        self.assertTrue((root/f"{session_id}.svg.gz").is_file())
        self.assertFalse((root/f"{session_id}.replay.json.gz").exists())
        self.assertLess(manifest["storage"]["artworkCompressedBytes"],manifest["storage"]["artworkRawBytes"])

    def test_archive_exposes_room_fields(self):
        final,_=asyncio.run(finish_session());recent=jpgfly.recent_artworks();item=recent["artworks"][0];self.assertEqual(item["session_id"],final["session_id"]);self.assertEqual(item["room_number"],1);self.assertEqual(item["room_code"],"ROOM-0001");archive=jpgfly.archive_artworks();self.assertEqual(archive["total"],1);self.assertFalse(archive["hasMore"])

    def test_archive_storage_stats_report_zero_replays_and_videos(self):
        final,_=asyncio.run(finish_session(seed=11))
        session_id=final["session_id"]
        root=jpgfly.storage_root()
        self.assertTrue((root/f"{session_id}.svg.gz").exists())
        self.assertFalse((root/f"{session_id}.replay.json.gz").exists())
        stats=jpgfly.archive_storage_stats()
        self.assertEqual(stats["mode"],"image+text")
        self.assertEqual(stats["replays"],0)
        self.assertEqual(stats["videos"],0)
        self.assertEqual(stats["artworks"],1)

    def test_browser_contains_no_artistic_brain(self):
        root=Path(jpgfly.ROOT);engine=(root/"web"/"art-engine.mjs").read_text();schema=(root/"web"/"flybrain.mjs").read_text();self.assertNotIn("ProceduralFlyBrain",engine+schema);self.assertNotIn("class ServerAIBrainProvider",engine+schema)

if __name__=="__main__":unittest.main()
