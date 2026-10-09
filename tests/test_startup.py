import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import json
import os
from pathlib import Path
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch
from bootstrap import Installer
from instance import report_ready

class StartupTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.events=[];self.engine=Installer(self.root,self.root,lambda key,**values:self.events.append(key))
        self.engine.python=Path(sys.executable);self.engine.app_dir.mkdir()
    def tearDown(self):self.folder.cleanup()
    def script(self,code):(self.engine.app_dir/'app.py').write_text(code,encoding='utf-8')
    def test_window_ready_is_emitted_only_after_child_handshake(self):
        self.script('import os,json;from pathlib import Path;Path(os.environ["FACELOCKER_READY_FILE"]).write_text(json.dumps({"pid":os.getpid()}))')
        self.engine.launch(startup_timeout=5)
        self.assertEqual(self.events,['boot_launch','boot_window_ready'])
        self.assertFalse(list((self.root/'logs').glob('window-ready-*')))
    def test_runtime_wrapper_captures_early_import_failure(self):
        shutil.copy2(Path(__file__).resolve().parents[1]/'src'/'runtime_entry.py',self.engine.app_dir/'runtime_entry.py')
        self.script('raise ImportError("early UI import failure")')
        with self.assertRaisesRegex(RuntimeError,'before its window was ready'):self.engine.launch(startup_timeout=5)
        log=self.engine.log_path.read_text()
        self.assertIn('early UI import failure',log)
        self.assertIn('[startup] Python',log)
        self.assertIn('-X faulthandler',log)

    def test_child_failure_does_not_hide_the_launcher(self):
        self.script('raise RuntimeError("startup regression")')
        with self.assertRaisesRegex(RuntimeError,'before its window was ready'):self.engine.launch(startup_timeout=5)
        self.assertNotIn('boot_window_ready',self.events)
        self.assertIn('startup regression',self.engine.log_path.read_text())
    def test_stalled_owned_child_is_stopped_with_bounded_wait(self):
        self.script('import time;time.sleep(120)')
        with self.assertRaisesRegex(RuntimeError,'did not become ready'):self.engine.launch(startup_timeout=0)
        self.assertNotIn('boot_window_ready',self.events)
    def test_report_ready_writes_only_the_requested_marker(self):
        marker=self.root/'marker.json'
        with patch.dict(os.environ,{'FACELOCKER_READY_FILE':str(marker)}):report_ready()
        self.assertEqual(json.loads(marker.read_text())['pid'],os.getpid())
        self.assertFalse(marker.with_suffix('.tmp').exists())

if __name__=='__main__':unittest.main()
