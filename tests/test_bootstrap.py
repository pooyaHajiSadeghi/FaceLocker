import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import json
import tempfile
import unittest
import types
from pathlib import Path
from unittest.mock import Mock,patch
from bootstrap import Installer,APP_FILES,deploy_payload,fingerprint,migrate_adjacent_data,external_env

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.base=Path(self.temporary.name);self.payload=self.base/'payload';self.payload.mkdir()
        for name in APP_FILES:(self.payload/name).write_text('source '+name,encoding='utf-8')
        self.root=self.base/'managed';self.engine=Installer(self.root,self.payload)
    def tearDown(self):self.temporary.cleanup()

    def test_payload_updates_preserve_state_and_models(self):
        (self.root/'data').mkdir();(self.root/'data'/'state.json').write_text('private state')
        (self.root/'models').mkdir();(self.root/'models'/'face.onnx').write_text('model')
        deploy_payload(self.payload,self.root)
        (self.payload/'app.py').write_text('new version');deploy_payload(self.payload,self.root)
        self.assertEqual((self.root/'app'/'app.py').read_text(),'new version')
        self.assertEqual((self.root/'data'/'state.json').read_text(),'private state')
        self.assertEqual((self.root/'models'/'face.onnx').read_text(),'model')

    def test_dependency_probe_requires_python_310_even_with_working_packages(self):
        self.engine.python.parent.mkdir(parents=True)
        self.engine.python.touch()
        modules={'cv2':types.SimpleNamespace(__version__='4.10.0'),
                 'numpy':types.SimpleNamespace(__version__='1.26.4'),
                 'tkinter':types.SimpleNamespace(),
                 'customtkinter':types.SimpleNamespace(),
                 'PIL':types.SimpleNamespace()}
        def probe(path,code):
            try:exec(code,{});return True
            except AssertionError:return False
        self.engine.probe=probe
        with patch.dict('sys.modules',modules),patch('struct.calcsize',return_value=8):
            with patch('sys.version_info',(3,10,11)):
                self.assertTrue(self.engine.dependencies_ok())
            with patch('sys.version_info',(3,11,9)):
                self.assertFalse(self.engine.dependencies_ok())

    def test_ready_install_has_no_installer_pip_or_download_steps(self):
        self.engine.ready.write_text(json.dumps({'fingerprint':fingerprint(self.payload)}))
        self.engine.dependencies_ok=Mock(return_value=True);self.engine.models_ok=Mock(return_value=True)
        self.engine.install_python=Mock();self.engine.command=Mock()
        self.assertEqual(self.engine.ensure(),self.engine.python)
        self.engine.install_python.assert_not_called();self.engine.command.assert_not_called()

    def test_ui_only_upgrade_does_not_reinstall_healthy_packages(self):
        import hashlib
        requirements_hash=hashlib.sha256((self.payload/'requirements.txt').read_bytes()).hexdigest()
        self.engine.ready.write_text(json.dumps({'fingerprint':'previous UI','requirements_hash':requirements_hash}))
        self.engine.dependencies_ok=Mock(return_value=True);self.engine.models_ok=Mock(return_value=True)
        self.engine.python_ok=Mock(return_value=True);self.engine.command=Mock()
        self.engine.ensure()
        self.engine.command.assert_not_called()
        self.assertTrue(self.engine.marked_ready(fingerprint(self.payload)))

    def test_changed_requirements_install_even_when_imports_work(self):
        self.engine.ready.write_text(json.dumps({'fingerprint':'old','requirements_hash':'old requirements'}))
        self.engine.dependencies_ok=Mock(return_value=True);self.engine.models_ok=Mock(return_value=True)
        self.engine.python_ok=Mock(return_value=True);self.engine.command=Mock()
        self.engine.ensure()
        self.assertEqual(self.engine.command.call_count,1)
        self.assertIn('pip',self.engine.command.call_args.args[0])

    def test_fresh_install_creates_env_packages_models_and_marker(self):
        self.engine.dependencies_ok=Mock(side_effect=[False,True])
        self.engine.models_ok=Mock(side_effect=[False,True])
        self.engine.python_ok=Mock(return_value=False)
        self.engine.install_python=Mock(return_value=self.base/'python.exe')
        self.engine.command=Mock()
        self.engine.ensure()
        commands=[call.args[0] for call in self.engine.command.call_args_list]
        self.assertTrue(any('venv' in args for args in commands))
        self.assertTrue(any('pip' in args for args in commands))
        self.assertTrue(any('--setup' in args for args in commands))
        self.assertTrue(self.engine.ready.exists())

    def test_failed_package_install_does_not_mark_ready_or_change_user_data(self):
        (self.root/'data').mkdir();data=self.root/'data'/'state.json';data.write_text('do not change')
        self.engine.dependencies_ok=Mock(return_value=False);self.engine.python_ok=Mock(return_value=True)
        self.engine.command=Mock(side_effect=RuntimeError('network failure'))
        with self.assertRaises(RuntimeError):self.engine.ensure()
        self.assertFalse(self.engine.ready.exists());self.assertEqual(data.read_text(),'do not change')

    def test_broken_env_is_backed_up(self):
        env=self.root/'.venv';env.mkdir();(env/'sentinel').write_text('keep')
        self.engine.dependencies_ok=Mock(side_effect=[False,True]);self.engine.models_ok=Mock(return_value=True)
        self.engine.python_ok=Mock(return_value=False);self.engine.install_python=Mock(return_value=self.base/'python.exe');self.engine.command=Mock()
        self.engine.ensure()
        backups=list(self.root.glob('.venv.incomplete-*'))
        self.assertEqual(len(backups),1);self.assertEqual((backups[0]/'sentinel').read_text(),'keep')

    def test_migration_never_overwrites_an_existing_managed_database(self):
        old=self.base/'old';(old/'data').mkdir(parents=True)
        (old/'data'/'state.json').write_text('{"version":2}')
        self.assertTrue(migrate_adjacent_data(old,self.root))
        (self.root/'data'/'state.json').write_text('{"private":true}')
        self.assertFalse(migrate_adjacent_data(old,self.root))
        self.assertEqual(json.loads((self.root/'data'/'state.json').read_text()),{'private':True})

    def test_external_python_does_not_inherit_pyinstaller_or_pythonpath(self):
        with patch.dict('os.environ',{'PYTHONHOME':'bad','PYTHONPATH':'bad','TCL_LIBRARY':'frozen tcl','TK_LIBRARY':'frozen tk','TCLLIBPATH':'frozen paths','_PYI_APPLICATION_HOME_DIR':'bad','_MEIPASS2':'bad'}):
            env=external_env(self.root)
        self.assertNotIn('TCL_LIBRARY',env);self.assertNotIn('TK_LIBRARY',env);self.assertNotIn('TCLLIBPATH',env)
        self.assertNotIn('PYTHONHOME',env);self.assertNotIn('PYTHONPATH',env)
        self.assertNotIn('_MEIPASS2',env);self.assertNotIn('_PYI_APPLICATION_HOME_DIR',env)
        self.assertEqual(env['FACELOCKER_HOME'],str(self.root))

    def test_external_path_excludes_frozen_bundle_only(self):
        import os
        bundle=self.base/'bundle';kept=self.base/'runtime'
        with patch('bootstrap.sys._MEIPASS',str(bundle),create=True),patch.dict('os.environ',{'PATH':os.pathsep.join([str(bundle),str(bundle/'bin'),str(kept)])}):
            env=external_env(self.root)
        self.assertEqual(env['PATH'],str(kept))

    def test_checksum_mismatch_does_not_publish_installer(self):
        class Response:
            headers={'Content-Length':'3'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,size):
                if hasattr(self,'done'):return b''
                self.done=True;return b'bad'
        with patch('bootstrap.urllib.request.urlopen',return_value=Response()):
            with self.assertRaises(RuntimeError):self.engine.download_python()
        self.assertFalse((self.root/'downloads'/'python-3.10.11-amd64.exe').exists())
        self.assertFalse((self.root/'downloads'/'python-3.10.11-amd64.part').exists())

if __name__=='__main__':unittest.main()
