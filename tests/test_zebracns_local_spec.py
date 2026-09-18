import unittest

from zebracns_local import PUBLIC_HTTPS_SOURCE, SAMPLE_BLOCKS, BLOCK_WIDTH, VISIBLE_NODES, ZebraCNSRuntime


class ZebraCNSLocalSpecTests(unittest.TestCase):
    def test_biological_working_set_is_large_but_browser_bounded(self):
        runtime=ZebraCNSRuntime()
        self.assertEqual(SAMPLE_BLOCKS*BLOCK_WIDTH,1024)
        self.assertEqual(len(runtime._expected_sample_ids()),1024)
        self.assertEqual(VISIBLE_NODES,256)

    def test_public_https_transport_requires_no_gcloud_login(self):
        runtime=ZebraCNSRuntime()
        spec=runtime._spec()
        self.assertEqual(spec["driver"],"zarr3")
        self.assertEqual(spec["kvstore"]["driver"],"http")
        self.assertEqual(spec["kvstore"]["base_url"],PUBLIC_HTTPS_SOURCE)
        self.assertTrue(PUBLIC_HTTPS_SOURCE.startswith("https://storage.googleapis.com/"))


if __name__=="__main__":
    unittest.main()
