import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import tempfile
import unittest
from bootstrap import APP_FILES,deploy_payload,payload_file,fingerprint

PROJECT=Path(__file__).resolve().parents[1]

class ProjectStructureTests(unittest.TestCase):
    def test_checkout_deploys_all_payloads_from_organized_folders(self):
        with tempfile.TemporaryDirectory(prefix='FaceLocker path with spaces ') as directory:
            target=Path(directory)/'managed'
            deployed=deploy_payload(PROJECT,target)
            for name in APP_FILES:
                source=payload_file(PROJECT,name)
                self.assertTrue(source.is_file(),str(source))
                self.assertEqual((deployed/name).read_bytes(),source.read_bytes())
            # The organized checkout and frozen flat payload must have equal fingerprints.
            self.assertEqual(fingerprint(PROJECT),fingerprint(deployed))

    def test_bat_files_resolve_project_root_and_moved_entrypoints(self):
        for name,entry in [('run.bat','src\\start_source.py'),('build_exe.bat','src\\build_exe.py'),('diagnose.bat','src\\runtime_entry.py')]:
            script=(PROJECT/'scripts'/name).read_text()
            self.assertIn('cd /d "%~dp0.."',script)
            self.assertIn(entry,script)
        self.assertFalse(list(PROJECT.glob('*.py')))
        self.assertFalse(list(PROJECT.glob('*.bat')))

if __name__=='__main__':unittest.main()
