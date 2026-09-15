import base64
import os
import tempfile
import unittest

import app


class ArchiveVisibilityTests(unittest.TestCase):
    def test_completed_dumb_dumb_room_is_persisted_and_listed(self):
        old_data=os.environ.get("JPGFLY_DATA_DIR")
        old_artworks=dict(app.ARTWORKS)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["JPGFLY_DATA_DIR"]=tmp
                app.ARTWORKS.clear()
                session_id="a"*64
                svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500"><rect width="800" height="500" fill="white"/></svg>'
                record={
                    "session_id":session_id,
                    "status":"COMPLETED",
                    "state":"COMPLETED",
                    "launch_eligible":False,
                    "room_title":"Fallback room",
                    "room_description":"A completed fallback test room.",
                    "completed_at":"2026-09-13T00:00:00+00:00",
                    "artifact_uri":"data:image/svg+xml;base64,"+base64.b64encode(svg.encode()).decode(),
                    "provenance":{},
                    "hashes":{},
                }

                app.persist_artwork(record)

                self.assertIn(session_id,app.ARTWORKS)
                self.assertEqual(app.ARTWORKS[session_id]["quality_tier"],"DUMB_DUMB")
                loaded=app.load_artwork_record(session_id)
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded["launch_id"],app.PUBLIC_LAUNCH_ID)
                self.assertEqual(loaded["quality_tier"],"DUMB_DUMB")
        finally:
            app.ARTWORKS.clear()
            app.ARTWORKS.update(old_artworks)
            if old_data is None:
                os.environ.pop("JPGFLY_DATA_DIR",None)
            else:
                os.environ["JPGFLY_DATA_DIR"]=old_data


if __name__=="__main__":
    unittest.main()
